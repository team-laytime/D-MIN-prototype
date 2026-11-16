"""ETB 이후 계산식 전체: ETB → 작업시작/완료 → ETU/호스분리 → ETANR → 정박개시 → 정박종료 → 체선료.

Alert에 걸리면 그 단계에서 CalcAlert를 낸다 (장표 흐름도처럼 이후 계산 중단).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..step3_berth_block import BerthBlock
from ..sun import ulsan_sunrise, ulsan_sunset
from .s1_work_start import work_start
from .s2_work_finish import PastShipment, RateResult, average_rate, work_finish
from .s3_etu import etu
from .s4_hose_off import hose_off
from .s5_etanr import etanr
from .s6_daylight import is_daylight
from .s7_laytime_start_no_daylight import LaytimeStart, laytime_start_no_daylight
from .s8_laytime_start_daylight import SunFn, laytime_start_daylight
from .s9_laytime_end import laytime_end
from .s10_weather_hours import weather_hours
from .s11_demurrage_time import demurrage_time
from .s12_demurrage_fee import demurrage_fee

CRUDE_VESSEL_TYPE = "원유선"


@dataclass(frozen=True)
class ShipmentPlan:
    etb: datetime | None  # ETB 산정(①~③) 결과
    berth: str | None
    vessel_code: str | None
    material_code: str
    qty: float
    vessel_type: str  # 원유선 / 석유제품선 / 특수제품선 / 윤활유제품선 / 화학제품선
    laycan_from: datetime
    laycan_to: datetime
    eta: datetime | None
    nr_tender: datetime | None = None
    planned_start: datetime | None = None  # 예상시작시간 (있으면 ETB + 1h 대신 사용)
    laytime: timedelta | None = None
    cfr: bool = False
    demurrage_rate: float | None = None  # 계약상 1일 체선료 ($/day)
    stops: tuple = ()  # 이 부두의 기상 하역작업 중단 구간 ((시작, 끝), …) — weather.Forecast.stops


@dataclass(frozen=True)
class AfterEtbResult:
    work_start: datetime
    rate: RateResult
    work_finish: datetime
    etu: datetime
    hose_off: datetime
    etanr: datetime
    daylight: bool
    laytime_start: LaytimeStart
    laytime_end: datetime
    weather: timedelta  # 기상체선 시간
    demurrage_time: timedelta
    demurrage_fee: float


def calc_after_etb(
    plan: ShipmentPlan,
    history: Sequence[PastShipment],
    blocks: Sequence[BerthBlock] = (),
    sunrise: SunFn = ulsan_sunrise,
    sunset: SunFn = ulsan_sunset,
) -> AfterEtbResult:
    start = work_start(plan.etb, plan.planned_start, plan.berth)
    rate = average_rate(history, plan.vessel_code, plan.material_code, plan.berth)
    finish = work_finish(start, plan.qty, rate, plan.stops)
    base = etanr(plan.nr_tender, plan.eta)
    daylight = is_daylight(plan.vessel_type)
    if daylight:
        lay_start = laytime_start_daylight(base, plan.etb, plan.laycan_from, plan.laycan_to, sunrise, sunset)
    else:
        lay_start = laytime_start_no_daylight(base, plan.etb, plan.laycan_from, plan.laycan_to)
    lay_end = laytime_end(lay_start.at, plan.laytime, plan.vessel_type == CRUDE_VESSEL_TYPE, plan.cfr)
    hose = hose_off(finish)
    weather = weather_hours(plan.berth, lay_end, hose, blocks)
    dem_time = demurrage_time(hose, lay_end, weather)
    fee = demurrage_fee(dem_time, plan.demurrage_rate)
    return AfterEtbResult(
        start, rate, finish, etu(finish), hose, base, daylight, lay_start, lay_end, weather, dem_time, fee
    )
