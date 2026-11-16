"""정박개시시간 — Daylight 적용 (원유선, 석유제품선).

장표 흐름 (첫 번째 YES에서 결정)
  1) ETANR < LayCan From && ETB < LayCan From → ETB
  2) ETANR > LayCan To                        → ETB
  3) ETANR < LayCan From                      → LayCan From의 오전 07시
  4) 일출 < ETANR < 일몰                       → ETANR + 6h
  5) ETANR <= 일출                             → ETANR날의 07시
  6) ETANR >= 일몰                             → ETANR 다음 날의 07시
     → 4~6 결과에 ETB < 정박개시시간 이면 정박개시시간 = ETB

구현 해석 (현업 확인 필요, 요구사항 문서 12장 Q4)
- 일출·일몰은 ETANR 날짜의 울산 일출·일몰 (sun.py 근사식, 공공데이터로 교체 가능).
- 'ETB < 정박개시시간 → ETB' 후처리는 4~6 분기(일출·일몰 판정) 결과에 적용한다. 3번(LayCan From 07시)은 고정.
"""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from ..sun import ulsan_sunrise, ulsan_sunset
from .s7_laytime_start_no_daylight import NOTICE_TIME, LaytimeStart, cap_at_etb, laycan_branch

LAYCAN_FROM_HOUR = time(7, 0)
MORNING = time(7, 0)

SunFn = Callable[[date], datetime]


def laytime_start_daylight(
    etanr: datetime,
    etb: datetime,
    laycan_from: datetime,
    laycan_to: datetime,
    sunrise: SunFn = ulsan_sunrise,
    sunset: SunFn = ulsan_sunset,
) -> LaytimeStart:
    found = laycan_branch(etanr, etb, laycan_from, laycan_to, LAYCAN_FROM_HOUR)
    if found is not None:
        return found

    rise, fall = sunrise(etanr.date()), sunset(etanr.date())
    if rise < etanr < fall:
        start, reason = etanr + NOTICE_TIME, f"일출 {rise:%H:%M} < ETANR < 일몰 {fall:%H:%M} → ETANR + 6h"
    elif etanr <= rise:
        start, reason = datetime.combine(etanr.date(), MORNING), f"ETANR <= 일출 {rise:%H:%M} → ETANR날 07:00"
    else:
        start = datetime.combine(etanr.date() + timedelta(days=1), MORNING)
        reason = f"ETANR >= 일몰 {fall:%H:%M} → ETANR 다음 날 07:00"
    return cap_at_etb(start, etb, reason)
