"""ETB 이후 계산 공통: 장표 Alert."""


class CalcAlert(Exception):
    """장표 흐름도의 Alert. 메시지는 장표 문구 그대로."""


ALERT_NO_ETB = "ETB 값이 존재하지 않습니다."
ALERT_NO_BERTH = "부두가 선택되지 않았습니다."
ALERT_NO_ETANR = "ETA시간과 N/R Tender 시간이 없으므로 예상 정박개시 산출할 수 없음."
ALERT_NO_LAYTIME = "LAY TIME이 없으므로 예상 정박종료를 산출할 수 없습니다."
# 장표에 없는 Alert (과거 데이터가 전혀 없을 때). 현업 확인 필요.
ALERT_NO_HISTORY = "일치하는 과거 Shipment가 없어 평균 Rate를 산출할 수 없습니다."
ALERT_NO_DEMURRAGE_RATE = "체선료 Rate가 없으므로 예상 체선료를 산출할 수 없습니다."
