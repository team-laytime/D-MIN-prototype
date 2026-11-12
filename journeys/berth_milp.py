"""접안 순서·선석 배정으로 총 체선료를 줄이는 수리계획법(MILP) 모델.

laytime_csv.py의 계산식을 그대로 목적함수로 쓴다. 비선형인 max(0, ·)·min(·)을 선형 제약으로 풀어 쓴 것이 핵심이다.

집합   i ∈ N 선박, k ∈ K 선석, B_i ⊆ K 선박 i가 들어갈 수 있는 선석
상수   a_i NOR 제출 시각, σ_i 양묘→접안 이동 시간, p_i 접안 완료→호스 분리 시간, L_i 허용 레이타임,
       r_i 체선료율(USD/일), n 통지시간, g_out 호스 분리→선석 비움, g_in 선석 비움→다음 배 접안 완료,
       F_k 선석 k가 비는 시각, c_i = a_i + n
변수   s_i 접안 완료 시각(연속) · d_i 체선 시간(연속) · δ_i 이동 공제(연속)
       x_ik 선석 배정 · o_ij 순서(i가 j보다 먼저) · z_i, y_i 공제 판정용 · (주간 접안만) day_i 정수, w_i 연속

목적   min Σ_i (r_i / 24) · d_i

제약   (C0) x_ik ≤ a_ik       a_ik = 0(선석 k에 들어갈 수 없음)인 쌍은 x_ik 변수를 만들지 않는다 (B_i = {k : a_ik = 1})
       (C1) Σ_k x_ik = 1
       (C2) s_i ≥ a_i + σ_i                                     NOR 이전·이동 중에는 접안 불가
       (C3) s_i ≥ F_k + g_in − M(1 − x_ik)                      앞 선박이 비우기 전에는 접안 불가
       (C4) s_j ≥ s_i + p_i + g_out + g_in − M(1−o_ij) − M(2−x_ik−x_jk)   같은 선석에서 겹치지 않음
            s_i ≥ s_j + p_j + g_out + g_in − M·o_ij       − M(2−x_ik−x_jk)
       (C5) d_i ≥ s_i + p_i − c_i − L_i − δ_i,   d_i ≥ max(0, p_i − L_i)
            ← 체선 D = max(0, U − L), U = max(p_i, 종료 − c_i − δ_i) 를 최소화 방향으로 선형화
              (접안이 NOR+n보다 빠르면 개시가 접안 시각이라 U = p_i, 늦으면 개시가 c_i라 U = s_i + p_i − c_i − δ_i)
       (C6) δ_i ≤ σ_i·z_i,  δ_i ≤ σ_i·y_i,  δ_i ≤ (s_i − c_i) + M(1 − y_i)
            s_i ≥ c_i − M(1 − y_i)              y_i = 1 이면 개시가 c_i (이동이 개시 뒤에 끝남)
            s_i ≤ c_i + L_i + σ_i − ε + M(1 − z_i)   z_i = 1 이면 양묘 시점이 아직 레이타임 안 (once on demurrage)
            ← 공제 δ_i = [양묘 시점에 레이타임 중] × min(σ_i, max(0, s_i − c_i)). 공제는 비용을 줄이는 방향이라 상한만 걸면 된다.
       (C7) 주간 접안 선박: s_i = 24·day_i + w_i,  w_i ∈ [07:00, 17:30]   (시각 0 = 자정)

비교 대상: brute_force() = 선석 배정 × 순서 완전 탐색(독립 구현), fcfs() = 도착 순서·가장 빨리 붙는 선석(현업 Rule 가정).
"""
from __future__ import annotations

import contextlib
import ctypes
import itertools
import math
import os
import re
import sys
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

