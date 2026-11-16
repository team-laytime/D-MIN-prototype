"""가상 선박 제원 (탱커 위주 + 가스 부두용 LPG선). 필요한 항목만 만든다: DWT, LOA, PBL, Draft, GRT.

1) 선박 등급(SHIP_CLASSES)으로 DWT 범위를 정한다. 화물 분류에 맞는 등급만 고른다.
   원유(CR)       → LR1 · Aframax · Suezmax · VLCC
   석유제품(PP)    → 소형 ~ Aframax/LR2
   화학·윤활유·특수 → 소형 ~ MR
   가스(LPG 등)    → LPG선
2) 나머지 치수는 실제 통계인 「선박 제원 Sample」의 DWT 구간 평균에서 가져온다.
   같은 구간 안에서도 크기가 다르므로 세제곱근 법칙으로 보정한다: 치수 ∝ (DWT / 구간 중앙 DWT)^(1/3)
   PBL = LOA × (구간 PBL / 구간 LOA), GRT = DWT × (구간 평균 GRT / 구간 중앙 DWT)
3) 실제 배정 부두에 맞을 때까지(부두 적합성 통과) 다시 뽑는다.

「선박 제원 Sample」의 '17만 ~ 22만' 구간은 LOA 363m, PBL/LOA 0.29로 다른 구간과 동떨어진 값이라(표본 26척)
치수 기준에서 빼고 바로 위 구간을 쓴다.
"""

import random
from dataclasses import dataclass

from .berth_fit import ShipDims, fits
from .master_data import DwtBucket, MasterData

GAS_CARGO = frozenset({"LPG", "PROPYLENE", "BUTENE", "ETHYLENE"})
OUTLIER_BUCKETS = frozenset({"17만 ~ 22만"})
MAX_TRIES = 500
DIM_NOISE = (0.95, 1.05)  # LOA · PBL 비율 · GRT 개별 편차
DRAFT_LOAD = (0.93, 1.0)  # 접안 시 Draft = 구간 Draft × 이 범위 (만재 근처)


@dataclass(frozen=True)
class ShipClass:
    name: str
    dwt_low: float
    dwt_high: float
    product_classes: frozenset[str] = frozenset()  # 실을 수 있는 제품 분류
    gas: bool = False


SHIP_CLASSES: tuple[ShipClass, ...] = (
    ShipClass("소형 탱커", 500, 5_000, frozenset({"PP", "PC", "LB", "SP"})),
    ShipClass("Small 탱커", 5_000, 10_000, frozenset({"PP", "PC", "LB", "SP"})),
    ShipClass("Handysize 탱커", 10_000, 25_000, frozenset({"PP", "PC", "LB", "SP"})),
    ShipClass("MR 탱커", 25_000, 55_000, frozenset({"PP", "PC", "LB"})),
    ShipClass("LR1 탱커", 55_000, 80_000, frozenset({"PP", "CR"})),
    ShipClass("Aframax/LR2 탱커", 80_000, 120_000, frozenset({"PP", "CR"})),
    ShipClass("Suezmax 탱커", 120_000, 200_000, frozenset({"CR"})),
    ShipClass("VLCC", 200_000, 320_000, frozenset({"CR"})),
    ShipClass("LPG선", 1_000, 60_000, gas=True),
)


@dataclass(frozen=True)
class ShipSpec:
    ship_class: str
    dwt: float
    grt: float
    loa: float
    pbl: float
    draft: float

    def dims(self, cargo_group: str | None = None) -> ShipDims:
        return ShipDims(self.dwt, self.loa, self.pbl, self.draft, cargo_group)


def reference_bucket(master: MasterData, dwt: float) -> DwtBucket:
    usable = [b for b in master.buckets if b.label not in OUTLIER_BUCKETS]
    for b in usable:
        if b.contains(dwt):
            return b
    return min(usable, key=lambda b: abs((b.low + b.high) / 2 - dwt))


def dimensions(master: MasterData, dwt: float, rng: random.Random) -> tuple[float, float, float, float]:
    """(GRT, LOA, PBL, Draft)"""
    b = reference_bucket(master, dwt)
    mid = (b.low + b.high) / 2
    scale = (dwt / mid) ** (1 / 3)
    loa = b.loa * scale * rng.uniform(*DIM_NOISE)
    pbl = loa * (b.pbl / b.loa) * rng.uniform(*DIM_NOISE)
    draft = b.draft * scale * rng.uniform(*DRAFT_LOAD)
    grt = dwt * b.avg_grt / mid * rng.uniform(*DIM_NOISE)
    return round(grt, -1), round(loa, 1), round(pbl, 1), round(draft, 2)


def eligible_classes(cargo_group: str, product_class: str) -> list[ShipClass]:
    if cargo_group in GAS_CARGO:
        return [c for c in SHIP_CLASSES if c.gas]
    return [c for c in SHIP_CLASSES if product_class in c.product_classes]


def generate(
    master: MasterData, berth: str, cargo_group: str, product_class: str, rng: random.Random
) -> ShipSpec:
    """berth에 접안 가능한 선박 제원을 만든다 (부두 적합성 통과할 때까지 다시 뽑음)."""
    spec = master.berths[berth]
    floor = spec.min_dwt or 0
    ranges = [
        (c, max(c.dwt_low, floor), min(c.dwt_high, spec.max_dwt))
        for c in eligible_classes(cargo_group, product_class)
    ]
    ranges = [r for r in ranges if r[1] < r[2]]
    if not ranges:
        raise ValueError(f"#{berth}: {cargo_group}({product_class})를 실을 수 있는 선박 등급이 부두 DWT 범위에 없음")
    for _ in range(MAX_TRIES):
        cls, lo, hi = rng.choice(ranges)
        dwt = round(rng.uniform(lo, hi), -1)
        grt, loa, pbl, draft = dimensions(master, dwt, rng)
        ship = ShipSpec(cls.name, dwt, grt, loa, pbl, draft)
        if not fits(ship.dims(cargo_group), berth, master):
            return ship
    raise ValueError(f"#{berth}: {MAX_TRIES}번 시도해도 부두 제원에 맞는 {cargo_group} 선박을 만들지 못함")
