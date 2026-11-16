"""`Sample data.xlsx` / `접안계획 예시` 시트 로더.

시트에는 연도가 없으므로(예: '11/09 18:00') year 인자로 보충한다.
같은 선박의 화물 라인이 여러 줄로 반복되므로 (부두, ETA, ETB, ETU, Biz)가 같은 행은 한 척으로 합친다.
"""

from datetime import datetime
from pathlib import Path

import openpyxl

from .models import Vessel
from .shifting import normalize_berth

SHEET = "접안계획 예시"


def parse_time(text: str, year: int) -> datetime:
    return datetime.strptime(f"{year}/{text.strip()}", "%Y/%m/%d %H:%M")


def load_berth_plan(path: str | Path, year: int = 2026) -> tuple[dict[str, list[Vessel]], dict[str, datetime]]:
    """부두별 접안 순서(원본 ETB 순)와 선박별 원본 ETB를 돌려준다.

    stay(부두 점유시간)는 원본 ETU - ETB로 둔다.
    """
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[SHEET]
    seen: set[tuple] = set()
    rows: list[tuple[str, datetime, datetime, datetime, str]] = []
    for row in ws.iter_rows(min_row=3, max_col=5, values_only=True):
        if not row[0]:
            continue
        key = tuple(str(c).strip() for c in row)
        if key in seen:
            continue
        seen.add(key)
        berth_raw, eta, etb, etu, biz = key
        rows.append((normalize_berth(berth_raw), parse_time(eta, year), parse_time(etb, year), parse_time(etu, year), biz))

    rows.sort(key=lambda r: (r[0], r[2], r[1]))
    sequences: dict[str, list[Vessel]] = {}
    original_etb: dict[str, datetime] = {}
    for berth, eta, etb, etu, biz in rows:
        seq = sequences.setdefault(berth, [])
        vessel_id = f"{berth}#{len(seq) + 1}"
        seq.append(Vessel(vessel_id, berth, eta, etu - etb, biz=biz))
        original_etb[vessel_id] = etb
    return sequences, original_etb
