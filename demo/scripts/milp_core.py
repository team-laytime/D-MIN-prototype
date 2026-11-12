"""수리계획법 모델 조립·풀이 도구 — 두 타입(주제 설명 문서 기준 milp_brief.py, 멘토링 PPT 기준 milp_berth_plan.py)이 같이 쓴다.

변수·제약을 모아 HiGHS(scipy.optimize.milp)에 넘기고, 솔버가 '최적'이라고 한 값을 그대로 믿지 않도록 두 설정으로 풀어 비교한다.
"""
from __future__ import annotations

import contextlib
import ctypes
import math
import os
import re
import sys
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

INF = math.inf
# 큰 수 M에 주는 여유(분). M을 '딱 필요한 만큼'으로 잡으면 HiGHS가 틀린 해를 최적이라고 돌려준 사례가 무작위 시험에서 나왔다
# (사전처리를 켠 풀이와 끈 풀이의 최적값이 서로 달랐다). 하루치 여유를 주면 두 풀이가 같아진다. Model.solve가 매번 둘을 비교한다.
M_PAD = 1440.0


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
            ctypes.CDLL(None).fflush(None)
        except OSError:
            pass
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        for fd in (*saved, null):
            os.close(fd)


@dataclass
class Res:
    status: int                  # 0 = 최적
    fun: float
    x: object                    # 변수 값(모델 단위 = 분)
    agree: bool = True           # 솔버 설정 두 가지(사전처리 켬·끔)의 최적값이 같았는가


