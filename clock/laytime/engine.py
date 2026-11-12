"""CLOCK — 레이타임 계산 엔진. docs/domain/03 §2 상태 기계와 §6 알고리즘을 따른다.

1. SOF 이벤트를 시각·06 표준 순서로 정렬하고 패턴을 검증한다(지원하지 않는 패턴이면 계산하지 않고 CaseError).
2. NOR 유효성을 보고 개시 시각을 정한다: min(NOR 수령 + 통지시간, 접안 완료) (ASB-06-NOR-START).
   도착 전 NOR이면 재제출 NOR 기준, 재제출이 없으면 하역 개시 (LAW-NOR-ARRIVAL, LAW-NOR-WAIVER).
3. 물리 구간(도착 전·묘박 대기·이동·접안 준비·하역·중단·호스 분리 전)을 만들고 대기에 사유를 붙인다.
4. 펌핑 보증 초과분을 하역 끝에서부터 공제 구간으로 바꾼다 (RIDER-PUMPING).
5. 개시부터 호스 분리까지 구간을 걸으며 레이타임을 쌓고, 허용 시간이 차면 체선으로 넘어간다.
   체선 중에는 반액 사유 중단을 반액으로, 계약·쟁점 정책에 따라 이동을 산입하거나 공제한다.
6. 05 §7 쟁점은 판정하지 않는다. 문서 정답과 같은 기준으로 기본 계산을 내고, 쟁점마다
   '담당자 확인 필요' 이슈와 반대 입장의 대안 계산을 붙인다.

시각은 기준 시각부터의 분(Fraction)으로 다뤄 반올림 오차 없이 계산한다. LLM·네트워크를 쓰지 않으며,
같은 입력이면 같은 출력이 나온다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any

from . import rules
from .fmt import fmt_dt, fmt_hours, fmt_num, fmt_rows, fmt_usd
from .model import HALF_RATE_BY_STOP_REASON, SOF_EVENT_TYPES, Case, CaseError, SofEvent

ENGINE_VERSION = "0.1.0"

LEVEL_REVIEW = "담당자 확인 필요"   # 05 §7 쟁점 — 판정하지 않고 두 계산을 함께 낸다
LEVEL_EVIDENCE = "증빙 확인"        # 계산에 반영했지만 근거 서류 대조가 필요한 것
LEVEL_WARNING = "경고"
LEVEL_INFO = "참고"
LEVEL_ORDER = {LEVEL_REVIEW: 0, LEVEL_EVIDENCE: 1, LEVEL_WARNING: 2, LEVEL_INFO: 3}

PRE, LAYTIME, DEMURRAGE, POST = "PRE_LAYTIME", "LAYTIME", "DEMURRAGE", "POST_LAYTIME"
COUNT, EXCLUDE, FULL, HALF, NOT_COUNTED = "COUNT", "EXCLUDE", "FULL", "HALF", "NOT_COUNTED"

PHASE_LABEL = {PRE: "개시 전", LAYTIME: "레이타임", DEMURRAGE: "체선", POST: "종료 후"}
EFFECT_LABEL = {COUNT: "산입", EXCLUDE: "공제", FULL: "체선 전액", HALF: "체선 반액", NOT_COUNTED: "미산입"}
KIND_LABEL = {
    "PASSAGE": "도착 전 항해", "WAIT": "묘박 대기", "SHIFT": "이동(묘박지→선석)",
    "BERTH_PREP": "접안·호스 연결", "BERTHED": "접안 중(하역 기록 없음)", "PUMPING": "하역",
    "STOPPAGE": "하역 중단", "EXCESS_PUMPING": "펌핑 보증 초과", "POST_OPS": "하역 완료~호스 분리",
    "DOCS_WAIT": "호스 분리 후 서류 대기", "DOCS_WAIT_GRACE": "서류 대기(유예 시간)",
}
WAIT_LABEL = {
    "BERTH_OCCUPIED": "선석 점유", "NIGHT_RESTRICTION": "야간 접안·계류 제한",
    "OTHER": "선석 가용 후 기타", "UNKNOWN": "사유 미상(선석 가용 시각 없음)",
}
STOP_LABEL = {
    "WEATHER": "기상", "SHORE_TANK": "육상 탱크", "SHIP_EQUIPMENT": "선박 설비", "SHORE_EQUIPMENT": "육상 설비",
    "DOCUMENTS": "서류", "SAFETY": "안전", "OTHER": "기타", "STRIKE": "파업", "FIRE": "화재", "EXPLOSION": "폭발",
}
START_BASIS_LABEL = {
    "ALL_FAST": "접안 완료가 통지시간 만료보다 먼저",
    "NOTICE_EXPIRY": "통지시간 만료가 접안 완료보다 먼저",
    "NOR_AFTER_BERTH": "접안 후 NOR — NOR 수령 시점",
    "RETENDER_ALL_FAST": "재제출 NOR 기준, 접안 완료가 먼저",
    "RETENDER_NOTICE_EXPIRY": "재제출 NOR 기준, 통지시간 만료가 먼저",
    "RETENDER_NOR_AFTER_BERTH": "재제출 NOR 기준, 접안 후 NOR",
    "OPS_COMMENCED": "무효 NOR·재제출 없음 → 하역 개시",
    "WAIVED_ALL_FAST": "무효 NOR을 유효로 볼 때, 접안 완료가 먼저",
    "WAIVED_NOTICE_EXPIRY": "무효 NOR을 유효로 볼 때, 통지시간 만료가 먼저",
    "WAIVED_NOR_AFTER_BERTH": "무효 NOR을 유효로 볼 때, 접안 후 NOR",
}
NIGHT_RULES = ("ULS-SBM-NIGHT", "ULS-SK38-DAYTIME", "ULS-SK12-DAYTIME")
SINGLETON_TYPES = ("ANCHORED", "ANCHOR_AWEIGH", "ALL_FAST", "HOSES_CONNECTED", "OPS_COMMENCED",
                   "OPS_COMPLETED", "HOSES_DISCONNECTED", "DOCS_ON_BOARD")
ORDER_CHECKS = (
    ("ANCHORED", "ANCHOR_AWEIGH"), ("ANCHORED", "ALL_FAST"), ("ANCHOR_AWEIGH", "ALL_FAST"),
    ("ALL_FAST", "HOSES_CONNECTED"), ("ALL_FAST", "OPS_COMMENCED"), ("HOSES_CONNECTED", "OPS_COMMENCED"),
    ("OPS_COMMENCED", "OPS_COMPLETED"), ("OPS_COMMENCED", "HOSES_DISCONNECTED"),
    ("OPS_COMPLETED", "HOSES_DISCONNECTED"), ("HOSES_CONNECTED", "HOSES_DISCONNECTED"),
    ("HOSES_DISCONNECTED", "DOCS_ON_BOARD"),
)
_TYPE_ORDER = {t: i for i, t in enumerate(SOF_EVENT_TYPES)}


@dataclass(frozen=True)
class Policy:
    """쟁점별 계산 입장. 기본값 = 04 문서 정답과 같은 기준. 대안 계산은 한 항목씩 뒤집는다."""
    shift_on_demurrage: str | None = None         # None = 계약 필드(YES→COUNT, NO→EXCLUDE, DISPUTED→COUNT)
    berth_delay_exception: bool = False            # True = 야간 제한 대기를 used laytime에서 뺌(cl.6 예외, 용선주 주장)
    laytime_stoppage_half_rate: bool = False       # True = 레이타임 중 반액 사유 중단 시간만큼 체선 앞부분을 반액
    invalid_nor_waived: bool = False               # True = 무효 NOR이 수령으로 치유됐다고 봄(선주 주장)
    pumping_deduction: bool = True                 # False = 펌핑 보증 초과 공제 안 함(선주 주장)
    vessel_fault_on_demurrage: str = "EXCLUDE"     # 체선 중 선박 귀책 중단: EXCLUDE | COUNT
    docs_wait_grace_hours: Fraction | None = None  # 숫자 = 호스 분리 후 서류 대기 중 이 시간을 넘는 부분 산입


# ---------------------------------------------------------------- 출력 모델 (06 §7 LAYTIME_STATEMENT 필드명)

@dataclass(frozen=True)
class Line:
    """계산서 한 줄(04 §0 템플릿). rule_ids와 sof_rows가 근거, SOF 밖 근거는 source."""
    label: str
    value: str
    rule_ids: tuple[str, ...]
    sof_rows: tuple[int, ...]
    source: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class LedgerEntry:
    """구간 원장 한 줄. 개시 전·종료 후 구간도 '미산입'으로 보여 준다."""
    from_ts: datetime
    to_ts: datetime
    kind: str
    reason: str | None
    label: str
    phase: str
    effect: str
    hours: Fraction
    rule_ids: tuple[str, ...]
    sof_rows: tuple[int, ...]


@dataclass(frozen=True)
class Deduction:
    """06 §7 DEDUCTION."""
    from_ts: datetime
    to_ts: datetime
    hours: Fraction
    category: str
    rule_id: str
    evidence_ref: str
    disputed: bool
    sof_rows: tuple[int, ...]


@dataclass(frozen=True)
class AltCalc:
    code: str
    title: str
    policy: dict
    laytime_start_at: datetime
    demurrage_start_at: datetime | None
    used_hours: Fraction
    demurrage_hours: Fraction
    half_rate_hours: Fraction
    amount_usd: Decimal
    delta_usd: Decimal


@dataclass(frozen=True)
class Issue:
    code: str
    level: str
    title: str
    detail: str
    rule_ids: tuple[str, ...]
    sof_rows: tuple[int, ...]
    dispute_ref: str | None = None
    hours: Fraction | None = None
    alternative: AltCalc | None = None


@dataclass(frozen=True)
class Statement:
    statement_id: str
    call_id: str
    layer: str
    form: str
    nor_tendered_at: datetime
    nor_received_at: datetime
    nor_valid: bool
    notice_expiry_at: datetime
    all_fast_at: datetime
    laytime_start_at: datetime
    start_basis: str
    start_rule: tuple[str, ...]
    laytime_end_at: datetime
    end_rule: tuple[str, ...]
    elapsed_hours: Fraction
    deductions: tuple[Deduction, ...]
    used_hours: Fraction
    allowed_hours: Fraction
    demurrage_hours: Fraction
    demurrage_start_at: datetime | None
    full_rate_hours: Fraction
    half_rate_hours: Fraction
    pumping_excess_hours: Fraction
    margin_hours: Fraction | None
    rate_usd_day: Decimal
    amount_usd: Decimal
    lines: tuple[Line, ...]
    ledger: tuple[LedgerEntry, ...]
    issues: tuple[Issue, ...]
    alt_calculations: tuple[AltCalc, ...]
    policy: Policy
    base_date: date | None = None
    title: str = ""
    version: str = ENGINE_VERSION
    rules_version: str = rules.RULES_VERSION
    computed_at: datetime | None = None   # 재현성을 위해 엔진은 비워 두고 호출 측이 채운다

    def issue(self, code: str) -> Issue | None:
        return next((i for i in self.issues if i.code == code), None)

    def to_dict(self) -> dict:
        return _jsonable(asdict(self))


# ---------------------------------------------------------------- 내부 구조

class _Timebase:
    """datetime ↔ 기준 시각부터의 분(Fraction)."""

    def __init__(self, epoch: datetime):
        self.epoch = epoch

    def m(self, dt: datetime) -> Fraction:
        d = dt - self.epoch
        return Fraction(d.days * 86400 + d.seconds, 60) + Fraction(d.microseconds, 60_000_000)

    def dt(self, minutes: Fraction) -> datetime:
        return self.epoch + timedelta(microseconds=round(minutes * 60_000_000))


@dataclass(frozen=True)
class _Ev:
    t: Fraction
    ev: SofEvent

    @property
    def row(self) -> int:
        return self.ev.row

    @property
    def type(self) -> str:
        return self.ev.event_type


@dataclass(frozen=True)
class _Notice:
    tendered: _Ev
    received: _Ev
    has_receipt: bool


@dataclass(frozen=True)
class _Seg:
    a: Fraction
    b: Fraction
    kind: str
    reason: str | None
    rows: tuple[int, ...]
    rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Piece:
    seg: _Seg
    a: Fraction
    b: Fraction
    phase: str
    effect: str
    rule_ids: tuple[str, ...]

    @property
    def dur(self) -> Fraction:
        return self.b - self.a


@dataclass
class _IssueSpec:
    code: str
    level: str
    title: str
    detail: str
    rule_ids: tuple[str, ...]
    sof_rows: tuple[int, ...]
    dispute_ref: str | None = None
    minutes: Fraction | None = None
    alt_policy: dict | None = None
    alt_title: str | None = None


def _rows(*items: Any) -> tuple[int, ...]:
    """_Ev·int·튜플이 섞인 인자에서 SOF 행 번호만 모아 오름차순(중복 제거)."""
    out: set[int] = set()
    for it in items:
        if it is None:
            continue
        if isinstance(it, _Ev):
            out.add(it.row)
        elif isinstance(it, int):
            out.add(it)
        else:
            out.update(v for v in it if v is not None)
    return tuple(sorted(out))


class _Index:
    """정렬된 SOF 이벤트와 패턴 검증."""

    def __init__(self, case: Case, tb: _Timebase):
        evs = sorted(case.sof_events, key=lambda e: (e.ts_local, _TYPE_ORDER[e.event_type], e.row))
        self.events = [_Ev(tb.m(e.ts_local), e) for e in evs]
        self.by_type: dict[str, list[_Ev]] = {}
        for e in self.events:
            self.by_type.setdefault(e.type, []).append(e)
        problems: list[str] = []
        for t in SINGLETON_TYPES:
            found = self.by_type.get(t, [])
            if len(found) > 1:
                problems.append(f"{t}가 {len(found)}번 나옴(행 {fmt_rows(_rows(*found))}) — 재투묘·선석 이동·재접안 패턴은 "
                                "아직 지원하지 않음, 수동 계산 필요")
        for t in ("ALL_FAST", "HOSES_DISCONNECTED"):
            if t not in self.by_type:
                problems.append(f"필수 이벤트 {t} 없음 — 레이타임 개시·종료를 정할 수 없음")
        if "NOR_TENDERED" not in self.by_type and "NOR_RECEIVED" not in self.by_type:
            problems.append("필수 이벤트 NOR_TENDERED·NOR_RECEIVED 없음")
        for a, b in ORDER_CHECKS:
            ea, eb = self.get(a), self.get(b)
            if ea and eb and ea.t > eb.t:
                problems.append(f"{a}(행 {ea.row})가 {b}(행 {eb.row})보다 늦음 — SOF 시각 확인")
        af, hd = self.get("ALL_FAST"), self.get("HOSES_DISCONNECTED")
        if af and hd and af.t >= hd.t:
            problems.append(f"ALL_FAST(행 {af.row})가 HOSES_DISCONNECTED(행 {hd.row})보다 늦거나 같음")
        self.stops = self._pair_stops(problems)
        if problems:
            raise CaseError(case.case_id, problems)

    def _pair_stops(self, problems: list[str]) -> list[tuple[_Ev, _Ev]]:
        seq = [e for e in self.events if e.type in ("OPS_STOPPED", "OPS_RESUMED")]
        if not seq:
            return []
        oc, ocomp = self.get("OPS_COMMENCED"), self.get("OPS_COMPLETED")
        if not (oc and ocomp):
            problems.append("OPS_STOPPED·OPS_RESUMED가 있는데 OPS_COMMENCED·OPS_COMPLETED가 없음")
            return []
        pairs, open_stop = [], None
        for e in seq:
            if not (oc.t <= e.t <= ocomp.t):
                problems.append(f"{e.type}(행 {e.row})가 하역 개시~완료 밖에 있음")
            elif e.type == "OPS_STOPPED" and open_stop is None:
                open_stop = e
            elif e.type == "OPS_RESUMED" and open_stop is not None:
                pairs.append((open_stop, e))
                open_stop = None
            else:
                problems.append(f"{e.type}(행 {e.row})의 짝이 맞지 않음 — 중단·재개가 번갈아 와야 함")
        if open_stop is not None:
            problems.append(f"OPS_STOPPED(행 {open_stop.row})에 OPS_RESUMED가 없음")
        return pairs

    def get(self, t: str) -> _Ev | None:
        found = self.by_type.get(t)
        return found[0] if found else None

    def all_of(self, t: str) -> list[_Ev]:
        return self.by_type.get(t, [])


def _notices(idx: _Index) -> list[_Notice]:
    """NOR_TENDERED·NOR_RECEIVED를 통지 단위로 묶는다. 수령 = 그 제출 이후, 다음 제출 전의 첫 수령."""
    tendered, received = idx.all_of("NOR_TENDERED"), idx.all_of("NOR_RECEIVED")
    if not tendered:
        return [_Notice(r, r, True) for r in received]
    out, used = [], set()
    for i, t in enumerate(tendered):
        nxt = tendered[i + 1].t if i + 1 < len(tendered) else None
        rec = next((r for r in received
                    if r.t >= t.t and (nxt is None or r.t < nxt) and r.ev.event_id not in used), None)
        if rec:
            used.add(rec.ev.event_id)
        out.append(_Notice(t, rec or t, rec is not None))
    return out


# ---------------------------------------------------------------- 구간 만들기

def _after_ready_reason(could_move: Fraction, idx: _Index, case: Case, tb: _Timebase) -> tuple[str, tuple[str, ...]]:
    """선석이 빈 뒤에도 묘박지에 있었던 이유. 그때 바로 움직였다면 접안 완료가 주간 창 밖이었는지 본다."""
    term = case.terminal
    night_rules = tuple(r for r in term.berthing_rules if r in NIGHT_RULES)
    if not night_rules:
        return "OTHER", ()
    aw, af = idx.get("ANCHOR_AWEIGH"), idx.get("ALL_FAST")
    shift = (af.t - aw.t) if aw else Fraction(0)
    if term.is_daytime(tb.dt(could_move + shift).time()):
        return "OTHER", ()
    return "NIGHT_RESTRICTION", night_rules + ("ULS-DAYTIME-DEF",)


def _physical(idx: _Index, case: Case, tb: _Timebase, lo: Fraction, first: _Notice) -> list[_Seg]:
    """lo(첫 NOR 또는 도착)부터 서류 완료까지의 물리 구간. 계산 단계와 무관하게 SOF만으로 만든다."""
    af, hd = idx.get("ALL_FAST"), idx.get("HOSES_DISCONNECTED")
    anch, aw = idx.get("ANCHORED"), idx.get("ANCHOR_AWEIGH")
    oc, ocomp, hc = idx.get("OPS_COMMENCED"), idx.get("OPS_COMPLETED"), idx.get("HOSES_CONNECTED")
    docs = idx.get("DOCS_ON_BOARD")
    term = case.terminal
    segs: list[_Seg] = []

    arrival_t = anch.t if anch else first.tendered.t
    if lo < arrival_t:
        segs.append(_Seg(lo, arrival_t, "PASSAGE", None, _rows(first.tendered, anch)))
    wait_end = aw.t if aw else af.t
    wait_from = max(arrival_t, lo)
    start_rows = _rows(anch) if anch else _rows(first.received)
    end_rows = _rows(aw) if aw else _rows(af)
    if wait_from < wait_end:
        if term.berth_ready_at is None:
            segs.append(_Seg(wait_from, wait_end, "WAIT", "UNKNOWN", start_rows + end_rows))
        else:
            ready_rows = _rows(term.berth_ready_row)
            could_move = max(tb.m(term.berth_ready_at), arrival_t)
            if wait_from < could_move:
                segs.append(_Seg(wait_from, min(could_move, wait_end), "WAIT", "BERTH_OCCUPIED",
                                 _rows(start_rows, ready_rows)))
            if could_move < wait_end:
                reason, extra = _after_ready_reason(could_move, idx, case, tb)
                segs.append(_Seg(max(could_move, wait_from), wait_end, "WAIT", reason,
                                 _rows(ready_rows or start_rows, end_rows), extra))
    if aw:
        segs.append(_Seg(aw.t, af.t, "SHIFT", None, _rows(aw, af)))
    if oc:
        segs.append(_Seg(af.t, oc.t, "BERTH_PREP", None, _rows(af, hc, oc)))
        ops_end = ocomp or hd
        cursor, cursor_row = oc.t, oc.row
        for s, r in idx.stops:
            segs.append(_Seg(cursor, s.t, "PUMPING", None, _rows(cursor_row, s)))
            segs.append(_Seg(s.t, r.t, "STOPPAGE", s.ev.reason_code or "OTHER", _rows(s, r)))
            cursor, cursor_row = r.t, r.row
        segs.append(_Seg(cursor, ops_end.t, "PUMPING", None, _rows(cursor_row, ops_end)))
        if ocomp:
            segs.append(_Seg(ocomp.t, hd.t, "POST_OPS", None, _rows(ocomp, hd)))
    else:
        segs.append(_Seg(af.t, hd.t, "BERTHED", None, _rows(af, hd)))
    if docs:
        segs.append(_Seg(hd.t, docs.t, "DOCS_WAIT", None, _rows(hd, docs)))
    return [s for s in segs if s.b > s.a]


def _clip(segs: list[_Seg], a: Fraction, b: Fraction) -> list[_Seg]:
    out = []
    for s in segs:
        lo, hi = max(s.a, a), min(s.b, b)
        if lo < hi:
            out.append(replace(s, a=lo, b=hi))
    return out


@dataclass(frozen=True)
class _Pumping:
    status: str            # NONE | DEDUCTED | OWNER_NO_DEDUCTION | NO_OPS | NO_LOG | SHORE_RESTRICTED | PRESSURE_MET
    pumping_minutes: Fraction
    excess_minutes: Fraction
    rows: tuple[int, ...]


def _apply_pumping(segs: list[_Seg], case: Case, idx: _Index, pol: Policy) -> tuple[list[_Seg], _Pumping]:
    """RIDER-PUMPING: 실하역(중단 제외)이 보증 시간을 넘고, 압력 미달·육상 제한 없음이 기록돼 있으면
    초과분을 하역 구간의 끝에서부터 '펌핑 보증 초과(공제)'로 바꾼다 [가정: 보증 시간 = 하역 앞부분]."""
    terms, log = case.terms, case.pumping_log
    zero = Fraction(0)
    if terms.pumping_warranty_hours is None or case.operation != "DISCHARGE":
        return segs, _Pumping("NONE", zero, zero, ())
    oc, ocomp = idx.get("OPS_COMMENCED"), idx.get("OPS_COMPLETED")
    if not (oc and ocomp):
        return segs, _Pumping("NO_OPS", zero, zero, ())
    pumping = sum((s.b - s.a for s in segs if s.kind == "PUMPING"), zero)
    excess = pumping - terms.pumping_warranty_hours * 60
    rows = _rows(oc, ocomp, log.sof_rows if log else ())
    if excess <= 0:
        return segs, _Pumping("NONE", pumping, zero, rows)
    if log is None or log.shore_restriction is None or (terms.pumping_warranty_psi is not None and log.avg_manifold_psi is None):
        return segs, _Pumping("NO_LOG", pumping, excess, rows)
    if log.shore_restriction:
        return segs, _Pumping("SHORE_RESTRICTED", pumping, excess, rows)
    if terms.pumping_warranty_psi is not None and log.avg_manifold_psi >= terms.pumping_warranty_psi:
        return segs, _Pumping("PRESSURE_MET", pumping, excess, rows)
    if not pol.pumping_deduction:
        return segs, _Pumping("OWNER_NO_DEDUCTION", pumping, excess, rows)
    out, remaining = list(segs), excess
    for i in range(len(out) - 1, -1, -1):
        s = out[i]
        if remaining <= 0:
            break
        if s.kind != "PUMPING":
            continue
        take = min(s.b - s.a, remaining)
        cut = s.b - take
        tail = replace(s, a=cut, kind="EXCESS_PUMPING", rows=_rows(s.rows, log.sof_rows))
        out[i:i + 1] = [replace(s, b=cut), tail] if cut > s.a else [tail]
        remaining -= take
    return out, _Pumping("DEDUCTED", pumping, excess, rows)


# ---------------------------------------------------------------- 레이타임·체선 걷기

def _half_rate_cause(reason: str | None, case: Case) -> bool:
    return HALF_RATE_BY_STOP_REASON.get(reason or "") in case.terms.half_rate_events


def _shift_mode(pol: Policy, case: Case) -> str:
    if pol.shift_on_demurrage:
        return pol.shift_on_demurrage
    return {"YES": "COUNT", "NO": "EXCLUDE", "DISPUTED": "COUNT"}[case.terms.shifting_counts_on_demurrage]


def _laytime_effect(s: _Seg, pol: Policy) -> tuple[str, tuple[str, ...]]:
    if s.kind == "PASSAGE":
        return COUNT, ("ASB-06-NOR-START",)    # 무효 NOR을 유효로 보는 대안 계산에서만 생긴다
    if s.kind == "WAIT":
        if s.reason == "NIGHT_RESTRICTION" and pol.berth_delay_exception:
            return EXCLUDE, ("ASB-06-BERTH-DELAY-EXC",) + s.rules
        return COUNT, ("ASB-09-REACHABLE",) + s.rules
    if s.kind == "SHIFT":
        return EXCLUDE, ("ASB-07-SHIFTING-EXCL",)
    if s.kind == "STOPPAGE" and s.reason == "SHIP_EQUIPMENT":
        return EXCLUDE, ("ASB-07-VESSEL-FAULT",)
    if s.kind == "EXCESS_PUMPING":
        return EXCLUDE, ("RIDER-PUMPING",)
    if s.kind == "DOCS_WAIT_GRACE":
        return EXCLUDE, ("SV6-DOCS-WAIT", "BPV4-DOCS-WAIT")
    if s.kind == "DOCS_WAIT":
        return COUNT, ("SV6-DOCS-WAIT", "BPV4-DOCS-WAIT")
    return COUNT, ("ASB-07-HOURS",)


def _demurrage_effect(s: _Seg, pol: Policy, case: Case) -> tuple[str, tuple[str, ...]]:
    if s.kind == "SHIFT":
        if _shift_mode(pol, case) == "COUNT":
            return FULL, ("LAW-ONCE-ON-DEM", "ASB-08-RATE-PRORATA")
        return EXCLUDE, ("ASB-07-SHIFTING-EXCL",)
    if s.kind == "STOPPAGE":
        if s.reason == "SHIP_EQUIPMENT":
            if pol.vessel_fault_on_demurrage == "EXCLUDE":
                return EXCLUDE, ("ASB-07-VESSEL-FAULT",)
            return FULL, ("LAW-ONCE-ON-DEM", "ASB-08-RATE-PRORATA")
        if _half_rate_cause(s.reason, case):
            return HALF, ("ASB-08-HALF-RATE",)
    if s.kind == "EXCESS_PUMPING":
        return EXCLUDE, ("RIDER-PUMPING",)
    if s.kind == "DOCS_WAIT_GRACE":
        return EXCLUDE, ("SV6-DOCS-WAIT", "BPV4-DOCS-WAIT")
    if s.kind == "DOCS_WAIT":
        return FULL, ("SV6-DOCS-WAIT", "BPV4-DOCS-WAIT", "ASB-08-RATE-PRORATA")
    if s.kind == "WAIT" and s.reason == "NIGHT_RESTRICTION":
        return FULL, ("LAW-ONCE-ON-DEM", "ASB-08-RATE-PRORATA") + s.rules
    return FULL, ("ASB-08-RATE-PRORATA",)


def _walk(segs: list[_Seg], start: Fraction, allowed: Fraction, pol: Policy, case: Case
          ) -> tuple[list[_Piece], Fraction | None]:
    pieces: list[_Piece] = []
    used_laytime = Fraction(0)
    phase, dem_start = (LAYTIME, None) if allowed > 0 else (DEMURRAGE, start)
    for s in segs:
        a = s.a
        while a < s.b:
            if phase == LAYTIME:
                effect, rids = _laytime_effect(s, pol)
                b = min(s.b, a + (allowed - used_laytime)) if effect == COUNT else s.b
                pieces.append(_Piece(s, a, b, LAYTIME, effect, rids))
                if effect == COUNT:
                    used_laytime += b - a
                    if used_laytime >= allowed:
                        phase, dem_start = DEMURRAGE, b
                a = b
            else:
                effect, rids = _demurrage_effect(s, pol, case)
                pieces.append(_Piece(s, a, s.b, DEMURRAGE, effect, rids))
                a = s.b
    return pieces, dem_start


def _half_rate_front(pieces: list[_Piece], minutes: Fraction) -> list[_Piece]:
    """대안 계산(05 §7-3): 체선 전액 구간의 앞에서부터 minutes만큼을 반액으로 바꾼다.
    레이타임 중 중단이 레이타임을 그만큼 먼저 소진시켰으므로 체선 앞부분을 그 결과로 본다."""
    out, left = [], minutes
    for p in pieces:
        if left > 0 and p.phase == DEMURRAGE and p.effect == FULL:
            take = min(p.dur, left)
            half = replace(p, b=p.a + take, effect=HALF, rule_ids=("ASB-08-HALF-RATE",))
            out.append(half)
            if take < p.dur:
                out.append(replace(p, a=p.a + take))
            left -= take
        else:
            out.append(p)
    return out


# ---------------------------------------------------------------- 계산

def compute_statement(case: Case, policy: Policy | None = None, *, with_alternatives: bool = True) -> Statement:
    """SOF + 계약 조건 → 레이타임 계산서. 지원하지 않는 SOF 패턴이면 CaseError."""
    pol = policy or Policy()
    times = [e.ts_local for e in case.sof_events]
    tb = _Timebase(datetime.combine(min(times).date(), datetime.min.time()))
    idx = _Index(case, tb)
    specs: list[_IssueSpec] = []
    terms, term = case.terms, case.terminal
    base = case.base_date

    def T(m: Fraction | None) -> datetime | None:
        return None if m is None else tb.dt(m)

    def F(m: Fraction | None) -> str:
        return fmt_dt(T(m), base)

    # 1) NOR 유효성과 개시 ------------------------------------------------------
    notices = _notices(idx)
    first = notices[0]
    anch, af, hd = idx.get("ANCHORED"), idx.get("ALL_FAST"), idx.get("HOSES_DISCONNECTED")
    oc = idx.get("OPS_COMMENCED")
    notice_min = terms.notice_hours * 60
    nor_valid = anch is None or first.tendered.t >= anch.t
    retender = None
    if not nor_valid:
        retender = next((n for n in notices[1:] if n.tendered.t >= anch.t), None)

    def by_notice(n: _Notice) -> tuple[Fraction, str, Fraction]:
        exp = n.received.t + notice_min
        if af.t < n.received.t:
            return n.received.t, "NOR_AFTER_BERTH", exp
        if af.t <= exp:
            return af.t, "ALL_FAST", exp
        return exp, "NOTICE_EXPIRY", exp

    effective = first
    if nor_valid:
        start, basis, notice_exp = by_notice(first)
        start_rules = ("ASB-06-NOR-START",)
        start_rows = _rows(first.received, af)
    elif pol.invalid_nor_waived:
        start, basis, notice_exp = by_notice(first)
        basis = "WAIVED_" + basis
        start_rules = ("ASB-06-NOR-START", "LAW-NOR-WAIVER")
        start_rows = _rows(first.received, af)
    elif retender:
        effective = retender
        start, basis, notice_exp = by_notice(retender)
        basis = "RETENDER_" + basis
        start_rules = ("ASB-06-NOR-START", "LAW-NOR-ARRIVAL")
        start_rows = _rows(retender.received, af)
    elif oc:
        start, basis, notice_exp = oc.t, "OPS_COMMENCED", first.received.t + notice_min
        start_rules = ("LAW-NOR-ARRIVAL", "LAW-NOR-WAIVER")
        start_rows = _rows(first.tendered, anch, oc)
    else:
        raise CaseError(case.case_id, f"도착 전 NOR(행 {first.tendered.row})이고 재제출·하역 개시 기록이 없어 "
                                      "개시를 정할 수 없음 — 담당자 판단 필요")
    if basis.endswith("NOR_AFTER_BERTH"):
        specs.append(_IssueSpec("NOR-AFTER-BERTH", LEVEL_INFO, "접안 완료 뒤에 NOR — NOR 수령 시점부터 개시",
                                f"접안 완료 {F(af.t)}, NOR 수령 {F(effective.received.t)}. 레이타임은 NOR 전에 개시되지 않음",
                                ("ASB-06-NOR-START",), _rows(af, effective.received)))
    if not first.has_receipt:
        specs.append(_IssueSpec("NOR-NO-RECEIPT", LEVEL_EVIDENCE, "NOR 수령 기록 없음 — 제출 시각을 수령 시각으로 사용",
                                "06 §6 기준 통지시간은 NOR_RECEIVED부터 센다. 대리점 수령 시각 확인",
                                ("ASB-06-NOR-START",), _rows(first.tendered)))
    if nor_valid and len(notices) > 1:
        specs.append(_IssueSpec("NOR-MULTIPLE", LEVEL_INFO, f"NOR {len(notices)}회 — 첫 유효 NOR 기준으로 계산",
                                "첫 NOR이 유효하므로 뒤의 NOR은 개시에 쓰지 않음. 재제출 사유 확인",
                                ("ASB-06-NOR-START",), _rows(*(n.tendered for n in notices))))
    if anch is None:
        specs.append(_IssueSpec("NOR-ARRIVAL-UNKNOWN", LEVEL_INFO, "묘박지 도착(ANCHORED) 기록 없음 — NOR 유효성 미확인",
                                "도착 시각을 AIS·SOF로 확인해야 도착 전 NOR 여부를 판단할 수 있음",
                                ("LAW-NOR-ARRIVAL",), _rows(first.tendered)))
    if not nor_valid:
        gap = anch.t - first.tendered.t
        if retender:
            outcome = f"재제출 NOR {F(retender.received.t)} 기준으로 개시"
        elif oc:
            outcome = f"재제출이 없어 하역 개시 {F(oc.t)}부터 레이타임(The Happy Day 논리)"
        else:
            outcome = "개시 판단 불가"
        specs.append(_IssueSpec(
            "NOR-EARLY", LEVEL_EVIDENCE, f"도착 전 NOR — 무효로 보고 계산 ({fmt_hours(gap / 60)} 빠름)",
            f"NOR 제출 {F(first.tendered.t)}이 묘박지 투묘 {F(anch.t)}보다 빠름 → {outcome}. "
            "AIS·SOF 도착 시각 대조 필요", ("LAW-NOR-ARRIVAL",), _rows(first.tendered, anch)))
        if first.has_receipt:
            specs.append(_IssueSpec(
                "DISPUTE-NOR-WAIVER", LEVEL_REVIEW, "대리점의 NOR 수령이 하자 포기(waiver)인지",
                f"무효 NOR을 대리점이 수령함(행 {first.received.row}). 수령 문구에 'validity reserved' 같은 유보가 "
                "없으면 선주는 하자가 치유됐다고 주장할 수 있음. 기본 계산은 무효 NOR 기준, 대안은 첫 NOR 유효",
                ("LAW-NOR-WAIVER", "LAW-NOR-ARRIVAL"), _rows(first.tendered, first.received, anch),
                dispute_ref="05 §7-4", alt_policy={"invalid_nor_waived": not pol.invalid_nor_waived},
                alt_title="선주 주장: 수령으로 하자 포기 → 첫 NOR 유효" if not pol.invalid_nor_waived
                else "용선주 주장: 무효 NOR 기준"))

    # 2) 구간 ----------------------------------------------------------------
    lo = min(first.tendered.t, anch.t if anch else first.tendered.t, start)
    phys = _physical(idx, case, tb, lo, first)
    phys, pump = _apply_pumping(phys, case, idx, pol)
    docs = idx.get("DOCS_ON_BOARD")
    end, end_rules = hd.t, ("ASB-11-END-HOSES",)
    grace = pol.docs_wait_grace_hours
    if grace is not None and docs and docs.t - hd.t > grace * 60:
        g = hd.t + grace * 60
        phys = [s for s in phys if s.kind != "DOCS_WAIT"] + [
            _Seg(hd.t, g, "DOCS_WAIT_GRACE", None, _rows(hd, docs)),
            _Seg(g, docs.t, "DOCS_WAIT", None, _rows(hd, docs)),
        ]
        end, end_rules = docs.t, ("ASB-11-END-HOSES", "SV6-DOCS-WAIT", "BPV4-DOCS-WAIT")
    if end <= start:
        raise CaseError(case.case_id, f"레이타임 개시 {F(start)}가 종료 {F(end)}보다 늦거나 같음 — SOF 확인")

    allowed = terms.laytime_this_port_hours * 60
    pieces, dem_start = _walk(_clip(phys, start, end), start, allowed, pol, case)
    half_cause_laytime = sum((p.dur for p in pieces if p.phase == LAYTIME and p.seg.kind == "STOPPAGE"
                              and _half_rate_cause(p.seg.reason, case)), Fraction(0))
    if pol.laytime_stoppage_half_rate and half_cause_laytime:
        pieces = _half_rate_front(pieces, half_cause_laytime)

    # 3) 합계 ----------------------------------------------------------------
    zero = Fraction(0)
    elapsed = end - start
    excluded = sum((p.dur for p in pieces if p.effect == EXCLUDE), zero)
    counted = sum((p.dur for p in pieces if p.effect == COUNT), zero)
    full = sum((p.dur for p in pieces if p.effect == FULL), zero)
    half = sum((p.dur for p in pieces if p.effect == HALF), zero)
    used = elapsed - excluded
    dem = full + half
    if used != counted + dem or dem != max(zero, used - allowed):   # 구간 합 불변식
        raise AssertionError(f"[{case.case_id}] 내부 합계 불일치: used={used} counted={counted} dem={dem} allowed={allowed}")
    rate = terms.demurrage_rate_usd_day
    amount = _usd(full / 60 * Fraction(rate) / 24 + half / 60 * Fraction(rate) / 48)
    if dem == 0:
        dem_start = None
    margin = (allowed - used) if dem == 0 else None

    # 4) 쟁점·경고 -------------------------------------------------------------
    def sum_where(pred) -> Fraction:
        return sum((p.dur for p in pieces if pred(p)), zero)

    def rows_where(pred) -> tuple[int, ...]:
        return _rows(*(p.seg.rows for p in pieces if pred(p)))

    if terms.shifting_counts_on_demurrage == "DISPUTED":
        is_dem_shift = lambda p: p.seg.kind == "SHIFT" and p.phase == DEMURRAGE  # noqa: E731
        dem_shift = sum_where(is_dem_shift)
        if dem_shift:
            counted_now = _shift_mode(pol, case) == "COUNT"
            specs.append(_IssueSpec(
                "DISPUTE-SHIFT-ON-DEM", LEVEL_REVIEW, f"체선 중 이동 {fmt_hours(dem_shift / 60)}의 산입 여부",
                "cl.7 이동 불산입은 'used laytime'만 언급함. 기본 계산은 once on demurrage 원칙으로 산입(선주 입장), "
                "용선주는 공제를 주장할 수 있음" if counted_now else
                "이 계산은 체선 중 이동을 공제함(용선주 입장). 선주는 once on demurrage 원칙으로 산입을 주장할 수 있음",
                ("ASB-07-SHIFTING-EXCL", "LAW-ONCE-ON-DEM"), rows_where(is_dem_shift), dispute_ref="05 §7-1",
                minutes=dem_shift, alt_policy={"shift_on_demurrage": "EXCLUDE" if counted_now else "COUNT"},
                alt_title="용선주 주장: 체선 중 이동도 공제" if counted_now else "선주 주장: 체선 중 이동 산입"))

    is_lt_night = lambda p: p.seg.kind == "WAIT" and p.seg.reason == "NIGHT_RESTRICTION" and p.phase == LAYTIME  # noqa: E731
    lt_night = sum_where(is_lt_night)
    if lt_night:
        dem_night = sum_where(lambda p: p.seg.kind == "WAIT" and p.seg.reason == "NIGHT_RESTRICTION"
                              and p.phase == DEMURRAGE)
        night_seg = next(s for s in phys if s.kind == "WAIT" and s.reason == "NIGHT_RESTRICTION")
        night_rules = tuple(r for r in night_seg.rules if r != "ULS-DAYTIME-DEF")
        demur_txt = f", 체선 중 {fmt_hours(dem_night / 60)}(once on demurrage로 산입)" if dem_night else ""
        specs.append(_IssueSpec(
            "DISPUTE-NIGHT-WAIT", LEVEL_REVIEW, f"야간 접안 제한 대기 {fmt_hours(lt_night / 60)}의 부담 주체",
            f"선석이 비었는데({F(night_seg.a)}) 그때 움직였다면 접안 완료가 주간 창"
            f"({term.daytime_start:%H:%M}~{term.daytime_end:%H:%M}) 밖이라 {F(night_seg.b)}까지 대기"
            f"({'·'.join(night_rules)}). 대기 {fmt_hours((night_seg.b - night_seg.a) / 60)} 중 레이타임 산입 "
            f"{fmt_hours(lt_night / 60)}{demur_txt}. 기본 계산은 reachable on arrival로 산입, "
            "용선주는 cl.6 예외(통제 밖 지연)를 주장할 수 있음",
            ("ASB-09-REACHABLE", "ASB-06-BERTH-DELAY-EXC") + night_seg.rules, night_seg.rows,
            dispute_ref="05 §7-2", minutes=lt_night,
            alt_policy={"berth_delay_exception": not pol.berth_delay_exception},
            alt_title="용선주 주장: 야간 제한 대기는 cl.6 예외로 불산입" if not pol.berth_delay_exception
            else "선주 주장: reachable on arrival로 산입"))

    if half_cause_laytime and (dem or pol.laytime_stoppage_half_rate):
        is_lt_half = lambda p: (p.phase == LAYTIME and p.seg.kind == "STOPPAGE"  # noqa: E731
                                and _half_rate_cause(p.seg.reason, case))
        specs.append(_IssueSpec(
            "DISPUTE-LAYTIME-HALF-RATE", LEVEL_REVIEW,
            f"레이타임 중 반액 사유 중단 {fmt_hours(half_cause_laytime / 60)}이 만든 체선의 반액 여부",
            "레이타임 중 중단은 그대로 산입(cl.7에 기상 예외 없음). 그 중단 때문에 생긴 체선을 반액으로 볼지는 "
            "해석이 갈림. 대안은 체선 앞부분의 같은 시간만큼을 반액으로 계산",
            ("ASB-08-HALF-RATE",), rows_where(is_lt_half), dispute_ref="05 §7-3", minutes=half_cause_laytime,
            alt_policy={"laytime_stoppage_half_rate": not pol.laytime_stoppage_half_rate},
            alt_title="용선주 주장: 해당 체선 반액" if not pol.laytime_stoppage_half_rate else "선주 주장: 전액"))

    if docs and docs.t - hd.t > rules.DOCS_WAIT_GRACE_HOURS * 60:
        wait = docs.t - hd.t
        specs.append(_IssueSpec(
            "DISPUTE-DOCS-WAIT", LEVEL_REVIEW, f"호스 분리 후 서류 대기 {fmt_hours(wait / 60)}의 산입 여부",
            f"{terms.form} 기준 기본 계산은 호스 분리에서 종료(서류 대기 미산입). 서식·Rider에 따라 "
            f"{rules.DOCS_WAIT_GRACE_HOURS}h 초과분을 산입하는 조항이 있을 수 있음 — 계약 문구 확인",
            ("ASB-11-END-HOSES", "SV6-DOCS-WAIT", "BPV4-DOCS-WAIT"), _rows(hd, docs), dispute_ref="05 §7-5",
            minutes=wait - rules.DOCS_WAIT_GRACE_HOURS * 60,
            alt_policy={"docs_wait_grace_hours": None if grace is not None else Fraction(rules.DOCS_WAIT_GRACE_HOURS)},
            alt_title=f"선주 주장: {rules.DOCS_WAIT_GRACE_HOURS}h 초과 서류 대기 산입" if grace is None
            else "용선주 주장: 호스 분리에서 종료"))

    is_dem_fault = lambda p: p.phase == DEMURRAGE and p.seg.kind == "STOPPAGE" and p.seg.reason == "SHIP_EQUIPMENT"  # noqa: E731
    dem_fault = sum_where(is_dem_fault)
    if dem_fault:
        excl = pol.vessel_fault_on_demurrage == "EXCLUDE"
        specs.append(_IssueSpec(
            "VESSEL-FAULT-ON-DEM", LEVEL_REVIEW, f"체선 중 선박 귀책 중단 {fmt_hours(dem_fault / 60)}",
            ("기본 계산은 선주 귀책 지연이라 체선료에서 뺌. " if excl else "이 계산은 once on demurrage로 산입함. ")
            + "cl.7 예외는 'used laytime'만 언급하므로 체선 중 적용 근거(문구·판례) 확인 필요(05 §7 목록 밖 추가 쟁점)",
            ("ASB-07-VESSEL-FAULT", "LAW-ONCE-ON-DEM"), rows_where(is_dem_fault), minutes=dem_fault,
            alt_policy={"vessel_fault_on_demurrage": "COUNT" if excl else "EXCLUDE"},
            alt_title="선주 주장: 체선 중이므로 산입" if excl else "용선주 주장: 선주 귀책이라 공제"))

    w = terms.pumping_warranty_hours
    if pump.status in ("DEDUCTED", "OWNER_NO_DEDUCTION"):
        log = case.pumping_log
        specs.append(_IssueSpec(
            "PUMPING-EVIDENCE", LEVEL_EVIDENCE,
            f"펌핑 보증 초과 {fmt_hours(pump.excess_minutes / 60)} 공제 — 육상 제한 없음 입증 필요"
            if pump.status == "DEDUCTED" else f"펌핑 보증 초과 {fmt_hours(pump.excess_minutes / 60)} — 이 계산은 공제 안 함",
            f"실하역 {fmt_hours(pump.pumping_minutes / 60)} > 보증 {fmt_num(w)}h, 평균 매니폴드 "
            f"{fmt_num(log.avg_manifold_psi) if log.avg_manifold_psi is not None else '—'} psi"
            f"{' < 보증 ' + fmt_num(terms.pumping_warranty_psi) + ' psi' if terms.pumping_warranty_psi is not None else ''}"
            f", 육상 제한 없음 기록({log.evidence_ref or '펌핑 로그'}). 공제는 터미널 배압·수용 기록이 근거이므로 "
            "원본 대조 필요", ("RIDER-PUMPING",), pump.rows, minutes=pump.excess_minutes,
            alt_policy={"pumping_deduction": not pol.pumping_deduction},
            alt_title="선주 주장: 펌핑 공제 없음" if pol.pumping_deduction else "용선주 주장: 펌핑 초과 공제"))
    elif pump.status == "NO_LOG":
        specs.append(_IssueSpec(
            "PUMPING-NO-LOG", LEVEL_EVIDENCE, "펌핑 보증 초과 가능성 — 펌핑 로그가 없어 공제 보류",
            f"실하역 {fmt_hours(pump.pumping_minutes / 60)} > 보증 {fmt_num(w)}h. 매니폴드 압력과 육상 제한 여부 "
            "기록이 있어야 공제할 수 있음", ("RIDER-PUMPING",), pump.rows, minutes=pump.excess_minutes))
    elif pump.status == "SHORE_RESTRICTED":
        specs.append(_IssueSpec(
            "PUMPING-SHORE-RESTRICTED", LEVEL_INFO, "육상 제한 기록이 있어 펌핑 초과 공제 안 함",
            f"실하역 {fmt_hours(pump.pumping_minutes / 60)} > 보증 {fmt_num(w)}h이지만 육상 배압·수용 제한이 기록됨",
            ("RIDER-PUMPING",), pump.rows))
    elif pump.status == "NO_OPS":
        specs.append(_IssueSpec(
            "PUMPING-NO-OPS", LEVEL_INFO, "하역 개시·완료 기록이 없어 펌핑 보증을 판단할 수 없음",
            "OPS_COMMENCED·OPS_COMPLETED가 있어야 실하역 시간을 잰다", ("RIDER-PUMPING",), ()))

    if dem == 0 and margin < rules.LOW_MARGIN_HOURS * 60:
        specs.append(_IssueSpec(
            "LOW-MARGIN", LEVEL_WARNING, f"레이타임 여유 {fmt_hours(margin / 60)} — 추가 지연은 곧바로 체선료",
            f"사용 {fmt_hours(used / 60)} / 허용 {fmt_hours(allowed / 60)}. 기준 {rules.LOW_MARGIN_HOURS}h 미만",
            ("ENG-LOW-MARGIN",), _rows(start_rows, hd), minutes=margin))
    if not idx.get("ANCHOR_AWEIGH") and start < af.t:
        specs.append(_IssueSpec(
            "NO-ANCHOR-AWEIGH", LEVEL_EVIDENCE, "양묘(ANCHOR_AWEIGH) 기록 없음 — 이동 시간 공제 불가",
            "묘박지에서 선석으로 이동한 시각이 없어 개시~접안 완료 전체를 대기로 계산함",
            ("ASB-07-SHIFTING-EXCL",), _rows(af)))
    for s, _ in idx.stops:
        if s.ev.reason_code is None:
            specs.append(_IssueSpec(
                "STOP-NO-REASON", LEVEL_EVIDENCE, f"하역 중단 사유 코드 없음(행 {s.row}) — 기타로 계산",
                "06 §6 OPS_STOPPED 사유 코드(WEATHER 등)가 있어야 반액·공제를 판단할 수 있음",
                ("ASB-08-HALF-RATE", "ASB-07-VESSEL-FAULT"), _rows(s)))

    # 5) 대안 계산 --------------------------------------------------------------
    issues: list[Issue] = []
    alts: list[AltCalc] = []
    for sp in specs:
        alt = None
        if with_alternatives and sp.alt_policy is not None:
            alt_st = compute_statement(case, replace(pol, **sp.alt_policy), with_alternatives=False)
            alt = AltCalc(sp.code, sp.alt_title or "", dict(sp.alt_policy), alt_st.laytime_start_at,
                          alt_st.demurrage_start_at, alt_st.used_hours, alt_st.demurrage_hours,
                          alt_st.half_rate_hours, alt_st.amount_usd, alt_st.amount_usd - amount)
            alts.append(alt)
        issues.append(Issue(sp.code, sp.level, sp.title, sp.detail, rules.check(*sp.rule_ids), sp.sof_rows,
                            sp.dispute_ref, None if sp.minutes is None else sp.minutes / 60, alt))
    issues.sort(key=lambda i: LEVEL_ORDER[i.level])

    # 6) 원장·공제·계산서 줄 ------------------------------------------------------
    ledger = [_entry(tb, s, PRE, NOT_COUNTED, start_rules) for s in _clip(phys, lo, start)]
    ledger += [_entry(tb, p.seg, p.phase, p.effect, p.rule_ids, p.a, p.b) for p in pieces]
    ledger += [_entry(tb, s, POST, NOT_COUNTED, ("ASB-11-END-HOSES",)) for s in _clip(phys, end, max(end, docs.t if docs else end))]
    deductions = _deductions(tb, pieces, case)
    lines = _lines(case, tb, F, first, effective, retender, nor_valid, anch, af, hd, notice_exp, start, basis,
                   start_rules, start_rows, end, end_rules, elapsed, pieces, phys, used, allowed, dem, dem_start,
                   full, half, rate, amount, docs, pump)

    return Statement(
        statement_id=f"LS-{case.case_id}", call_id=case.call_id or case.case_id, layer=terms.layer, form=terms.form,
        nor_tendered_at=T(first.tendered.t), nor_received_at=T(effective.received.t), nor_valid=nor_valid,
        notice_expiry_at=T(notice_exp), all_fast_at=T(af.t),
        laytime_start_at=T(start), start_basis=basis, start_rule=rules.check(*start_rules),
        laytime_end_at=T(end), end_rule=rules.check(*end_rules),
        elapsed_hours=elapsed / 60, deductions=tuple(deductions), used_hours=used / 60, allowed_hours=allowed / 60,
        demurrage_hours=dem / 60, demurrage_start_at=T(dem_start), full_rate_hours=full / 60, half_rate_hours=half / 60,
        pumping_excess_hours=(pump.excess_minutes / 60 if pump.status == "DEDUCTED" else zero),
        margin_hours=None if margin is None else margin / 60, rate_usd_day=rate, amount_usd=amount,
        lines=tuple(lines), ledger=tuple(ledger), issues=tuple(issues), alt_calculations=tuple(alts),
        policy=pol, base_date=base, title=case.title,
    )


def _usd(x: Fraction) -> Decimal:
    """센트 반올림(ROUND_HALF_UP). 정수 연산이라 정밀도 손실이 없다."""
    sign = -1 if x < 0 else 1
    cents = int(abs(x) * 100 + Fraction(1, 2))
    return (Decimal(sign * cents) / 100).quantize(Decimal("0.01"))


def _label(kind: str, reason: str | None) -> str:
    base = KIND_LABEL.get(kind, kind)
    if kind == "WAIT" and reason:
        return f"{base} — {WAIT_LABEL.get(reason, reason)}"
    if kind == "STOPPAGE" and reason:
        return f"{base} — {STOP_LABEL.get(reason, reason)}"
    return base


def _entry(tb: _Timebase, s: _Seg, phase: str, effect: str, rule_ids: tuple[str, ...],
           a: Fraction | None = None, b: Fraction | None = None) -> LedgerEntry:
    a = s.a if a is None else a
    b = s.b if b is None else b
    return LedgerEntry(tb.dt(a), tb.dt(b), s.kind, s.reason, _label(s.kind, s.reason), phase, effect,
                       (b - a) / 60, rules.check(*rule_ids), s.rows)


_DEDUCTION_CATEGORY = {"SHIFT": "SHIFTING", "EXCESS_PUMPING": "PUMPING_EXCESS"}


def _deductions(tb: _Timebase, pieces: list[_Piece], case: Case) -> list[Deduction]:
    out = []
    for p in pieces:
        if p.effect != EXCLUDE:
            continue
        s = p.seg
        if s.kind == "STOPPAGE" and s.reason == "SHIP_EQUIPMENT":
            cat = "VESSEL_FAULT"
        else:
            cat = _DEDUCTION_CATEGORY.get(s.kind, "OTHER")
        disputed = ((s.kind == "SHIFT" and p.phase == DEMURRAGE and case.terms.shifting_counts_on_demurrage == "DISPUTED")
                    or (s.kind == "WAIT" and s.reason == "NIGHT_RESTRICTION")
                    or (s.kind == "STOPPAGE" and p.phase == DEMURRAGE))
        out.append(Deduction(tb.dt(p.a), tb.dt(p.b), p.dur / 60, cat, p.rule_ids[0],
                             f"SOF {fmt_rows(s.rows)}행", disputed, s.rows))
    return out


def _lines(case, tb, F, first, effective, retender, nor_valid, anch, af, hd, notice_exp, start, basis, start_rules,
           start_rows, end, end_rules, elapsed, pieces, phys, used, allowed, dem, dem_start, full, half, rate, amount,
           docs, pump) -> list[Line]:
    """04 §0 레이타임 계산서 템플릿 순서. 모든 줄에 룰 ID, SOF 행(없으면 source)을 붙인다."""
    terms = case.terms
    zero = Fraction(0)
    out: list[Line] = []

    def add(label, value, rule_ids, sof_rows=(), source=None, note=None):
        out.append(Line(label, value, rules.check(*rule_ids), tuple(sof_rows), source, note))

    def excl(pred) -> tuple[Fraction, tuple[int, ...]]:
        sel = [p for p in pieces if p.effect == EXCLUDE and pred(p)]
        return sum((p.dur for p in sel), zero), _rows(*(p.seg.rows for p in sel))

    add("NOR 제출", F(first.tendered.t), ("ASB-06-NOR-START",) + (() if nor_valid else ("LAW-NOR-ARRIVAL",)),
        _rows(first.tendered), note=None if nor_valid else "도착 전 제출 → 무효")
    add("NOR 수령", F(first.received.t), ("ASB-06-NOR-START",), _rows(first.received),
        note=None if first.has_receipt else "수령 기록 없음 — 제출 시각 사용")
    if anch:
        add("묘박지 도착(투묘)", F(anch.t), ("LAW-NOR-ARRIVAL",), _rows(anch), note="NOR 유효성 대조 기준")
    if retender:
        add("재제출 NOR 수령", F(retender.received.t), ("ASB-06-NOR-START", "LAW-NOR-ARRIVAL"), _rows(retender.received))
    add(f"통지시간 만료 (NOR+{fmt_num(terms.notice_hours)}h)", F(notice_exp), ("ASB-06-NOR-START",),
        _rows(effective.received), source="CONTRACT_TERMS.notice_hours",
        note="무효 NOR 기준이라 개시에 쓰지 않음" if basis == "OPS_COMMENCED" else None)
    add("접안 완료 (all fast)", F(af.t), ("ASB-06-NOR-START",), _rows(af))
    add("레이타임 개시", f"{F(start)} — {START_BASIS_LABEL[basis]}", start_rules, start_rows)
    add("호스 분리 = 레이타임 종료", F(end), end_rules, _rows(hd) if end == hd.t else _rows(hd, docs),
        note=None if end == hd.t else "대안 계산: 서류 대기 초과분 산입")
    add("경과 시간", fmt_hours(elapsed / 60), start_rules + end_rules, _rows(start_rows, hd))

    shift_ex, shift_rows = excl(lambda p: p.seg.kind == "SHIFT")
    shift_all = [s for s in phys if s.kind == "SHIFT"]
    note = None
    if shift_all and shift_all[0].b <= start:
        note = "개시 전 이동이라 이미 미산입"
    elif any(p.seg.kind == "SHIFT" and p.phase == DEMURRAGE and p.effect == FULL for p in pieces):
        note = "체선 중 이동은 기본 계산에서 산입 — 담당자 확인 필요(05 §7-1)"
    add("(−) 이동 shifting", fmt_hours(shift_ex / 60), ("ASB-07-SHIFTING-EXCL",),
        shift_rows or (shift_all[0].rows if shift_all else ()), note=note,
        source=None if (shift_rows or shift_all) else "SOF에 이동 없음")
    fault, fault_rows = excl(lambda p: p.seg.kind == "STOPPAGE" and p.seg.reason == "SHIP_EQUIPMENT")
    add("(−) 선박 귀책", fmt_hours(fault / 60), ("ASB-07-VESSEL-FAULT",), fault_rows,
        source=None if fault_rows else "SOF에 선박 귀책 중단 없음")
    excess, excess_rows = excl(lambda p: p.seg.kind == "EXCESS_PUMPING")
    pump_note = {"NONE": None if terms.pumping_warranty_hours is None else "보증 이내",
                 "NO_LOG": "펌핑 로그 없음 — 공제 보류", "SHORE_RESTRICTED": "육상 제한 기록 — 공제 안 함",
                 "PRESSURE_MET": "압력 보증 충족 — 공제 안 함", "OWNER_NO_DEDUCTION": "대안 계산: 공제 안 함",
                 "NO_OPS": "하역 기록 없음 — 판단 불가", "DEDUCTED": "실하역 − 보증 시간"}[pump.status]
    add("(−) 펌핑 보증 초과", fmt_hours(excess / 60), ("RIDER-PUMPING",), excess_rows or pump.rows,
        source=None if (excess_rows or pump.rows) else
        ("CONTRACT_TERMS.pumping_warranty_hours 없음" if terms.pumping_warranty_hours is None else "펌핑 기록 없음"),
        note=pump_note)
    other, other_rows = excl(lambda p: p.seg.kind not in ("SHIFT", "EXCESS_PUMPING")
                             and not (p.seg.kind == "STOPPAGE" and p.seg.reason == "SHIP_EQUIPMENT"))
    if other:
        others = sorted({r for p in pieces if p.effect == EXCLUDE and p.seg.kind not in ("SHIFT", "EXCESS_PUMPING")
                         for r in p.rule_ids})
        add("(−) 기타 공제", fmt_hours(other / 60), tuple(others), other_rows, note="대안 계산의 쟁점 입장")
    add("사용 시간 = 경과 − 공제", fmt_hours(used / 60), ("ASB-07-HOURS",),
        _rows(start_rows, hd, shift_rows, fault_rows, excess_rows))
    add("허용 시간", fmt_hours(allowed / 60), ("ASB-07-HOURS",), source="CONTRACT_TERMS.laytime_this_port_hours")
    dem_rows = _rows(*(p.seg.rows for p in pieces if p.phase == DEMURRAGE and p.effect in (FULL, HALF)))
    add("체선 시간 = max(0, 사용 − 허용)", fmt_hours(dem / 60), ("ASB-08-RATE-PRORATA",), dem_rows,
        source=None if dem_rows else "체선 없음",
        note=None if dem else f"여유 {fmt_hours((allowed - used) / 60)}")
    first_dem = next((p for p in pieces if p.phase == DEMURRAGE), None)
    add("체선 개시 시각", F(dem_start), ("ASB-07-HOURS", "ASB-08-RATE-PRORATA"),
        first_dem.seg.rows if (first_dem and dem_start is not None) else (),
        source=None if dem_start is not None else "체선 없음")
    half_pieces = [p for p in pieces if p.effect == HALF]
    spans = ", ".join(f"{F(p.a)}~{F(p.b)}" for p in half_pieces)
    add("반액 구간", fmt_hours(half / 60) + (f" ({spans})" if spans else ""), ("ASB-08-HALF-RATE",),
        _rows(*(p.seg.rows for p in half_pieces)), source=None if half_pieces else "반액 구간 없음")
    add("전액 구간 = 체선 − 반액", fmt_hours(full / 60), ("ASB-08-RATE-PRORATA",),
        _rows(*(p.seg.rows for p in pieces if p.effect == FULL)), source=None if full else "체선 없음")
    add("요율", f"USD {rate:,.0f}/일", ("ASB-08-RATE-PRORATA",), source="CONTRACT_TERMS.demurrage_rate_usd_day")
    add("체선료 = 전액×율/24 + 반액×율/48",
        f"{fmt_usd(amount)} = {fmt_num(full / 60)}×{rate:,.0f}/24 + {fmt_num(half / 60)}×{rate:,.0f}/48",
        ("ASB-08-RATE-PRORATA", "ASB-08-HALF-RATE"), dem_rows, source=None if dem_rows else "체선 없음")
    if docs and end == hd.t and docs.t > hd.t:
        add("(참고) 호스 분리 후 서류 대기", fmt_hours((docs.t - hd.t) / 60), ("ASB-11-END-HOSES",), _rows(hd, docs),
            note="종료 뒤라 미산입")
    return out


def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, datetime):
        return x.isoformat(timespec="minutes") if not x.second else x.isoformat()
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, Fraction):
        return float(x) if x.denominator != 1 else int(x)
    if isinstance(x, Decimal):
        return float(x)
    return x
