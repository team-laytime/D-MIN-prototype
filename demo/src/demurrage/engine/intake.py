"""입력검증 (FR-01 시나리오 입력, FR-02 입력 검증, FR-05 일출·일몰, FR-23 작업시간 추정 가능 여부).

원칙: 오류가 하나라도 있으면 계산을 시작하지 않는다(FR-02). 오류는 '어느 선박의, 어느 값이, 왜'로 알려 준다.
경고(WARN)는 계산은 하되 결과에 '가정값 포함' 같은 상태를 붙인다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional

from ..domain.model import MOVABLE_STATUSES, STATUSES, VESSEL_TYPES, Contract, InventoryGroup, Restriction, Scenario, Vessel
from ..domain.timeutil import TimeFormatError, hours_to_min, parse_ts
from ..rules.contracts import contract_from_doc
from .eligibility import eligible_berths


@dataclass
class Issue:
    level: str          # ERROR / WARN
    vessel: str
    field: str
    code: str           # MISSING / FORMAT / RANGE / ORDER / DUPLICATE / UNKNOWN_REF / NO_BERTH / NO_WORKTIME
    message: str

    def as_dict(self):
        return {"level": self.level, "vessel": self.vessel, "field": self.field, "code": self.code, "message": self.message}


REQUIRED_VESSEL = ["id", "vessel_type", "grt", "dwt", "loa", "draft", "direction", "material_code", "qty", "eta", "status"]
REQUIRED_CONTRACT = ["type", "laytime_h", "demurrage_rate_usd_day", "laycan_from", "laycan_to"]


def _canon(x):
    """화면(JS)을 거치며 17.0 → 17처럼 바뀌어도 같은 지문이 나오게 정수 같은 실수는 정수로."""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, dict):
        return {k: _canon(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_canon(v) for v in x]
    return x


def scenario_hash(doc: dict) -> str:
    blob = json.dumps(_canon(doc), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


class _Collector:
    def __init__(self):
        self.items = []

    def err(self, vessel, field, code, message):
        self.items.append(Issue("ERROR", vessel, field, code, message))

    def warn(self, vessel, field, code, message):
        self.items.append(Issue("WARN", vessel, field, code, message))

    @property
    def errors(self):
        return [i for i in self.items if i.level == "ERROR"]


def _num(c: _Collector, vid, d: dict, key, *, positive=True, integer=False, maximum=None):
    if key not in d or d[key] is None or d[key] == "":
        c.err(vid, key, "MISSING", f"{key} 값이 없음")
        return None
    try:
        val = Fraction(str(d[key])) if not integer else int(d[key])
    except (ValueError, TypeError):
        c.err(vid, key, "FORMAT", f"{key}={d[key]!r} 는 숫자가 아님")
        return None
    if positive and val <= 0:
        c.err(vid, key, "RANGE", f"{key}={d[key]} 는 0보다 커야 함")
        return None
    if maximum is not None and val > maximum:
        c.err(vid, key, "RANGE", f"{key}={d[key]} 는 {maximum} 이하여야 함")
        return None
    return val


def _ts(c: _Collector, vid, d: dict, key, *, required=True, end_of_day=False):
    v = d.get(key)
    if v in (None, ""):
        if required:
            c.err(vid, key, "MISSING", f"{key} 값이 없음")
        return None
    try:
        return parse_ts(v, end_of_day=end_of_day)
    except TimeFormatError as exc:
        c.err(vid, key, "FORMAT", str(exc))
        return None


def parse_scenario(doc: dict, rules, contracts: dict = None) -> tuple:
    """시나리오 JSON → (Scenario 또는 None, [Issue]). 선박은 계약서 번호(contract_id) 또는 계약 조건(contract)을 가진다."""
    contracts = contracts or {}
    c = _Collector()
    sid = doc.get("id", "?")
    hz = doc.get("horizon") or {}
    h0 = _ts(c, "-", hz, "start")
    h1 = _ts(c, "-", hz, "end")
    if h0 is not None and h1 is not None and h1 <= h0:
        c.err("-", "horizon", "ORDER", "horizon.end가 start보다 늦어야 함")
    active = tuple(doc.get("berths") or rules.berth_order)
    for b in active:
        if b not in rules.berths:
            c.err("-", "berths", "UNKNOWN_REF", f"부두 {b} 는 기준 정보에 없음")

    vessels = []
    seen = set()
    for raw in doc.get("vessels", []):
        vid = str(raw.get("id") or "?")
        for k in REQUIRED_VESSEL:
            if k not in raw or raw[k] in (None, ""):
                c.err(vid, k, "MISSING", f"필수값 {k} 없음")
        if vid in seen:
            c.err(vid, "id", "DUPLICATE", f"선박 ID {vid} 중복")
        seen.add(vid)
        vt = raw.get("vessel_type")
        if vt and vt not in VESSEL_TYPES:
            c.err(vid, "vessel_type", "FORMAT", f"선종 {vt} 는 {VESSEL_TYPES} 중 하나여야 함")
        direction = raw.get("direction")
        if direction and direction not in ("IMPORT", "EXPORT"):
            c.err(vid, "direction", "FORMAT", "입출 구분은 IMPORT 또는 EXPORT")
        status = raw.get("status")
        if status and status not in STATUSES:
            c.err(vid, "status", "FORMAT", f"상태 {status} 는 {STATUSES} 중 하나여야 함")
        mat = raw.get("material_code")
        group = rules.cargo_map.get(mat) if mat else None
        if mat and group is None:
            c.err(vid, "material_code", "UNKNOWN_REF", f"자재코드 {mat} 가 화물 그룹 매핑표에 없음 (ELG-02)")
        grt = _num(c, vid, raw, "grt", integer=True)
        dwt = _num(c, vid, raw, "dwt", integer=True)
        loa = _num(c, vid, raw, "loa")
        pbl = _num(c, vid, raw, "pbl", positive=False) if "pbl" in raw else Fraction(0)
        draft = _num(c, vid, raw, "draft", maximum=30)
        qty = _num(c, vid, raw, "qty")
        eta = _ts(c, vid, raw, "eta")

        nor = _ts(c, vid, raw, "nor_tender", required=False)
        if nor is not None and eta is not None and nor < eta:
            c.warn(vid, "nor_tender", "ORDER", "NOR 제출이 ETA보다 이름 — ETANR은 NOR 제출 시각을 쓴다(LAY-01)")
        contract_obj = None
        cid = raw.get("contract_id")
        if cid:
            cdoc = contracts.get(cid)
            if cdoc is None:
                c.err(vid, "contract_id", "UNKNOWN_REF", f"계약서 {cid} 가 계약서 목록(data/contracts)에 없음")
            elif cdoc["type"] not in rules.contract_types:
                c.err(vid, "contract_id", "UNKNOWN_REF", f"계약서 {cid}의 유형 {cdoc['type']} 가 계약 규칙 테이블에 없음")
            elif parse_ts(cdoc["laycan"]["to"], end_of_day=True) < parse_ts(cdoc["laycan"]["from"]):
                c.err(vid, "contract_id", "ORDER", f"계약서 {cid}의 Laycan To가 Laycan From보다 이름")
            elif qty is not None:
                contract_obj = contract_from_doc(cdoc, float(qty), nor)
        else:
            con = raw.get("contract") or {}
            if not con:
                c.err(vid, "contract", "MISSING", "계약서 번호(contract_id) 또는 계약 조건(contract)이 필요함")
            for k in REQUIRED_CONTRACT:
                if con and (k not in con or con[k] in (None, "")):
                    c.err(vid, f"contract.{k}", "MISSING", f"계약 필수값 {k} 없음")
            ctype = con.get("type")
            if ctype and ctype not in rules.contract_types:
                c.err(vid, "contract.type", "UNKNOWN_REF", f"계약 유형 {ctype} 는 계약 규칙 테이블에 없음 ({', '.join(rules.contract_types)})")
            lay = _num(c, vid, con, "laytime_h") if "laytime_h" in con else None
            rate = _num(c, vid, con, "demurrage_rate_usd_day", integer=True) if "demurrage_rate_usd_day" in con else None
            lf = _ts(c, vid, con, "laycan_from", required=False)
            lt = _ts(c, vid, con, "laycan_to", required=False, end_of_day=True)
            if lf is not None and lt is not None and lt < lf:
                c.err(vid, "contract.laycan", "ORDER", "Laycan To가 Laycan From보다 이름")
            if con and lay is not None and rate is not None and lf is not None and lt is not None:
                contract_obj = Contract(type=ctype, laytime_h=lay, rate_usd_day=int(rate), laycan_from=lf, laycan_to=lt, nor_tender=nor)

        work = raw.get("work") or {}
        wh = _num(c, vid, work, "hours") if "hours" in work else None
        hose = _num(c, vid, work, "hose_term_h", positive=False) if "hose_term_h" in work else None
        delay_h = work.get("start_delay_h")
        delay_min = hours_to_min(delay_h) if delay_h is not None else rules.work_start_delay_min

        fixed_berth = fixed_etb = ws_actual = None
        if status == "FIX":
            fx = raw.get("fixed") or {}
            fixed_berth = fx.get("berth")
            fixed_etb = _ts(c, vid, fx, "etb")
            if not fixed_berth:
                c.err(vid, "fixed.berth", "MISSING", "FIX 선박은 부두를 지정해야 함")
        if status == "WORKING":
            wk = raw.get("working") or {}
            fixed_berth = wk.get("berth")
            fixed_etb = _ts(c, vid, wk, "etb")
            ws_actual = _ts(c, vid, wk, "work_start", required=False)
            if not fixed_berth:
                c.err(vid, "working.berth", "MISSING", "WORKING 선박은 현재 부두가 있어야 함")
        if fixed_berth and fixed_berth not in rules.berths:
            c.err(vid, "berth", "UNKNOWN_REF", f"부두 {fixed_berth} 는 기준 정보에 없음")
        if fixed_etb is not None and eta is not None and fixed_etb < eta:
            c.err(vid, "etb", "ORDER", "ETB가 ETA보다 이름")
        if ws_actual is not None and fixed_etb is not None and ws_actual < fixed_etb:
            c.err(vid, "working.work_start", "ORDER", "작업시작이 ETB보다 이름")
        allowed = tuple(raw["allowed_berths"]) if raw.get("allowed_berths") else None
        for b in allowed or ():
            if b not in rules.berths:
                c.err(vid, "allowed_berths", "UNKNOWN_REF", f"부두 {b} 는 기준 정보에 없음")
        deadline = _ts(c, vid, raw, "deadline", required=False)

        if (c.errors and any(i.vessel == vid for i in c.errors)) or contract_obj is None:
            continue
        vessels.append(Vessel(
            id=vid, name=str(raw.get("name") or vid), vessel_type=vt, grt=int(grt), dwt=int(dwt), loa=float(loa),
            pbl=float(pbl), draft=float(draft), direction=direction, material_code=mat, cargo_group=group, qty=float(qty),
            eta=eta, contract=contract_obj,
            status=status, fixed_berth=fixed_berth, fixed_etb=fixed_etb, work_start_actual=ws_actual,
            work_hours=wh, hose_term_h=hose, work_start_delay_min=delay_min, allowed_berths=allowed,
            deadline=deadline, remarks=str(raw.get("remarks") or ""), vessel_code=raw.get("vessel_code"),
            priority=raw.get("priority")))

    restrictions = []
    for i, r in enumerate(doc.get("restrictions", [])):
        rid = r.get("id") or f"R{i + 1}"
        s = _ts(c, rid, r, "start")
        e = _ts(c, rid, r, "end")
        if s is not None and e is not None and e <= s:
            c.err(rid, "restriction", "ORDER", "제한 종료가 시작보다 늦어야 함")
        bs = tuple(r.get("berths") or ["*"])
        for b in bs:
            if b != "*" and b not in rules.berths:
                c.err(rid, "restriction.berths", "UNKNOWN_REF", f"부두 {b} 는 기준 정보에 없음")
        reason = r.get("reason", "USER")
        if reason not in ("MAINTENANCE", "USER", "WEATHER"):
            c.err(rid, "restriction.reason", "FORMAT", "사유는 MAINTENANCE / USER / WEATHER")
        if s is not None and e is not None:
            restrictions.append(Restriction(id=rid, berths=bs, start=s, end=e, reason=reason, note=r.get("note", ""), source="사용자 입력"))

    wx = doc.get("weather_forecast") or {}
    segs = []
    for seg in wx.get("segments", []):
        s = _ts(c, "weather", seg, "from")
        e = _ts(c, "weather", seg, "to")
        w = seg.get("wind_ms")
        if s is not None and e is not None and w is not None:
            segs.append((s, e, float(w)))
    tide = {}
    for bid, wins in (doc.get("tide_windows") or {}).items():
        if bid.startswith("_"):
            continue
        tide[bid] = sorted((parse_ts(a), parse_ts(b)) for a, b in wins)
    inv = {}
    for g in doc.get("inventory", []):
        inv[g["group"]] = InventoryGroup(group=g["group"], unit=g.get("unit", "kl"), capacity=float(g["capacity"]),
                                         opening=float(g["opening"]), daily_net=float(g.get("daily_net", 0)),
                                         minimum=float(g.get("minimum", 0)))
    sun = {}
    for k, v in (doc.get("sun") or {}).items():
        if k.startswith("_"):
            continue
        sun[k] = (v[0], v[1])

    if c.errors:
        return None, c.items
    sc = Scenario(
        id=sid, title=doc.get("title", sid), description=doc.get("description", ""),
        data_label=doc.get("data_label", "가상 데이터"), horizon_start=h0, horizon_end=h1, active_berths=active,
        vessels=vessels, restrictions=restrictions, weather_segments=segs,
        weather_meta={k: wx.get(k) for k in ("source", "issued_at", "note")},
        tide_windows=tide, inventory=inv, sun_override=sun, raw=doc, source_hash=scenario_hash(doc))
    return sc, c.items


def check_assignability(sc: Scenario, rules, work_model) -> list:
    """배정 가능한 부두가 있는지, 작업시간을 정할 수 있는지(FR-23) — 계산 전에 확인."""
    c = _Collector()
    for v in sc.vessels:
        if v.status == "COMPLETED":
            continue
        if v.immovable:
            b = rules.berths.get(v.fixed_berth)
            if b and work_model.plan(v, b.id) is None:
                c.err(v.id, "work", "NO_WORKTIME", f"{b.id} 작업시간·호스분리 소요를 입력하거나 과거 실적이 있어야 함 (FR-23)")
            continue
        ok, excluded = eligible_berths(v, rules.berths, rules.berth_order, active=sc.active_berths)
        if not ok:
            why = "; ".join(f"{bid}: {r[0]['message']}" for bid, r in excluded.items() if bid in sc.active_berths)
            c.err(v.id, "berth", "NO_BERTH", f"배정 가능한 부두가 없음 — {why}")
            continue
        planned = [bid for bid in ok if work_model.plan(v, bid) is not None]
        if not planned:
            c.err(v.id, "work", "NO_WORKTIME", "작업시간·호스분리 소요를 입력하거나 과거 실적이 있어야 함 (FR-23)")
    return c.items
