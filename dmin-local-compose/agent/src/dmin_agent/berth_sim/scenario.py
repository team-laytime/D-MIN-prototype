"""시나리오 1개 전체 평가: 실제 접안계획 + (가상) 선박·계약 정보 → ETB 산정 ①②③ → ETB 이후 계산 → 체선료 합계.

ETB 산정과 ETB 이후 계산의 연결
  ETB 산정(step1~3)은 부두 점유시간(stay = ETU - ETB)이 필요하다. 이 값을 입력으로 받지 않고
  ETB 이후 계산식(작업시작 ETB+1h → 평균 Rate로 작업완료 → ETU = 작업완료+2h)으로 구한다.
  작업시작이 ETB+1h로 정해지면 점유시간은 ETB와 무관하므로 미리 한 번 계산해 둘 수 있다.

평가 방식 두 가지
  baseline : 실제 접안계획의 ETB를 그대로 쓴다 (현행 계획의 체선료)
  rules    : ETB를 ①+②+③ 규칙으로 다시 산정한다
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .after_etb.common import CalcAlert
from .after_etb.pipeline import AfterEtbResult, ShipmentPlan, calc_after_etb
from .after_etb.s1_work_start import ETB_TO_START
from .after_etb.s2_work_finish import PastShipment, average_rate, work_finish
from .after_etb.s3_etu import etu
from .berth_availability import make_availability_adjuster
from .models import Vessel
from .step1_prev_fix import Step1Result, schedule
from .step2_night_pilot import make_night_pilot_adjuster
from .step3_berth_block import BerthBlock, make_berth_block_adjuster
from .step3_berth_pair import make_berth_pair_adjuster
from .step3_cargo_group import make_cargo_group_adjuster
from .synth import SynthData, VesselProfile
from .weather import wind_blocks

_ANCHOR = datetime(2000, 1, 1)


def occupancy(p: VesselProfile, berth: str, history: Sequence[PastShipment]) -> timedelta:
    """기상 중단이 없을 때의 부두 점유시간 = ETU - ETB (ETB 이후 계산식 s1~s3로 계산)."""
    rate = average_rate(history, p.vessel_code, p.material_code, berth)
    return etu(work_finish(_ANCHOR + ETB_TO_START, p.qty, rate)) - _ANCHOR


def stay_function(p: VesselProfile, berth: str, data: SynthData):
    """ETB → 부두 점유시간. 그 부두의 기상 하역 중단 구간에는 작업이 멈춰 그만큼 길어진다."""
    stops = data.stops(berth)
    if not stops:
        return None
    rate = average_rate(data.history, p.vessel_code, p.material_code, berth)

    def stay_at(etb: datetime) -> timedelta:
        return etu(work_finish(etb + ETB_TO_START, p.qty, rate, stops)) - etb

    return stay_at


def build_sequences(
    sequences: dict[str, list[Vessel]], data: SynthData
) -> dict[str, list[Vessel]]:
    """실제 접안 순서에 GRT/Draft/화물 그룹을 붙이고 점유시간을 계산식으로 바꾼다."""
    out = {}
    for berth, seq in sequences.items():
        out[berth] = [
            replace(
                v, grt=(p := data.profiles[v.vessel_id]).grt, draft=p.draft, cargo_group=p.cargo_group,
                stay=occupancy(p, berth, data.history), stay_at=stay_function(p, berth, data),
            )
            for v in seq
        ]
    return out


def all_blocks(blocks: Sequence[BerthBlock], data: SynthData, berths) -> list[BerthBlock]:
    """사용자 부두 제약 + 풍속 예보의 접안 불가(이안 기준) 구간."""
    return [*blocks, *wind_blocks(data.weather, berths)]


def make_adjusters(blocks: Sequence[BerthBlock] = (), available_from: dict[str, datetime] | None = None):
    return [
        *([make_availability_adjuster(available_from)] if available_from else []),
        make_night_pilot_adjuster(),
        make_cargo_group_adjuster(),
        make_berth_pair_adjuster(),
        make_berth_block_adjuster(blocks),
    ]


@dataclass(frozen=True)
class VesselOutcome:
    vessel: Vessel
    profile: VesselProfile
    etb: datetime
    etb_notes: tuple[str, ...]
    berthable: bool
    after: AfterEtbResult | None
    alert: str | None
    rule: str | None = None  # ① DIRECTION / SWITCHING (규칙 재산정일 때)

    @property
    def fee(self) -> float:
        return self.after.demurrage_fee if self.after else 0.0


@dataclass(frozen=True)
class ScenarioResult:
    label: str
    outcomes: tuple[VesselOutcome, ...]

    @property
    def total_fee(self) -> float:
        return sum(o.fee for o in self.outcomes)

    @property
    def feasible(self) -> bool:
        return all(o.berthable for o in self.outcomes)

    def by_id(self) -> dict[str, VesselOutcome]:
        return {o.vessel.vessel_id: o for o in self.outcomes}


def _after(v: Vessel, p: VesselProfile, etb: datetime, data: SynthData, blocks) -> tuple[AfterEtbResult | None, str | None]:
    plan = ShipmentPlan(
        etb=etb, berth=v.berth, vessel_code=p.vessel_code, material_code=p.material_code, qty=p.qty,
        vessel_type=p.vessel_type, laycan_from=p.laycan_from, laycan_to=p.laycan_to, eta=v.eta,
        nr_tender=p.nr_tender, laytime=p.laytime, cfr=p.cfr, demurrage_rate=p.demurrage_rate,
        stops=data.stops(v.berth),
    )
    try:
        return calc_after_etb(plan, data.history, blocks), None
    except CalcAlert as e:
        return None, str(e)


def evaluate_rules(
    sequences: dict[str, list[Vessel]], data: SynthData, blocks: Sequence[BerthBlock] = (), label: str = "규칙 재산정",
    available_from: dict[str, datetime] | None = None,
) -> ScenarioResult:
    seqs = build_sequences(sequences, data)
    berths = set(available_from or {}) | set(sequences)
    results: dict[str, list[Step1Result]] = schedule(seqs, make_adjusters(all_blocks(blocks, data, berths), available_from))
    outcomes = []
    for rows in results.values():
        for r in rows:
            p = data.profiles[r.vessel_id]
            after, alert = _after(r.vessel, p, r.etb, data, blocks)
            outcomes.append(VesselOutcome(r.vessel, p, r.etb, r.notes, r.berthable, after, alert, r.rule.value))
    return ScenarioResult(label, tuple(outcomes))


def evaluate_fixed_etb(
    sequences: dict[str, list[Vessel]], etbs: dict[str, datetime], data: SynthData,
    blocks: Sequence[BerthBlock] = (), label: str = "실제 계획",
) -> ScenarioResult:
    seqs = build_sequences(sequences, data)
    outcomes = []
    for seq in seqs.values():
        for v in seq:
            p = data.profiles[v.vessel_id]
            after, alert = _after(v, p, etbs[v.vessel_id], data, blocks)
            outcomes.append(VesselOutcome(v, p, etbs[v.vessel_id], (), True, after, alert))
    return ScenarioResult(label, tuple(outcomes))
