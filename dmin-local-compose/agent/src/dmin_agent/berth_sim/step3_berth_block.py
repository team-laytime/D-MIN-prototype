"""ETB 산정 ③-3 사용자 설정 부두 제약 (pptx 9번째 슬라이드, 쪽번호 08).

장표 원문
  *부두 제약에 따른 ETB 계산
   1) 기상, 부두/선석 공사 등에 따른 부두 제약(사용자 설정) → ETB = 부두제약 종료시간 + Direction
  (13번째 슬라이드: 기상 정보는 필요 없고 '부두 제약 시간 설정 기능'으로 대체)

녹취 (요구사항 문서 5.3)
  기상 악화 → 전체 부두 / 부두·선석 공사, 설비 고장 → 개별 부두. 현업이 시작·종료 시각을 입력.

구현 해석 (현업 확인 필요, 요구사항 문서 12장 Q3-2)
- 제약 구간 [시작, 종료) 동안에는 접안 작업을 할 수 없으므로, 후보 ETB가 [시작, 종료 + Direction)에 들면
  ETB = 종료 + Direction 으로 미룬다. 제약 시작 전에 접안을 마치는 선박은 그대로 둔다.
- whole_stay=True 인 제약(예: 공사로 부두 자체를 비워야 하는 경우)은 접안 시각뿐 아니라
  부두 점유 구간 [ETB, ETU)가 제약과 겹쳐도 미룬다.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .models import Vessel
from .shifting import direction
from .step1_prev_fix import EtbAdjuster, Step1Result


class BlockKind(str, Enum):
    WEATHER = "기상"  # 사용자 입력 기상 제약 (기상체선 50% 계산에도 쓰임)
    CONSTRUCTION = "공사"
    EQUIPMENT = "설비"
    WIND = "강풍·태풍"  # 풍속 예보의 접안 불가(이안 기준) 구간 — weather.wind_blocks


@dataclass(frozen=True)
class BerthBlock:
    start: datetime
    end: datetime
    kind: BlockKind
    berths: frozenset[str] | None = None  # None = 전체 부두
    whole_stay: bool = False

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"부두 제약 종료({self.end})가 시작({self.start})보다 늦어야 합니다.")

    def applies_to(self, berth: str) -> bool:
        return self.berths is None or berth in self.berths


def make_berth_block_adjuster(blocks: Sequence[BerthBlock]) -> EtbAdjuster:
    def adjust(v: Vessel, etb: datetime, committed: Sequence[Step1Result] = ()) -> tuple[datetime, str | None]:
        dr = direction(v.berth)
        mine = sorted((b for b in blocks if b.applies_to(v.berth)), key=lambda b: b.start)
        moves: list[str] = []
        moved = True
        while moved:  # 미룬 뒤 다른 제약에 또 걸릴 수 있다
            moved = False
            for b in mine:
                hit = b.start <= etb < b.end + dr
                if b.whole_stay:
                    hit = hit or (etb < b.end and b.start < etb + v.stay_for(etb))
                if hit:
                    etb = b.end + dr
                    moves.append(
                        f"부두 제약({b.kind.value}) {b.start:%m/%d %H:%M}~{b.end:%m/%d %H:%M}"
                        f" → ETB = 종료 + Direction {dr.total_seconds() / 3600:g}h = {etb:%m/%d %H:%M}"
                    )
                    moved = True
        return etb, "; ".join(moves) or None

    return adjust
