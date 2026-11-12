"""도메인 모델 (표준 라이브러리 dataclass만 쓴다 — 엔진은 외부 패키지에 기대지 않는다).

입력 쪽: Berth(부두), Contract(계약), Vessel(선박), Restriction(부두 사용 제한), InventoryGroup(재고), Scenario
계산 쪽: Push(접안 가능시각을 민 기록), Placement(한 선박의 배정과 시각), LaytimeResult(정박·체선 계산서)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

# 선박 상태 (FR-11) — 재배정 대상은 ORDERED·PLANNED뿐
MOVABLE_STATUSES = ("ORDERED", "PLANNED")
STATUSES = ("ORDERED", "PLANNED", "WORKING", "COMPLETED", "FIX")

# 선종 (Daylight 적용 여부는 규칙 테이블이 정한다)
VESSEL_TYPES = ("CRUDE", "PRODUCT", "SPECIAL_PRODUCT", "BASE_OIL", "CHEMICAL", "LPG")
VESSEL_TYPE_KO = {
    "CRUDE": "원유선", "PRODUCT": "제품선", "SPECIAL_PRODUCT": "특수제품선",
    "BASE_OIL": "기유선", "CHEMICAL": "화학선", "LPG": "가스선",
}


@dataclass(frozen=True)
class Berth:
    id: str
    shift_group: str          # Shifting 소요시간 표의 행 (#1~2, #4, #6 …)
    type: str                 # PIER / BUOY
    max_dwt: int
    min_loa: float
    max_loa: float
    min_pbl: float
    max_draft: float
    cargo_groups: tuple
    direction: int            # 부두가 비어 있을 때 ETA → 접안 (Direction, 분)
    switching: int            # 앞 선박 이안 → 다음 선박 접안 (Switching, 분)
    tide_draft_threshold: Optional[float]
    order: int                # 표시·동점 처리 순서


@dataclass(frozen=True)
class Contract:
    type: str                 # CP / FOB / CFR / CFR_PLUS
    laytime_h: Fraction       # 허용 정박시간(계약)
    rate_usd_day: int         # 하루 체선료
    laycan_from: int
    laycan_to: int
    nor_tender: Optional[int]
    # 계약서(data/contracts)에서 읽은 경우에만 채워진다. 비어 있으면 규칙 표 기본값을 쓴다.
    id: Optional[str] = None                  # 계약서 번호 (예: CT-2611-05)
    title: str = ""
    counterparty: str = ""
    notice_min: Optional[int] = None          # NOR 통지시간
    weather_ratio: Optional[Fraction] = None  # 기상 체선 공제 비율 (0이면 공제 조항 없음)
    daylight_nor: Optional[bool] = None       # 주간 NOR 조항
    laytime_basis: str = ""                   # 허용 정박시간을 어떻게 정했나 (예: 부분 화물 비례)
    refs: tuple = ()                          # ((규칙 ID, (조항, …)), …) — 근거 표시용

    def ref(self, rule_id: str) -> tuple:
        """이 규칙을 정한 계약 조항들. 없으면 빈 튜플."""
        for rid, clauses in self.refs:
            if rid == rule_id:
                return clauses
        return ()


@dataclass(frozen=True)
class Vessel:
    id: str
    name: str
    vessel_type: str
    grt: int
    dwt: int
    loa: float
    pbl: float
    draft: float
    direction: str            # IMPORT(수입·입고) / EXPORT(수출·출하)
    material_code: str
    cargo_group: str
    qty: float
    eta: int
    contract: Contract
    status: str
    fixed_berth: Optional[str] = None     # FIX 선박의 부두
    fixed_etb: Optional[int] = None       # FIX·WORKING 선박의 ETB
    work_start_actual: Optional[int] = None
    work_hours: Optional[Fraction] = None
    hose_term_h: Optional[Fraction] = None
    work_start_delay_min: int = 60        # 작업시작 = ETB + 1시간 (PPT 09쪽)
    allowed_berths: Optional[tuple] = None
    deadline: Optional[int] = None        # 접안 마감(FR-18)
    remarks: str = ""
    vessel_code: Optional[str] = None     # 과거 실적 매칭용 선박코드 (없으면 id)
    priority: Optional[str] = None        # URGENT = 긴급 출하 지정(FR-18 우선 배정, 리스크 점검용)

    @property
    def movable(self) -> bool:
        return self.status in MOVABLE_STATUSES

    @property
    def immovable(self) -> bool:
        return self.status in ("FIX", "WORKING")


@dataclass(frozen=True)
class Restriction:
    id: str
    berths: tuple             # ('*',)이면 전 부두
    start: int
    end: int
    reason: str               # WEATHER / MAINTENANCE / USER
    note: str = ""
    source: str = ""

    def covers(self, berth_id: str) -> bool:
        return "*" in self.berths or berth_id in self.berths


@dataclass(frozen=True)
class InventoryGroup:
    group: str
    unit: str
    capacity: float
    opening: float
    daily_net: float          # 하루 순증감 (생산 +, 공정 투입 −)
    minimum: float = 0.0


@dataclass
class Scenario:
    id: str
    title: str
    description: str
    data_label: str
    horizon_start: int
    horizon_end: int
    active_berths: tuple
    vessels: list
    restrictions: list          # 사용자 입력 제한 (기상 제한은 예보에서 만든다)
    weather_segments: list      # [(start, end, wind_ms)]
    weather_meta: dict
    tide_windows: dict          # berth → [(start, end)]
    inventory: dict             # group → InventoryGroup
    sun_override: dict          # 'YYYY-MM-DD' → (sunrise_min_of_day, sunset_min_of_day)
    raw: dict = field(default_factory=dict)
    source_hash: str = ""

    def vessel(self, vid: str) -> Vessel:
        for v in self.vessels:
            if v.id == vid:
                return v
        raise KeyError(vid)


# ---------- 계산 결과 ----------

# 접안 가능시각을 민 사유 → 체선 사유 분해(FR-32)의 분류
REASON_CATEGORY = {
    "APPROACH": "접안 전 대기",
    "PREV": "선행 선박 대기",
    "FIX": "선행 선박 대기",
    "NIGHT_POB": "야간 도선",
    "NIGHT_DAWN": "야간 도선",
    "MAINTENANCE": "부두 제한",
    "USER": "부두 제한",
    "WEATHER": "기상",
    "SAME_GROUP": "동시 접안 제한",
    "SIMUL": "동시 접안 제한",
    "TIDE": "조석",
    "INVENTORY": "재고·설비",
    "AT_BERTH": "접안 후 작업",
    "UNKNOWN": "미상",
}


@dataclass
class Push:
    rule_id: str
    frm: int
    to: int
    reason: str               # REASON_CATEGORY의 키
    detail: str

    def as_dict(self):
        from .timeutil import fmt_iso
        return {"rule_id": self.rule_id, "from": fmt_iso(self.frm), "to": fmt_iso(self.to),
                "minutes": self.to - self.frm, "reason": self.reason,
                "category": REASON_CATEGORY.get(self.reason, "미상"), "detail": self.detail}


@dataclass
class Placement:
    vid: str
    berth: str
    etb: int
    work_start: int
    work_end: int
    hose_off: int
    etu: int
    excl_end: int             # 동시 접안 판단용 배타 구간 끝 = ETU − 2시간
    lb0: int                  # ETA + Direction
    kind: str                 # MOVABLE / FIX / WORKING
    pushes: list = field(default_factory=list)
    etb_nowx: Optional[int] = None        # 기상 제한이 없었다면의 ETB (기상 체선 시간 산정용)
    pushes_nowx: Optional[list] = None
    work_basis: dict = field(default_factory=dict)


@dataclass
class Infeasible:
    vid: str
    berth: str
    reason: str
    rule_id: str
    detail: str
