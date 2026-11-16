"""ETB 有? → 예상시작시간 有? → 부두 지정?

  ETB 없음          → Alert "ETB 값이 존재하지 않습니다."
  예상시작시간 없음  → 예상시작시간 = ETB + 1h
  부두 없음          → Alert "부두가 선택되지 않았습니다."
"""

from datetime import datetime, timedelta

from .common import ALERT_NO_BERTH, ALERT_NO_ETB, CalcAlert

ETB_TO_START = timedelta(hours=1)


def work_start(etb: datetime | None, planned_start: datetime | None, berth: str | None) -> datetime:
    if etb is None:
        raise CalcAlert(ALERT_NO_ETB)
    start = planned_start if planned_start is not None else etb + ETB_TO_START
    if not berth:
        raise CalcAlert(ALERT_NO_BERTH)
    return start
