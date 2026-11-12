"""explorer.html 생성 — 항차 데이터, 수리계획법 모델 입력·해, Python 정답(골든)을 템플릿에 내장한 한 장짜리 화면.

화면의 계산은 laytime_csv.py·berth_milp.py와 같은 식을 JavaScript로 옮긴 것이다. 옮기면서 어긋나지 않았는지
화면이 열릴 때마다 (1) 여기서 Python이 미리 계산해 내장한 값과 대조하고, (2) tests/test_explorer.py가 node로 무작위
조건에서 다시 대조한다. 수리계획법 탭의 모델(변수·제약 행)도 JS가 조립하고, Python의 build_model()과 행 단위로 같은지 테스트한다.

    python3 -I journeys/make_explorer.py            # journeys/explorer.html 생성
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import berth_milp as bm  # noqa: E402
import laytime_csv as lc  # noqa: E402
import run_milp as rm  # noqa: E402

BASE = datetime(2025, 1, 1)
DEFAULT_CSV = HERE / "data" / "vessel_journeys.csv"
TEMPLATE = HERE / "explorer_template.html"
OUT = HERE / "explorer.html"

BASE_CFG = dict(L=24, rate=26000, notice=6, lag=0, norBasis="tender", norValidity="lenient", shiftCounts=True,
                gaps="count")
SC01_P = {"X": {"a": 2, "sigma": 0, "p": 16, "L": 24, "rate": 48000},
          "Y": {"a": 4, "sigma": 0, "p": 10, "L": 12, "rate": 96000},
          "free": 6, "gout": 1, "gin": 1, "notice": 6}
STAGGERS = (1.0, 1.5, 2.0)


def mins(t: datetime | None) -> int | None:
    return None if t is None else int((t - BASE).total_seconds() // 60)


def voyage(c: lc.Call) -> dict:
    return {"jid": c.jid, "vessel": c.vessel, "op": c.operation, "berth": c.berth, "cargo": c.cargo, "qty": c.qty_t,
            "norT": mins(c.nor_t), "norA": mins(c.nor_a), "allfast": mins(c.allfast), "opsStart": mins(c.ops_start),
            "opsEnd": mins(c.ops_end), "anchorFirst": mins(c.anchor_first),
            "shifts": [[mins(a), mins(b)] for a, b in c.shifts], "gaps": [[mins(a), mins(b)] for a, b in c.gaps],
            "flags": list(c.flags)}


def golden_configs(n_random: int = 24, seed: int = 20251105) -> list[dict]:
    cfgs = [dict(BASE_CFG), dict(BASE_CFG, L=36, rate=120000), dict(BASE_CFG, norBasis="accepted"),
            dict(BASE_CFG, norValidity="strict"), dict(BASE_CFG, shiftCounts=False), dict(BASE_CFG, gaps="exclude"),
            dict(BASE_CFG, lag=30, notice=0), dict(BASE_CFG, L=12, rate=10000, notice=12, lag=180),
            dict(BASE_CFG, L=48, norBasis="accepted", norValidity="strict", shiftCounts=False, gaps="exclude"),
            dict(BASE_CFG, L=6, rate=5000, lag=90, norBasis="accepted")]
    rng = random.Random(seed)
    for _ in range(n_random):
        cfgs.append(dict(L=rng.randint(6, 96), rate=rng.randrange(5000, 150001, 1000), notice=rng.choice([0, 3, 6, 9, 12]),
                         lag=rng.choice([0, 15, 45, 120]), norBasis=rng.choice(["tender", "accepted"]),
                         norValidity=rng.choice(["lenient", "strict"]), shiftCounts=rng.random() < 0.5,
                         gaps=rng.choice(["count", "exclude"])))
    return cfgs


def py_result(c: lc.Call, cfg: dict) -> list[float] | None:
    terms = lc.Terms(laytime_hours=cfg["L"], notice_hours=cfg["notice"], rate_usd_day=cfg["rate"],
                     hose_lag_min=cfg["lag"], shift_counts_on_demurrage=cfg["shiftCounts"])
    try:
        r = lc.compute(c, terms, nor_basis=cfg["norBasis"], nor_validity=cfg["norValidity"], gaps=cfg["gaps"])
    except ValueError:
        return None
    return [r.demurrage_h * 60, r.amount_usd, r.used_h * 60, r.deducted_h * 60]


def golden(calls: list[lc.Call]) -> list[dict]:
    return [{"cfg": cfg, "res": {c.jid: py_result(c, cfg) for c in calls}} for cfg in golden_configs()]


# ----------------------------------------------------------------------------- 수리계획법 탭

def inst_of(vessels: list[bm.Vessel], prm: bm.Params) -> dict:
    """Vessel·Params → 화면이 모델을 조립하는 입력(JS의 inst). 시각·시간은 h."""
    return {"vessels": [{"name": v.name, "a": v.nor, "sigma": v.sigma, "p": v.p, "L": v.L, "rate": v.rate,
                         "berths": list(v.berths)} for v in vessels],
            "n": prm.notice, "gout": prm.g_out, "gin": prm.g_in, "free": dict(prm.berth_free)}


def plan_of(sol: bm.Solution) -> dict:
    return {"berth": {r["name"]: r["berth"] for r in sol.rows}, "s": {r["name"]: r["s"] for r in sol.rows}}


def canonical_plan(vessels: list[bm.Vessel], prm: bm.Params, sol: bm.Solution) -> dict:
    """솔버가 고른 선석 배정과 순서는 그대로 두고 접안 시각을 정확히 다시 계산한다.
    솔버 해는 제약을 허용오차(1e-6h)만큼 어길 수 있어, 화면에 내장할 해는 선석별 순서에서 가장 이르게 붙인 일정으로 바꾼다."""
    by = {v.name: v for v in vessels}
    s: dict[str, float] = {}
    for k, names in sol.order.items():
        for v, t in bm._schedule_berth([by[n] for n in names], k, prm):
            s[v.name] = t
    cost = sum(bm.cost_usd(by[n], t, prm) for n, t in s.items())
    assert abs(cost - sol.cost) < 0.01, (cost, sol.cost)
    return {"berth": {r["name"]: r["berth"] for r in sol.rows}, "s": s}


def order_cost(p: dict) -> list[float]:
    X = bm.Vessel("X", p["X"]["a"], p["X"]["p"], p["X"]["L"], p["X"]["rate"], ("K",), p["X"]["sigma"])
    Y = bm.Vessel("Y", p["Y"]["a"], p["Y"]["p"], p["Y"]["L"], p["Y"]["rate"], ("K",), p["Y"]["sigma"])
    prm = bm.Params(notice=p["notice"], g_out=p["gout"], g_in=p["gin"], berth_free={"K": p["free"]})
    return [bm.evaluate_order([X, Y], "K", prm), bm.evaluate_order([Y, X], "K", prm)]


def golden2(n_random: int = 10, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    sets = [SC01_P]
    for _ in range(n_random):
        v = lambda: {"a": round(rng.uniform(0, 12), 1), "sigma": rng.choice([0, 0, 0.5, 1.0, 1.5]),  # noqa: E731
                     "p": round(rng.uniform(4, 20), 1), "L": rng.choice([6, 12, 24, 36]),
                     "rate": rng.choice([10000, 26000, 48000, 96000])}
        sets.append({"X": v(), "Y": v(), "free": round(rng.uniform(0, 10), 1), "gout": rng.choice([0.5, 1.0]),
                     "gin": rng.choice([0.5, 1.0, 1.5]), "notice": rng.choice([0, 6, 12])})
    return [{"p": p, "res": order_cost(p)} for p in sets]


_STRESS_CACHE: dict = {}


def stress_models(calls: list[lc.Call]) -> list[dict]:
    """실제 서비스 시간 8척·선석 3개 압축 시나리오(도착 간격별)의 모델 입력과 해(MILP 최적, 현업 Rule)."""
    key = tuple((c.jid, c.allfast, c.ops_end) for c in calls)
    if key not in _STRESS_CACHE:
        out = []
        for stagger in STAGGERS:
            vs, prm = rm.stress_scenario(calls, lc.Terms(), stagger, hetero=False)
            f, o = bm.fcfs(vs, prm), bm.solve_milp(vs, prm)
            out.append({"stagger": stagger, "inst": inst_of(vs, prm),
                        "milp": {"plan": canonical_plan(vs, prm, o), "cost": o.cost, "nVars": o.n_vars, "nBin": o.n_bin, "nRows": o.n_rows},
                        "fcfs": {"plan": plan_of(f), "cost": f.cost}})
        _STRESS_CACHE[key] = out
    return _STRESS_CACHE[key]


def js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build(csv_path: str | Path = DEFAULT_CSV, out: str | Path | None = OUT) -> str:
    _, calls = lc.analyze(csv_path)
    html = TEMPLATE.read_text(encoding="utf-8")
    for key, val in (("DATA", [voyage(c) for c in calls]), ("GOLDEN", golden(calls)), ("GOLDEN2", golden2()),
                     ("STRESS", stress_models(calls)), ("SC01", SC01_P), ("FLAGTEXT", lc.FLAG_TEXT)):
        marker = f"/*__{key}__*/" + ("{}" if key in ("FLAGTEXT", "SC01") else "[]")
        assert html.count(marker) == 1, marker
        html = html.replace(marker, js(val))
    if out:
        Path(out).write_text(html, encoding="utf-8")
    return html


def core_js(html: str) -> str:
    return html.split("/*CORE-BEGIN*/")[1].split("/*CORE-END*/")[0]


if __name__ == "__main__":
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    out_arg = sys.argv[2] if len(sys.argv) > 2 else OUT
    build(csv_arg, out_arg)
    print("saved:", out_arg)
