"""체선료 = Demurrage Time * Rate / 24.

Rate는 계약상 1일 체선료(Demurrage Rate, $/day). 작업 처리 Rate(s2)와 다른 값이다.
시나리오 전체 예상 체선료 = Σ 선박별 예상 체선료 (녹취).
"""

from collections.abc import Iterable
from datetime import timedelta

from .common import ALERT_NO_DEMURRAGE_RATE, CalcAlert


def demurrage_fee(dem_time: timedelta, rate_per_day: float | None) -> float:
    if rate_per_day is None:
        raise CalcAlert(ALERT_NO_DEMURRAGE_RATE)
    return dem_time.total_seconds() / 3600 * rate_per_day / 24


def scenario_total(fees: Iterable[float]) -> float:
    return sum(fees)
