"""수리계획법(MILP) 모델 검증.

1. 골든: docs/requirements/09-first-steps.md SC-01 손계산 정답 (순서 A 52,000 · 순서 B 6,000 · 최적 B)
2. 식 = 모델: 실제 23개 항차를 실제 접안 시각에 고정하면 MILP의 d_i가 계산식(laytime_csv)과 같다
3. 모델 = 완전 탐색: 무작위 문제(이동·선석 배정·선석 가용·주간 접안 포함)에서 MILP 최적값 = 완전 탐색 최적값,
   MILP 해는 모든 제약을 지킨다
4. 완전 탐색의 전제(비용이 접안 시각에 줄어들지 않는다)를 격자로 확인
"""
import random
from datetime import datetime
from pathlib import Path

import pytest

import berth_milp as bm
import laytime_csv as lc

DATA = Path(__file__).resolve().parents[1] / "data" / "vessel_journeys.csv"
TERMS = lc.Terms()


# ---------------------------------------------------------------- 1. SC-01 골든

SC01 = (bm.Vessel("X", nor=2, p=16, L=24, rate=48000, berths=("SK7",)),
        bm.Vessel("Y", nor=4, p=10, L=12, rate=96000, berths=("SK7",)))
SC01_PRM = bm.Params(berth_free={"SK7": 6.0})


def test_sc01_order_a_hand_calculation():
    """X 먼저: X 접안 D1 07:00 체선 0, Y 접안 D2 01:00 → 체선 13h × 4,000 = 52,000."""
    x, y = SC01
    sched = {v.name: s for v, s in bm._schedule_berth([x, y], "SK7", SC01_PRM)}
    assert sched == {"X": 7.0, "Y": 25.0}
    assert bm.demurrage_hours(y, sched["Y"], SC01_PRM) == 13
    assert bm.evaluate_order([x, y], "SK7", SC01_PRM) == 52000


def test_sc01_order_b_hand_calculation():
    """Y 먼저: Y 접안 D1 07:00 체선 0, X 접안 D1 19:00 → 체선 3h × 2,000 = 6,000."""
    x, y = SC01
    sched = {v.name: s for v, s in bm._schedule_berth([y, x], "SK7", SC01_PRM)}
    assert sched == {"Y": 7.0, "X": 19.0}
    assert bm.demurrage_hours(x, sched["X"], SC01_PRM) == 3
    assert bm.evaluate_order([y, x], "SK7", SC01_PRM) == 6000


def test_sc01_milp_reproduces_both_orders_and_picks_b():
    a = bm.solve_milp(list(SC01), SC01_PRM, force_before=[("X", "Y")])
    b = bm.solve_milp(list(SC01), SC01_PRM, force_before=[("Y", "X")])
    best = bm.solve_milp(list(SC01), SC01_PRM)
    assert (a.milp_cost, b.milp_cost, best.milp_cost) == pytest.approx((52000, 6000, 6000))
    assert best.order == {"SK7": ["Y", "X"]}
    assert best.start_of("Y") == pytest.approx(7.0) and best.start_of("X") == pytest.approx(19.0)


# ---------------------------------------------------------------- 2. 식 = 모델 (실제 항차)

@pytest.fixture(scope="module")
def real():
    res, calls = lc.analyze(DATA, TERMS)
    return {r.jid: r for r in res}, {c.jid: c for c in calls}


@pytest.mark.parametrize("jid", [f"J{n:03d}" for n in range(1, 24)])
def test_closed_form_and_milp_equal_laytime_csv_at_actual_berthing(real, jid):
    results, calls = real
    c, r = calls[jid], results[jid]
    origin = c.nor_t.replace(hour=0, minute=0)          # 시각 0 = NOR 당일 자정
    v = bm.vessel_from_call(c, TERMS, origin)
    s = (c.allfast - origin).total_seconds() / 3600
    assert bm.demurrage_hours(v, s) == pytest.approx(r.demurrage_h, abs=1e-9)
    sol = bm.solve_milp([v], fix_start={v.name: s})
    assert sol.rows[0]["d"] == pytest.approx(r.demurrage_h, abs=1e-6)
    assert sol.milp_cost == pytest.approx(r.amount_usd, abs=0.01)


def test_floor_is_service_time_only(real):
    """NOR 직후 바로 접안(s = a + σ)하면 체선은 max(0, p − L)뿐 — 선석 대기가 만드는 체선의 하한."""
    results, calls = real
    for jid, c in calls.items():
        v = bm.vessel_from_call(c, TERMS, c.nor_t.replace(hour=0, minute=0))
        floor = bm.demurrage_hours(v, v.nor + v.sigma)
        assert floor == pytest.approx(max(0.0, v.p - v.L))
        assert floor <= results[jid].demurrage_h + 1e-9


