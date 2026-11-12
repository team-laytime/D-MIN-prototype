#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수리계획법 최종본의 검산 예제.

원유 수입선 하역 일정 최적화 — 작업계획 선택 MILP (식 (1)~(8))와 작업계획 생성 규칙 (식 (9)~(20)).
예제 숫자는 설명용 가상 값이다. 체선료는 계약상 사용시간 종료인 호스분리 시각으로 계산한다.

  python3 docs/milp/milp_final_example.py          # 결과를 글로 출력
  python3 docs/milp/milp_final_example.py --json   # 보드 생성기가 읽는 JSON

하는 일
  1. 입력 → 작업계획(방문 일정 s·a·c·h·u) 생성            식 (9)~(16)
  2. 재고 평가 시점 τ, 구간별 하역량 q, 소비량 D            식 (17)
  3. 충돌 쌍 F                                           식 (18)
  4. 체선료 C                                            식 (20)
  5. 조합 전수 조사 + HiGHS로 식 (1)~(8) 풀기, 다음 후보안은 조합 제외 식을 더해 다시 푼다
"""
from __future__ import annotations

import itertools
import json
import sys

# ─────────────────────────── 입력 (예제용 가상 값) ───────────────────────────
T_END = 36.0                      # 계획기간 [0, 36] 시간
R0, R_MIN, R_MAX = 10.0, 7.0, 18.0  # 재고: 만 배럴
D_RATE = 0.5                      # 공정 소비속도: 만 배럴/시간 (계획기간 내내 일정)
BERTHS = {"BUOY3": dict(direction=2.0, switching=2.0), "BUOY2": dict(direction=2.0, switching=2.0)}
D_SETUP, D_HOSE, D_DEPART = 1.0, 0.5, 2.0   # 접안→하역 시작, 하역 완료→호스분리, 하역 완료→이안 (시간)

ARRIVALS = {
    # 입항 건: ETA(시간), 남은 물량 Q(만 배럴), 하역속도 v[부두], 일 체선료 r(USD/일), 정박개시 ℓ(시간), Laytime A(시간), 공제 e(시간)
    "A": dict(eta=0.0, Q=12.0, v={"BUOY3": 1.0, "BUOY2": 0.8}, rate_day=48000.0, laytime_start=2.0, laytime=14.0, deduction=0.0),
    "B": dict(eta=6.0, Q=8.0, v={"BUOY3": 1.0, "BUOY2": 0.8}, rate_day=36000.0, laytime_start=8.0, laytime=10.0, deduction=0.0),
}
# 예제의 작업계획: (이름, 입항 건, 부두, 접안 s를 정하는 방식)
#   earliest      = ETA + Direction                                   식 (11)을 등호로
#   after:<계획>  = 그 계획의 이안 u + Switching (같은 부두에서 뒤따름)   식 (18)을 등호로
PLAN_SPECS = [
    ("A1", "A", "BUOY3", "earliest"),
    ("A2", "A", "BUOY2", "earliest"),
    ("A3", "A", "BUOY3", "after:B1"),
    ("B1", "B", "BUOY3", "earliest"),
    ("B2", "B", "BUOY2", "earliest"),
    ("B3", "B", "BUOY3", "after:A1"),
]


def build_plans():
    plans = {}
    pending = list(PLAN_SPECS)
    while pending:
        progressed = False
        for spec in list(pending):
            name, arr, berth, how = spec
            a = ARRIVALS[arr]
            earliest = a["eta"] + BERTHS[berth]["direction"]            # (11)
            if how == "earliest":
                s = earliest
            else:
                ref = how.split(":")[1]
                if ref not in plans:
                    continue
                s = max(earliest, plans[ref]["u"] + BERTHS[berth]["switching"])  # (18)
            st = s + D_SETUP                                            # (12)
            c = st + a["Q"] / a["v"][berth]                             # (13)
            h = c + D_HOSE                                              # (14)
            u = c + D_DEPART                                            # (15)
            over = max(0.0, h - a["laytime_start"] - a["laytime"] - a["deduction"])
            cost = a["rate_day"] / 24.0 * over                           # (20)
            plans[name] = dict(name=name, arrival=arr, berth=berth, how=how, s=s, a=st, c=c, h=h, u=u,
                               rate=a["v"][berth], Q=a["Q"], laytime_end=a["laytime_start"] + a["laytime"],
                               over=over, cost=cost, within=u <= T_END + 1e-9)
            pending.remove(spec)
            progressed = True
        if not progressed:
            raise RuntimeError("작업계획 참조가 서로 물려 있다: %s" % pending)
    return {n: plans[n] for n, *_ in PLAN_SPECS}


# 유형 2 설명용 작업계획 A4: BUOY3에서 7만 배럴 → 이동 → BUOY2에서 5만 배럴. 예제의 Ω에는 넣지 않는다.
TYPE2_DEMO = dict(name="A4", arrival="A", move=3.0, visits=[("BUOY3", 7.0), ("BUOY2", 5.0)])   # move = τ_move (가상 값)


def type2_demo():
    d = TYPE2_DEMO
    a = ARRIVALS[d["arrival"]]
    visits, prev_u = [], None
    for m, (berth, qty) in enumerate(d["visits"], 1):
        s = a["eta"] + BERTHS[berth]["direction"] if m == 1 else prev_u + d["move"]   # (11) (16)
        st = s + D_SETUP                                                # (12)
        c = st + qty / a["v"][berth]                                    # (13)
        h = c + D_HOSE                                                  # (14)
        u = c + D_DEPART                                                # (15)
        visits.append(dict(m=m, berth=berth, Q=qty, s=s, a=st, c=c, h=h, u=u, rate=a["v"][berth]))
        prev_u = u
    H = visits[-1]["h"]                                                 # 마지막 방문의 호스분리
    over = max(0.0, H - a["laytime_start"] - a["laytime"] - a["deduction"])
    return dict(name=d["name"], arrival=d["arrival"], move=d["move"], visits=visits, Q=sum(v["Q"] for v in visits),
                H=H, laytime_end=a["laytime_start"] + a["laytime"], over=over, cost=a["rate_day"] / 24.0 * over)


def conflicts(plans):
    F = []
    for p, q in itertools.combinations(plans.values(), 2):
        if p["arrival"] == q["arrival"] or p["berth"] != q["berth"]:
            continue
        sw = BERTHS[p["berth"]]["switching"]
        ok = q["s"] >= p["u"] + sw - 1e-9 or p["s"] >= q["u"] + sw - 1e-9   # (18)
        if not ok:
            lo, hi = max(p["s"], q["s"]), min(p["u"], q["u"])
            F.append(dict(pair=(p["name"], q["name"]), berth=p["berth"], overlap=(lo, hi)))
    return F


def grid(plans):
    pts = {0.0, T_END}
    for p in plans.values():
        pts.update((p["a"], p["c"]))
    return sorted(pts)


def inflow(plan, tau):
    out = []
    for t in range(len(tau) - 1):
        lo, hi = max(tau[t], plan["a"]), min(tau[t + 1], plan["c"])
        out.append(plan["rate"] * max(0.0, hi - lo))                     # (17)
    return out


def stock(sel, plans, tau):
    R = [R0]
    q = {n: inflow(plans[n], tau) for n in sel}
    for t in range(len(tau) - 1):
        R.append(R[-1] + sum(q[n][t] for n in sel) - D_RATE * (tau[t + 1] - tau[t]))   # (4)
    return R


def enumerate_all(plans, F, tau):
    by_arr = {}
    for p in plans.values():
        by_arr.setdefault(p["arrival"], []).append(p["name"])
    fset = {frozenset(f["pair"]) for f in F}
    rows = []
    for combo in itertools.product(*by_arr.values()):
        cost = sum(plans[n]["cost"] for n in combo)
        hit = [tuple(sorted(pr)) for pr in itertools.combinations(combo, 2) if frozenset(pr) in fset]
        R = stock(combo, plans, tau)
        lo = min(range(len(R)), key=lambda i: R[i])
        hi = max(range(len(R)), key=lambda i: R[i])
        why = []
        if hit:
            why.append("conflict")
        if R[hi] > R_MAX + 1e-9:
            why.append("over")
        if R[lo] < R_MIN - 1e-9:
            why.append("under")
        first_bad = next((i for i, r in enumerate(R) if r > R_MAX + 1e-9 or r < R_MIN - 1e-9), None)
        rows.append(dict(combo=combo, cost=cost, conflict=hit, R=R, min=(tau[lo], R[lo]), max=(tau[hi], R[hi]),
                         first_bad=None if first_bad is None else (tau[first_bad], R[first_bad]),
                         why=why, feasible=not why))
    rows.sort(key=lambda r: (r["cost"], r["combo"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def solve_milp(plans, F, tau, banned=(), fixed=()):
    """식 (1)~(8)을 HiGHS로 푼다.

    banned: 이미 낸 스케줄 후보안(작업계획 이름 묶음)들 — 조합 제외 식으로 막는다.
    fixed:  FIX로 지정된 작업계획 이름들 — 식 (8) z = 1.
    """
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp

    names = list(plans)
    nz, H = len(names), len(tau) - 1
    n = nz + H + 1
    col = {nm: i for i, nm in enumerate(names)}
    c = np.zeros(n)
    for nm in names:
        c[col[nm]] = plans[nm]["cost"]                                   # (1)
    A, lo, hi = [], [], []
    for arr in sorted({p["arrival"] for p in plans.values()}):            # (2)
        row = np.zeros(n)
        for nm in names:
            if plans[nm]["arrival"] == arr:
                row[col[nm]] = 1
        A.append(row); lo.append(1); hi.append(1)
    for f in F:                                                          # (3)
        row = np.zeros(n)
        row[col[f["pair"][0]]] = 1; row[col[f["pair"][1]]] = 1
        A.append(row); lo.append(-np.inf); hi.append(1)
    q = {nm: inflow(plans[nm], tau) for nm in names}
    for t in range(H):                                                   # (4)  R[t+1] − R[t] − Σ q z = −D[t]
        row = np.zeros(n)
        row[nz + t + 1] = 1; row[nz + t] = -1
        for nm in names:
            row[col[nm]] = -q[nm][t]
        d = D_RATE * (tau[t + 1] - tau[t])
        A.append(row); lo.append(-d); hi.append(-d)
    row = np.zeros(n); row[nz] = 1                                        # (5)
    A.append(row); lo.append(R0); hi.append(R0)
    for nm in fixed:                                                     # (8)
        row = np.zeros(n); row[col[nm]] = 1
        A.append(row); lo.append(1); hi.append(1)
    for b in banned:                                                     # 조합 제외 식
        row = np.zeros(n)
        for nm in b:
            row[col[nm]] = 1
        A.append(row); lo.append(-np.inf); hi.append(len(b) - 1)
    lb = np.concatenate([np.zeros(nz), np.full(H + 1, R_MIN)])           # (6) (7)
    ub = np.concatenate([np.ones(nz), np.full(H + 1, R_MAX)])
    integrality = np.concatenate([np.ones(nz), np.zeros(H + 1)])
    res = milp(c, constraints=LinearConstraint(np.array(A), lo, hi), integrality=integrality, bounds=Bounds(lb, ub))
    if res.status != 0 or res.x is None:
        return dict(status="infeasible", message=res.message)
    z = {nm: int(round(res.x[col[nm]])) for nm in names}
    return dict(status="optimal", objective=float(res.fun), z=z, chosen=tuple(nm for nm in names if z[nm] == 1),
                R=[float(v) for v in res.x[nz:]])


def run():
    plans = build_plans()
    F = conflicts(plans)
    tau = grid(plans)
    q = {n: inflow(p, tau) for n, p in plans.items()}
    D = [D_RATE * (tau[t + 1] - tau[t]) for t in range(len(tau) - 1)]
    rows = enumerate_all(plans, F, tau)
    out = dict(T_END=T_END, R0=R0, R_MIN=R_MIN, R_MAX=R_MAX, D_RATE=D_RATE, berths=BERTHS, arrivals=ARRIVALS,
               deltas=dict(setup=D_SETUP, hose=D_HOSE, depart=D_DEPART),
               plans=plans, F=F, tau=tau, q=q, D=D, combos=rows)
    sols, banned = [], []
    try:
        for _ in range(3):
            r = solve_milp(plans, F, tau, banned)
            sols.append(r)
            if r["status"] != "optimal":
                break
            banned.append(r["chosen"])
        out["solver"] = "HiGHS (scipy.optimize.milp)"
    except ImportError:
        out["solver"] = None
    out["solutions"] = sols
    # 식 (8) 시연: B를 B1으로 고정하면 가능한 조합이 없다
    try:
        out["fix_demo"] = dict(fixed=("B1",), result=solve_milp(plans, F, tau, fixed=("B1",)))
    except ImportError:
        out["fix_demo"] = None
    out["type2"] = type2_demo()
    # 호스분리 대신 하역 완료로 계산했던 이전 판 금액 (비교용)
    out["old_cost"] = {n: ARRIVALS[p["arrival"]]["rate_day"] / 24.0 * max(0.0, p["c"] - p["laytime_end"]) for n, p in plans.items()}
    return out


def main():
    out = run()
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    P = out["plans"]
    print("작업계획 (시간: 계획 시작 0h 기준)")
    for n, p in P.items():
        print(f"  {n} {p['berth']:6s} 접안 {p['s']:5.1f} · 하역 {p['a']:5.1f}→{p['c']:5.1f} · 호스분리 {p['h']:5.1f} · 이안 {p['u']:5.1f}"
              f" | 정박종료 {p['laytime_end']:4.1f} · 초과 {p['over']:4.1f}h · 체선료 ${p['cost']:,.0f} (이전 판 ${out['old_cost'][n]:,.0f})")
    print("충돌 쌍 F:", [(f["pair"], f["berth"], f["overlap"]) for f in out["F"]])
    print("재고 평가 시점 τ:", out["tau"])
    print("조합 전수 조사")
    for r in out["combos"]:
        tag = "통과" if r["feasible"] else "탈락(" + ",".join(r["why"]) + ")"
        print(f"  {r['rank']} {'+'.join(r['combo'])}  ${r['cost']:>9,.0f}  {tag}  최소 {r['min'][1]:.1f}@{r['min'][0]:g}h  최대 {r['max'][1]:.1f}@{r['max'][0]:g}h")
    print("솔버:", out["solver"])
    for i, s in enumerate(out["solutions"], 1):
        if s["status"] == "optimal":
            print(f"  {i}안  {'+'.join(s['chosen'])}  ${s['objective']:,.0f}  R = {[round(v, 2) for v in s['R']]}")
        else:
            print(f"  {i}안  없음 ({s['status']})")
    if out.get("fix_demo"):
        fd = out["fix_demo"]
        print(f"FIX 시연 (z[{'+'.join(fd['fixed'])}] = 1):", fd["result"]["status"])
    t2 = out["type2"]
    print(f"유형 2 설명용 {t2['name']}: " + " → ".join(
        f"{v['berth']} 접안 {v['s']:g} · 하역 {v['a']:g}~{v['c']:g} · 호스분리 {v['h']:g} · 이안 {v['u']:g}" for v in t2["visits"])
        + f" | 사용시간 종료 {t2['H']:g} · 초과 {t2['over']:g}h · 체선료 ${t2['cost']:,.0f}")
    best = [r for r in out["combos"] if r["feasible"]]
    ok = bool(best) and out["solutions"] and out["solutions"][0]["status"] == "optimal" and \
        abs(out["solutions"][0]["objective"] - best[0]["cost"]) < 1e-6 and set(out["solutions"][0]["chosen"]) == set(best[0]["combo"])
    print("전수 조사와 솔버의 답이 같은가:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
