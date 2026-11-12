"""검증 일괄 실행 (FR-49 검증 시나리오, FR-50 결과표, FR-51 최적성 검증, 성공기준 ①②).

세 가지를 한 번에 돌린다.
  1) 정답 세트(data/golden): 사람이 손으로 계산한 값과 엔진 값을 칸마다 비교 → 일치율
  2) 검증 시나리오(data/scenarios): 기준안 대비 절감액, 후보의 하드 제약 위반 건수(0이어야 함)
  3) 최적성 검증: 6척 이하 시나리오는 가능한 배정을 모두 탐색한 결과와 1안 금액을 비교
불일치는 기대값·실제값·관련 규칙 ID와 함께 남긴다.
"""
from __future__ import annotations

import copy
import json
import time
from fractions import Fraction
from pathlib import Path

from .domain.timeutil import fmt_iso, hours_to_min, parse_ts
from .engine.build import build_context
from .engine.eligibility import check_berth
from .engine.intake import parse_scenario
from .engine.optimizer import brute_force, optimize
from .engine.schedule import fcfs, replay
from .engine.worktime import WorkModel, load_history
from .rules.loader import DATA_DIR, load_rules

TIME_FIELDS = {"etb", "etb_without_weather", "work_start", "work_end", "hose_off", "etu", "laytime_start", "laytime_end", "etanr"}
HOUR_FIELDS = {"demurrage_hours": "demurrage_minutes", "weather_hours": "weather_minutes",
               "weather_deduction_hours": "weather_deduction_minutes", "demurrage_raw_hours": "demurrage_raw_minutes"}


