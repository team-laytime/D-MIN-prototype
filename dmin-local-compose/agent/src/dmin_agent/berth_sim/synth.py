"""실제 접안계획에 없는 선박·계약 정보를 임의로 만든다 (가상 데이터, 같은 seed면 항상 같은 결과).

실제 데이터 (Sample data.xlsx)
  접안계획 예시           부두, ETA, ETB, ETU, Biz (선박 54척)
  부두별 제원             Max/Min DWT, Max Draft, Max/Min LOA, Min PBL
  부두 별 접안 가능 제품   부두 → 제품 그룹 / 분류 → 선종
  선박 제원 Sample        DWT 구간별 평균 GRT / Draft / LOA / PBL / 일 체선료

가상으로 만드는 값과 근거
  제품 그룹   부두의 접안 가능 제품 중 선박 방향(Biz: IM·DI 반입 / EX·DO 반출)에 맞는 제품에서 (product_direction).
             수입(IM)이고 원유(CR) 가능 부두면 원유 그룹
  선박 제원   DWT·GRT·LOA·PBL·Draft — vessel_specs.generate (탱커 등급 + 선박 제원 Sample 구간 평균)
             실제 배정 부두의 부두 적합성(berth_fit)을 통과할 때까지 다시 뽑는다
  다른 부두 실적  최적화에서 다른 부두로 옮길 때 평균 Rate를 구할 수 있도록, 접안 가능한 다른 부두에도
             같은 자재의 과거 Shipment를 만든다 (부두마다 처리 속도 차이 ALT_BERTH_RATE).
             기존 값이 바뀌지 않게 별도 난수 흐름을 쓴다.
  선종        제품 분류 → 선종 ('참고 - 제품 분류' 열)
  작업량 QTY  '실제 ETU가 그대로 재현되도록' 역산: QTY = 평균 Rate × (실제 ETU - 실제 ETB - 3h)
             (작업시작 = ETB + 1h, ETU = 작업완료 + 2h 이므로 작업시간 = 점유시간 - 3h)
  과거 Shipment  선박별 목표 Rate(= DWT × 60~95% / 작업시간) 주변 ±15%로 생성.
             75%는 같은 선박코드 기록이 있고, 25%는 부두+자재코드 기록만 있다 (2단계 조회 확인용)
  LayCan     ETA 기준 3일 창. 60% 창 안 도착 / 25% 조기 도착 / 15% 지연 도착 (LayCan Miss)
  N/R Tender 70%는 ETA + 0~2h, 30%는 없음 (ETANR = ETA)
  LayTime    (작업시간 + 3h) × 1.0~1.6, 6시간 단위 올림. 원유선은 ×1.6~2.4
             (원유 && CFR False면 절반만 인정되므로 계약상 길게 잡는다고 가정)
  일 체선료   DWT 구간 평균 일 체선료 × 85~115%
  CFR        원유선만 50% 확률로 True
"""

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .after_etb.s2_work_finish import PastShipment, average_rate
from .master_data import MasterData, ProductGroup
from .models import Vessel
from .berth_fit import ShipDims, allowed_berths
from .product_direction import matches
from .vessel_specs import generate
from .weather import Forecast, synthesize_forecast

SEED = 20261112
WORK_OVERHEAD = timedelta(hours=3)  # 작업시작 ETB+1h, ETU = 작업완료+2h
CRUDE_CLASS = "CR"

# ── 가상 데이터 생성 가정값 (워크플로우 그림에 링크로 표시됨) ──
LOAD_FACTOR = (0.6, 0.95)  # 적재량 = DWT × 이 비율 → 목표 작업 Rate
OWN_HISTORY_P = 0.75  # 같은 선박코드 과거 Shipment가 있을 확률 (나머지는 부두+자재코드만)
HISTORY_RATE_NOISE = (0.85, 1.15)  # 과거 Shipment Rate = 목표 Rate × 이 범위
QTY_DWT_CAP = 0.98  # 역산 QTY가 DWT × 이 값을 넘으면 자체 과거 기록을 추가
LAYCAN_IN_P = 0.60  # LayCan 창 안 도착
LAYCAN_EARLY_P = 0.25  # 조기 도착 (나머지 = 지연 도착)
LAYCAN_WINDOW_DAYS = 2  # LayCan From ~ To 간격(일)
NR_TENDER_P = 0.70  # N/R Tender가 있을 확률
NR_DELAY_H = (0, 0.5, 1, 2)  # N/R Tender = ETA + 이 중 하나(시간)
LAYTIME_FACTOR = (1.0, 1.6)  # LayTime = (작업시간 + 3h) × 이 범위
LAYTIME_FACTOR_CRUDE = (1.6, 2.4)  # 원유선 (CFR False면 절반만 인정되므로 길게)
LAYTIME_ROUND_H = 6  # LayTime 올림 단위(시간)
DEMURRAGE_RATE_NOISE = (0.85, 1.15)  # 일 체선료 = DWT 구간 평균 × 이 범위
CFR_P = 0.5  # 원유선의 CFR True 확률
ALT_HISTORY_P = 0.8  # 접안 가능한 다른 부두마다 같은 자재 과거 실적이 있을 확률
ALT_BERTH_RATE = (0.8, 1.25)  # 다른 부두 처리 속도 = 목표 Rate × 이 범위 (부두 설비 차이)


