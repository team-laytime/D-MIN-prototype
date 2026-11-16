"""Demurrage Time.

장표
  Demurrage Time = 호스분리시간 – 정박종료시간
  Demurrage Time -= 기상체선 시간 / 2

녹취: 호스분리가 정박종료 이전이면 체선료 0 (조출료/Despatch는 고려하지 않음).
구현: 차감 후 음수면 0 (요구사항 문서 9장 [추론]).
"""

from datetime import datetime, timedelta


def demurrage_time(hose_off: datetime, laytime_end: datetime, weather: timedelta = timedelta()) -> timedelta:
    return max(timedelta(), hose_off - laytime_end - weather / 2)
