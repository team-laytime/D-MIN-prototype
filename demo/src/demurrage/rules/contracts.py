"""계약서 — 계산에 쓰는 계약 조건을 계약서 문서(data/contracts/*.json)에서 읽는다 (FR-26, NFR-04).

계약서 하나 = 사람이 읽는 문서(당사자·조항 원문·리캡) + 엔진이 읽는 조건(terms).
조항마다 'rules'에 엔진 규칙 ID를 적어 두면, 계산서의 근거 칸에 "계약서 CT-2611-05 제10조"처럼 조항이 그대로 붙는다.
모든 계약서는 가상 예시다(실제 계약이 아님).
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from ..domain.model import Contract
from ..domain.timeutil import hours_to_min, parse_ts


def load_contracts(data_dir: Path) -> dict:
    out = {}
    d = Path(data_dir) / "contracts"
    if not d.exists():
        return out
    for p in sorted(d.glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        out[doc["id"]] = doc
    return out


def clause_refs(doc: dict) -> tuple:
    """규칙 ID → 그 규칙을 정한 조항들(계약서에 적힌 순서). ((규칙 ID, (조항, …)), …)"""
    m = {}
    for c in doc.get("clauses", []):
        for rid in c.get("rules", []):
            m.setdefault(rid, [])
            if c["ref"] not in m[rid]:
                m[rid].append(c["ref"])
    return tuple(sorted((rid, tuple(v)) for rid, v in m.items()))


def contract_from_doc(doc: dict, qty: float, nor_tender) -> Contract:
    t = doc["terms"]
    lay = t["laytime"]
    full = Fraction(str(lay["hours"]))
    basis = f"{lay['hours']:g}시간 {lay.get('basis', '')}".strip()
    if lay.get("pro_rata") and lay.get("full_qty"):
        hours = full * Fraction(str(qty)) / Fraction(str(lay["full_qty"]))
        basis = (f"전량 {lay['hours']:g}시간 × 선적 {qty:,.0f} ÷ 계약 {lay['full_qty']:,.0f} "
                 f"= {float(hours):g}시간 (부분 화물 비례)")
    else:
        hours = full
    ratio = t.get("weather_deduction_ratio")
    return Contract(
        type=doc["type"], laytime_h=hours, rate_usd_day=int(t["demurrage_rate_usd_day"]),
        laycan_from=parse_ts(doc["laycan"]["from"]), laycan_to=parse_ts(doc["laycan"]["to"], end_of_day=True),
        nor_tender=nor_tender, id=doc["id"], title=doc.get("title", ""),
        counterparty=next((p["name"] for p in doc.get("parties", []) if p.get("counterparty")), ""),
        notice_min=hours_to_min(t["notice_hours"]) if t.get("notice_hours") is not None else None,
        weather_ratio=Fraction(str(ratio)) if ratio is not None else None,
        daylight_nor=t.get("daylight_nor"), laytime_basis=basis, refs=clause_refs(doc))


def contract_summary(doc: dict) -> dict:
    """목록·화면용 요약."""
    t = doc["terms"]
    lay = t["laytime"]
    return {
        "id": doc["id"], "title": doc.get("title"), "kind": doc.get("kind"), "type": doc["type"],
        "signed_on": doc.get("signed_on"), "vessel": doc.get("vessel", {}).get("name"),
        "vessel_class": doc.get("vessel", {}).get("class"),
        "counterparty": next((p["name"] for p in doc.get("parties", []) if p.get("counterparty")), ""),
        "laycan": doc["laycan"], "laytime_hours": lay["hours"], "pro_rata": bool(lay.get("pro_rata")),
        "rate_usd_day": t["demurrage_rate_usd_day"], "notice_hours": t.get("notice_hours"),
        "weather_deduction_ratio": t.get("weather_deduction_ratio"), "daylight_nor": t.get("daylight_nor"),
        "payer_note": doc.get("payer_note", ""),
    }
