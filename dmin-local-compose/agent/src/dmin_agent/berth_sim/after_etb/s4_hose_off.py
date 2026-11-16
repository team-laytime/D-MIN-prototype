"""호스분리시간 = 완료시간 + 30분.

장표의 '작업완료~호스분리 평균소요시간 산출'(과거 최빈 Term) 박스는 멘토 피드백으로 삭제(X 표시)되었으므로
과거 데이터를 보지 않고 30분 고정값을 쓴다.
"""

from datetime import datetime, timedelta

FINISH_TO_HOSE_OFF = timedelta(minutes=30)


def hose_off(work_finish: datetime) -> datetime:
    return work_finish + FINISH_TO_HOSE_OFF
