"""비용표: 접안 가능한 칸 (선박, 부두, 접안 시각)마다 '여기에 이때 접안하면' 나오는 결과와 체선료.

접안 가능 시각표(feasibility)에서 1인 칸만 계산한다. 계산은 ETB 이후 계산식을 그대로 쓴다
(after_etb.pipeline.calc_after_etb). 그 선박의 체선료는 자기 부두·접안 시각만으로 정해지고
다른 선박 배치와 무관하므로 미리 다 계산해 둘 수 있다 → CP-SAT 목표식의 계수로 쓴다.

속도: 과거 Shipment는 그 부두 + 자재 기록만 추려 넘긴다 (조회 규칙상 결과 동일).
"""

import csv
import math
from array import array
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .after_etb.pipeline import ShipmentPlan, calc_after_etb
from .feasibility import FeasibilityTable, Reason
from .step3_berth_block import BerthBlock
from .synth import SynthData

MIN = timedelta(minutes=1)


@dataclass(frozen=True)
class CostRow:
    """(선박, 부두) 한 쌍의 칸별 결과. 접안 불가 칸은 fee = -1. 시각은 표 시작 기준 분."""

    vessel_id: str
    berth: str
    fee: array  # $ (정수 반올림) — 표시용
    fee_c: array  # 센트 — CP-SAT 계산용 (54척 합계 오차가 $1 미만이 되도록)
    etu: array
    laytime_start: array
    laytime_end: array
    hose_off: array
    demurrage_min: array

    def feasible_slots(self) -> list[int]:
        return [i for i, f in enumerate(self.fee) if f >= 0]


def build_costs(
    table: FeasibilityTable, data: SynthData, blocks: Sequence[BerthBlock] = (),
) -> dict[tuple[str, str], CostRow]:
    vessels = {v.vessel_id: v for v in table.vessels}
    by_pair: dict[tuple[str, str], list] = {}
    for h in data.history:
        by_pair.setdefault((h.berth, h.material_code), []).append(h)

    out = {}
    for r in table.rows:
        if Reason.OK not in r.codes:
            continue
        v, p = vessels[r.vessel_id], data.profiles[r.vessel_id]
        hist = by_pair.get((r.berth, p.material_code), [])
        stops = data.stops(r.berth)  # 기상 하역작업 중단 구간 → 작업이 멈춘 만큼 ETU · 호스분리가 늦어짐
        cols = [array("i", [-1]) * table.n_slots for _ in range(6)]
        fee_c = array("q", [-1]) * table.n_slots
        for i, c in enumerate(r.codes):
            if c != Reason.OK:
                continue
            etb = table.time(i)
            plan = ShipmentPlan(
                etb=etb, berth=r.berth, vessel_code=p.vessel_code, material_code=p.material_code, qty=p.qty,
                vessel_type=p.vessel_type, laycan_from=p.laycan_from, laycan_to=p.laycan_to, eta=v.eta,
                nr_tender=p.nr_tender, laytime=p.laytime, cfr=p.cfr, demurrage_rate=p.demurrage_rate, stops=stops,
            )
            a = calc_after_etb(plan, hist, blocks)
            m = lambda t: math.ceil((t - table.start) / MIN)  # noqa: E731  분 올림 (초 단위 ETU를 버리면 다음 선박이 몇 초 일찍 들어올 수 있음)
            cols[0][i] = round(a.demurrage_fee)
            fee_c[i] = round(a.demurrage_fee * 100)
            cols[1][i], cols[2][i], cols[3][i], cols[4][i] = m(a.etu), m(a.laytime_start.at), m(a.laytime_end), m(a.hose_off)
            cols[5][i] = int(a.demurrage_time / MIN)
        out[(r.vessel_id, r.berth)] = CostRow(r.vessel_id, r.berth, cols[0], fee_c, *cols[1:])
    return out


def write_csv(table: FeasibilityTable, costs: dict[tuple[str, str], CostRow], path: Path) -> Path:
    """긴 표: 접안 가능한 칸 한 줄씩."""
    path.parent.mkdir(parents=True, exist_ok=True)
    t = lambda m: f"{table.start + m * MIN:%Y-%m-%d %H:%M}"  # noqa: E731
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["vessel_id", "berth", "etb", "etu", "laytime_start", "laytime_end", "hose_off", "demurrage_h", "fee_usd"])
        for c in costs.values():
            for i in c.feasible_slots():
                w.writerow([c.vessel_id, c.berth, f"{table.time(i):%Y-%m-%d %H:%M}", t(c.etu[i]), t(c.laytime_start[i]),
                            t(c.laytime_end[i]), t(c.hose_off[i]), round(c.demurrage_min[i] / 60, 2), c.fee[i]])
    return path


def fee_at(costs: dict[tuple[str, str], CostRow], table: FeasibilityTable, vessel_id: str, berth: str,
           etb: datetime) -> int:
    return costs[(vessel_id, berth)].fee[int((etb - table.start) / table.step)]
