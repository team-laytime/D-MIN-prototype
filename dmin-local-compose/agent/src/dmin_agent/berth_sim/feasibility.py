"""접안 가능 여부 표: 선박 × 부두 × 시각(5분 단위) → 1(접안 가능) / 0(불가) + 불가 사유.

칸 하나의 의미
  "이 선박이 이 부두에 이 시각에 접안(ETB)을 시작할 수 있는가"

반영하는 조건 — 선박 한 척과 부두 · 시각만으로 정해지는 것 (경우의 수를 뽑기 전 1차 필터)
  1 MISFIT          부두 적합성 (DWT · LOA · PBL · Draft · 제품)          berth_fit
  2 NO_HISTORY      그 부두 과거 Shipment 없음 → 작업시간(평균 Rate) 산출 불가  s2_work_finish
  3 BEFORE_ARRIVAL  ETA + Direction 이전 (아직 도착·이동 전)              ① shifting
  4 NOT_AVAILABLE   부두 사용 가능 시각 이전 (데이터 범위)                 berth_availability
  5 NIGHT_PILOT     야간 도선 제한 (02~08시, Last POB 이후 도착)           ②
  6 BERTH_BLOCK     사용자 설정 부두 제약 (기상 · 공사 · 설비)              ③-3
  7 FIX_CONFLICT    FIX 선박과 충돌 (같은 부두 점유 / 동일 화물 / #4 동시 접안) ① · ③-1 · ③-2
  8 WIND            풍속 예보 접안 불가(이안 기준) 구간이 접안 기간 [ETB, ETU)와 겹침  weather
  (하역작업 중단 구간은 접안 가능 — 작업이 멈춰 ETU가 늦어지는 것으로 반영)

반영하지 않는 조건 — 다른 선박을 어디에 넣느냐에 따라 달라지는 것 (경우의 수 조합 단계에서 판정)
  같은 부두 앞 선박의 점유(Switching), FIX가 아닌 선박과의 동일 화물 그룹 · #4 동시 접안

시간 판정은 기존 규칙 조정기를 그대로 쓴다: 조정기가 그 시각을 미루지 않으면 통과.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import IntEnum
from functools import cached_property

from .after_etb.s2_work_finish import find_past
from .berth_availability import make_availability_adjuster
from .berth_fit import fits
from .master_data import MasterData
from .models import Vessel
from .scenario import occupancy, stay_function
from .weather import wind_blocks
from .shifting import direction, switching
from .step1_prev_fix import EtbRule, Step1Result
from .step2_night_pilot import make_night_pilot_adjuster
from .step3_berth_block import BerthBlock, make_berth_block_adjuster
from .step3_berth_pair import make_berth_pair_adjuster
from .step3_cargo_group import make_cargo_group_adjuster
from .synth import SynthData
from .validate import dims_of

SLOT = timedelta(minutes=5)
HORIZON_TAIL = timedelta(days=1)  # 실제 마지막 ETU 이후로 더 보는 기간


class Reason(IntEnum):
    OK = 0
    MISFIT = 1
    NO_HISTORY = 2
    BEFORE_ARRIVAL = 3
    NOT_AVAILABLE = 4
    NIGHT_PILOT = 5
    BERTH_BLOCK = 6
    FIX_CONFLICT = 7
    WIND = 8


REASON_LABEL = {
    Reason.OK: "접안 가능",
    Reason.MISFIT: "부두 부적합",
    Reason.NO_HISTORY: "과거 실적 없음",
    Reason.BEFORE_ARRIVAL: "도착 전 (ETA + Direction)",
    Reason.NOT_AVAILABLE: "부두 사용 가능 시각 전",
    Reason.NIGHT_PILOT: "야간 도선 제한",
    Reason.BERTH_BLOCK: "부두 제약 (기상·공사·설비)",
    Reason.FIX_CONFLICT: "FIX 선박과 충돌",
    Reason.WIND: "강풍·태풍 (이안 기준, 접안 기간과 겹침)",
}


@dataclass(frozen=True)
class Row:
    vessel_id: str
    berth: str
    stay: timedelta | None  # 이 부두에서의 점유시간 (ETB → ETU). 계산 불가면 None
    codes: bytes  # 시각 칸마다 Reason 값
    detail: str  # 정적 불가 사유(부적합 사유 등)

    def feasible(self) -> list[int]:
        return [1 if c == Reason.OK else 0 for c in self.codes]

    def windows(self) -> list[tuple[int, int]]:
        """접안 가능한 연속 구간 [시작 칸, 끝 칸) 목록."""
        out, start = [], None
        for i, c in enumerate(self.codes):
            if c == Reason.OK and start is None:
                start = i
            elif c != Reason.OK and start is not None:
                out.append((start, i))
                start = None
        if start is not None:
            out.append((start, len(self.codes)))
        return out


@dataclass(frozen=True)
class FeasibilityTable:
    start: datetime
    step: timedelta
    n_slots: int
    berths: tuple[str, ...]
    vessels: tuple[Vessel, ...]
    rows: tuple[Row, ...]

    def time(self, i: int) -> datetime:
        return self.start + self.step * i

    def row(self, vessel_id: str, berth: str) -> Row:
        return self._index[(vessel_id, berth)]

    @cached_property
    def _index(self) -> dict[tuple[str, str], Row]:
        return {(r.vessel_id, r.berth): r for r in self.rows}


def _floor(t: datetime, step: timedelta) -> datetime:
    base = datetime(t.year, t.month, t.day)
    return base + step * ((t - base) // step)


def build_table(
    sequences: dict[str, list[Vessel]], data: SynthData, master: MasterData,
    available_from: dict[str, datetime] | None = None, blocks: Sequence[BerthBlock] = (),
    start: datetime | None = None, end: datetime | None = None, step: timedelta = SLOT,
) -> FeasibilityTable:
    vessels = [v for seq in sequences.values() for v in seq]
    if start is None:
        start = min(available_from.values()) if available_from else min(v.eta for v in vessels)
    if end is None:
        end = max(v.eta for v in vessels) + max(v.stay for v in vessels) + HORIZON_TAIL
    start, n = _floor(start, step), int((end - _floor(start, step)) / step) + 1

    night = make_night_pilot_adjuster()
    block = make_berth_block_adjuster(blocks)
    wind = make_berth_block_adjuster(wind_blocks(data.weather, master.berths))
    avail = make_availability_adjuster(available_from or {})
    cargo, pair = make_cargo_group_adjuster(), make_berth_pair_adjuster()

    # FIX 선박은 위치가 정해져 있으므로 다른 선박의 1차 필터에 넣는다
    fixed = []
    for v in vessels:
        if v.is_fix:
            p = data.profiles[v.vessel_id]
            fv = replace(v, grt=p.grt, draft=p.draft, cargo_group=p.cargo_group, stay=occupancy(p, v.berth, data.history),
                         stay_at=stay_function(p, v.berth, data))
            fixed.append(Step1Result(fv, v.fixed_etb, v.fixed_etb + fv.stay_for(v.fixed_etb), EtbRule.FIXED, None, True, "FIX"))

    times = [start + step * i for i in range(n)]
    rows = []
    for v in vessels:
        p = data.profiles[v.vessel_id]
        for b in master.berths:
            misfit = fits(dims_of(p), b, master)
            if misfit:
                rows.append(Row(v.vessel_id, b, None, bytes([Reason.MISFIT]) * n, ", ".join(misfit)))
                continue
            if b != v.berth and not find_past(data.history, p.vessel_code, p.material_code, b)[0]:
                rows.append(Row(v.vessel_id, b, None, bytes([Reason.NO_HISTORY]) * n, "과거 Shipment 없음"))
                continue
            stay = occupancy(p, b, data.history)
            vb = replace(v, berth=b, grt=p.grt, draft=p.draft, cargo_group=p.cargo_group, stay=stay,
                         stay_at=stay_function(p, b, data))
            if v.is_fix:
                codes = bytes(Reason.OK if (b == v.berth and t == v.fixed_etb) else Reason.FIX_CONFLICT for t in times)
                rows.append(Row(v.vessel_id, b, stay, codes, "FIX 선박: 고정 ETB만 가능"))
                continue
            earliest = v.eta + direction(b)
            sw = switching(b)
            others = [f for f in fixed if f.vessel_id != v.vessel_id]
            same = [f for f in others if f.berth == b]
            codes = bytearray(n)
            for i, t in enumerate(times):
                if t < earliest:
                    codes[i] = Reason.BEFORE_ARRIVAL
                elif avail(vb, t, ())[0] != t:
                    codes[i] = Reason.NOT_AVAILABLE
                elif night(vb, t, ())[0] != t:
                    codes[i] = Reason.NIGHT_PILOT
                elif block(vb, t, ())[0] != t:
                    codes[i] = Reason.BERTH_BLOCK
                elif wind(vb, t, ())[0] != t:
                    codes[i] = Reason.WIND
                elif others and (
                    any(not (t >= f.etu + sw or t + vb.stay_for(t) + sw < f.etb) for f in same)
                    or cargo(vb, t, others)[0] != t or pair(vb, t, others)[0] != t
                ):
                    codes[i] = Reason.FIX_CONFLICT
            rows.append(Row(v.vessel_id, b, stay, bytes(codes), ""))
    return FeasibilityTable(start, step, n, tuple(master.berths), tuple(vessels), tuple(rows))
