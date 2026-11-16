"""정박개시시간 — Daylight 미적용 (특수제품선, 윤활유제품선, 화학제품선).

장표 흐름 (첫 번째 YES에서 결정)
  1) ETANR < LayCan From && ETB < LayCan From  (Early Loading) → ETB
  2) ETANR > LayCan To                          (LayCan Miss)    → ETB
  3) ETANR < LayCan From                                          → LayCan From의 오전 06시
  4) 그 외 (LayCan From < ETA < LayCan To)                        → ETANR + 6h
     → ETB < 정박개시시간 이면 정박개시시간 = ETB

구현 해석
- LayCan From/To는 일시(datetime)로 받는다.
- 4번 분기 라벨의 ETA는 ETANR로 통일하고, 1~3에 해당하지 않으면 모두 4번으로 본다.
- 'ETB < 정박개시시간 → ETB' 후처리는 4번 분기(ETANR + 6h)에만 적용한다. 3번(LayCan From 06시)은 고정.
- LayCan은 접안 제약이 아니다: LayCan 전에도 접안할 수 있다 (그 경우가 1번 Early Loading → ETB).
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

NOTICE_TIME = timedelta(hours=6)
LAYCAN_FROM_HOUR = time(6, 0)


@dataclass(frozen=True)
class LaytimeStart:
    at: datetime
    reason: str


def cap_at_etb(start: datetime, etb: datetime, reason: str) -> LaytimeStart:
    """ETB < 정박개시시간 → 정박개시시간 = ETB."""
    if etb < start:
        return LaytimeStart(etb, f"{reason} → ETB({etb:%m/%d %H:%M})가 더 이르므로 ETB")
    return LaytimeStart(start, reason)


def laycan_branch(
    etanr: datetime, etb: datetime, laycan_from: datetime, laycan_to: datetime, from_hour: time
) -> LaytimeStart | None:
    """Daylight 적용/미적용 공통인 LayCan 분기 1~3. 해당 없으면 None."""
    if etanr < laycan_from and etb < laycan_from:
        return LaytimeStart(etb, "Early Loading: ETANR, ETB < LayCan From → ETB")
    if etanr > laycan_to:
        return LaytimeStart(etb, "LayCan Miss: ETANR > LayCan To → ETB")
    if etanr < laycan_from:
        at = datetime.combine(laycan_from.date(), from_hour)
        return LaytimeStart(at, f"ETANR < LayCan From → LayCan From의 {from_hour:%H:%M}")
    return None


def laytime_start_no_daylight(
    etanr: datetime, etb: datetime, laycan_from: datetime, laycan_to: datetime
) -> LaytimeStart:
    found = laycan_branch(etanr, etb, laycan_from, laycan_to, LAYCAN_FROM_HOUR)
    if found is not None:
        return found
    return cap_at_etb(etanr + NOTICE_TIME, etb, "LayCan 내 도착 → ETANR + 6h")