@dataclass(frozen=True)
class VesselProfile:
    vessel_id: str
    vessel_code: str
    ship_class: str  # 탱커 등급 / LPG선
    dwt: float
    grt: float
    draft: float
    loa: float
    pbl: float
    cargo_group: str
    product_class: str
    vessel_type: str
    material_code: str
    qty: float
    work_hours: float
    demurrage_rate: float
    laycan_from: datetime
    laycan_to: datetime
    laycan_case: str  # 창 안 / 조기 / 지연 (생성 의도)
    nr_tender: datetime | None
    laytime: timedelta
    cfr: bool


@dataclass(frozen=True)
class SynthData:
    profiles: dict[str, VesselProfile]
    history: tuple[PastShipment, ...]
    seed: int
    weather: Forecast | None = None  # 시간별 풍속 예보 (data/dummy/weather.csv)

    def stops(self, berth: str) -> tuple:
        """그 부두의 기상 하역작업 중단 구간."""
        return self.weather.stops(berth) if self.weather is not None else ()


def _rng(seed: int, key: str) -> random.Random:
    return random.Random(f"{seed}:{key}")


def _pick_cargo(rng: random.Random, v: Vessel, groups: Sequence[ProductGroup]) -> ProductGroup:
    """부두의 접안 가능 제품 중 선박 방향(Biz)에 맞는 제품. 수입이고 원유가 가능하면 원유."""
    ok = [g for g in groups if matches(g.name, v.biz)]
    if not ok:
        raise ValueError(f"{v.vessel_id} ({v.biz}, #{v.berth}): 방향에 맞는 접안 가능 제품이 없음")
    crude = [g for g in ok if g.product_class == CRUDE_CLASS]
    others = [g for g in ok if g.product_class != CRUDE_CLASS]
    if v.biz == "IM" and crude:
        return rng.choice(crude)
    return rng.choice(others or crude)


def _laycan(rng: random.Random, eta: datetime) -> tuple[datetime, datetime, str]:
    day_end = time(23, 59)
    roll = rng.random()
    if roll < LAYCAN_IN_P:
        start = eta.date() - timedelta(days=rng.choice([0, 1]))
        case = "창 안"
    elif roll < LAYCAN_IN_P + LAYCAN_EARLY_P:
        start = eta.date() + timedelta(days=rng.choice([1, 2]))
        case = "조기 도착"
    else:
        start = eta.date() - timedelta(days=rng.choice([3, 4]))
        case = "지연 도착"
    return datetime.combine(start, time()), datetime.combine(start + timedelta(days=LAYCAN_WINDOW_DAYS), day_end), case


