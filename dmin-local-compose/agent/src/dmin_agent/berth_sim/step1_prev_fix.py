"""ETB 산정 ① 이전 선박, FIX 선박 접안 일정 충족 (멘토링 장표 07p).

같은 부두의 접안 순서가 주어지면 앞에서부터 차례로 ETB/ETU를 계산한다.

1) 이전 선박이 있는가?
   기준: ETA + Direction <= 바로 직전 선박 ETU + Switching
   - YES: ETB = 이전 선박 ETU + Switching
   - NO : ETB = ETA + Direction
2) 다음 선박이 FIX 선박인가?
   - YES 이고 FIX 선박 ETB <= 현재 선박 ETU + Switching → 접안불가
   - 그 외 → 접안가능

FIX 선박은 ETB 자동 산출 대상이 아니다. 고정 ETB를 그대로 쓰고, 뒤 선박의 '이전 선박'으로만 작용한다.

이후 단계(② 야간 도선 등)는 `EtbAdjuster`로 끼워 넣는다. 조정기는 ①로 구한 후보 ETB를 받아
더 늦은 ETB로 미룰 수 있고, 조정된 ETB로 ETU와 다음 FIX 충돌을 다시 판정한다.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .models import Vessel
from .shifting import direction, switching


class EtbRule(str, Enum):
    DIRECTION = "DIRECTION"  # ETB = ETA + Direction (부두 비어 있음)
    SWITCHING = "SWITCHING"  # ETB = 이전 선박 ETU + Switching
    FIXED = "FIXED"  # FIX 선박: 고정 ETB


@dataclass(frozen=True)
class Step1Result:
    vessel: Vessel
    etb: datetime
    etu: datetime
    rule: EtbRule
    prev_vessel_id: str | None
    berthable: bool
    reason: str
    notes: tuple[str, ...] = ()  # 이후 단계 조정기가 남긴 근거

    @property
    def vessel_id(self) -> str:
        return self.vessel.vessel_id

    @property
    def berth(self) -> str:
        return self.vessel.berth

    @property
    def eta(self) -> datetime:
        return self.vessel.eta


# (선박, 후보 ETB, 이미 확정된 다른 선박 일정) -> (조정된 ETB, 근거 메모 또는 None).
# 조정된 ETB는 후보보다 이르면 안 된다. 확정 일정에는 모든 FIX 선박이 처음부터 들어 있다.
EtbAdjuster = Callable[[Vessel, datetime, Sequence[Step1Result]], tuple[datetime, str | None]]


def _fixed_result(v: Vessel) -> Step1Result:
    return Step1Result(v, v.fixed_etb, v.fixed_etb + v.stay_for(v.fixed_etb), EtbRule.FIXED, None, True, "접안가능")


def _candidate(v: Vessel, prev: Step1Result | None) -> tuple[datetime, EtbRule, str | None]:
    """① 이전 선박 기준 후보 ETB."""
    dr = direction(v.berth)
    sw = switching(v.berth)
    if prev is not None and v.eta + dr <= prev.etu + sw:
        return prev.etu + sw, EtbRule.SWITCHING, prev.vessel_id
    return v.eta + dr, EtbRule.DIRECTION, None


def _apply_adjusters(
    v: Vessel, etb: datetime, adjusters: Sequence[EtbAdjuster], committed: Sequence[Step1Result]
) -> tuple[datetime, tuple[str, ...]]:
    """조정기를 ETB가 더 이상 바뀌지 않을 때까지 반복 적용한다 (모든 제약 AND)."""
    notes: dict[str, None] = {}  # 순서 유지 + 중복 제거
    while True:
        start = etb
        for adjust in adjusters:
            adjusted, note = adjust(v, etb, committed)
            if adjusted < etb:
                raise ValueError(f"{v.vessel_id}: 조정기가 ETB를 앞당겼습니다 ({etb} -> {adjusted}).")
            etb = adjusted
            if note:
                notes[note] = None
        if etb == start:
            return etb, tuple(notes)


def schedule(
    sequences: dict[str, list[Vessel]], adjusters: Sequence[EtbAdjuster] = ()
) -> dict[str, list[Step1Result]]:
    """부두별 접안 순서 전체(시나리오 1개)를 계산한다.

    부두 간 제약(③)이 있으므로 부두를 따로 계산하지 않고, 모든 부두의 다음 선박 중
    ① 후보 ETB가 가장 이른 선박부터 하나씩 확정한다. 각 부두 안의 순서는 입력 순서를 지킨다.
    """
    for berth, seq in sequences.items():
        if any(v.berth != berth for v in seq):
            raise ValueError(f"{berth} 순서에 다른 부두 선박이 섞여 있습니다.")

    fixed = {v.vessel_id: _fixed_result(v) for seq in sequences.values() for v in seq if v.is_fix}
    committed: list[Step1Result] = list(fixed.values())
    results: dict[str, list[Step1Result]] = {berth: [] for berth in sequences}
    pos = {berth: 0 for berth in sequences}

    while True:
        heads = []
        for berth, seq in sequences.items():
            if pos[berth] < len(seq):
                v = seq[pos[berth]]
                prev = results[berth][-1] if results[berth] else None
                cand = (v.fixed_etb, EtbRule.FIXED, None) if v.is_fix else _candidate(v, prev)
                heads.append((cand[0], berth, v, cand))
        if not heads:
            return results
        _, berth, v, (etb, rule, prev_id) = min(heads, key=lambda h: (h[0], h[1]))
        seq = sequences[berth]
        i = pos[berth]
        pos[berth] += 1

        if v.is_fix:
            results[berth].append(fixed[v.vessel_id])
            continue

        etb, notes = _apply_adjusters(v, etb, adjusters, committed)
        etu = etb + v.stay_for(etb)

        berthable, reason = True, "접안가능"
        sw = switching(berth)
        nxt = seq[i + 1] if i + 1 < len(seq) else None
        if nxt is not None and nxt.is_fix and nxt.fixed_etb <= etu + sw:
            berthable = False
            reason = (
                f"접안불가: 다음 FIX 선박 {nxt.vessel_id} ETB {nxt.fixed_etb:%m/%d %H:%M}"
                f" <= 예상 ETU {etu:%m/%d %H:%M} + Switching {sw.total_seconds() / 3600:g}h"
            )

        result = Step1Result(v, etb, etu, rule, prev_id, berthable, reason, notes)
        results[berth].append(result)
        committed.append(result)


def schedule_berth(sequence: list[Vessel], adjusters: Sequence[EtbAdjuster] = ()) -> list[Step1Result]:
    """한 부두만 계산할 때의 편의 함수."""
    if not sequence:
        return []
    return schedule({sequence[0].berth: sequence}, adjusters)[sequence[0].berth]


def is_feasible(result: dict[str, list[Step1Result]]) -> bool:
    return all(r.berthable for rows in result.values() for r in rows)
