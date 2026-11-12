"""파이프라인 오케스트레이터 — 피그마 워크플로우 1~7단계를 코드로 고정한 흐름.

  1 입력      입력검증 Agent      오류가 있으면 여기서 멈춘다(FR-02). 입력은 그대로 돌려준다(NFR-11)
  2 계산      제약판단 → 최적화 → 체선료계산 Agent
  3 후보 비교  (화면) 타임라인·비교표·근거
  4 리스크     리스크 Agent
  5 보고서     보고서 Agent (LLM 선택)
  6 일정 확정  사람(API 결정 기록) — Agent 없음
  7 검증      검증 Agent (실행 단위 검사) + `demurrage verify`(정답 세트 일괄)

각 단계를 실행 로그(NFR-17)에 남긴다: 순서, Agent, 걸린 시간, 입력·출력 요약, LLM 사용 여부.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

from .. import ENGINE_VERSION
from ..domain.timeutil import DAY, day_start, fmt_iso
from ..engine.build import build_context
from ..engine.optimizer import optimize
from ..engine.risk import assess
from ..engine.sensitivity import analyze
from ..llm.adapter import CostMeter, DisabledLLM
from ..report.builder import audit_numbers, llm_narrative, render_html, render_mail, render_markdown, template_narrative
from ..report.timeline import render_svg
from ..report.views import restriction_view, schedule_view
from ..rules.loader import load_rules
from .roles import AGENTS

KST = timezone(timedelta(hours=9))

STATUS_KO = {"OPTIMAL": "최적 증명", "BEST_FOUND": "최선 탐색 결과(제한시간 도달)", "NO_IMPROVEMENT": "개선 없음",
             "NO_FEASIBLE": "실행 가능한 후보 없음"}

OPEN_ASSUMPTIONS = [
    ("ETB-03", "야간 도선 대상 조건(멘토링 PPT 07쪽)의 '3만톤 이하·수입선·Draft 10.5 이상'과 'GRT 3만 이하는 야간 도선 제한 없음'이 서로 맞지 않습니다. 적힌 대로 적용했고, Last POB 판정 기준이 ETA인지 실제 도선 시각인지 확인이 필요합니다."),
    ("LAY-06", "Daylight 적용 흐름(PPT 10쪽)을 받지 못해 팀 요구사항 FR-25 문장대로 구현했습니다(Laycan 분기 ①②③ 먼저, ④만 Daylight 식)."),
    ("DEM-02", "'기상 체선 시간'은 '기상 제한이 없었다면 접안했을 시각 ~ 실제 ETB' 중 체선 기간에 든 시간으로 정의했습니다(정의 확인 필요)."),
    ("ETB-09", "재고는 일 단위로 단순화했습니다(작업시작일에 물량 전부 반영)."),
    ("WRK-02", "작업시간·호스분리 소요는 입력값 또는 가상 과거 실적의 평균 Rate·최빈값입니다."),
    ("OPT-02", "의도적으로 접안을 늦추는 안(예: Laycan From까지 기다렸다 접안)은 탐색하지 않습니다 — ETB는 늘 '가장 이른 가능 시각'입니다."),
]


class RunLog:
    def __init__(self):
        self.items = []
        self.seq = 0

    def stage(self, agent_key: str, input_summary: dict):
        return _Stage(self, agent_key, input_summary)


class _Stage:
    def __init__(self, log, key, inp):
        self.log, self.key, self.inp = log, key, inp

    def __enter__(self):
        self.t0 = time.perf_counter()
        self.out = {}
        return self

    def __exit__(self, et, ev, tb):
        self.log.seq += 1
        spec = AGENTS[self.key]
        self.log.items.append({"seq": self.log.seq, "agent": spec.name, "label": spec.label, "code": spec.code, "stage": spec.stage,
                               "uses_llm": spec.uses_llm, "elapsed_ms": round((time.perf_counter() - self.t0) * 1000, 1),
                               "input": self.inp, "output": self.out, "error": repr(ev) if ev else None})
        return False


def _nights(ctx) -> list:
    """타임라인 음영용 야간 구간 [일몰, 다음 날 일출] — 계산에는 쓰지 않는다."""
    out = []
    d = day_start(ctx.sc.horizon_start) - DAY
    while d <= ctx.sc.horizon_end + DAY:
        _, sset = ctx.sun.get(d)
        rise2, _ = ctx.sun.get(d + DAY)
        out.append([fmt_iso(sset), fmt_iso(rise2)])
        d += DAY
    return out


def fingerprint(run: dict) -> str:
    core = {"baseline": run["baseline"]["total_cents"],
            "candidates": [(c["label"], c["total_cents"], c["signature"]) for c in run["candidates"]],
            "rules": run["versions"]["rules"]["version"], "scenario": run["scenario"]["hash"]}
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def run_pipeline(doc: dict, *, rules=None, rules_patch: dict = None, llm=None, k: int = 3, time_limit_s: float = 20.0,
                 cost_cap_usd: float = 1.0, data_dir=None, run_id: str = None, with_sensitivity: bool = True) -> dict:
    log = RunLog()
    rules = rules or load_rules(patch=rules_patch, data_dir=data_dir)
    llm = llm or DisabledLLM()
    meter = CostMeter(cap_usd=cost_cap_usd)
    run = {"run_id": run_id or uuid.uuid4().hex[:12], "created_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
           "versions": {"engine": ENGINE_VERSION, "rules": rules.summary(),
                        "solver": {"method": "FCFS + 지역 탐색 + 분기한정(DFS, 비감소 ETB 순서)", "k": k, "time_limit_s": time_limit_s}},
           "input": doc, "status": "RUNNING", "forbidden_phrases": rules.phrases.get("forbidden_phrases")}

    # 1 입력
    with log.stage("intake", {"scenario": doc.get("id"), "vessels": len(doc.get("vessels", []))}) as st:
        ctx, issues = build_context(doc, rules, data_dir=data_dir)
        st.out = {"errors": sum(1 for i in issues if i.level == "ERROR"), "warnings": sum(1 for i in issues if i.level == "WARN")}
    run["input_issues"] = [i.as_dict() for i in issues]
    if ctx is None:
        run["status"] = "INPUT_ERROR"
        run["agent_log"] = log.items
        run["scenario"] = {"id": doc.get("id"), "title": doc.get("title", doc.get("id"))}
        return run
    sc = ctx.sc
    run["scenario"] = {"id": sc.id, "title": sc.title, "description": sc.description, "data_label": sc.data_label,
                       "hash": sc.source_hash, "horizon": {"start": fmt_iso(sc.horizon_start), "end": fmt_iso(sc.horizon_end)},
                       "berths": list(sc.active_berths), "vessel_ids": [v.id for v in sc.vessels],
                       "movable": list(ctx.movable), "immovable": list(ctx.immovable),
                       "weather": sc.weather_meta if sc.weather_segments else None,
                       "card": doc.get("card"), "nights": _nights(ctx),
                       "tide_windows": {b: [[fmt_iso(a), fmt_iso(e)] for a, e in w] for b, w in sc.tide_windows.items()}}

    # 2 계산 — 제약 판단
    with log.stage("constraint", {"berths": list(sc.active_berths)}) as st:
        run["restrictions"] = restriction_view(ctx)
        run["eligibility"] = {vid: {"eligible": ctx.eligible.get(vid, []),
                                    "excluded": {b: [x["message"] for x in r] for b, r in ctx.excluded.get(vid, {}).items() if b in sc.active_berths}}
                              for vid in ctx.movable}
        run["night_rules"] = {vid: {"last_pob_release": fmt_iso(ctx.last_pob[vid][0]) if ctx.last_pob.get(vid) else None,
                                    "dawn_window": ctx.vessels[vid].grt >= ctx.dawn_grt} for vid in ctx.movable}
        st.out = {"restrictions": len(run["restrictions"]), "weather_restrictions": len(ctx.wx_restrictions),
                  "night_pob_vessels": sum(1 for v in run["night_rules"].values() if v["last_pob_release"])}
    # 2 계산 — 최적화
    with log.stage("optimizer", {"movable": len(ctx.movable), "k": k, "time_limit_s": time_limit_s}) as st:
        res = optimize(ctx, k=k, time_limit_s=time_limit_s)
        st.out = {"status": res.status, "baseline_usd": res.baseline.total_cents / 100,
                  "candidates_usd": [c.total_cents / 100 for c in res.candidates], "nodes": res.stats["bnb"]["nodes"],
                  "gap": round(res.gap, 4), "rejected": len(res.rejected)}
    run["search"] = {"status": res.status, "status_ko": STATUS_KO[res.status], "proven_optimal": res.proven_optimal,
                     "lower_bound_usd": res.lower_bound_cents / 100, "gap": round(res.gap, 4), "stats": res.stats,
                     "optimality_ko": "최적 증명(모든 배정 중 가장 낮음)" if res.proven_optimal else "최선 탐색 결과(최적성 미증명)",
                     "rejected": len(res.rejected)}
    # 2 계산 — 체선료 계산
    with log.stage("demurrage", {"schedules": 1 + len(res.candidates)}) as st:
        res.baseline.label = "기준안"
        run["baseline"] = schedule_view(ctx, res.baseline)
        run["baseline"]["meta"] = {"optimality": "비교용 기준안(현행 실적 아님)", **res.baseline.meta}
        run["candidates"] = [schedule_view(ctx, c, res.baseline) for c in res.candidates]
        svgs = {"기준안": render_svg(ctx, res.baseline, "기준안(도착 순서·FCFS) — 비교용, 현행 실적 아님")}
        rng = None
        all_s = [res.baseline] + res.candidates
        t0 = min(min(ctx.vessels[v].eta for v in s.state.pl) for s in all_s)
        t1 = max(max(p.etu for p in s.state.pl.values()) for s in all_s)
        from ..domain.timeutil import DAY, day_start
        rng = (day_start(t0), day_start(t1) + DAY)
        svgs["기준안"] = render_svg(ctx, res.baseline, "기준안(도착 순서·FCFS) — 비교용, 현행 실적 아님", rng)
        for c in res.candidates:
            svgs[c.label] = render_svg(ctx, c, f"{c.label} — {c.meta.get('optimality')}", rng)
        run["timeline_svgs"] = svgs
        st.out = {"vessel_calcs": sum(len(s["vessels"]) for s in [run["baseline"]] + run["candidates"]),
                  "statuses": sorted({s for c in run["candidates"] for s in c["statuses"]})}

    # 4 리스크
    with log.stage("risk", {"candidates": len(res.candidates), "sensitivity": with_sensitivity}) as st:
        plans = {"기준안": res.baseline.plan, **{c.label: c.plan for c in res.candidates}}
        if with_sensitivity and res.candidates:
            run["sensitivity"] = analyze(doc, rules, plans, data_dir=data_dir)
        else:
            run["sensitivity"] = {"rows": [], "flagged": {n: [] for n in plans}, "base_ranks": {}, "shift_hours": 6}
        run["risks"] = {c.label: assess(ctx, c, run["sensitivity"]["flagged"].get(c.label)) for c in res.candidates}
        st.out = {"applies": {k: sum(1 for r in v if r["status"] == "APPLIES") for k, v in run["risks"].items()},
                  "perturbations": len(run["sensitivity"]["rows"]),
                  "rank_changed": {k: len(v) for k, v in run["sensitivity"]["flagged"].items()}}

    used_rules = {r for s in [run["baseline"]] + run["candidates"] for v in s["vessels"] for r in v["rule_ids"]}
    run["open_assumptions"] = [text for rid, text in OPEN_ASSUMPTIONS if rid in used_rules or rid in ("WRK-02", "OPT-02", "DEM-02")]

    # 5 보고서
    with log.stage("report", {"llm": llm.name, "cost_cap_usd": cost_cap_usd}) as st:
        nar, why = llm_narrative(run, llm, meter)
        if nar is None:
            nar = template_narrative(run)
        md = render_markdown(run, nar)
        html = render_html(run, nar, {k: v for k, v in svgs.items() if k != "기준안"})
        mail = render_mail(run, nar)
        audit_r = audit_numbers(md, run)
        audit_m = audit_numbers(mail["body"], run)
        run["report"] = {"markdown": md, "html": html, "narrative": nar, "narrative_source": why,
                         "audit": {"report": audit_r, "mail": audit_m}}
        run["mail"] = mail
        st.out = {"generated_by": nar.get("generated_by"), "reason": why,
                  "numbers_checked": audit_r["checked"] + audit_m["checked"],
                  "number_mismatches": len(audit_r["mismatches"]) + len(audit_m["mismatches"])}
    run["llm"] = meter.summary()

    # 7 검증(실행 단위)
    with log.stage("verify", {}) as st:
        checks = []
        for s in [run["baseline"]] + run["candidates"]:
            checks.append({"what": f"{s['label']} 총액 = 선박별 금액 합", "ok": s["total_cents"] == sum(v["amount_cents"] for v in s["vessels"])})
            if "delta_sum_cents" in s:
                checks.append({"what": f"{s['label']} 선박별 증감 합 = −절감액", "ok": s["delta_sum_cents"] == -s["savings_cents"]})
        checks.append({"what": "후보 하드 제약 위반 0건", "ok": all(not c["violations"] for c in run["candidates"])})
        checks.append({"what": "보고서·메일 숫자 대조 불일치 0건", "ok": not (audit_r["mismatches"] or audit_m["mismatches"])})
        forb = rules.phrases.get("forbidden_phrases", [])
        checks.append({"what": "단정 표현('지금 확정' 등) 0건", "ok": not any(f in md or f in mail["body"] for f in forb)})
        run["checks"] = checks
        run["fingerprint"] = fingerprint(run)
        st.out = {"passed": sum(1 for c in checks if c["ok"]), "total": len(checks), "fingerprint": run["fingerprint"]}
    run["status"] = "OK" if res.candidates else "NO_CANDIDATE"
    run["agent_log"] = log.items
    return run
