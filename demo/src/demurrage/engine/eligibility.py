"""부두 적합성 (FR-07 제원, FR-08 화물 그룹).

ELG-01: DWT ≤ 최대, 최소 LOA ≤ LOA ≤ 최대 LOA, PBL ≥ 최소 PBL, (수입선만) Draft ≤ 최대 Draft
ELG-02: 화물 그룹을 취급하는 부두만
맞지 않는 부두는 '왜 빠졌는지'를 남긴다(근거 조회에 그대로 보인다).
"""
from __future__ import annotations

from ..domain.model import Berth, Vessel


def check_berth(v: Vessel, b: Berth) -> list:
    """맞지 않는 이유 목록. 빈 목록이면 배정 가능."""
    reasons = []
    if v.cargo_group not in b.cargo_groups:
        reasons.append({"rule_id": "ELG-02", "item": "화물 그룹",
                        "message": f"{b.id}는 {v.cargo_group}을(를) 취급하지 않음 (취급: {', '.join(b.cargo_groups)})"})
    if v.dwt > b.max_dwt:
        reasons.append({"rule_id": "ELG-01", "item": "최대 DWT", "message": f"DWT {v.dwt:,} > {b.id} 최대 {b.max_dwt:,}"})
    if v.loa > b.max_loa:
        reasons.append({"rule_id": "ELG-01", "item": "최대 LOA", "message": f"LOA {v.loa:g} m > {b.id} 최대 {b.max_loa:g} m"})
    if v.loa < b.min_loa:
        reasons.append({"rule_id": "ELG-01", "item": "최소 LOA", "message": f"LOA {v.loa:g} m < {b.id} 최소 {b.min_loa:g} m"})
    if v.pbl < b.min_pbl:
        reasons.append({"rule_id": "ELG-01", "item": "최소 PBL", "message": f"PBL {v.pbl:g} m < {b.id} 최소 {b.min_pbl:g} m"})
    if v.direction == "IMPORT" and v.draft > b.max_draft:
        reasons.append({"rule_id": "ELG-01", "item": "최대 Draft", "message": f"수입선 Draft {v.draft:g} m > {b.id} 최대 {b.max_draft:g} m"})
    return reasons


def eligible_berths(v: Vessel, berths: dict, order: list, active=None) -> tuple:
    """(배정 가능 부두 목록, {부두: 제외 이유})."""
    ok, excluded = [], {}
    for bid in order:
        b = berths[bid]
        if active and bid not in active:
            excluded[bid] = [{"rule_id": "SCN", "item": "시나리오 부두", "message": "이 시나리오에서 쓰지 않는 부두"}]
            continue
        if v.allowed_berths and bid not in v.allowed_berths:
            excluded[bid] = [{"rule_id": "SCN", "item": "지정 부두", "message": f"지정 부두({', '.join(v.allowed_berths)})가 아님"}]
            continue
        r = check_berth(v, b)
        if r:
            excluded[bid] = r
        else:
            ok.append(bid)
    return ok, excluded
