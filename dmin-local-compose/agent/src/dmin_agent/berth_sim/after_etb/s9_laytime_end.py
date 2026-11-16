"""예상 정박종료 산출.

  LayTime 없음        → Alert "LAY TIME이 없으므로 예상 정박종료를 산출할 수 없습니다."
  원유 && CFR False   → 정박종료시간 = 정박개시시간 + (LayTime / 2)
  그 외               → 정박종료시간 = 정박개시시간 + LayTime

'원유' 여부는 호출하는 쪽에서 판단해 넘긴다 (pipeline은 선종 '원유선'으로 판단).
CFR 플래그의 정확한 정의는 현업 확인 필요 (요구사항 문서 12장 Q5).
"""

from datetime import datetime, timedelta

from .common import ALERT_NO_LAYTIME, CalcAlert


def laytime_end(laytime_start: datetime, laytime: timedelta | None, is_crude: bool, cfr: bool) -> datetime:
    if laytime is None:
        raise CalcAlert(ALERT_NO_LAYTIME)
    if is_crude and not cfr:
        return laytime_start + laytime / 2
    return laytime_start + laytime
