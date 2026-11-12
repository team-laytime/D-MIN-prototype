"""일출·일몰 계산 (NOAA 태양 위치식, 오프라인).

공공데이터포털(한국천문연구원 출몰시각 정보)은 서비스키가 있어야 한다. 키가 없거나 API가 멈춰도
데모가 끝까지 돌도록(NFR-10) 같은 값을 계산으로 낸다. 오차는 보통 1~2분이다.
근거: NOAA Global Monitoring Laboratory 'General Solar Position Calculations' 식(천정각 90.833°).
"""
from __future__ import annotations

import math
from datetime import date

ZENITH_DEG = 90.833  # 대기 굴절·태양 반지름 보정


def _sun_event(d: date, lat: float, lon: float, tz_hours: float, rising: bool) -> float:
    """그날 0시부터 지난 분(현지 표준시). 극지방처럼 해가 안 뜨면 ValueError."""
    n = d.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (n - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                       - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    lat_r = math.radians(lat)
    cos_ha = (math.cos(math.radians(ZENITH_DEG)) / (math.cos(lat_r) * math.cos(decl))
              - math.tan(lat_r) * math.tan(decl))
    if not -1 <= cos_ha <= 1:
        raise ValueError("해가 뜨거나 지지 않는 날")
    ha = math.degrees(math.acos(cos_ha))
    if rising:
        utc_min = 720 - 4 * (lon + ha) - eqtime
    else:
        utc_min = 720 - 4 * (lon - ha) - eqtime
    return utc_min + tz_hours * 60


def sunrise_sunset(d: date, lat: float, lon: float, tz_hours: float = 9) -> tuple:
    """(일출 분, 일몰 분) — 그날 0시 기준, 분 단위로 반올림."""
    rise = _sun_event(d, lat, lon, tz_hours, True)
    sset = _sun_event(d, lat, lon, tz_hours, False)
    return int(round(rise)), int(round(sset))
