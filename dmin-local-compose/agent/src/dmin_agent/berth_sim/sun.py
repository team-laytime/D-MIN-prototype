"""울산 일출·일몰 시각.

공공데이터(한국천문연구원 출몰시각) 연동 전까지 NOAA 태양 위치 근사식으로 계산한다.
공공데이터가 준비되면 같은 시그니처(date -> datetime)의 함수로 교체해 `make_night_pilot_adjuster`에 넘기면 된다.
"""

import math
from functools import lru_cache
from datetime import date, datetime, time, timedelta

ULSAN_LAT = 35.5384
ULSAN_LON = 129.3114
KST_OFFSET_H = 9
_ZENITH_DEG = 90.833  # 대기 굴절 + 태양 반지름 보정


@lru_cache(maxsize=None)
def ulsan_sunset(day: date) -> datetime:
    """울산 기준 일몰 시각(KST, 분 단위 반올림)."""
    return _sun_event(day, rising=False)


@lru_cache(maxsize=None)
def ulsan_sunrise(day: date) -> datetime:
    """울산 기준 일출 시각(KST, 분 단위 반올림)."""
    return _sun_event(day, rising=True)


def _sun_event(day: date, rising: bool) -> datetime:
    n = day.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (n - 1)  # 정오 기준 연각
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    lat = math.radians(ULSAN_LAT)
    cos_ha = math.cos(math.radians(_ZENITH_DEG)) / (math.cos(lat) * math.cos(decl)) - math.tan(lat) * math.tan(decl)
    ha = math.degrees(math.acos(cos_ha))
    utc_minutes = 720 - 4 * (ULSAN_LON + (ha if rising else -ha)) - eqtime
    local = datetime.combine(day, time()) + timedelta(minutes=utc_minutes + KST_OFFSET_H * 60)
    return (local + timedelta(seconds=30)).replace(second=0, microsecond=0)
