"""입력 모델 — docs/domain/06 데이터 사전의 SOF_EVENT · CONTRACT_TERMS 필드명을 그대로 쓴다.

06에 없는 입력은 '확장'이라고 주석을 달았다(README §4).
시각은 현지시각(KST) naive datetime이고 계산은 running hours다(06 머리말).
숫자는 Fraction·Decimal로 받아 계산 중에 부동소수점 오차가 생기지 않게 한다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

# 06 §6 event_type 표준 목록. 같은 시각 이벤트의 정렬 순서로도 쓴다.
SOF_EVENT_TYPES = (
    "EOSP", "PILOT_STATION_ARR", "ANCHORED", "NOR_TENDERED", "NOR_RECEIVED", "FREE_PRATIQUE",
    "CUSTOMS_CLEARED", "PILOT_ON_BOARD", "ANCHOR_AWEIGH", "FIRST_LINE", "ALL_FAST", "GANGWAY",
    "SSSCL_DONE", "HOSES_CONNECTED", "OPS_COMMENCED", "OPS_STOPPED", "OPS_RESUMED", "OPS_COMPLETED",
    "HOSES_DISCONNECTED", "DOCS_ON_BOARD", "LAST_LINE", "PILOT_AWAY", "COSP",
)
SOURCES = ("MASTER", "AGENT", "TERMINAL", "AIS", "PILOT")
# 06 §6 OPS_STOPPED 사유 코드 (STRIKE·FIRE·EXPLOSION은 cl.8 반액 사유라 2026-11-02 추가)
STOP_REASONS = ("WEATHER", "SHORE_TANK", "SHIP_EQUIPMENT", "SHORE_EQUIPMENT", "DOCUMENTS", "SAFETY",
                "STRIKE", "FIRE", "EXPLOSION", "OTHER")
# 06 §5 CONTRACT_TERMS 열거값
FORMS = ("ASBATANKVOY", "SHELLVOY6", "BPVOY4", "GTC_BP", "GTC_SHELL", "OTHER")
LAYERS = ("CHARTER_PARTY", "SALES_CONTRACT")
HALF_RATE_EVENTS = ("FIRE", "EXPLOSION", "STORM", "STRIKE", "PLANT_BREAKDOWN")
SHIFTING_ON_DEMURRAGE = ("YES", "NO", "DISPUTED")
OPERATIONS = ("LOAD", "DISCHARGE")
# OPS_STOPPED 사유 코드 → cl.8 반액 사유 [가정: 강풍 중단 = storm, 육상 설비 고장 = 용선주 측 플랜트 고장]
HALF_RATE_BY_STOP_REASON = {
    "WEATHER": "STORM", "SHORE_EQUIPMENT": "PLANT_BREAKDOWN",
    "STRIKE": "STRIKE", "FIRE": "FIRE", "EXPLOSION": "EXPLOSION",
}

_REL_TS = re.compile(r"^D(\d+)\s+(\d{1,2}):(\d{2})$")
_KST = timedelta(hours=9)


class CaseError(ValueError):
    """입력이 06 형식에 맞지 않거나 CLOCK이 지원하지 않는 SOF 패턴. 계산하지 않고 멈춘다."""

    def __init__(self, case_id: str | None, problems: list[str] | str):
        self.case_id = case_id
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        head = f"[{case_id}] " if case_id else ""
        super().__init__(head + " / ".join(self.problems))


@dataclass(frozen=True)
class SofEvent:
    """06 §6 SOF_EVENT. row = SOF 원문 행 번호(계산서 근거로 그대로 인용)."""
    event_id: str
    row: int
    event_type: str
    ts_local: datetime
    source: str | None = None
    remarks: str | None = None
    evidence_ref: str | None = None
    confidence: float | None = None
    reason_code: str | None = None  # OPS_STOPPED 사유 코드(06 §6)
    call_id: str | None = None


@dataclass(frozen=True)
class ContractTerms:
    """06 §5 CONTRACT_TERMS 중 CLOCK이 쓰는 필드."""
    form: str
    layer: str
    laytime_this_port_hours: Fraction
    notice_hours: Fraction
    demurrage_rate_usd_day: Decimal
    laytime_total_hours: Fraction | None = None
    reversible: bool | None = None
    half_rate_events: tuple[str, ...] = HALF_RATE_EVENTS
    pumping_warranty_hours: Fraction | None = None
    pumping_warranty_psi: Fraction | None = None
    shifting_counts_on_demurrage: str = "DISPUTED"


@dataclass(frozen=True)
class Terminal:
    """대기 사유를 가르는 터미널 맥락(BERTH · BERTH_PLAN에서 옴).

    berth_ready_at = 06 §9 BERTH_PLAN 필드. 이 배를 받을 수 있게 선석이 빈 시각(앞 선박 LAST_LINE).
    None이면 대기 사유를 '미상'으로 둔다. berthing_rules·daytime·berth_ready_row/ref는 확장.
    """
    berth_id: str | None = None
    berth_type: str | None = None
    berthing_rules: tuple[str, ...] = ()
    daytime_start: time = time(7, 0)    # ULS-DAYTIME-DEF [가정]
    daytime_end: time = time(17, 30)
    berth_ready_at: datetime | None = None
    berth_ready_row: int | None = None
    berth_ready_ref: str | None = None

    def is_daytime(self, t: time) -> bool:
        if self.daytime_start <= self.daytime_end:
            return self.daytime_start <= t <= self.daytime_end
        return t >= self.daytime_start or t <= self.daytime_end  # 자정을 넘는 창


@dataclass(frozen=True)
class PumpingLog:
    """06 §6 PUMPING_LOG. RIDER-PUMPING 공제 판단의 증거. sof_rows는 계산서 근거용 확장."""
    avg_manifold_psi: Fraction | None
    shore_restriction: bool | None
    sof_rows: tuple[int, ...] = ()
    evidence_ref: str | None = None
    source: str | None = None   # MASTER(선박 펌핑 로그) | TERMINAL(배압 기록·확인서)


@dataclass(frozen=True)
class Case:
    case_id: str
    title: str
    terms: ContractTerms
    sof_events: tuple[SofEvent, ...]
    terminal: Terminal
    operation: str = "DISCHARGE"
    pumping_log: PumpingLog | None = None
    call_id: str | None = None
    vessel_name: str | None = None
    base_date: date | None = None   # 'D1 08:00' 표기의 D1 날짜(표시에도 씀)
    source: str | None = None
    raw: dict | None = None


# ---------------------------------------------------------------- 파싱 도우미

def parse_local_ts(value: Any, base_date: date | None) -> datetime:
    """'D1 08:00'(D1 = base_date, D0 = 전날) 또는 ISO 8601 현지시각. 오프셋은 +09:00만 받는다."""
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    m = _REL_TS.match(s)
    if m:
        if base_date is None:
            raise CaseError(None, f"상대 시각 {s!r}을 쓰려면 base_date가 필요")
        day, hh, mm = (int(g) for g in m.groups())
        try:
            return datetime.combine(base_date + timedelta(days=day - 1), time(hh, mm))
        except ValueError as e:
            raise CaseError(None, f"시각 범위 오류: {s!r} ({e})") from None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise CaseError(None, f"시각 형식 오류: {s!r} — 'D1 08:00' 또는 ISO 8601(2026-11-03T08:00+09:00)") from None
    if dt.tzinfo is not None:
        if dt.utcoffset() != _KST:
            raise CaseError(None, f"KST(+09:00)가 아닌 시각: {s!r} — INTAKE에서 현지시각으로 바꿔 넣을 것(06 머리말)")
        dt = dt.replace(tzinfo=None)
    return dt


def _fraction(value: Any, name: str, *, required: bool = True, minimum: Fraction | None = Fraction(0)) -> Fraction | None:
    if value is None or value == "":
        if required:
            raise CaseError(None, f"{name} 값이 필요")
        return None
    if isinstance(value, bool):
        raise CaseError(None, f"{name} 숫자가 아님: {value!r}")
    try:
        fr = Fraction(str(value))   # str을 거쳐 0.1 같은 값도 정확히
    except (ValueError, ZeroDivisionError):
        raise CaseError(None, f"{name} 숫자가 아님: {value!r}") from None
    if minimum is not None and fr < minimum:
        raise CaseError(None, f"{name}는 {minimum} 이상이어야 함: {value!r}")
    return fr


def _decimal(value: Any, name: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise CaseError(None, f"{name} 숫자가 아님: {value!r}") from None
    if not d.is_finite() or d <= 0:
        raise CaseError(None, f"{name}는 0보다 커야 함: {value!r}")
    return d


def _enum(value: Any, name: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise CaseError(None, f"{name} 값 {value!r}은 허용값 {allowed}에 없음")
    return value


def _hhmm(value: str, name: str) -> time:
    try:
        hh, mm = str(value).split(":")
        return time(int(hh), int(mm))
    except ValueError:
        raise CaseError(None, f"{name} 형식 오류(HH:MM): {value!r}") from None


# ---------------------------------------------------------------- dict → Case

def terms_from_dict(d: dict) -> ContractTerms:
    half = tuple(d.get("half_rate_events", HALF_RATE_EVENTS))
    for h in half:
        _enum(h, "half_rate_events", HALF_RATE_EVENTS)
    return ContractTerms(
        form=_enum(d.get("form", "ASBATANKVOY"), "form", FORMS),
        layer=_enum(d.get("layer", "CHARTER_PARTY"), "layer", LAYERS),
        laytime_this_port_hours=_fraction(d.get("laytime_this_port_hours"), "laytime_this_port_hours"),
        notice_hours=_fraction(d.get("notice_hours", 6), "notice_hours"),
        demurrage_rate_usd_day=_decimal(d.get("demurrage_rate_usd_day"), "demurrage_rate_usd_day"),
        laytime_total_hours=_fraction(d.get("laytime_total_hours"), "laytime_total_hours", required=False),
        reversible=d.get("reversible"),
        half_rate_events=half,
        pumping_warranty_hours=_fraction(d.get("pumping_warranty_hours"), "pumping_warranty_hours", required=False,
                                         minimum=Fraction(0)),
        pumping_warranty_psi=_fraction(d.get("pumping_warranty_psi"), "pumping_warranty_psi", required=False),
        shifting_counts_on_demurrage=_enum(d.get("shifting_counts_on_demurrage") or "DISPUTED",
                                           "shifting_counts_on_demurrage", SHIFTING_ON_DEMURRAGE),
    )


def event_from_dict(d: dict, base_date: date | None) -> SofEvent:
    etype = d.get("event_type")
    if etype not in SOF_EVENT_TYPES:
        raise CaseError(None, f"알 수 없는 event_type {etype!r} (행 {d.get('row')}) — 06 §6 표준 목록에 없음")
    row = d.get("row")
    if not isinstance(row, int) or isinstance(row, bool) or row < 1:
        raise CaseError(None, f"row는 1 이상의 정수여야 함: {row!r} ({etype})")
    source = d.get("source")
    if source is not None:
        _enum(source, "source", SOURCES)
    reason = d.get("reason_code")
    if reason is not None:
        if etype != "OPS_STOPPED":
            raise CaseError(None, f"reason_code는 OPS_STOPPED에만 씀 (행 {row} {etype})")
        _enum(reason, "reason_code", STOP_REASONS)
    return SofEvent(
        event_id=str(d.get("event_id") or f"R{row:02d}-{etype}"),
        row=row,
        event_type=etype,
        ts_local=parse_local_ts(d.get("ts_local"), base_date),
        source=source,
        remarks=d.get("remarks"),
        evidence_ref=d.get("evidence_ref") or f"SOF {row}행",
        confidence=d.get("confidence"),
        reason_code=reason,
        call_id=d.get("call_id"),
    )


def terminal_from_dict(d: dict | None, base_date: date | None) -> Terminal:
    d = d or {}
    day = d.get("daytime") or {}
    ready = d.get("berth_ready_at")
    return Terminal(
        berth_id=d.get("berth_id"),
        berth_type=d.get("berth_type"),
        berthing_rules=tuple(d.get("berthing_rules", ())),
        daytime_start=_hhmm(day.get("start", "07:00"), "daytime.start"),
        daytime_end=_hhmm(day.get("end", "17:30"), "daytime.end"),
        berth_ready_at=parse_local_ts(ready, base_date) if ready else None,
        berth_ready_row=d.get("berth_ready_row"),
        berth_ready_ref=d.get("berth_ready_ref"),
    )


def pumping_log_from_dict(d: dict | None) -> PumpingLog | None:
    if not d:
        return None
    shore = d.get("shore_restriction")
    if shore is not None and not isinstance(shore, bool):
        raise CaseError(None, f"pumping_log.shore_restriction은 true/false: {shore!r}")
    source = d.get("source")
    if source is not None:
        _enum(source, "pumping_log.source", ("MASTER", "TERMINAL"))
    return PumpingLog(
        avg_manifold_psi=_fraction(d.get("avg_manifold_psi"), "pumping_log.avg_manifold_psi", required=False),
        shore_restriction=shore,
        sof_rows=tuple(d.get("sof_rows", ())),
        evidence_ref=d.get("evidence_ref"),
        source=source,
    )


def case_from_dict(d: dict) -> Case:
    case_id = d.get("case_id") or "CASE"
    try:
        base = date.fromisoformat(d["base_date"]) if d.get("base_date") else None
        call = d.get("port_call") or {}
        events = d.get("sof_events") or []
        if not events:
            raise CaseError(None, "sof_events가 비어 있음")
        from . import rules  # 순환 import 방지
        terminal = terminal_from_dict(d.get("terminal"), base)
        for r in terminal.berthing_rules:
            rules.rule(r)
        return Case(
            case_id=case_id,
            title=d.get("title", ""),
            terms=terms_from_dict(d.get("contract_terms") or {}),
            sof_events=tuple(event_from_dict(e, base) for e in events),
            terminal=terminal,
            operation=_enum(call.get("operation", "DISCHARGE"), "port_call.operation", OPERATIONS),
            pumping_log=pumping_log_from_dict(d.get("pumping_log")),
            call_id=call.get("call_id") or case_id,
            vessel_name=call.get("vessel_name"),
            base_date=base,
            source=d.get("source"),
            raw=d,
        )
    except CaseError as e:
        raise CaseError(case_id, e.problems) from None
    except KeyError as e:   # rules.rule()의 미등록 rule_id
        raise CaseError(case_id, str(e.args[0]) if e.args else repr(e)) from None


def load_case(path: str | Path) -> Case:
    return case_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