def synthesize(sequences: dict[str, list[Vessel]], master: MasterData, seed: int = SEED) -> SynthData:
    vessels = [v for seq in sequences.values() for v in seq]
    draft_profiles: dict[str, dict] = {}
    target_rates: dict[str, float] = {}
    history: list[PastShipment] = []
    hist_base = datetime(2026, 1, 1)

    for i, v in enumerate(vessels):
        rng = _rng(seed, v.vessel_id)
        cargo = _pick_cargo(rng, v, master.products[v.berth])
        ship = generate(master, v.berth, cargo.name, cargo.product_class, rng)
        dwt = ship.dwt
        material = f"MAT-{cargo.name}"
        code = f"VSL-{i + 1:03d}"
        work_hours = (v.stay - WORK_OVERHEAD).total_seconds() / 3600
        target_rate = dwt * rng.uniform(*LOAD_FACTOR) / work_hours
        target_rates[v.vessel_id] = target_rate

        # 과거 Shipment: 75%는 같은 선박코드, 25%는 다른 선박(같은 부두+자재)만
        own = rng.random() < OWN_HISTORY_P
        for k in range(rng.randint(1, 3) if own else rng.randint(2, 3)):
            hours = round(rng.uniform(4, 30) * 60) / 60  # 분 단위
            rate = target_rate * rng.uniform(*HISTORY_RATE_NOISE)
            start = hist_base + timedelta(days=rng.randint(0, 280), hours=rng.randint(0, 23))
            history.append(
                PastShipment(code if own else f"HIST-{i + 1:03d}-{k}", material, v.berth, start,
                             start + timedelta(hours=hours), round(rate * hours, 1))
            )

        is_crude = cargo.product_class == CRUDE_CLASS
        laycan_from, laycan_to, case = _laycan(rng, v.eta)
        nr = v.eta + timedelta(hours=rng.choice(NR_DELAY_H)) if rng.random() < NR_TENDER_P else None
        lay_factor = rng.uniform(*LAYTIME_FACTOR_CRUDE) if is_crude else rng.uniform(*LAYTIME_FACTOR)
        laytime_h = math.ceil((work_hours + 3) * lay_factor / LAYTIME_ROUND_H) * LAYTIME_ROUND_H
        draft_profiles[v.vessel_id] = dict(
            vessel_id=v.vessel_id, vessel_code=code, ship_class=ship.ship_class, dwt=dwt, grt=ship.grt,
            draft=ship.draft, loa=ship.loa, pbl=ship.pbl,
            cargo_group=cargo.name, product_class=cargo.product_class,
            vessel_type=master.vessel_type_by_class[cargo.product_class], material_code=material,
            work_hours=work_hours,
            demurrage_rate=round(master.bucket(dwt).demurrage_per_day * rng.uniform(*DEMURRAGE_RATE_NOISE), -2),
            laycan_from=laycan_from, laycan_to=laycan_to, laycan_case=case, nr_tender=nr,
            laytime=timedelta(hours=laytime_h), cfr=is_crude and rng.random() < CFR_P,
        )

    # 다른 부두 실적: 이 선박이 접안 가능한 다른 부두에 같은 자재의 과거 Shipment (다른 선박 기록)
    for i, v in enumerate(vessels):
        p = draft_profiles[v.vessel_id]
        alt_rng = _rng(seed, f"{v.vessel_id}:alt")
        dims = ShipDims(p["dwt"], p["loa"], p["pbl"], p["draft"], p["cargo_group"])
        for b in allowed_berths(dims, master):
            if b == v.berth or alt_rng.random() >= ALT_HISTORY_P:
                continue
            rate = target_rates[v.vessel_id] * alt_rng.uniform(*ALT_BERTH_RATE)
            for k in range(alt_rng.randint(1, 2)):
                hours = round(alt_rng.uniform(4, 30) * 60) / 60  # 분 단위
                start = hist_base + timedelta(days=alt_rng.randint(0, 280), hours=alt_rng.randint(0, 23))
                history.append(PastShipment(f"HIST-ALT-{i + 1:03d}-{b}-{k}", p["material_code"], b, start,
                                            start + timedelta(hours=hours), round(rate * hours, 1)))

    # QTY 역산: 조회 규칙(s2)이 실제로 고르는 평균 Rate로 계산해야 실제 ETU가 재현된다.
    # 부두+자재코드 조회(다른 선박 기록)로 QTY가 DWT를 넘으면 그 선박의 자체 기록을 하나 넣어
    # 선박코드 조회로 바뀌게 한다. 이 기록이 같은 부두+자재 다른 선박의 평균을 바꿀 수 있으므로 반복한다.
    def qty_of(vid: str) -> float:
        p = draft_profiles[vid]
        berth = p["vessel_id"].split("#")[0]
        return average_rate(history, p["vessel_code"], p["material_code"], berth).rate * p["work_hours"]

    for attempt in range(len(vessels)):
        over = [vid for vid, p in draft_profiles.items() if qty_of(vid) > p["dwt"] * QTY_DWT_CAP]
        if not over:
            break
        for vid in over:  # 시도마다 날짜·작업시간을 바꿔 같은 기록이 중복되지 않게
            p = draft_profiles[vid]
            hours = 8 + 3 * attempt
            start = hist_base + timedelta(days=290 + 7 * attempt, hours=6)
            history.append(PastShipment(p["vessel_code"], p["material_code"], vid.split("#")[0], start,
                                        start + timedelta(hours=hours), round(target_rates[vid] * hours, 1)))

    profiles = {vid: VesselProfile(qty=qty_of(vid), **p) for vid, p in draft_profiles.items()}
    vs = [v for seq in sequences.values() for v in seq]
    fc = synthesize_forecast(min(v.eta for v in vs).replace(hour=0, minute=0) - timedelta(days=1),
                             max(v.eta for v in vs) + timedelta(days=7), seed)
    return SynthData(profiles, tuple(history), seed, fc)
