"""ETB 산정 ③-2 부두 동시 접안 제약 (pptx 9번째 슬라이드, 쪽번호 08).

장표 원문
  *부두 동시 접안 제약
   #4-1, #4-2 부두 동시 접안 불가(*단, 두 선박 모두 GRT 3천톤 이하일 경우 가능)
   → ETB = 접안한 선박 ETU – 2hr

구현 해석 (현업 확인 필요, 요구사항 문서 12장 Q3)
- 화물과 관계없이 #4-1과 #4-2의 작업 구간 [ETB, ETU - 2h)가 겹치면 ETB = 중복 선박 ETU - 2h.
  겹침 판정과 반복 미루기는 ③-1(step3_cargo_group.shift_past_rivals)과 같다.
- 예외: 두 선박 모두 GRT <= 3,000이면 동시 접안 가능.
- GRT가 없으면 예외를 확인할 수 없으므로 제약을 적용하고 그 사실을 근거 메모에 남긴다 (보수적 판단).
"""

from collections.abc import Sequence
from datetime import datetime

from .models import Vessel
from .step1_prev_fix import EtbAdjuster, Step1Result
from .step3_cargo_group import shift_past_rivals

SIMULTANEOUS_BERTH_PAIRS: tuple[frozenset[str], ...] = (frozenset({"4-1", "4-2"}),)
SMALL_GRT = 3_000  # 두 선박 모두 이 이하면 동시 접안 가능


def paired_berths(berth: str) -> frozenset[str]:
    for pair in SIMULTANEOUS_BERTH_PAIRS:
        if berth in pair:
            return pair - {berth}
    return frozenset()


def _small(v: Vessel) -> bool:
    return v.grt is not None and v.grt <= SMALL_GRT


def make_berth_pair_adjuster() -> EtbAdjuster:
    def adjust(v: Vessel, etb: datetime, committed: Sequence[Step1Result]) -> tuple[datetime, str | None]:
        paired = paired_berths(v.berth)
        if not paired:
            return etb, None

        rivals = [r for r in committed if r.berth in paired and not (_small(v) and _small(r.vessel))]
        etb, moves = shift_past_rivals(v, etb, rivals, lambda _: "부두 동시 접안 제약")
        if moves and (v.grt is None or any(r.vessel.grt is None for r in rivals)):
            moves.insert(0, "GRT 없음 → GRT 3천톤 이하 예외 미적용")
        return etb, "; ".join(moves) or None

    return adjust
