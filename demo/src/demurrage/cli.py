"""명령줄 입구.

  python -m demurrage run S05-storm-rush [--out out/] [--confirm 1안 --actor 이름 --reason 이유]
  python -m demurrage verify [--strict]          정답 세트 + 검증 시나리오 + 최적성(FR-50) — CI 문지기
  python -m demurrage bench [--sizes 8 12 16]    성능·확장성(NFR-08·09)
  python -m demurrage serve [--port 8000]        API + 화면
  python -m demurrage fetch-public               공공데이터 수집본 만들기(키가 없으면 오프라인 계산본)
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import time
from pathlib import Path

from .domain.timeutil import fmt_iso, parse_ts
from .rules.loader import DATA_DIR


def _scenario(arg: str) -> dict:
    p = Path(arg)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    for q in sorted((DATA_DIR / "scenarios").rglob("*.json")):
        d = json.loads(q.read_text(encoding="utf-8"))
        if d.get("id") == arg:
            return d
    sys.exit(f"시나리오 {arg} 를 찾지 못함 (data/scenarios의 id 또는 파일 경로)")


def cmd_run(a):
    from .agents.orchestrator import run_pipeline
    from .llm.adapter import get_llm
    from .report.builder import schedule_csv
    from .store.db import Store

    doc = _scenario(a.scenario)
    patch = json.loads(a.rules_patch) if a.rules_patch else None
    t0 = time.perf_counter()
    run = run_pipeline(doc, rules_patch=patch, llm=get_llm(), time_limit_s=a.time_limit, k=a.k,
                       cost_cap_usd=float(os.environ.get("LLM_COST_CAP_USD", "1.0")))
    el = time.perf_counter() - t0
    print(f"■ 시나리오 {run['scenario'].get('id')} — {run['scenario'].get('title')}  ({el:.2f}s)")
    for it in run["agent_log"]:
        print(f"  {it['seq']}. {it['agent']:<12} {it['elapsed_ms']:>8.1f}ms  {json.dumps(it['output'], ensure_ascii=False)[:150]}")
    if run["status"] == "INPUT_ERROR":
        for i in run["input_issues"]:
            print(f"  [{i['level']}] {i['vessel']} {i['field']}: {i['message']}")
        sys.exit(2)
    print(f"\n  기준안(FCFS) {run['baseline']['total_display']}")
    for c in run["candidates"]:
        print(f"  {c['label']} {c['total_display']}  절감 {c['savings_display']} ({c['savings_pct']}%)  위반 {len(c['violations'])}  {c['meta'].get('optimality')}")
    print(f"  탐색: {run['search']['status_ko']} · 노드 {run['search']['stats']['bnb']['nodes']} · 갭 {run['search']['gap']:.1%}")
    print(f"  보고서 문장: {run['report']['narrative']['generated_by']} ({run['report']['narrative_source']})")
    print(f"  실행 검사: {sum(c['ok'] for c in run['checks'])}/{len(run['checks'])} 통과 · 지문 {run['fingerprint']}")
    store = Store(a.db) if a.db else None
    if store:
        store.save_run(run, el * 1000)
    if a.confirm:
        if not store:
            sys.exit("--confirm은 --db와 함께 써야 결정이 기록됩니다")
        if not a.actor:
            sys.exit("--confirm은 --actor(담당자 이름)가 필요합니다 — 확정은 사람만 합니다")
        d = store.add_decision(run["run_id"], run["scenario"]["hash"], a.confirm, "SELECT", a.actor, a.reason or "")
        print(f"  ✔ 담당자 {a.actor}가 {a.confirm} 확정 기록 (#{d['id']} {d['created_at']})")
    if a.out:
        out = Path(a.out) / run["run_id"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.md").write_text(run["report"]["markdown"], encoding="utf-8")
        (out / "report.html").write_text(run["report"]["html"], encoding="utf-8")
        (out / "mail.txt").write_text(f"제목: {run['mail']['subject']}\n\n{run['mail']['body']}", encoding="utf-8")
        for label, svg in run["timeline_svgs"].items():
            (out / f"timeline-{label}.svg").write_text(svg, encoding="utf-8")
        for s in run["candidates"][:1]:
            (out / f"schedule-{s['label']}.csv").write_text(schedule_csv(s), encoding="utf-8-sig")
        slim = {k: v for k, v in run.items() if k not in ("timeline_svgs",)}
        slim["report"] = {k: v for k, v in run["report"].items() if k != "html"}
        (out / "run.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"  산출물: {out}")
    return run


def cmd_verify(a):
    from .verify import run_golden, run_scenarios

    g = run_golden()
    print(f"■ 정답 세트: {g['passed']}/{g['total']}칸 일치 ({g['match_rate']:.1%})")
    for m in g["mismatches"]:
        print(f"  ✘ {m['gc']} | {m['case']} | {m['item']} {m['field']}: 기대 {m['expected']} / 실제 {m['actual']} (규칙 {', '.join(m['rule_ids'])})")
    for e in g["errors"]:
        print(f"  ✘ 입력 오류 {e['gc']} {e['case']}: {e['issues'][:2]}")
    s = run_scenarios(scenario_dir=DATA_DIR / "scenarios" / "validation", time_limit_s=a.time_limit)
    d = run_scenarios(scenario_dir=DATA_DIR / "scenarios", time_limit_s=a.time_limit, brute_max=0)
    print("■ 검증 시나리오(완전 탐색 비교 포함)")
    for r in s["scenarios"] + d["scenarios"]:
        bf = f" | 완전탐색 ${r['brute_force_usd']:,.2f} ({r['brute_force_plans']:,}가지) {'일치' if r['optimal_match'] else '불일치'}" if "brute_force_usd" in r else ""
        if "error" in r:
            print(f"  {r['scenario']:<18} ✘ 입력 오류 {r['error'][:2]}")
            continue
        gain = (f"절감 ${r['savings_usd']:,.2f}" if r["baseline_complete"]
                else f"기준안 성립 안 함({', '.join(r['baseline_missing'])} 배정 불가)")
        print(f"  {r['scenario']:<18} 선박 {r['vessels']} | 기준안 ${r['baseline_usd']:,.2f} → 1안 ${r['best_usd']:,.2f} {gain} | 위반 {r['candidate_violations']} | {r['status']} {r['elapsed_s']}s{bf}")
    viol = s["violations_total"] + d["violations_total"]
    opt_ok = all(r["optimal_match"] for r in s["optimal_checks"])
    ok = (g["passed"] == g["total"] and not g["errors"] and viol == 0 and opt_ok and s["all_saved_or_equal"] and d["all_saved_or_equal"]
          and not s["errors"] and not d["errors"])
    print(f"■ 결과: 일치율 {g['match_rate']:.1%} · 후보 위반 {viol}건 · 최적성 {'일치' if opt_ok else '불일치'} → {'통과' if ok else '실패'}")
    if a.json:
        Path(a.json).write_text(json.dumps({"golden": g, "validation": s, "demo": d}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if a.strict and not ok:
        sys.exit(1)


def _synthetic(n: int, seed: int = 7) -> dict:
    """확장성 측정용 가상 시나리오(부두 3곳, 경유·휘발유·등유·벙커)."""
    rng = random.Random(seed + n)
    mats = [("DS-ULSD", "SPECIAL_PRODUCT"), ("PG-RG92", "PRODUCT"), ("KR-JETA1", "SPECIAL_PRODUCT"), ("BC-HSFO", "BASE_OIL")]
    vs = []
    for i in range(n):
        mat, vt = rng.choice(mats)
        h = rng.randint(0, 6 * n)
        vs.append({"id": f"B{i + 1:02d}", "vessel_type": vt, "grt": rng.choice([20000, 28000, 42000]), "dwt": 50000, "loa": 183, "pbl": 95,
                   "draft": 11, "direction": "EXPORT", "material_code": mat, "qty": 30000, "status": "PLANNED",
                   "eta": fmt_iso(parse_ts("2026-11-10 00:00") + h * 60),
                   "contract": {"type": "CP", "laytime_h": rng.choice([8, 12, 18, 24]), "demurrage_rate_usd_day": rng.choice([16000, 22000, 28000, 36000]),
                                "laycan_from": "2026-11-09", "laycan_to": "2026-11-14"},
                   "work": {"hours": rng.choice([10, 12, 14, 16]), "hose_term_h": 1}})
    return {"id": f"BENCH-{n}", "title": f"확장성 {n}척", "horizon": {"start": "2026-11-10 00:00", "end": "2026-11-16 00:00"},
            "berths": ["#6", "#7", "#8"], "vessels": vs,
            "weather_forecast": {"segments": [{"from": "2026-11-11 09:00", "to": "2026-11-12 03:00", "wind_ms": 17}]}}


def cmd_bench(a):
    from .engine.build import build_context
    from .engine.optimizer import optimize
    from .rules.loader import load_rules

    rules = load_rules()
    rows = []
    for n in a.sizes:
        doc = _synthetic(n)
        ctx, _ = build_context(doc, rules)
        times, res = [], None
        for _ in range(a.repeat):
            t0 = time.perf_counter()
            res = optimize(ctx, k=3, time_limit_s=a.time_limit)
            times.append(time.perf_counter() - t0)
        best = res.candidates[0].total_cents / 100 if res.candidates else None
        rows.append({"vessels": n, "berths": 3, "avg_s": round(sum(times) / len(times), 2), "max_s": round(max(times), 2),
                     "status": res.status, "gap": round(res.gap, 4), "baseline_usd": res.baseline.total_cents / 100,
                     "best_usd": best, "nodes": res.stats["bnb"]["nodes"]})
        print(f"  {n:>2}척 · 부두 3곳: 평균 {rows[-1]['avg_s']}s (최대 {rows[-1]['max_s']}s) · {res.status} · 갭 {res.gap:.1%} · 노드 {res.stats['bnb']['nodes']:,} · 기준안 ${rows[-1]['baseline_usd']:,.0f} → 1안 ${best:,.0f}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_serve(a):
    import uvicorn
    uvicorn.run("demurrage.api.app:create_app", factory=True, host=a.host, port=a.port, log_level="warning")


def cmd_fetch_public(a):
    """FR-06: 공공데이터포털(한국천문연구원 출몰시각 등) — 서비스키가 있을 때만 호출. 없으면 오프라인 계산본을 저장."""
    from datetime import date, datetime, timedelta

    from .data.solar import sunrise_sunset
    from .rules.loader import load_rules

    loc = load_rules().location
    key = os.environ.get("PUBLIC_DATA_SERVICE_KEY")
    days = {}
    d0 = date.fromisoformat(a.start)
    for i in range(a.days):
        d = d0 + timedelta(days=i)
        r, s = sunrise_sunset(d, loc["lat"], loc["lon"], loc.get("tz_hours", 9))
        days[d.isoformat()] = [f"{r // 60:02d}:{r % 60:02d}", f"{s // 60:02d}:{s % 60:02d}"]
    doc = {"source": "NOAA 태양 위치식 계산(서비스키 없음 — 공공데이터 API 대체)" if not key else "한국천문연구원 출몰시각(공공데이터포털)",
           "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "status": "fallback" if not key else "api",
           "location": loc, "days": days}
    if key:
        print("  서비스키가 있지만 이 데모는 API 응답 형식 확인 전이라 호출하지 않습니다 [확인 필요]. 계산본을 저장합니다.")
    out = DATA_DIR / "public" / "sun_ulsan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  저장: {out} ({len(days)}일, 출처: {doc['source']})")


def main(argv=None):
    p = argparse.ArgumentParser(prog="demurrage", description="척화비 데모 — 울산 CLX 체선료 최적화 Agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="시나리오 하나를 1~7단계로 실행")
    r.add_argument("scenario")
    r.add_argument("--out")
    r.add_argument("--db", help="결정·실행을 기록할 DB(예: sqlite:///runtime/demurrage.db)")
    r.add_argument("--confirm", help="담당자 확정(예: 1안) — --actor 필요")
    r.add_argument("--actor")
    r.add_argument("--reason")
    r.add_argument("--rules-patch", help='예: {"contract.weather_deduction.ratio": 0}')
    r.add_argument("--time-limit", type=float, default=20.0)
    r.add_argument("-k", type=int, default=3)
    r.set_defaults(fn=cmd_run)
    v = sub.add_parser("verify", help="정답 세트·검증 시나리오·최적성 일괄 검증(FR-50)")
    v.add_argument("--strict", action="store_true", help="하나라도 틀리면 종료 코드 1 (CI 문지기)")
    v.add_argument("--json")
    v.add_argument("--time-limit", type=float, default=20.0)
    v.set_defaults(fn=cmd_verify)
    b = sub.add_parser("bench", help="성능·확장성 측정(NFR-08·09)")
    b.add_argument("--sizes", type=int, nargs="+", default=[8, 12, 16])
    b.add_argument("--repeat", type=int, default=5)
    b.add_argument("--time-limit", type=float, default=30.0)
    b.add_argument("--json")
    b.set_defaults(fn=cmd_bench)
    s = sub.add_parser("serve", help="API + 화면")
    s.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    s.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    s.set_defaults(fn=cmd_serve)
    f = sub.add_parser("fetch-public", help="일출·일몰 수집본 저장(FR-05·06)")
    f.add_argument("--start", default="2026-11-01")
    f.add_argument("--days", type=int, default=60)
    f.set_defaults(fn=cmd_fetch_public)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
