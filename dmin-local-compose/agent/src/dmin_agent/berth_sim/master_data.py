"""`Sample data.xlsx`의 기준정보 시트 로더 (실제 데이터).

- 부두별 제원                : Max DWT / Max Draft / Max LOA / Min LOA / Min PBL / 규모
- 부두 별 접안 가능 제품 그룹 : 부두 → 제품 그룹(DSL, CRUDE …) + 제품 분류(CR/PP/PC/LB/SP)
                              '참고 - 제품 분류' 열: 분류 → 선종 (CR=원유선, PP=석유제품선 …)
- 선박 제원 Sample           : DWT 구간별 평균 GRT / Draft / LOA / PBL / 일 체선료 / 작업속도 (참고용 통계)
                              'epeo' 열은 PBL(평행부 길이)로 본다: 모든 구간에서 LOA의 0.4~0.5배 (탱커 PBL 비율)

'-' 또는 빈 칸은 '비교하지 않음'(None)으로 읽는다.

시트에 없는 값은 SK에너지 공개 부두 제원표에서 보충한다 (BERTH_SUPPLEMENT).
시트와 공개 제원표가 다르면 시트(멘토링 자료)를 따른다. 예: BUOY3 Max Draft 시트 22.1m / 공개표 23.04m → 22.1m
"""

import re
from dataclasses import dataclass
from pathlib import Path

SHEET_BERTH = "부두별 제원"
SHEET_PRODUCT = "부두 별 접안 가능 제품 그룹"
SHEET_SHIP = "선박 제원 Sample"

# 공개 부두 제원표(SK No.2~3 Buoy)에만 있는 값: Min. Mooring Capacity DWT 80,000
BERTH_SUPPLEMENT: dict[str, dict[str, float]] = {
    "BUOY2": {"min_dwt": 80_000},
    "BUOY3": {"min_dwt": 80_000},
}


@dataclass(frozen=True)
class BerthSpec:
    berth: str
    max_dwt: float
    max_draft: float
    max_loa: float | None
    min_loa: float | None
    min_pbl: float | None
    size: str | None  # 소형 / 대형 / 초대형
    min_dwt: float | None = None  # 공개 제원표 보충 (Buoy)


@dataclass(frozen=True)
class ProductGroup:
    name: str  # 제품 그룹 (DSL, CRUDE …)
    product_class: str  # CR / PP / PC / LB / SP


@dataclass(frozen=True)
class DwtBucket:
    label: str
    low: float
    high: float
    count: int
    avg_grt: float
    draft: float
    loa: float
    pbl: float  # 'epeo' 열
    demurrage_per_day: float  # 평균 일 체선료($)
    work_speed: float  # 평균 작업속도 (단위 미기재)

    def contains(self, dwt: float) -> bool:
        return self.low <= dwt < self.high


@dataclass(frozen=True)
class MasterData:
    berths: dict[str, BerthSpec]
    products: dict[str, tuple[ProductGroup, ...]]
    vessel_type_by_class: dict[str, str]
    buckets: tuple[DwtBucket, ...]

    def bucket(self, dwt: float) -> DwtBucket:
        for b in self.buckets:
            if b.contains(dwt):
                return b
        return self.buckets[-1]


def _num(v) -> float | None:
    if v is None or (isinstance(v, str) and v.strip() in ("", "-")):
        return None
    return float(v)


def _berth_name(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip().upper()


def _man(text: str) -> float:
    """'17만' -> 170000, '0' -> 0"""
    text = text.strip()
    return float(text[:-1]) * 10_000 if text.endswith("만") else float(text)


def parse_dwt_label(label: str) -> tuple[float, float]:
    low, high = re.split(r"\s*~\s*", label.strip())
    return _man(low), _man(high)


def load_master(path: str | Path) -> MasterData:
    import openpyxl  # 엑셀을 읽을 때만 필요

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    berths: dict[str, BerthSpec] = {}
    for row in wb[SHEET_BERTH].iter_rows(min_row=2, max_col=7, values_only=True):
        if row[0] is None:
            continue
        name = _berth_name(row[0])
        berths[name] = BerthSpec(
            name, _num(row[1]), _num(row[2]), _num(row[3]), _num(row[4]), _num(row[5]), row[6],
            **BERTH_SUPPLEMENT.get(name, {}),
        )

    products: dict[str, list[ProductGroup]] = {}
    vessel_type_by_class: dict[str, str] = {}
    current = None
    for row in wb[SHEET_PRODUCT].iter_rows(min_row=2, max_col=8, values_only=True):
        if row[0] is not None:
            current = _berth_name(row[0])
        if row[1] is not None and current is not None:
            products.setdefault(current, []).append(ProductGroup(str(row[1]).strip(), str(row[2]).strip()))
        if row[6] is not None and row[7] is not None:
            vessel_type_by_class[str(row[6]).strip()] = str(row[7]).strip()

    buckets = []
    for row in wb[SHEET_SHIP].iter_rows(min_row=2, max_col=8, values_only=True):
        if row[0] is None:
            continue
        low, high = parse_dwt_label(str(row[0]))
        buckets.append(DwtBucket(str(row[0]), low, high, int(row[1]), *(float(x) for x in row[2:6]), float(row[6]), float(row[7])))

    return MasterData(berths, {k: tuple(v) for k, v in products.items()}, vessel_type_by_class, tuple(buckets))
