"""수리계획법 실험.

  1. SC-01 (손계산 정답): 순서 A 52,000 · 순서 B 6,000 → MILP가 같은 값을 내고 B를 고른다
  2. 실제 23개 항차의 체선 분해: 실제 접안 시각 vs NOR 직후 바로 접안했을 때(MILP의 하한)
  3. 압축 시나리오 [가정·합성]: 실제 서비스 시간 8척을 3개 선석에 몰아 넣고 현업 Rule vs MILP vs 완전 탐색

실행:  python3 -I journeys/run_milp.py journeys/data/vessel_journeys.csv --json journeys/out/milp_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import berth_milp as bm  # noqa: E402
import laytime_csv as lc  # noqa: E402

SC01_VESSELS = (bm.Vessel("X", nor=2, p=16, L=24, rate=48000, berths=("SK7",)),
                bm.Vessel("Y", nor=4, p=10, L=12, rate=96000, berths=("SK7",)))
SC01_PARAMS = bm.Params(berth_free={"SK7": 6.0})

# 관측된 (화물군 → 하역한 선석)에서 만든 적합 선석 — 윤활기유: SK #3·#5-4, PX: SK #3·#5-5
LUBE = ("SK #3", "SK #5-4")
PX = ("SK #3", "SK #5-5")
STRESS_ORDER = [("J001", LUBE), ("J010", PX), ("J004", LUBE), ("J007", LUBE), ("J014", PX), ("J013", LUBE),
                ("J019", LUBE), ("J023", LUBE)]


def rows_of(sol: bm.Solution) -> list[dict]:
    return [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in sol.rows]


def sc01() -> dict:
    x, y = SC01_VESSELS
    a = bm.solve_milp(list(SC01_VESSELS), SC01_PARAMS, force_before=[("X", "Y")])
    b = bm.solve_milp(list(SC01_VESSELS), SC01_PARAMS, force_before=[("Y", "X")])
    best = bm.solve_milp(list(SC01_VESSELS), SC01_PARAMS)
    return {"A": {"cost": a.cost, "rows": rows_of(a)}, "B": {"cost": b.cost, "rows": rows_of(b)},
            "best": {"cost": best.cost, "order": best.order, "rows": rows_of(best),
                     "n_vars": best.n_vars, "n_bin": best.n_bin, "n_rows": best.n_rows},
            "hand": {"A": 52000, "B": 6000}}


def real_decomposition(calls: list[lc.Call], terms: lc.Terms) -> dict:
    rows = []
    for c in calls:
        origin = c.nor_t.replace(hour=0, minute=0)
        v = bm.vessel_from_call(c, terms, origin)
        s = (c.allfast - origin).total_seconds() / 3600
        early = v.nor + v.sigma                       # NOR 직후 이동만 하고 바로 접안했다면
        rows.append({"jid": c.jid, "vessel": c.vessel, "berth": c.berth, "wait_h": round(s - early, 2),
                     "actual_h": bm.demurrage_hours(v, s), "floor_h": bm.demurrage_hours(v, early),
                     "actual_usd": bm.cost_usd(v, s), "floor_usd": bm.cost_usd(v, early)})
    actual = sum(r["actual_usd"] for r in rows)
    floor = sum(r["floor_usd"] for r in rows)

    def occ_end(c):
        return c.depart if (c.depart and c.depart >= c.ops_end) else c.ops_end
    blocked = [c.jid for c in calls if any(
        o.jid != c.jid and o.berth == c.berth and o.allfast < c.allfast and occ_end(o) > c.nor_t for o in calls)]
    return {"rows": rows, "actual_usd": actual, "floor_usd": floor, "avoidable_usd": actual - floor,
            "blocked_by_csv_vessels": blocked}


def stress_scenario(calls: list[lc.Call], terms: lc.Terms, stagger: float = 1.0, hetero: bool = False,
                    free_at: float = 6.0) -> tuple[list[bm.Vessel], bm.Params]:
    by = {c.jid: c for c in calls}
    vs = []
    for i, (jid, berths) in enumerate(STRESS_ORDER):
        big = berths is PX
        L, rate = (36.0, 78_000.0) if (hetero and big) else (terms.laytime_hours, terms.rate_usd_day)
        vs.append(bm.vessel_from_call(by[jid], terms, datetime(2025, 1, 1), berths=berths, nor=i * stagger, L=L, rate=rate))
    prm = bm.Params(notice=terms.notice_hours, berth_free={k: free_at for k in ("SK #3", "SK #5-4", "SK #5-5")})
    return vs, prm


def stress(calls, terms, stagger=1.0, hetero=False) -> dict:
    vs, prm = stress_scenario(calls, terms, stagger, hetero)
    f, o, b = bm.fcfs(vs, prm), bm.solve_milp(vs, prm), bm.brute_force(vs, prm)
    return {"stagger_h": stagger, "hetero": hetero, "fcfs": {"cost": f.cost, "order": f.order, "rows": rows_of(f)},
            "milp": {"cost": o.cost, "order": o.order, "rows": rows_of(o), "n_vars": o.n_vars, "n_bin": o.n_bin,
                     "n_rows": o.n_rows, "seconds": round(o.seconds, 2)},
            "brute": {"cost": b.cost, "seconds": round(b.seconds, 2)}, "vessels": [v.__dict__ for v in vs]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--json")
    ap.add_argument("--lp-dir", help="솔버에 그대로 넣을 수 있는 LP 형식 모델 파일을 저장할 폴더")
    ap.add_argument("--laytime", type=float, default=lc.Terms.laytime_hours)
    ap.add_argument("--rate", type=float, default=lc.Terms.rate_usd_day)
    a = ap.parse_args(argv)
    terms = lc.Terms(laytime_hours=a.laytime, rate_usd_day=a.rate)
    _, calls = lc.analyze(a.csv, terms)

    print("== 1. SC-01 (손계산 정답과 대조) ==")
    s1 = sc01()
    print(f"  순서 A(X 먼저) MILP {s1['A']['cost']:>8,.0f}  손계산 {s1['hand']['A']:>8,}")
    print(f"  순서 B(Y 먼저) MILP {s1['B']['cost']:>8,.0f}  손계산 {s1['hand']['B']:>8,}")
    print(f"  최적 순서 {s1['best']['order']}  비용 {s1['best']['cost']:,.0f}   (변수 {s1['best']['n_vars']} · 정수 {s1['best']['n_bin']}"
          f" · 제약 {s1['best']['n_rows']})")

    print("\n== 2. 실제 23개 항차: 체선료 중 선석 대기가 만든 몫 ==")
    dec = real_decomposition(calls, terms)
    print(f"  실제 체선료                               {dec['actual_usd']:>12,.0f} USD")
    print(f"  NOR 직후 바로 접안했다면(MILP 하한)       {dec['floor_usd']:>12,.0f} USD   ← 작업 시간만으로 허용을 넘긴 몫")
    print(f"  접안 지연이 만든 몫(상한)                 {dec['avoidable_usd']:>12,.0f} USD ({dec['avoidable_usd'] / dec['actual_usd']:.1%})")
    print(f"  같은 부두를 쓰던 다른 항차 때문에 기다린 항차: {len(dec['blocked_by_csv_vessels'])}/{len(calls)}건 → 이 데이터만으로는 순서를 바꿔 줄일 체선이 없음")

    print("\n== 3. 압축 시나리오 [가정] — 실제 서비스 시간 8척 · 선석 3개 ==")
    sc = []
    for stagger, hetero in ((1.0, False), (1.5, False), (2.0, False), (1.0, True)):
        r = stress(calls, terms, stagger, hetero)
        sc.append(r)
        tag = "PX 36h/78k" if hetero else "동일 조건"
        print(f"  도착 간격 {stagger:.1f}h · {tag:<10}  현업 Rule {r['fcfs']['cost']:>8,.0f}   MILP {r['milp']['cost']:>8,.0f}"
              f"   완전 탐색 {r['brute']['cost']:>8,.0f}   절감 {r['fcfs']['cost'] - r['milp']['cost']:>6,.0f}"
              f"   (MILP {r['milp']['seconds']}s, 정수변수 {r['milp']['n_bin']})")
    if a.lp_dir:
        d = Path(a.lp_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / "berth_model_sc01.lp").write_text(bm.build_model(list(SC01_VESSELS), SC01_PARAMS).to_lp(
            "SC-01 두 척 · 한 부두 — 접안 순서 MILP (체선료 최소화)\n손계산 정답: 순서 A 52,000 / 순서 B 6,000 USD"), encoding="utf-8")
        vs, prm = stress_scenario(calls, terms, 1.0)
        (d / "berth_model_stress_1h.lp").write_text(bm.build_model(vs, prm).to_lp(
            "실제 서비스 시간 8척 · 선석 3개 · NOR 도착 간격 1시간 [합성 시나리오]\n접안 순서·선석 배정 MILP (체선료 최소화)"), encoding="utf-8")
        print("\nLP 파일:", d / "berth_model_sc01.lp", d / "berth_model_stress_1h.lp")
    if a.json:
        Path(a.json).write_text(json.dumps({"sc01": s1, "real": dec, "stress": sc}, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