# ---------------------------------------------------------------- 3. 모델 = 완전 탐색

def random_instance(seed: int, n: int = 5):
    rng = random.Random(seed)
    vs = []
    for i in range(n):
        vs.append(bm.Vessel(
            f"V{i}", nor=round(rng.uniform(0, 30), 2), p=round(rng.uniform(5, 20), 2), L=rng.choice([12, 24, 36]),
            rate=rng.choice([10_000, 26_000, 55_000, 120_000]), berths=rng.choice([("A",), ("B",), ("A", "B")]),
            sigma=rng.choice([0, 0, 0.5, 1.0, 1.5]), daytime_only=rng.random() < 0.25))
    free = {k: round(rng.uniform(0, 14), 2) for k in ("A", "B") if rng.random() < 0.7}
    prm = bm.Params(berth_free=free, g_out=rng.choice([0.5, 1.0]), g_in=rng.choice([0.5, 1.0, 1.5]))
    return vs, prm


def check_feasible(vessels, prm, sol, tol=1e-5):
    by = {v.name: v for v in vessels}
    gap = prm.g_out + prm.g_in
    for r in sol.rows:
        v = by[r["name"]]
        assert r["berth"] in v.berths
        assert r["s"] >= v.nor + v.sigma - tol
        if r["berth"] in prm.berth_free:
            assert r["s"] >= prm.berth_free[r["berth"]] + prm.g_in - tol
        if v.daytime_only:
            assert prm.day_start - tol <= r["s"] % 24 <= prm.day_end + tol
    for k, names in sol.order.items():
        for a, b in zip(names, names[1:]):
            assert sol.start_of(b) >= sol.start_of(a) + by[a].p + gap - tol


@pytest.mark.parametrize("seed", range(40))
def test_milp_matches_brute_force_on_random_instances(seed):
    vs, prm = random_instance(seed)
    sol, bf = bm.solve_milp(vs, prm), bm.brute_force(vs, prm)
    assert sol.status == "최적"
    check_feasible(vs, prm, sol)
    assert sol.milp_cost == pytest.approx(sol.cost, abs=0.01)         # 모델이 센 비용 = 식으로 다시 센 비용
    assert sol.cost == pytest.approx(bf.cost, abs=0.01), (sol.order, bf.order)


@pytest.mark.parametrize("seed", range(100, 108))
def test_milp_matches_brute_force_with_six_vessels(seed):
    vs, prm = random_instance(seed, n=6)
    sol, bf = bm.solve_milp(vs, prm), bm.brute_force(vs, prm)
    check_feasible(vs, prm, sol)
    assert sol.cost == pytest.approx(bf.cost, abs=0.01)


def test_milp_never_worse_than_fcfs():
    for seed in range(200, 215):
        vs, prm = random_instance(seed)
        assert bm.solve_milp(vs, prm).cost <= bm.fcfs(vs, prm).cost + 0.01


def test_daytime_constraint_pushes_berthing_to_morning():
    """앞 배가 밤에 나가면 주간 접안 선박은 아침 07:00까지 기다린다 (C7)."""
    a = bm.Vessel("A", nor=0, p=14, L=24, rate=24_000, berths=("K",))
    b = bm.Vessel("B", nor=2, p=8, L=6, rate=48_000, berths=("K",), daytime_only=True)
    prm = bm.Params(berth_free={"K": 6.0})
    sol = bm.solve_milp([a, b], prm, force_before=[("A", "B")])
    assert sol.start_of("A") == pytest.approx(7.0)
    assert sol.start_of("B") % 24 == pytest.approx(7.0)               # A 호스 분리 21:00 → 접안 가능 23:00 → 다음 날 07:00
    assert sol.start_of("B") == pytest.approx(31.0)
    assert sol.cost == pytest.approx(bm.evaluate_order([a, b], "K", prm))


# ---------------------------------------------------------------- 4. 완전 탐색의 전제

@pytest.mark.parametrize("seed", range(20))
def test_cost_never_decreases_with_later_berthing(seed):
    rng = random.Random(seed)
    v = bm.Vessel("V", nor=0, p=rng.uniform(5, 20), L=rng.choice([12, 24, 36]), rate=26_000, berths=("A",),
                  sigma=rng.choice([0, 0.5, 1.0, 1.5]))
    prev = -1.0
    for k in range(0, 4000):
        s = v.nor + v.sigma + k * 0.05
        d = bm.demurrage_hours(v, s)
        assert d >= prev - 1e-9
        prev = d
