"""예상이안시간(ETU) = 작업완료시간 + 2h."""

from datetime import datetime, timedelta

FINISH_TO_ETU = timedelta(hours=2)


def etu(work_finish: datetime) -> datetime:
    return work_finish + FINISH_TO_ETU
