"""기상체선 시간.

장표: Demurrage Time -= 기상체선 시간 / 2  (선주와 SK에너지가 절반씩 부담 — 녹취)

구현 해석 (현업 확인 필요, 요구사항 문서 12장 Q7)
- 기상 정보는 '부두 제약 시간 설정'으로 대체하므로(13번째 슬라이드) 기상(WEATHER) 부두 제약에서 뽑는다.
- 기상체선 시간 = 해당 부두의 기상 제약 구간이 체선 구간 [정박종료, 호스분리]와 겹치는 시간.
  (기상 제약끼리 겹치면 한 번만 센다.)
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from ..step3_berth_block import BerthBlock, BlockKind


def weather_hours(
    berth: str, laytime_end: datetime, hose_off: datetime, blocks: Sequence[BerthBlock]
) -> timedelta:
    spans = sorted(
        (max(b.start, laytime_end), min(b.end, hose_off))
        for b in blocks
        if b.kind is BlockKind.WEATHER and b.applies_to(berth)
    )
    total = timedelta()
    cur_start = cur_end = None
    for s, e in spans:
        if e <= s:
            continue
        if cur_end is None or s > cur_end:
            if cur_end is not None:
                total += cur_end - cur_start
            cur_start, cur_end = s, e
        else:
            cur_end = max(cur_end, e)
    if cur_end is not None:
        total += cur_end - cur_start
    return total