class Model:
    """변수·제약을 모아 HiGHS(scipy.optimize.milp)에 넘긴다.

    모델은 '분' 단위 정수로 적고, 솔버에는 '시간' 단위로 바꿔 넣는다(큰 수 M이 약 14,000 → 약 240).
    솔버가 '최적'이라고 한 값도 틀릴 수 있어서(M_PAD 설명 참고) 사전처리(presolve)를 켠 풀이와 끈 풀이를 둘 다 하고,
    최적값이 다르면 더 좋은 쪽을 쓰되 엇갈린 횟수를 센다(disagreements).
    """

    def __init__(self):
        self.names, self.lb, self.ub, self.integ, self.cost, self.unit = [], [], [], [], [], []
        self.rows = []      # (계수 {변수: a}, 하한, 상한, 이름, 행 스케일)
        self.disagreements = 0

    def var(self, name, lb=0.0, ub=INF, integer=False, cost=0.0, unit=1.0):
        self.names.append(name)
        self.lb.append(lb)
        self.ub.append(ub)
        self.integ.append(1 if integer else 0)
        self.cost.append(cost)
        self.unit.append(unit)          # 60이면 '분으로 적은 시각·시간' 변수 → 솔버에는 시간으로
        return len(self.names) - 1

    def binary(self, name):
        return self.var(name, 0, 1, True)

    def time(self, name, lb=0.0, ub=INF, cost=0.0):
        return self.var(name, lb, ub, False, cost, unit=60.0)

    def add(self, coefs, lo=-INF, hi=INF, name="", scale=None):
        c = {}
        for j, a in coefs:
            c[j] = c.get(j, 0.0) + a
        self.rows.append((c, lo, hi, name, scale))

    def _scaled(self, rows):
        cs = np.array(self.unit, float)
        ri, ci, va = [], [], []
        lo, hi = np.empty(len(rows)), np.empty(len(rows))
        for r, (co, l, h, _, scale) in enumerate(rows):
            rs = scale if scale is not None else (1 / 60.0 if any(cs[j] != 1 for j in co) else 1.0)
            for j, a in co.items():
                ri.append(r), ci.append(j), va.append(a * cs[j] * rs)
            lo[r], hi[r] = l * rs, h * rs
        return coo_matrix((va, (ri, ci)), shape=(len(rows), len(self.names))).tocsr(), lo, hi, cs

    def solve(self, cost=None, extra=(), fix=None, time_limit=120.0, check=True) -> Res:
        A, lo, hi, cs = self._scaled(self.rows + list(extra))
        lb, ub = np.array(self.lb, float), np.array(self.ub, float)
        for j, val in (fix or {}).items():
            lb[j] = ub[j] = val
        c = np.array(self.cost if cost is None else cost, float) * cs
        best = None
        funs = []
        for presolve in ((True, False) if check else (True,)):
            with _quiet():
                r = milp(c=c, constraints=LinearConstraint(A, lo, hi), integrality=np.array(self.integ), bounds=Bounds(lb / cs, ub / cs),
                         options={"time_limit": time_limit, "mip_rel_gap": 0.0, "presolve": presolve, "disp": False})
            if r.x is None:
                continue
            funs.append(float(r.fun))
            if best is None or r.fun < best.fun - 1e-9 or (r.status == 0 and best.status != 0 and r.fun <= best.fun + 1e-9):
                best = r
        if best is None:
            return Res(2, math.nan, None)
        agree = len(funs) < 2 or abs(funs[0] - funs[1]) <= 1e-6 * max(1.0, abs(funs[0]))
        if not agree:
            self.disagreements += 1
        return Res(int(best.status), float(best.fun), best.x * cs, agree)

    def to_lp(self, title="") -> str:
        """CPLEX LP 형식 — HiGHS·CPLEX·Gurobi에 그대로 넣을 수 있는 모델 전문(솔버에 넣는 것과 같은 '시간' 단위)."""
        def safe(raw, prefix):
            out, seen = [], set()
            for j, nm in enumerate(raw):
                t = re.sub(r"_+", "_", re.sub(r"[^0-9A-Za-z_]", "_", nm.replace("#", "B").replace("<", "_lt_"))).strip("_") or f"{prefix}{j}"
                if t[0].isdigit():
                    t = prefix + t
                if t in seen:
                    t = f"{t}_{j}"
                seen.add(t)
                out.append(t)
            return out
        vn = safe(self.names, "v")
        rn = safe([r[3] or f"R{i}" for i, r in enumerate(self.rows)], "r")
        A, lo, hi, cs = self._scaled(self.rows)
        A = A.tocsr()

        def expr(cols, vals):
            parts = [f"{'-' if a < 0 else '+'} {abs(a):.10g} {vn[j]}" for j, a in zip(cols, vals) if a != 0]
            return " ".join(parts) if parts else f"0 {vn[0]}"
        lines = [f"\\ {t}" for t in title.splitlines()]
        obj = [(j, c * cs[j]) for j, c in enumerate(self.cost) if c]
        lines += ["Minimize", " obj: " + expr([j for j, _ in obj], [c for _, c in obj]), "Subject To"]
        for r, label in enumerate(rn):
            cols, vals = A.indices[A.indptr[r]:A.indptr[r + 1]], A.data[A.indptr[r]:A.indptr[r + 1]]
            if lo[r] == hi[r]:
                lines.append(f" {label}: {expr(cols, vals)} = {lo[r]:.10g}")
            elif lo[r] > -INF and hi[r] < INF:
                lines.append(f" {label}: {lo[r]:.10g} <= {expr(cols, vals)} <= {hi[r]:.10g}")
            elif lo[r] > -INF:
                lines.append(f" {label}: {expr(cols, vals)} >= {lo[r]:.10g}")
            else:
                lines.append(f" {label}: {expr(cols, vals)} <= {hi[r]:.10g}")
        lines.append("Bounds")
        binaries = []
        for j, (lb, ub, integ) in enumerate(zip(self.lb, self.ub, self.integ)):
            if integ:
                binaries.append(vn[j])
            elif ub == INF:
                lines.append(f" {vn[j]} >= {lb / cs[j]:.10g}")
            else:
                lines.append(f" {lb / cs[j]:.10g} <= {vn[j]} <= {ub / cs[j]:.10g}")
        lines += ["Binaries", " " + " ".join(binaries), "End", ""]
        return "\n".join(lines)
