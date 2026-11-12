"""성공기준 ② — 후보의 하드 제약 위반 0건, 기준안 대비 절감, 6척 이하 완전 탐색과 같은 최적(FR-35·36·51)."""
import copy
import json
import random

import pytest

from demurrage.engine.build import build_context
from demurrage.engine.optimizer import brute_force, optimize
from demurrage.rules.loader import DATA_DIR

GROUPS = ["DS-ULSD", "PG-RG92", "KR-JETA1", "BC-HSFO"]


def _random_case(rng, n):
    vs = []
    for i in range(n):
        h = rng.randint(0, 40)
        lf = 9 + (2 if rng.random() < 0.25 else 0)
        vs.append({"id": f"R{i}", "vessel_type": rng.choice(["SPECIAL_PRODUCT", "PRODUCT"]), "grt": rng.choice([20000, 28000, 40000]),
                   "dwt": 50000, "loa": 183, "pbl": 95, "draft": 11, "direction": "EXPORT", "material_code": rng.choice(GROUPS),
                   "qty": 30000, "eta": f"2026-11-{10 + h // 24:02d} {h % 24:02d}:{rng.choice(['00', '30'])}", "status": "PLANNED",
                   "contract": {"type": "CP", "laytime_h": rng.choice([6, 12, 18, 24, 36]), "demurrage_rate_usd_day": rng.choice([12000, 24000, 36000, 48000]),
                                "laycan_from": f"2026-11-{lf:02d}", "laycan_to": f"2026-11-{lf + 2:02d}"},
                   "work": {"hours": rng.choice([6, 8, 10, 14]), "hose_term_h": 1}})
    d = {"id": "rand", "horizon": {"start": "2026-11-10 00:00", "end": "2026-11-14 00:00"}, "berths": ["#6", "#7", "#8"], "vessels": vs}
    if rng.random() < 0.5:
        s = rng.randint(4, 30)
        d["weather_forecast"] = {"segments": [{"from": f"2026-11-{10 + s // 24:02d} {s % 24:02d}:00", "to": f"2026-11-{10 + (s + 10) // 24:02d} {(s + 10) % 24:02d}:00", "wind_ms": 17}]}
    if rng.random() < 0.3:
        d["restrictions"] = [{"id": "M", "berths": [rng.choice(["#6", "#7", "#8"])], "start": "2026-11-10 12:00", "end": "2026-11-11 00:00", "reason": "MAINTENANCE"}]
    if rng.random() < 0.3:
        d["inventory"] = [{"group": "DIESEL", "capacity": 1e9, "opening": 40000, "daily_net": 20000, "minimum": 0}]
    return d


def test_branch_and_bound_equals_brute_force_on_random_cases(rules):
    rng = random.Random(20261109)
    checked = 0
    for _ in range(80):
        ctx, _ = build_context(_random_case(rng, rng.choice([2, 3, 4, 5])), rules)
        if ctx is None:
            continue
        res = optimize(ctx, k=3, time_limit_s=10)
        bf, _ = brute_force(ctx, k=3)
        assert [c.total_cents for c in res.candidates] == [c for c, _ in bf]
        assert all(not c.violations for c in res.candidates)
        checked += 1
    assert checked >= 60


@pytest.mark.parametrize("path", sorted((DATA_DIR / "scenarios").rglob("*.json")), ids=lambda p: p.stem)
def test_scenarios_have_valid_distinct_candidates(rules, path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    ctx, issues = build_context(doc, rules)
    assert ctx is not None, [i.as_dict() for i in issues]
    res = optimize(ctx, k=3, time_limit_s=20)
    assert res.candidates, "후보가 하나도 없음"
    assert all(not c.violations for c in res.candidates)                        # 하드 제약 위반 0
    if res.baseline.complete:
        assert res.candidates[0].total_cents <= res.baseline.total_cents         # 기준안보다 나쁘지 않음
    else:                                                                        # 도착 순서로는 못 넣는 배(S15)도 후보에는 들어감
        missing = {b.vid for b in res.baseline.infeasible}
        assert missing and all(vid in c.state.pl for c in res.candidates for vid in missing)
    sigs = [c.signature() for c in res.candidates]
    assert len(set(sigs)) == len(sigs)                                           # 후보끼리 1척 이상 배정이 다름
    assert [c.total_cents for c in res.candidates] == sorted(c.total_cents for c in res.candidates)
    if path.stem != "S16-large":                                                 # 대규모는 제한시간에 걸리면 '최선 탐색 결과'
        assert res.proven_optimal and res.gap == 0.0
    for c in res.candidates:                                                     # FIX·작업 중 선박은 그대로
        for vid in ctx.immovable:
            p = c.state.pl[vid]
            assert (p.berth, p.etb) == (ctx.vessels[vid].fixed_berth, ctx.vessels[vid].fixed_etb)


def test_no_improvement_is_labelled(rules):
    from tests.conftest import load_scenario
    ctx, _ = build_context(load_scenario("VAL-02-buoy-tide"), rules)
    res = optimize(ctx, k=3, time_limit_s=10)
    assert res.status == "NO_IMPROVEMENT"


def test_time_limit_reports_best_found_and_gap(rules):
    from demurrage.cli import _synthetic
    ctx, _ = build_context(_synthetic(12), rules)
    res = optimize(ctx, k=3, time_limit_s=0.05, node_limit=50)
    assert res.candidates and all(not c.violations for c in res.candidates)
    if not res.proven_optimal:
        assert res.status in ("BEST_FOUND", "NO_IMPROVEMENT") and 0.0 <= res.gap <= 1.0
        assert res.candidates[0].meta["optimality"] == "최선 탐색 결과"


def test_no_feasible_candidate_is_reported(rules):
    from tests.conftest import load_scenario
    doc = copy.deepcopy(load_scenario("VAL-01-combo"))
    for v in doc["vessels"]:
        if v["id"] == "V03":
            v["deadline"] = "2026-11-10 05:00"   # ETA 07:00보다 이른 마감 → 어디에도 못 붙음
    ctx, _ = build_context(doc, rules)
    res = optimize(ctx, k=3, time_limit_s=5)
    assert res.status == "NO_FEASIBLE" and res.candidates == []
