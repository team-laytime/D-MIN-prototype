"""작업 시각 산정 (FR-22 작업시작·완료·호스분리·ETU, FR-23 작업시간 추정).

PPT 09쪽:
  작업완료 = 작업시작 + 작업시간, 작업시간 = QTY ÷ (과거 Shipment 평균 Rate)
  호스분리 = 작업완료 + Term, Term = 과거 (호스분리 − 작업완료)의 최빈값
  매칭: ① 선박코드·자재코드·부두가 같은 실적 → ② 없으면 자재코드·부두가 같은 실적
  둘 다 없으면 입력 오류 (작업시간·호스분리 소요시간을 입력해야 한다)
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Optional

from ..domain.money import round_half_up
from ..domain.timeutil import hours_to_min, parse_ts


@dataclass(frozen=True)
class Shipment:
    vessel_code: str
    material_code: str
    berth: str
    work_start: int
    work_end: int
    qty: float
    hose_off: int


def load_history(path: Path) -> list:
    rows = []
    if not path or not Path(path).exists():
        return rows
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(Shipment(
                vessel_code=r["vessel_code"].strip(), material_code=r["material_code"].strip(), berth=r["berth"].strip(),
                work_start=parse_ts(r["work_start"]), work_end=parse_ts(r["work_end"]), qty=float(r["qty"]),
                hose_off=parse_ts(r["hose_off"])))
    return rows


@dataclass(frozen=True)
class WorkPlan:
    """(선박, 부두)별 작업 소요. 모두 분."""
    start_delay: int
    work: int
    hose_term: int
    etu_after_work: int
    basis: dict

    @property
    def etb_to_etu(self) -> int:
        return self.start_delay + self.work + self.etu_after_work

    @property
    def etb_to_hose(self) -> int:
        return self.start_delay + self.work + self.hose_term

    @property
    def etb_to_work_end(self) -> int:
        return self.start_delay + self.work


class WorkModel:
    def __init__(self, history: list, etu_after_work_min: int, default_delay_min: int):
        self.history = history
        self.etu_after = etu_after_work_min
        self.default_delay = default_delay_min

    def _match(self, vessel_code: str, material: str, berth: str):
        first = [s for s in self.history if s.vessel_code == vessel_code and s.material_code == material and s.berth == berth]
        if first:
            return "1차 매칭(선박·자재·부두)", first
        second = [s for s in self.history if s.material_code == material and s.berth == berth]
        if second:
            return "2차 매칭(자재·부두)", second
        return None, []

    def plan(self, v, berth_id: str) -> Optional[WorkPlan]:
        """작업 소요를 정한다. 정할 수 없으면 None(입력 오류)."""
        code = getattr(v, "vessel_code", None) or v.id
        basis = {}
        if v.work_hours is not None:
            work = hours_to_min(v.work_hours)
            basis["work"] = {"stage": "입력값", "hours": str(v.work_hours)}
        else:
            stage, rows = self._match(code, v.material_code, berth_id)
            if not rows:
                return None
            tot_qty = sum(r.qty for r in rows)
            tot_min = sum(r.work_end - r.work_start for r in rows)
            rate_per_h = Fraction(str(tot_qty)) / (Fraction(tot_min) / 60)
            work = round_half_up(Fraction(str(v.qty)) / rate_per_h * 60)
            basis["work"] = {"stage": stage, "records": len(rows), "rate_per_h": float(round(rate_per_h, 1)),
                             "qty": v.qty, "hours": round(work / 60, 2)}
        if v.hose_term_h is not None:
            term = hours_to_min(v.hose_term_h)
            basis["hose"] = {"stage": "입력값", "hours": str(v.hose_term_h)}
        else:
            stage, rows = self._match(code, v.material_code, berth_id)
            if not rows:
                return None
            terms = Counter(r.hose_off - r.work_end for r in rows)
            top = max(terms.values())
            term = min(t for t, c in terms.items() if c == top)  # 최빈값, 동률이면 짧은 쪽
            basis["hose"] = {"stage": stage, "records": len(rows), "mode_minutes": term, "count": top}
        delay = v.work_start_delay_min if v.work_start_delay_min is not None else self.default_delay
        return WorkPlan(start_delay=delay, work=work, hose_term=term, etu_after_work=self.etu_after, basis=basis)
