"""평균 Rate 산출, 작업완료시간 산출.

장표 원문
  * 선박코드, 자재코드, 부두 일치하는 과거 Shipment를 찾는다.
  * 일치하는 과거 Shipment를 찾지 못했을 때는 부두, 자재코드를 가지고(선박코드 제외) 과거 데이터들을 찾는다.
  * 과거 작업시작시간/종료시간/총 작업량을 가지고 평균 Rate 산출해서 현재 Shipment의 QTY를 이용해 예상 작업시간을 산출한다.

구현 해석 (현업 확인 필요)
- 평균 Rate = 과거 Shipment별 (작업량 / 작업시간) 의 산술평균 [단위: QTY/h].
  (총 작업량 / 총 작업시간 가중평균으로 바꿀 수도 있다.)
- 작업시간이 0 이하인 과거 기록은 제외한다.
- 두 단계 조회 모두 없으면 장표에 정의가 없으므로 Alert를 낸다.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from .common import ALERT_NO_HISTORY, CalcAlert


@dataclass(frozen=True)
class PastShipment:
    vessel_code: str
    material_code: str
    berth: str
    work_start: datetime
    work_end: datetime
    qty: float

    @property
    def hours(self) -> float:
        return (self.work_end - self.work_start).total_seconds() / 3600


@dataclass(frozen=True)
class RateResult:
    rate: float  # QTY / h
    basis: str  # "선박코드+자재코드+부두" 또는 "부두+자재코드"
    sample_count: int


def find_past(
    history: Sequence[PastShipment], vessel_code: str | None, material_code: str, berth: str
) -> tuple[list[PastShipment], str]:
    usable = [h for h in history if h.hours > 0]
    exact = [h for h in usable if (h.vessel_code, h.material_code, h.berth) == (vessel_code, material_code, berth)]
    if exact:
        return exact, "선박코드+자재코드+부두"
    return [h for h in usable if (h.material_code, h.berth) == (material_code, berth)], "부두+자재코드"


def average_rate(
    history: Sequence[PastShipment], vessel_code: str | None, material_code: str, berth: str
) -> RateResult:
    records, basis = find_past(history, vessel_code, material_code, berth)
    if not records:
        raise CalcAlert(ALERT_NO_HISTORY)
    rate = sum(r.qty / r.hours for r in records) / len(records)
    return RateResult(rate, basis, len(records))


def work_finish(start: datetime, qty: float, rate: RateResult,
                stops: Sequence[tuple[datetime, datetime]] = ()) -> datetime:
    """작업완료 = 작업시작 + QTY / 평균 Rate.

    작업 중 기상 중단을 만나면 호스를 분리하고, 기상 회복 뒤 다시
    연결·준비한 다음 남은 작업을 이어서 한다.
    """
    return pump_finish(start, timedelta(hours=qty / rate.rate), stops)


HOSE_DISCONNECT = timedelta(minutes=30)
HOSE_RECONNECT = timedelta(hours=1)
WEATHER_RESTART_OVERHEAD = HOSE_DISCONNECT + HOSE_RECONNECT


def _merged_stops(stops: Sequence[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """겹치거나 맞닿은 중단 구간을 합쳐 호스 작업을 중복 계산하지 않는다."""
    merged: list[list[datetime]] = []
    for s, e in sorted(stops):
        if e <= s:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def pump_finish(start: datetime, work: timedelta, stops: Sequence[tuple[datetime, datetime]] = ()) -> datetime:
    """start부터 실제 작업 시간 work를 채우는 시각.

    실제 펌핑 도중 기상 중단을 만나면 중단 구간에 더해 호스 분리 30분과
    재연결·작업준비 1시간을 건너뛴다. 작업 시작 전부터 진행 중인 기상
    중단에는 분리할 호스가 없으므로 재시작 시간을 추가하지 않는다.
    """
    t, left = start, work
    for s, e in _merged_stops(stops):
        if e <= t:
            continue
        if s > t:
            if left <= s - t:
                return t + left
            left -= s - t
            t = e + WEATHER_RESTART_OVERHEAD
        else:
            t = e
    return t + left


def pumped(start: datetime, until: datetime, stops: Sequence[tuple[datetime, datetime]] = ()) -> timedelta:
    """start ~ until 사이 실제 펌핑 시간 (기상 및 호스 재시작 작업 제외)."""
    if until <= start:
        return timedelta()
    total, t = timedelta(), start
    for s, e in _merged_stops(stops):
        if e <= t:
            continue
        if s > t:
            pump_to = min(s, until)
            if pump_to > t:
                total += pump_to - t
            if until <= s:
                return total
            t = e + WEATHER_RESTART_OVERHEAD
        else:
            t = e
        if until <= t:
            return total
    if until > t:
        total += until - t
    return total