def _merge_vessel(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = copy.deepcopy(v)
    return out


def build_case_scenario(gc: dict, case: dict) -> dict:
    d = gc.get("defaults", {})
    sc = copy.deepcopy(d.get("scenario", {}))
    sc.update(copy.deepcopy({k: v for k, v in case.get("scenario", {}).items() if k != "vessels"}))
    vbase = d.get("vessel", {})
    sc["vessels"] = [_merge_vessel(vbase, v) for v in case.get("scenario", {}).get("vessels", [])]
    sc.setdefault("id", f"{gc['id']}")
    return sc


def _actual(calc: dict, field: str):
    if field in TIME_FIELDS:
        return fmt_iso(calc[field])
    if field in HOUR_FIELDS:
        m = calc[HOUR_FIELDS[field]]
        return Fraction(max(m, 0) if field == "demurrage_raw_hours" else m) / 60
    if field == "amount_usd":
        return Fraction(calc["amount_cents"], 100)
    return calc.get(field)


def _expected(field: str, value):
    if field in TIME_FIELDS:
        return fmt_iso(parse_ts(value))
    if field in HOUR_FIELDS or field == "amount_usd":
        return Fraction(str(value))
    return value


def _show(x):
    if isinstance(x, Fraction):
        return str(float(x)) if x.denominator != 1 else str(x.numerator)
    return x


class Checker:
    def __init__(self):
        self.rows = []

    def add(self, gc, case, item, field, expected, actual, rule_ids):
        ok = expected == actual
        self.rows.append({"gc": gc, "case": case, "item": item, "field": field, "expected": _show(expected),
                          "actual": _show(actual), "ok": ok, "rule_ids": rule_ids})
        return ok


def _check_plan_vessels(chk, gc_id, case_name, sch, vexp: dict, rule_ids):
    for vid, fields in vexp.items():
        calc = sch.calcs.get(vid)
        for f, ev in fields.items():
            if calc is None:
                chk.add(gc_id, case_name, f"{sch.label}/{vid}", f, ev, "미배정", rule_ids)
                continue
            if f == "laytime_start_rule":
                chk.add(gc_id, case_name, f"{sch.label}/{vid}", f, ev, calc["laytime_start_rule"], rule_ids)
            elif f == "berth":
                chk.add(gc_id, case_name, f"{sch.label}/{vid}", f, ev, calc["berth"], rule_ids)
            else:
                chk.add(gc_id, case_name, f"{sch.label}/{vid}", f, _expected(f, ev), _actual(calc, f), rule_ids)


def run_golden(golden_dir: Path = None, data_dir: Path = None, quick: bool = False) -> dict:
    base = Path(data_dir) if data_dir else DATA_DIR
    gdir = Path(golden_dir) if golden_dir else base / "golden"
    chk = Checker()
    errors = []
    for path in sorted(gdir.glob("GC-*.json")):
        gc = json.loads(path.read_text(encoding="utf-8"))
        gid, rids = gc["id"], gc.get("rule_ids", [])
        for case in gc.get("cases", []):
            name = case["name"]
            rules = load_rules(patch=case.get("rules_patch"), data_dir=base)
            doc = build_case_scenario(gc, case)
            ctx, issues = build_context(doc, rules, data_dir=base)
            if ctx is None:
                errors.append({"gc": gid, "case": name, "issues": [i.as_dict() for i in issues]})
                chk.add(gid, name, "입력", "검증 통과", True, False, rids)
                continue
            exp = case.get("expect", {})
            base_sch = fcfs(ctx)
            plans = exp.get("plans", {})
            if "vessels" in exp:
                _check_plan_vessels(chk, gid, name, base_sch, exp["vessels"], rids)
            for pname, pexp in plans.items():
                sch = base_sch if pname == "FCFS" else replay(ctx, [tuple(x) for x in pexp["order"]], pname)
                sch.label = pname
                if "total_usd" in pexp:
                    chk.add(gid, name, pname, "total_usd", Fraction(pexp["total_usd"]), Fraction(sch.total_cents, 100), rids)
                _check_plan_vessels(chk, gid, name, sch, pexp.get("vessels", {}), rids)
            for vid, seq in exp.get("pushes", {}).items():
                p = base_sch.state.pl.get(vid)
                chk.add(gid, name, f"기준안/{vid}", "적용 규칙(밀어낸 순서)", list(seq), [x.rule_id for x in p.pushes] if p else None, rids)
            if "optimizer" in exp and not quick:
                oe = exp["optimizer"]
                res = optimize(ctx, k=3, time_limit_s=10)
                if "baseline_total_usd" in oe:
                    chk.add(gid, name, "최적화", "기준안 총액", Fraction(oe["baseline_total_usd"]), Fraction(res.baseline.total_cents, 100), rids)
                if "best_total_usd" in oe:
                    chk.add(gid, name, "최적화", "1안 총액", Fraction(oe["best_total_usd"]), Fraction(res.candidates[0].total_cents, 100) if res.candidates else None, rids)
                if "candidate_totals_usd" in oe:
                    chk.add(gid, name, "최적화", "후보 총액(1·2·3안)", [Fraction(x) for x in oe["candidate_totals_usd"]],
                            [Fraction(c.total_cents, 100) for c in res.candidates], rids)
                if "savings_usd" in oe and res.candidates:
                    chk.add(gid, name, "최적화", "절감액", Fraction(oe["savings_usd"]),
                            Fraction(res.baseline.total_cents - res.candidates[0].total_cents, 100), rids)
                if "violations" in oe:
                    chk.add(gid, name, "최적화", "후보 제약 위반", oe["violations"], sum(len(c.violations) for c in res.candidates), rids)
                if "best_signature" in oe and res.candidates:
                    want = tuple(sorted((b, tuple(v)) for b, v in oe["best_signature"]))
                    chk.add(gid, name, "최적화", "1안 부두별 순서", str(want), str(res.candidates[0].signature()), rids)
        # 적합성(FR-07·08)
        el = gc.get("eligibility")
        if el:
            rules = load_rules(data_dir=base)
            for c in el["checks"]:
                raw = _merge_vessel(el["base_vessel"], c["vessel"])
                sc, issues = parse_scenario({"id": "elig", "horizon": {"start": "2026-11-10 00:00", "end": "2026-11-12 00:00"}, "vessels": [raw]}, rules)
                v = sc.vessels[0]
                got = sorted(r["item"] for r in check_berth(v, rules.berths[c["berth"]]))
                chk.add(gid, c["name"], c["berth"], "제외 항목", sorted(c["excluded_items"]), got, rids)
        if gc.get("cargo_mapping"):
            rules = load_rules(data_dir=base)
            for code, grp in gc["cargo_mapping"].items():
                chk.add(gid, "자재코드 → 화물 그룹", code, "화물 그룹", grp, rules.cargo_map.get(code), rids)
            bad = gc.get("unknown_material_code")
            if bad:
                raw = _merge_vessel(gc["eligibility"]["base_vessel"], {"material_code": bad})
                _, issues = parse_scenario({"id": "x", "horizon": {"start": "2026-11-10 00:00", "end": "2026-11-12 00:00"}, "vessels": [raw]}, load_rules(data_dir=base))
                codes = [i.code for i in issues if i.field == "material_code"]
                chk.add(gid, "매핑표에 없는 자재코드", bad, "입력 오류", ["UNKNOWN_REF"], codes, rids)
        # 작업시간 추정(FR-23)
        if gc.get("work_checks"):
            rules = load_rules(data_dir=base)
            wm = WorkModel(load_history(base / "history" / "shipments.v1.csv"), rules.etu_after_work_min, rules.work_start_delay_min)
            for c in gc["work_checks"]:
                raw = {"id": c["vessel"]["id"], "vessel_type": "SPECIAL_PRODUCT", "grt": 20000, "dwt": 30000, "loa": 180, "pbl": 85,
                       "draft": 10, "direction": "EXPORT", "eta": "2026-11-10 08:00", "status": "PLANNED",
                       "contract": {"type": "CP", "laytime_h": 24, "demurrage_rate_usd_day": 20000, "laycan_from": "2026-11-09", "laycan_to": "2026-11-11"},
                       **c["vessel"]}
                sc, _ = parse_scenario({"id": "w", "horizon": {"start": "2026-11-10 00:00", "end": "2026-11-12 00:00"}, "vessels": [raw]}, rules)
                wp = wm.plan(sc.vessels[0], c["berth"])
                if c.get("work_min") is None:
                    chk.add(gid, c["name"], c["berth"], "추정 불가(입력 오류)", True, wp is None, rids)
                    continue
                chk.add(gid, c["name"], c["berth"], "작업 분", c["work_min"], wp.work if wp else None, rids)
                chk.add(gid, c["name"], c["berth"], "호스분리 분", c["hose_min"], wp.hose_term if wp else None, rids)
                chk.add(gid, c["name"], c["berth"], "매칭 단계", c["stage"], wp.basis["work"]["stage"] if wp else None, rids)
                chk.add(gid, c["name"], c["berth"], "실적 건수", c["records"], wp.basis["work"].get("records") if wp else None, rids)
    total = len(chk.rows)
    passed = sum(1 for r in chk.rows if r["ok"])
    return {"checks": chk.rows, "total": total, "passed": passed,
            "match_rate": (passed / total) if total else 0.0, "errors": errors,
            "mismatches": [r for r in chk.rows if not r["ok"]]}


def run_scenarios(scenario_dir: Path = None, data_dir: Path = None, time_limit_s: float = 20.0, brute_max: int = 6) -> dict:
    """검증 시나리오마다 기준안·후보·위반·절감·(6척 이하면) 완전 탐색 비교."""
    base = Path(data_dir) if data_dir else DATA_DIR
    sdir = Path(scenario_dir) if scenario_dir else base / "scenarios"
    rows = []
    for path in sorted(sdir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        rules = load_rules(data_dir=base)
        t0 = time.perf_counter()
        ctx, issues = build_context(doc, rules, data_dir=base)
        if ctx is None:
            rows.append({"scenario": doc.get("id"), "title": doc.get("title"), "error": [i.as_dict() for i in issues if i.level == "ERROR"]})
            continue
        res = optimize(ctx, k=3, time_limit_s=time_limit_s)
        elapsed = time.perf_counter() - t0
        row = {
            "scenario": doc.get("id"), "title": doc.get("title"), "vessels": len(ctx.movable), "berths": len(ctx.sc.active_berths),
            "baseline_usd": res.baseline.total_cents / 100,
            "baseline_complete": res.baseline.complete,
            "baseline_missing": sorted({b.vid for b in res.baseline.infeasible}),
            "baseline_violations": len(res.baseline.violations),
            "candidates_usd": [c.total_cents / 100 for c in res.candidates],
            "best_usd": res.candidates[0].total_cents / 100 if res.candidates else None,
            "savings_usd": ((res.baseline.total_cents - res.candidates[0].total_cents) / 100
                            if res.candidates and res.baseline.complete else None),
            "candidate_violations": sum(len(c.violations) for c in res.candidates),
            "status": res.status, "proven_optimal": res.proven_optimal, "gap": round(res.gap, 4),
            "nodes": res.stats["bnb"]["nodes"], "elapsed_s": round(elapsed, 2),
        }
        if len(ctx.movable) <= brute_max:
            bf, count = brute_force(ctx, k=1, max_vessels=brute_max)
            row["brute_force_usd"] = bf[0][0] / 100 if bf else None
            row["brute_force_plans"] = count
            row["optimal_match"] = (bf[0][0] == res.candidates[0].total_cents) if (bf and res.candidates) else None
        rows.append(row)
    return {"scenarios": rows,
            "violations_total": sum(r.get("candidate_violations", 0) for r in rows),
            # 기준안이 성립하지 않는 시나리오(도착 순서로는 제약을 못 지킴)는 절감 비교에서 뺀다
            "all_saved_or_equal": all((r.get("savings_usd") or 0) >= 0 for r in rows if "error" not in r and r.get("baseline_complete")),
            "errors": [r for r in rows if "error" in r],
            "optimal_checks": [r for r in rows if "optimal_match" in r]}
