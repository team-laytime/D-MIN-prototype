"""가상 선박을 만드는 틀 — 제원은 샘플 엑셀 '선박 제원 Sample'의 DWT 구간 평균을 그대로 쓴다.

실제 선박·계약 데이터를 받기 전까지 검산과 시연에 쓰는 가상 입력이다. 여기서 정한 것(물량, Laytime, LayCan, 제품 그룹)은 모두 [가정]이다.
평균 작업속도는 엑셀에 단위가 적혀 있지 않다. DWT 3만 이상 구간은 배럴/시간으로 읽었을 때 작업시간이 26~45시간으로 나와 그대로 썼고,
소형선은 값이 맞지 않아(DWT 1만 미만 구간이 25,163) 작업시간을 직접 넣었다.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_T = json.loads((HERE / "rules" / "terminal.json").read_text(encoding="utf-8"))
BAND = {c["dwt_band"]: c for c in _T["ship_classes"]}

# 이름: (DWT 구간, DWT, 선종, 입출, 제품 그룹, 물량(배럴), Laytime(h), 지정 부두 후보 또는 None, 작업시간(h) 또는 None, 덮어쓸 제원)
TEMPLATES = {
    "MR-DSL":   ("4만~5만", 45000, "PP", "EX", "DSL", 300000, 36, None, None, {}),
    "MR-RG":    ("4만~5만", 45000, "PP", "EX", "R-G", 300000, 36, None, None, {}),
    "MR-NAPH":  ("4만~5만", 45000, "PP", "IM", "NAPH", 300000, 36, None, None, {}),
    "LR1-DSL":  ("7만~8만", 75000, "PP", "EX", "DSL", 500000, 36, None, None, {}),
    "LR1-JET":  ("7만~8만", 75000, "PP", "EX", "JET", 450000, 36, None, None, {}),
    "AFRA-CR":  ("10만~11만", 105000, "CR", "IM", "CRUDE", 700000, 72, None, None, {}),
    "SUEZ-CR":  ("16만~17만", 165000, "CR", "IM", "CRUDE", 1000000, 72, None, None, {}),
    "VLCC-CR":  ("29만~30만", 295000, "CR", "IM", "CRUDE", 2000000, 72, None, None, {}),
    "CHEM-BZ":  ("0~1만", 3500, "PC", "IM", "BENZENE", 20000, 24, None, 9, {"grt": 2800, "loa": 85.0, "pbl": 37.5, "draft": 5.9}),
    "CHEM-XYL": ("0~1만", 3900, "PC", "EX", "XYL", 22000, 24, None, 10, {"grt": 3300, "loa": 88.0, "pbl": 38.0, "draft": 6.0}),
    "CHEM-TOL": ("0~1만", 3800, "PC", "EX", "TOL", 21000, 24, None, 8, {"grt": 2900, "loa": 86.0, "pbl": 37.5, "draft": 5.9}),
    "SP-ASPH":  ("0~1만", 4500, "SP", "DO", "ASPH", 25000, 24, ["#1-1", "#1-2", "#2-7"], 11, {"grt": 3100, "loa": 90.0, "pbl": 37.5, "draft": 6.0}),
    "LB-YUB":   ("1만~2만", 15000, "LB", "EX", "YUBASE", 90000, 30, None, 14, {}),
}


def make(aid, template, eta, laycan=("−1d", "+2d"), nor=None, cfr=None, rate=None, laytime=None, qty=None, **extra):
    """가상 입항 건 하나. laycan은 (From, To) ISO 글자다."""
    band, dwt, vclass, biz, cargo, q, lay, berths, hours_, over = TEMPLATES[template]
    c = BAND[band]
    doc = {
        "id": aid, "vessel": f"{template} ({band})", "class": vclass, "biz": biz, "cargo_group": cargo, "qty": qty or q, "eta": eta,
        "grt": over.get("grt", c["grt"]), "dwt": dwt, "loa": over.get("loa", c["loa"]), "pbl": over.get("pbl", c["pbl"]), "draft": over.get("draft", c["draft"]),
        "contract": {"laycan_from": laycan[0], "laycan_to": laycan[1], "laytime_h": laytime or lay, "rate_usd_day": rate or c["rate_usd_day"],
                     "cfr": bool(cfr) if cfr is not None else False},
        "work": {"hours": hours_} if hours_ else {"rate_per_h": c["work_speed"]},
    }
    if nor:
        doc["nor_tender"] = nor
    if berths:
        doc["berths"] = berths
    doc.update(extra)
    return doc
