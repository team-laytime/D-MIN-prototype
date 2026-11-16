"""예상 정박개시 산출 시작: ETA & NR Tender 시간 有? → ETANR = NVL(NR_TENDER, ETA).

NVL이므로 둘 중 하나만 있어도 계산할 수 있다. 둘 다 없을 때만 Alert (요구사항 문서 12장 Q4-5).
"""

from datetime import datetime

from .common import ALERT_NO_ETANR, CalcAlert


def etanr(nr_tender: datetime | None, eta: datetime | None) -> datetime:
    if nr_tender is not None:
        return nr_tender
    if eta is not None:
        return eta
    raise CalcAlert(ALERT_NO_ETANR)
