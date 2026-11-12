"""일정 한 안(기준안 또는 후보)을 만들고 평가한다.

- 계획(plan) = [(선박, 부두), …] 우선순위 목록. 앞에서부터 하나씩 그 부두의 '다음 순서'로 붙인다.
- 기준안(FCFS, OPT-01, FR-34) = ETA 순서대로, 접안 가능시각이 가장 이른 부두에 붙인 계획.
- 평가 = 선박별 계산서(laytime.compute) + 합계(FR-30) + 독립 제약 검증(validator).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.model import Infeasible
from .etb import SchedState, immovable_placement, place
from .laytime import compute


@dataclass
class Schedule:
    label: str
    plan: list                    # [(vid, berth)] 이동 가능 선박의 우선순위
    state: SchedState
    calcs: dict                   # vid → 계산서
    total_cents: int
    infeasible: list = field(default_factory=list)
    violations: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return not self.infeasible

    def signature(self) -> tuple:
        """후보 구별용: 부두별 이동 가능 선박의 순서. 1척이라도 배정이 다르면 다른 후보(FR-35)."""
        per = {}
        for vid, p in sorted(self.state.pl.items(), key=lambda kv: (kv[1].etb, kv[0])):
            if p.kind == "MOVABLE":
                per.setdefault(p.berth, []).append(vid)
        return tuple(sorted((b, tuple(vs)) for b, vs in per.items()))

    def assignment(self) -> dict:
        return {vid: p.berth for vid, p in self.state.pl.items() if p.kind == "MOVABLE"}


def initial_state(ctx) -> SchedState:
    st = SchedState(ctx)
    for vid in sorted(ctx.immovable, key=lambda x: (ctx.vessels[x].fixed_etb, x)):
        st.add(immovable_placement(ctx, ctx.vessels[vid]))
    return st


def decode(ctx, plan, label: str = "", base: SchedState = None):
    """계획을 순서대로 붙인다. (상태, 불가 목록)."""
    st = (base or initial_state(ctx)).copy()
    bad = []
    for vid, bid in plan:
        p = place(ctx, vid, bid, st)
        if isinstance(p, Infeasible):
            bad.append(p)
            continue
        st.add(p)
    return st, bad


def evaluate(ctx, st: SchedState, plan, label: str, infeasible=None, meta=None) -> Schedule:
    calcs = {}
    for vid, p in st.pl.items():
        calcs[vid] = compute(ctx, ctx.vessels[vid], p)
    total = sum(c["amount_cents"] for c in calcs.values())
    return Schedule(label=label, plan=list(plan), state=st, calcs=calcs, total_cents=total,
                    infeasible=list(infeasible or []), meta=dict(meta or {}))


def fcfs(ctx) -> Schedule:
    """기준안: ETA 순서, 가장 이른 접안 가능시각의 부두(동률이면 부두 표 순서)."""
    st = initial_state(ctx)
    plan, bad = [], []
    for vid in sorted(ctx.movable, key=lambda x: (ctx.vessels[x].eta, x)):
        best = None
        last_bad = None
        for bid in ctx.eligible[vid]:
            p = place(ctx, vid, bid, st)
            if isinstance(p, Infeasible):
                last_bad = p
                continue
            if best is None or p.etb < best.etb:
                best = p
        if best is None:
            bad.append(last_bad or Infeasible(vid, "-", "배정 가능 부두 없음", "ELG-01", "배정 가능한 부두가 없음"))
            continue
        st.add(best)
        plan.append((vid, best.berth))
    return evaluate(ctx, st, plan, "기준안(FCFS)", bad, {"rule_id": "OPT-01", "note": "비교용 기준안(현행 실적 아님)"})


def replay(ctx, plan, label: str) -> Schedule:
    st, bad = decode(ctx, plan)
    return evaluate(ctx, st, plan, label, bad)