INF = math.inf
EPS = 1e-4          # (C6)의 '<'를 '≤ − ε'로 쓰는 값(시간) = 0.36초
# LP 파일 머리의 변수 사전 — 화면(explorer.html)의 LP_LEGEND와 같다
LP_LEGEND = (
    "s_선박 접안시각(h) · d_선박 체선시간(h) · delta_선박 이동공제(h)",
    "x_선박_선석 선석배정(0/1) · o_A_B 앞뒤순서(1이면 A가 B보다 먼저) · z, y 이동공제 판정 보조(0/1)",
    "C1 선석 배정 · C3 선석 비움 · C4a/C4b 같은 선석 겹침 금지 · C5a 체선시간 · C6a~e 이동공제",
    "C0 접근 불가(a_ik = 0)인 (선박, 선석) 쌍은 x 변수를 만들지 않는다 = 선석배정 0",
)


@contextlib.contextmanager
def _quiet():
    """HiGHS가 C 쪽에서 직접 찍는 내부 로그를 막는다(파일 디스크립터 수준)."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved, null = [os.dup(1), os.dup(2)], os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null, 1)
        os.dup2(null, 2)
        yield
    finally:
        try:
            ctypes.CDLL(None).fflush(None)      # C 버퍼에 남은 로그가 복구된 터미널로 새지 않게 비운다
        except OSError:
            pass
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        for fd in (*saved, null):
            os.close(fd)


@dataclass(frozen=True)
class Vessel:
    name: str
    nor: float                      # a_i
    p: float                        # p_i
    L: float                        # L_i
    rate: float                     # r_i (USD/일)
    berths: tuple[str, ...]         # B_i
    sigma: float = 0.0              # σ_i
    daytime_only: bool = False


@dataclass(frozen=True)
class Params:
    notice: float = 6.0
    g_out: float = 1.0
    g_in: float = 1.0
    berth_free: dict = field(default_factory=dict)      # F_k
    day_start: float = 7.0
    day_end: float = 17.5


# ----------------------------------------------------------------------------- 계산식 (laytime_csv.compute와 같은 식)

def demurrage_hours(v: Vessel, s: float, prm: Params = Params()) -> float:
    """접안 완료 시각 s에서 선박 v의 체선 시간. 개시 = max(a, min(c, s)), 이동은 레이타임 중일 때만 공제."""
    c = v.nor + prm.notice
    start = max(v.nor, min(c, s))
    ded = 0.0
    if v.sigma > 0:
        aw = s - v.sigma
        if max(0.0, aw - start) < v.L:
            ded = max(0.0, s - max(aw, start))
    return max(0.0, (s + v.p) - start - ded - v.L)


def cost_usd(v: Vessel, s: float, prm: Params = Params()) -> float:
    return v.rate / 24 * demurrage_hours(v, s, prm)


def next_daytime(s: float, prm: Params) -> float:
    tod = s % 24
    if prm.day_start <= tod <= prm.day_end:
        return s
    return s - tod + prm.day_start if tod < prm.day_start else s + (24 - tod) + prm.day_start


def _hours(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 3600


def vessel_from_call(call, terms, origin: datetime, *, berths: tuple[str, ...] | None = None, nor: float | None = None,
                     name: str | None = None, L: float | None = None, rate: float | None = None) -> Vessel:
    """laytime_csv.Call → Vessel. p = 접안 완료→호스 분리, σ = 접안 직전 양묘→접안 이동. nor를 주면 도착 시각만 바꾼다(시나리오용)."""
    p = _hours(call.allfast, call.ops_end + timedelta(minutes=terms.hose_lag_min))
    shift = next(((a, b) for a, b in call.shifts if b == call.allfast), None)
    sigma = _hours(*shift) if shift else 0.0
    return Vessel(name or call.jid, _hours(origin, call.nor_t) if nor is None else nor, p,
                  terms.laytime_hours if L is None else L, terms.rate_usd_day if rate is None else rate,
                  berths or (call.berth,), sigma)


# ----------------------------------------------------------------------------- 결과

@dataclass
class Solution:
    status: str
    cost: float                      # 식으로 다시 계산한 총 체선료
    milp_cost: float | None          # 솔버 목적함수 값 (cost와 같아야 한다)
    rows: list[dict]
    order: dict[str, list[str]]
    n_vars: int = 0
    n_bin: int = 0
    n_rows: int = 0
    seconds: float = 0.0

    def start_of(self, name: str) -> float:
        return next(r["s"] for r in self.rows if r["name"] == name)


# ----------------------------------------------------------------------------- 모델 조립

class _Model:
    def __init__(self):
        self.names, self.lb, self.ub, self.integ, self.c, self.rows = [], [], [], [], [], []

    def var(self, name, lb=0.0, ub=INF, integer=False, cost=0.0) -> int:
        self.names.append(name)
        self.lb.append(lb)
        self.ub.append(ub)
        self.integ.append(1 if integer else 0)
        self.c.append(cost)
        return len(self.names) - 1

    def binary(self, name, fixed=None) -> int:
        lo, hi = (0, 1) if fixed is None else (fixed, fixed)
        return self.var(name, lo, hi, True)

    def add(self, coefs: dict, lo=-INF, hi=INF, name: str | None = None) -> None:
        self.rows.append((coefs, lo, hi, name))

    def to_lp(self, title: str = "") -> str:
        """CPLEX LP 형식 — HiGHS·CPLEX·Gurobi 등 솔버에 그대로 넣을 수 있는 모델 전문. 이름은 LP 규칙에 맞게 바꾼다."""
        def safe_names(raw):
            out, seen = [], set()
            for j, nm in enumerate(raw):
                t = re.sub(r"_+", "_", re.sub(r"[^0-9A-Za-z_]", "_", nm or "")).strip("_") or f"n{j}"
                if t[0].isdigit():
                    t = "n" + t
                if t in seen:
                    t = f"{t}_{j}"
                seen.add(t)
                out.append(t)
            return out
        vn = safe_names(self.names)
        rn = safe_names([r[3] or f"R{i}" for i, r in enumerate(self.rows)])

        def expr(coefs):
            parts = [f"{'-' if c < 0 else '+'} {abs(c):.10g} {vn[j]}" for j, c in coefs.items() if c != 0]
            return " ".join(parts) if parts else f"0 {vn[0]}"
        lines = [f"\\ {t}" for t in [*title.splitlines(), *LP_LEGEND]]
        lines += ["Minimize", " obj: " + expr({j: c for j, c in enumerate(self.c) if c}), "Subject To"]
        for (coefs, lo, hi, _), label in zip(self.rows, rn):
            if lo == hi:
                lines.append(f" {label}: {expr(coefs)} = {lo:.10g}")
            elif lo > -INF and hi < INF:
                lines.append(f" {label}: {lo:.10g} <= {expr(coefs)} <= {hi:.10g}")
            elif lo > -INF:
                lines.append(f" {label}: {expr(coefs)} >= {lo:.10g}")
            else:
                lines.append(f" {label}: {expr(coefs)} <= {hi:.10g}")
        bounds, binaries, generals = [], [], []
        for j, (lb, ub, integ) in enumerate(zip(self.lb, self.ub, self.integ)):
            if integ and lb == 0 and ub == 1:
                binaries.append(vn[j])
            elif lb == ub:
                bounds.append(f" {vn[j]} = {lb:.10g}")
            else:
                if integ:
                    generals.append(vn[j])
                bounds.append(f" {vn[j]} >= {lb:.10g}" if ub == INF else f" {lb:.10g} <= {vn[j]} <= {ub:.10g}")
        lines += ["Bounds"] + bounds
        if generals:
            lines += ["Generals", " " + " ".join(generals)]
        if binaries:
            lines += ["Binaries", " " + " ".join(binaries)]
        return "\n".join(lines + ["End", ""])

    def solve(self, c, extra=(), time_limit=120.0):
        n, rows = len(self.names), list(self.rows) + list(extra)
        A = np.zeros((len(rows), n))
        lo, hi = np.empty(len(rows)), np.empty(len(rows))
        for r, (co, l, h, _nm) in enumerate(rows):
            for j, a in co.items():
                A[r, j] += a
            lo[r], hi[r] = l, h
        with _quiet():
            return milp(c=np.asarray(c, float), constraints=LinearConstraint(A, lo, hi),
                        integrality=np.asarray(self.integ), bounds=Bounds(np.asarray(self.lb), np.asarray(self.ub)),
                        options={"time_limit": time_limit, "mip_rel_gap": 0.0})


@dataclass
class _Built:
    m: _Model
    s: list
    d: list
    dl: list
    z: list
    y: list
    x: dict
    o: dict
    cand: list
    big: float
    smax: float


def _build(vessels: list[Vessel], prm: Params = Params(), force_before=(), fix_start: dict | None = None,
           fix_berth: dict | None = None) -> _Built:
    """변수와 제약 행을 조립한다(풀지 않는다). 행마다 이름이 있어 화면·LP 파일·검증이 같은 모델을 본다."""
    N = len(vessels)
    names = [v.name for v in vessels]
    assert len(set(names)) == N, "선박 이름이 겹침"
    fix_start, fix_berth = fix_start or {}, fix_berth or {}
    cand = [tuple([fix_berth[v.name]] if v.name in fix_berth else v.berths) for v in vessels]
    g = prm.g_out + prm.g_in
    lb_s = [v.nor + v.sigma for v in vessels]
    free = prm.berth_free
    smax = max(max(lb_s), max(free.values(), default=-INF) + prm.g_in,
               max(fix_start.values(), default=-INF) + 1.0) + sum(v.p + g for v in vessels) + 48.0
    big = smax - min(lb_s) + max(v.p for v in vessels) + g + 1.0
    m = _Model()

    s, d, dl, z, y, dayv, wv = [], [], [], [], [], {}, {}
    for i, v in enumerate(vessels):
        lo = hi = fix_start[v.name] if v.name in fix_start else None
        s.append(m.var(f"s[{v.name}]", lb_s[i] if lo is None else lo, smax if hi is None else hi))
        d.append(m.var(f"d[{v.name}]", max(0.0, v.p - v.L), INF, cost=v.rate / 24))
        if v.sigma > 0:
            dl.append(m.var(f"delta[{v.name}]", 0.0, v.sigma))
            z.append(m.binary(f"z[{v.name}]"))
            y.append(m.binary(f"y[{v.name}]"))
        else:
            dl.append(None), z.append(None), y.append(None)
        if v.daytime_only:
            dayv[i] = m.var(f"day[{v.name}]", 0, math.ceil(smax / 24) + 1, integer=True)
            wv[i] = m.var(f"w[{v.name}]", prm.day_start, prm.day_end)
            m.add({s[i]: 1, dayv[i]: -24, wv[i]: -1}, 0, 0, f"C7[{v.name}]")

    x = {}
    for i, v in enumerate(vessels):
        for k in cand[i]:
            x[i, k] = m.binary(f"x[{v.name},{k}]", fixed=1 if len(cand[i]) == 1 else None)
        m.add({x[i, k]: 1 for k in cand[i]}, 1, 1, f"C1[{v.name}]")                  # (C1)
        for k in cand[i]:                                                            # (C3)
            if k in free:
                m.add({s[i]: 1, x[i, k]: -big}, free[k] + prm.g_in - big, name=f"C3[{v.name}|{k}]")

    o = {}
    for i, j in itertools.combinations(range(N), 2):                                 # (C4)
        common = [k for k in cand[i] if k in cand[j]]
        if not common:
            continue
        a, b = vessels[i], vessels[j]
        fixed_pair = len(cand[i]) == 1 and len(cand[j]) == 1
        ov = o[i, j] = m.binary(f"o[{a.name}<{b.name}]")
        for k in common:
            na, nb = f"C4a[{a.name}<{b.name}|{k}]", f"C4b[{a.name}<{b.name}|{k}]"
            if fixed_pair:
                m.add({s[j]: 1, s[i]: -1, ov: -big}, a.p + g - big, name=na)
                m.add({s[i]: 1, s[j]: -1, ov: big}, b.p + g, name=nb)
            else:
                m.add({s[j]: 1, s[i]: -1, ov: -big, x[i, k]: -big, x[j, k]: -big}, a.p + g - 3 * big, name=na)
                m.add({s[i]: 1, s[j]: -1, ov: big, x[i, k]: -big, x[j, k]: -big}, b.p + g - 2 * big, name=nb)
    for first, second in force_before:
        i, j = names.index(first), names.index(second)
        if (i, j) in o:
            m.add({o[i, j]: 1}, 1, 1, f"FORCE[{first}<{second}]")
        elif (j, i) in o:
            m.add({o[j, i]: 1}, 0, 0, f"FORCE[{first}<{second}]")

    for i, v in enumerate(vessels):                                                  # (C5)(C6)
        c_i = v.nor + prm.notice
        if v.sigma > 0:
            m.add({d[i]: 1, s[i]: -1, dl[i]: 1}, v.p - c_i - v.L, name=f"C5a[{v.name}]")
            m.add({dl[i]: 1, z[i]: -v.sigma}, hi=0, name=f"C6a[{v.name}]")
            m.add({dl[i]: 1, y[i]: -v.sigma}, hi=0, name=f"C6b[{v.name}]")
            m.add({dl[i]: 1, s[i]: -1, y[i]: big}, hi=big - c_i, name=f"C6c[{v.name}]")
            m.add({s[i]: 1, y[i]: -big}, lo=c_i - big, name=f"C6d[{v.name}]")
            m.add({s[i]: 1, z[i]: big}, hi=c_i + v.L + v.sigma - EPS + big, name=f"C6e[{v.name}]")
        else:
            m.add({d[i]: 1, s[i]: -1}, v.p - c_i - v.L, name=f"C5a[{v.name}]")
    return _Built(m, s, d, dl, z, y, x, o, cand, big, smax)


def build_model(vessels: list[Vessel], prm: Params = Params(), **kw) -> _Model:
    """풀지 않고 모델만 조립한다 — 행·변수 검사와 LP 파일 내보내기용."""
    return _build(vessels, prm, **kw).m


def solve_milp(vessels: list[Vessel], prm: Params = Params(), *, force_before=(), fix_start: dict | None = None,
               fix_berth: dict | None = None, time_limit: float = 120.0, compact: bool = True) -> Solution:
    """총 체선료 최소 MILP. force_before=[(a, b)]는 같은 선석에서 a가 b보다 먼저(순서 평가용),
    fix_start는 접안 시각 고정(식과 모델의 일치 검사용), fix_berth는 선석 고정."""
    t_begin = _time.perf_counter()
    N = len(vessels)
    b = _build(vessels, prm, force_before, fix_start, fix_berth)
    m, s, d, x, cand = b.m, b.s, b.d, b.x, b.cand

    res = m.solve(m.c, time_limit=time_limit)
    if res.status != 0 or res.x is None:
        return Solution({1: "시간 초과", 2: "해 없음", 3: "무한"}.get(res.status, f"status {res.status}"),
                        math.nan, None, [], {}, len(m.names), sum(m.integ), len(m.rows), _time.perf_counter() - t_begin)
    star = float(res.fun)
    if compact:     # 같은 비용 안에서 접안 시각이 가장 이른 일정
        tol = max(1e-3, 1e-7 * abs(star))
        row = ({d[i]: vessels[i].rate / 24 for i in range(N)}, -INF, star + tol, "COMPACT")
        c2 = np.zeros(len(m.names))
        for i in range(N):
            c2[s[i]] = 1.0
        res2 = m.solve(c2, extra=[row], time_limit=time_limit)
        if res2.status == 0 and res2.x is not None:
            res = res2
    xs = res.x
    rows, order = [], {}
    for i, v in enumerate(vessels):
        k = next(k for k in cand[i] if xs[x[i, k]] > 0.5)
        si = float(xs[s[i]])
        rows.append({"name": v.name, "berth": k, "nor": v.nor, "s": si, "e": si + v.p, "d": demurrage_hours(v, si, prm),
                     "cost": cost_usd(v, si, prm)})
    for r in rows:
        order.setdefault(r["berth"], []).append(r["name"])
    for k in order:
        order[k].sort(key=lambda nm: next(r["s"] for r in rows if r["name"] == nm))
    return Solution("최적", sum(r["cost"] for r in rows), star, rows, order, len(m.names), sum(m.integ), len(m.rows),
                    _time.perf_counter() - t_begin)


# ----------------------------------------------------------------------------- 독립 구현: 완전 탐색·현업 Rule

def _schedule_berth(order, k: str, prm: Params):
    """선석 k에서 정해진 순서로 가장 이르게 붙인 일정. 비용이 접안 시각에 줄어들지 않으므로 이게 그 순서의 최적이다."""
    t_free = prm.berth_free.get(k, -INF) + prm.g_in
    out = []
    for v in order:
        s = max(v.nor + v.sigma, t_free)
        if v.daytime_only:
            s = next_daytime(s, prm)
        out.append((v, s))
        t_free = s + v.p + prm.g_out + prm.g_in
    return out


def evaluate_order(order, k: str, prm: Params = Params()) -> float:
    return sum(cost_usd(v, s, prm) for v, s in _schedule_berth(order, k, prm))


def brute_force(vessels: list[Vessel], prm: Params = Params()) -> Solution:
    t_begin = _time.perf_counter()
    best_cost, best = INF, None
    for assign in itertools.product(*[v.berths for v in vessels]):
        groups: dict[str, list[Vessel]] = {}
        for v, k in zip(vessels, assign):
            groups.setdefault(k, []).append(v)
        total, orders = 0.0, {}
        for k, grp in groups.items():
            bc, bo = INF, None
            for perm in itertools.permutations(grp):
                c = evaluate_order(perm, k, prm)
                if c < bc - 1e-9:
                    bc, bo = c, perm
            total += bc
            orders[k] = bo
            if total >= best_cost - 1e-9:
                break
        else:
            if total < best_cost - 1e-9:
                best_cost, best = total, orders
    rows = []
    for k, perm in best.items():
        for v, s in _schedule_berth(perm, k, prm):
            rows.append({"name": v.name, "berth": k, "nor": v.nor, "s": s, "e": s + v.p, "d": demurrage_hours(v, s, prm),
                         "cost": cost_usd(v, s, prm)})
    return Solution("최적", best_cost, None, rows, {k: [v.name for v in perm] for k, perm in best.items()},
                    seconds=_time.perf_counter() - t_begin)


def fcfs(vessels: list[Vessel], prm: Params = Params()) -> Solution:
    """현업 Rule(가정): NOR 도착 순서대로, 각 선박을 가장 먼저 접안할 수 있는 적합 선석에 붙인다."""
    free = {k: prm.berth_free.get(k, -INF) + prm.g_in for v in vessels for k in v.berths}
    rows, order = [], {}
    for v in sorted(vessels, key=lambda v: (v.nor, v.name)):
        def when(k):
            s = max(v.nor + v.sigma, free[k])
            return next_daytime(s, prm) if v.daytime_only else s
        k = min(v.berths, key=lambda k: (when(k), k))
        s = when(k)
        free[k] = s + v.p + prm.g_out + prm.g_in
        rows.append({"name": v.name, "berth": k, "nor": v.nor, "s": s, "e": s + v.p, "d": demurrage_hours(v, s, prm),
                     "cost": cost_usd(v, s, prm)})
        order.setdefault(k, []).append(v.name)
    return Solution("현업 Rule", sum(r["cost"] for r in rows), None, rows, order)
