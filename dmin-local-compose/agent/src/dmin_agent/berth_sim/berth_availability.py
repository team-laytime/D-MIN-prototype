"""부두 사용 가능 시작 시각 (데이터 범위 제약, 장표 규칙 아님).

실제 접안계획은 'ETB 11.09 ~ 11.15 조회 결과'라서, 그 전에 부두를 쓰던 선박은 데이터에 없다.
그대로 두면 ETA가 이른 선박(예: 11/04 도착)이 빈 부두로 보이는 과거 시간에 접안해 버린다.
그래서 부두마다 '이 시각 전에는 비어 있는지 알 수 없음'을 제약으로 둔다.

  부두에 실제 선박이 있으면 : 그 부두의 첫 실제 ETB
  부두에 실제 선박이 없으면 : 데이터 전체의 첫 실제 ETB
  → ETB = max(후보 ETB, 부두 사용 가능 시각)
"""

from collections.abc import Sequence
from datetime import datetime

from .models import Vessel
from .step1_prev_fix import EtbAdjuster, Step1Result


def availability_from_plan(
    sequences: dict[str, list[Vessel]], original_etb: dict[str, datetime], berths: Sequence[str]
) -> dict[str, datetime]:
    first = {b: min(original_etb[v.vessel_id] for v in seq) for b, seq in sequences.items() if seq}
    horizon = min(first.values())
    return {b: first.get(b, horizon) for b in berths}


def make_availability_adjuster(available_from: dict[str, datetime]) -> EtbAdjuster:
    def adjust(v: Vessel, etb: datetime, committed: Sequence[Step1Result] = ()) -> tuple[datetime, str | None]:
        start = available_from.get(v.berth)
        if start is not None and etb < start:
            return start, f"부두 사용 가능 시각: #{v.berth} {start:%m/%d %H:%M} 이전 점유 정보 없음 → ETB {start:%m/%d %H:%M}"
        return etb, None

    return adjust
