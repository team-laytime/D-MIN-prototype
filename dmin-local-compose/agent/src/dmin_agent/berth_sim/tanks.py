"""탱크 재고 제약: 탱크 묶음별 용량 · 공정 처리 · 생산 · 선박 하역/선적으로 재고를 계산하고 안전 범위를 지킨다.

설정 (현업 지시)
  탱크 1개 = 60만 배럴. 원유 17개, 나머지 13개는 반입·반출 묶음에 물동량 비례로 배치
  반입 탱크: 공정 처리량만큼 시간당 일정하게 감소     반출 탱크: 제품 생산량만큼 시간당 일정하게 증가
  안전 범위: 용량의 20% 이상 80% 미만 (항상)

구현 가정
  - 단위는 톤 (QTY와 같은 단위). 60만 배럴 ÷ 7.33배럴/톤(원유 기준) ≈ 81,855톤. 모든 탱크에 같은 환산을 쓴다.
  - 탱크 묶음 = product_direction.tank_group (원유 / 반입 원료 / 양방향 / 분류별 반출). 묶음 안 탱크는 합쳐서 본다.
  - 공정 처리량 · 생산량 = 기간 중 선박 반입량 − 반출량을 기간 시간으로 나눈 값.
    → 기간 끝 재고가 시작 재고와 같아진다 (일주일 동안 재고가 한쪽으로 쏠리지 않음). 양방향 묶음은 순 흐름.
  - 시작 재고 = 용량의 50% (안전 범위 한가운데).
  - 선박 하역·선적은 작업시작(ETB+1h)부터 작업완료(ETU−2h)까지 일정한 속도로 이루어진다.
    기상 하역작업 중단 구간에는 탱크 ↔ 선박 흐름이 없다 (그동안 공정 처리·생산은 계속).
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from .after_etb.s2_work_finish import pumped
from .models import Vessel
from .product_direction import IN, tank_group, vessel_direction
from .synth import SynthData

TANK_BBL = 600_000  # 탱크 1개 용량 (배럴)
BBL_PER_TON = 7.33  # 원유 기준 환산
TANK_TON = round(TANK_BBL / BBL_PER_TON)
CRUDE_TANKS = 17
OTHER_TANKS = 13
SAFE_MIN = 0.20  # 이상
SAFE_MAX = 0.80  # 미만
INITIAL_FILL = 0.50


@dataclass(frozen=True)
class VesselFlow:
    vessel_id: str
    tank: str
    sign: int  # +1 반입(재고 증가) / −1 반출(재고 감소)
    qty: int  # 톤


@dataclass(frozen=True)
class Tank:
    name: str
    n_tanks: int
    capacity: int
    initial: int
    rate_per_h: float  # + 생산(증가) / − 공정 처리(감소)
    inflow: int  # 기간 중 선박 반입 합
    outflow: int  # 기간 중 선박 반출 합

    @property
    def lo(self) -> int:
        return math.ceil(SAFE_MIN * self.capacity)

    @property
    def hi(self) -> int:  # 80% 미만 → 정수로 80% 직전까지
        return math.ceil(SAFE_MAX * self.capacity) - 1

    @property
    def kind(self) -> str:
        return "공정 처리 (감소)" if self.rate_per_h < 0 else "제품 생산 (증가)"


@dataclass(frozen=True)
class TankSet:
    tanks: dict[str, Tank]
    flows: dict[str, VesselFlow]
    start: datetime
    hours: int  # 기간 (시간)


def vessel_flows(sequences: dict[str, list[Vessel]], data: SynthData) -> dict[str, VesselFlow]:
    out = {}
    for seq in sequences.values():
        for v in seq:
            p = data.profiles[v.vessel_id]
            sign = 1 if vessel_direction(v.biz) == IN else -1
            out[v.vessel_id] = VesselFlow(v.vessel_id, tank_group(p.cargo_group, p.product_class), sign, round(p.qty))
    return out


def allocate(volumes: dict[str, int], n: int) -> dict[str, int]:
    """n개 탱크를 물동량 비례로 (최소 1개, 큰 나머지 순)."""
    names = [k for k, v in volumes.items() if v > 0]
    if len(names) > n:
        raise ValueError(f"탱크 {n}개로 묶음 {len(names)}개를 채울 수 없음")
    total = sum(volumes[k] for k in names)
    base = {k: 1 for k in names}
    left = n - len(names)
    share = {k: left * volumes[k] / total for k in names}
    for k in names:
        base[k] += int(share[k])
    rest = n - sum(base.values())
    for k in sorted(names, key=lambda k: -(share[k] - int(share[k])))[:rest]:
        base[k] += 1
    return base


def build_tanks(sequences: dict[str, list[Vessel]], data: SynthData, start: datetime, hours: int,
                initial_fill: float = INITIAL_FILL) -> TankSet:
    flows = vessel_flows(sequences, data)
    inflow: dict[str, int] = {}
    outflow: dict[str, int] = {}
    for f in flows.values():
        (inflow if f.sign > 0 else outflow)[f.tank] = (inflow if f.sign > 0 else outflow).get(f.tank, 0) + f.qty
    names = sorted(set(inflow) | set(outflow))
    others = {k: inflow.get(k, 0) + outflow.get(k, 0) for k in names if k != "원유"}
    counts = allocate(others, OTHER_TANKS)
    if "원유" in names:
        counts["원유"] = CRUDE_TANKS
    tanks = {}
    for k in names:
        cap = counts[k] * TANK_TON
        tanks[k] = Tank(k, counts[k], cap, round(initial_fill * cap),
                        (outflow.get(k, 0) - inflow.get(k, 0)) / hours, inflow.get(k, 0), outflow.get(k, 0))
    return TankSet(tanks, flows, start, hours)


@dataclass(frozen=True)
class TankTrace:
    name: str
    times: list[datetime]
    levels: list[float]
    violations: list[str]  # 범위를 벗어난 구간 설명


def simulate(ts: TankSet, work: dict[str, tuple], step: timedelta = timedelta(minutes=30),
             until: datetime | None = None) -> dict[str, TankTrace]:
    """계획의 시간대별 재고. work = 선박 → (작업시작, 작업완료[, 기상 중단 구간들]).
    하역·선적은 작업한 시간에 비례 (중단 구간에는 흐름 없음)."""
    end = until or ts.start + timedelta(hours=ts.hours)
    times = []
    t = ts.start
    while t <= end:
        times.append(t)
        t += step
    out = {}
    for name, tank in ts.tanks.items():
        moves = []
        for f in ts.flows.values():
            if f.tank == name and f.vessel_id in work:
                ws, wf, *rest = work[f.vessel_id]
                stops = rest[0] if rest else ()
                moves.append((ws, wf, stops, pumped(ws, wf, stops), f.sign * f.qty))
        levels = []
        for t in times:
            lvl = tank.initial + tank.rate_per_h * (t - ts.start).total_seconds() / 3600
            for ws, wf, stops, total, q in moves:
                if t >= wf:
                    lvl += q
                elif t > ws and total > timedelta():
                    lvl += q * (pumped(ws, t, stops) / total)
            levels.append(lvl)
        bad, run = [], None
        for t, lvl in zip(times, levels):
            out_of = lvl < tank.lo or lvl > tank.hi
            if out_of and run is None:
                run = [t, t, lvl]
            elif out_of:
                run[1] = t
                run[2] = min(run[2], lvl) if lvl < tank.lo else max(run[2], lvl)
            elif run is not None:
                bad.append(_describe(tank, run))
                run = None
        if run is not None:
            bad.append(_describe(tank, run))
        out[name] = TankTrace(name, times, levels, bad)
    return out


def _describe(tank: Tank, run) -> str:
    side = f"하한 {tank.lo:,}t 미만" if run[2] < tank.lo else f"상한 {tank.hi:,}t 초과"
    return f"{tank.name}: {run[0]:%m/%d %H:%M}~{run[1]:%m/%d %H:%M} {side} (최저/최고 {run[2]:,.0f}t)"


def work_from_outcomes(outcomes: Iterable, data: SynthData | None = None) -> dict[str, tuple]:
    """규칙 엔진 결과(ScenarioResult.outcomes) → 선박별 (작업시작, 작업완료, 기상 중단 구간)."""
    return {o.vessel.vessel_id: (o.after.work_start, o.after.work_finish, data.stops(o.vessel.berth) if data else ())
            for o in outcomes if o.after}
