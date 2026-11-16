"""부두 적합성: 선박 제원으로 접안 가능한 부두를 거른다 (장표 13p '부두 정보' + 녹취).

비교 항목 (부두 제원이 비어 있거나 '-'면 그 항목은 비교하지 않음)
  DWT    : 선박 DWT <= 부두 Max DWT, Buoy는 선박 DWT >= Min DWT (공개 제원표 80,000)
  LOA    : 부두 Min LOA <= 선박 LOA <= 부두 Max LOA
  PBL    : 선박 PBL >= 부두 Min PBL (평행부가 짧으면 펜더에 닿지 않음)
  Draft  : 선박 Draft <= 부두 Max Draft  — 수입·수출 모두 비교 (현업 확인: 장표의 '수입만'보다 넓게)
  제품   : 화물 제품 그룹이 그 부두의 접안 가능 제품 그룹에 포함
Depth(수심)는 Max Draft에 이미 반영되어 있으므로 비교하지 않는다.
"""

from dataclasses import dataclass

from .master_data import BerthSpec, MasterData


@dataclass(frozen=True)
class ShipDims:
    dwt: float
    loa: float
    pbl: float
    draft: float
    cargo_group: str | None = None


def misfit_reasons(ship: ShipDims, spec: BerthSpec, allowed_cargo: set[str] | None = None) -> list[str]:
    """접안 불가 사유 목록. 비어 있으면 접안 가능."""
    r = []
    if ship.dwt > spec.max_dwt:
        r.append(f"DWT {ship.dwt:,.0f} > Max {spec.max_dwt:,.0f}")
    if spec.min_dwt is not None and ship.dwt < spec.min_dwt:
        r.append(f"DWT {ship.dwt:,.0f} < Min {spec.min_dwt:,.0f}")
    if spec.max_loa is not None and ship.loa > spec.max_loa:
        r.append(f"LOA {ship.loa:g} > Max {spec.max_loa:g}")
    if spec.min_loa is not None and ship.loa < spec.min_loa:
        r.append(f"LOA {ship.loa:g} < Min {spec.min_loa:g}")
    if spec.min_pbl is not None and ship.pbl < spec.min_pbl:
        r.append(f"PBL {ship.pbl:g} < Min {spec.min_pbl:g}")
    if ship.draft > spec.max_draft:
        r.append(f"Draft {ship.draft:g} > Max {spec.max_draft:g}")
    if allowed_cargo is not None and ship.cargo_group is not None and ship.cargo_group not in allowed_cargo:
        r.append(f"제품 {ship.cargo_group} 접안 불가")
    return r


def fits(ship: ShipDims, berth: str, master: MasterData) -> list[str]:
    return misfit_reasons(ship, master.berths[berth], {g.name for g in master.products.get(berth, ())})


def compatible_berths(ship: ShipDims, master: MasterData) -> dict[str, list[str]]:
    """부두별 접안 불가 사유. 사유가 빈 부두가 접안 가능 부두."""
    return {b: fits(ship, b, master) for b in master.berths}


def allowed_berths(ship: ShipDims, master: MasterData) -> list[str]:
    return [b for b, reasons in compatible_berths(ship, master).items() if not reasons]
