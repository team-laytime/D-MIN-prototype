"""ETB 산정 ③-1 동일 화물 그룹 제약 (pptx 9번째 슬라이드, 쪽번호 08).

장표 원문
  *동일화물그룹 제약
   #6, #7, #8 동일 화물그룹 동시 접안 불가
   #1-1, #1-2, #2-7 동일 화물 그룹 동시 접안 불가
  *부두 제약에 따른 ETB 계산
   2) 동일 화물그룹 / 부두 동시 접안 제약 → ETB = 중복 선박 ETU – 2h

구현 해석 (현업 확인 필요, 요구사항 문서 12장 Q3)
- 화물 그룹은 Sample data `부두 별 접안 가능 제품 그룹` 시트의 '제품 그룹'(DSL, R-G, CRUDE …) 값으로 비교한다.
- ETU = 작업완료 + 2h 이므로 'ETU - 2h'는 작업완료 시각이다. 그래서 선박마다 [ETB, ETU - 2h)를
  '작업 구간'으로 보고, 같은 부두 묶음의 다른 부두에서 같은 화물 그룹 선박과 작업 구간이 겹치면
  ETB = 그 선박 ETU - 2h 로 미룬다. 미룬 뒤 다른 선박과 또 겹치면 반복한다.
- 같은 부두 안의 선후 관계는 ①(Switching)이 처리하므로 여기서는 다른 부두만 본다.
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from .models import Vessel
from .step1_prev_fix import EtbAdjuster, Step1Result

SAME_CARGO_BERTH_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"6", "7", "8"}),
    frozenset({"1-1", "1-2", "2-7"}),
)
ETU_TO_WORK_END = timedelta(hours=2)  # ETU - 2h = 작업완료


def linked_berths(berth: str) -> frozenset[str]:
    """같은 화물 그룹을 동시에 작업할 수 없는 다른 부두들."""
    for group in SAME_CARGO_BERTH_GROUPS:
        if berth in group:
            return group - {berth}
    return frozenset()


def shift_past_rivals(
    v: Vessel, etb: datetime, rivals: Sequence[Step1Result], describe: Callable[[Step1Result], str]
) -> tuple[datetime, list[str]]:
    """작업 구간 [ETB, ETU - 2h)가 rivals와 겹치지 않을 때까지 ETB = 중복 선박 ETU - 2h 로 미룬다."""
    moves: list[str] = []
    while True:
        work_end = etb + v.stay_for(etb) - ETU_TO_WORK_END
        blocker = next(
            (r for r in rivals if etb < r.etu - ETU_TO_WORK_END and r.etb < work_end),
            None,
        )
        if blocker is None:
            return etb, moves
        etb = blocker.etu - ETU_TO_WORK_END
        moves.append(
            f"{describe(blocker)}: #{blocker.berth} {blocker.vessel_id}"
            f" 작업 {blocker.etb:%m/%d %H:%M}~{blocker.etu - ETU_TO_WORK_END:%m/%d %H:%M}과 겹침"
            f" → ETB = 중복 선박 ETU - 2h = {etb:%m/%d %H:%M}"
        )


def make_cargo_group_adjuster() -> EtbAdjuster:
    def adjust(v: Vessel, etb: datetime, committed: Sequence[Step1Result]) -> tuple[datetime, str | None]:
        linked = linked_berths(v.berth)
        if not linked:
            return etb, None
        if v.cargo_group is None:
            return etb, "동일 화물 그룹 미판정: 화물 그룹 없음"

        rivals = [r for r in committed if r.berth in linked and r.vessel.cargo_group == v.cargo_group]
        etb, moves = shift_past_rivals(v, etb, rivals, lambda _: f"동일 화물 그룹({v.cargo_group}) 제약")
        return etb, "; ".join(moves) or None

    return adjust
