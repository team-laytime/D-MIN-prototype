"""vessel_journeys.csv → 항차별 레이타임·체선료 계산.

계산식은 clock/ 엔진(ASBATANKVOY 기준 룰, docs/domain/05)과 같다. CSV에는 계약 조건(허용 레이타임·요율)이
없으므로 Terms 기본값은 [가정]이고, 체선 "시간"은 요율과 무관하게 먼저 나온다.

    개시  t0 = min(NOR 수령 + 통지시간, 접안 완료)           ASB-06-NOR-START
              (접안 완료가 NOR 수령보다 앞서면 NOR 수령 시각부터)
    종료  t1 = 호스 분리 = 마지막 선적·양하 완료 + 지연(기본 0)   ASB-11-END-HOSES
    공제  레이타임 중 양묘→접안 이동은 뺀다                     ASB-07-SHIFTING-EXCL
          이미 체선이면 산입(once on demurrage, 기본)           LAW-ONCE-ON-DEM
    사용  U = (t1 - t0) - 공제
    체선  D = max(0, U - L)            금액 = D × 요율 / 24       ASB-08-RATE-PRORATA

실행 (CSV는 신뢰하지 않는 입력이라 -I 로 격리해 돌린다):
    python3 -I journeys/laytime_csv.py journeys/data/vessel_journeys.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path

_FMT = "%Y-%m-%d %H:%M:%S"
_TIME_ONLY = re.compile(r"^\d{1,2}:\d{2}$")

KIND = {
    "입항": "ARRIVE", "투묘": "ANCHOR", "양묘": "AWEIGH", "NOR 제출": "NOR_T", "NOR 승인": "NOR_A",
    "접안": "BERTH", "이안": "UNBERTH", "이선": "MOVE", "출항": "DEPART", "화물정보": "CARGO",
    "선적 시작": "OPS_S", "선적 완료": "OPS_E", "양하 시작": "OPS_S", "양하 완료": "OPS_E",
}

FLAG_TEXT = {
    "NOR-EARLY": "NOR이 투묘보다 빠름 — 엄격하게 보면 무효 NOR(LAW-NOR-ARRIVAL)",
    "MULTI-CALL": "가스부두 방문 구간은 이벤트가 없어 SK 구간만 계산",
    "RE-BERTH": "하역 도중 이안 후 재접안 — 중단 구간 산입 여부 쟁점",
    "RE-ANCHOR": "접안 전 재투묘(묘박지 이동) — 산입으로 계산",
    "WAIT-ALONGSIDE": "대기 중 다른 부두에 접안해 있었음 — 하역 선석 접안 완료만 all fast로 봄",
    "PIER-SHIFT": "대기 중 부두 간 이동(이선) — 부두 간 이동은 산입(cl.9)",
    "LOW-MARGIN": "체선은 없지만 허용 시간 여유가 2시간 미만(ENG-LOW-MARGIN)",
    "INFERRED": "시각만 있는 행의 날짜를 추정해 사용",
}


# ----------------------------------------------------------------------------- 입력

@dataclass
class Row:
    jid: str
    seq: int
    vessel: str
    work: str
    ts: datetime | None
    event: str
    berth: str
    cargo: str
    weight: float | None
    bl: str
    ops_ts: datetime | time | None
    cargo_ts: datetime | time | None


def parse_stamp(s: str | None) -> datetime | time | None:
    s = (s or "").strip()
    if not s:
        return None
    if _TIME_ONLY.match(s):
        h, m = s.split(":")
        return time(int(h), int(m))
    return datetime.strptime(s, _FMT)


def load_rows(path: str | Path) -> list[Row]:
    rows: list[Row] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            ts = parse_stamp(r["일시"])
            if isinstance(ts, time):
                raise ValueError(f"일시에 시각만 있는 행: {r}")
            w = (r["중량(톤)"] or "").strip()
            rows.append(Row(
                jid=r["일정ID"].strip(), seq=int(r["순서"]), vessel=r["선박명"].strip(), work=r["작업구분"].strip(),
                ts=ts, event=r["이벤트"].strip(), berth=r["부두"].strip(), cargo=r["화물"].strip(),
                weight=float(w) if w else None, bl=r["B/L"].strip(),
                ops_ts=parse_stamp(r["운항기록시각"]), cargo_ts=parse_stamp(r["하역기록시각"]),
            ))
    return rows


@dataclass
class Event:
    kind: str
    t: datetime
    seq: int
    berth: str = ""
    cargo: str = ""
    work: str = ""
    raw: str = ""
    src: str = "일시"          # 일시 | 하역기록 | 운항기록 | 시각만(날짜 추정)
    inferred: bool = False


@dataclass
class Voyage:
    jid: str
    vessel: str
    events: list[Event]
    rows: list[Row]
    notes: list[str] = field(default_factory=list)


def _ref_time(evs: list[Event], kind: str, r: Row) -> datetime:
    """시각만 있는 행의 날짜를 정할 기준 시각: 그 시각 '이후 처음 오는' 같은 HH:MM을 고른다."""
    def latest(kinds, pred=lambda e: True):
        c = [e.t for e in evs if e.kind in kinds and pred(e)]
        return max(c) if c else None

    ref = None
    if kind == "NOR_A":
        ref = latest(("NOR_T",))
    elif kind == "OPS_E":
        ref = latest(("OPS_S",), lambda e: e.cargo == r.cargo) or latest(("OPS_S",))
    elif kind == "OPS_S":
        ref = latest(("BERTH",))
    if ref is None:
        prior = [e.t for e in evs if e.seq < r.seq]
        ref = max(prior) if prior else min(e.t for e in evs)
    return ref


def _build(jid: str, rs: list[Row]) -> Voyage:
    evs: list[Event] = []
    tail: list[tuple[Row, str, time]] = []
    notes: list[str] = []
    for r in rs:
        kind = KIND.get(r.event)
        if kind is None:
            notes.append(f"알 수 없는 이벤트 {r.event!r}(순서 {r.seq}) 무시")
            continue
        if kind == "CARGO":
            continue
        t, src = None, ""
        if r.ts is not None:
            t, src = r.ts, "일시"
        elif isinstance(r.cargo_ts, datetime):
            t, src = r.cargo_ts, "하역기록"
        elif isinstance(r.ops_ts, datetime):
            t, src = r.ops_ts, "운항기록"
        if t is not None:
            evs.append(Event(kind, t, r.seq, r.berth, r.cargo, r.work, r.event, src))
            continue
        only = next((v for v in (r.cargo_ts, r.ops_ts) if isinstance(v, time)), None)
        if only is not None:
            tail.append((r, kind, only))
        # 시각이 전혀 없는 행은 자리표시(중복) 행이라 무시한다.
    for r, kind, only in tail:
        if any(e.kind == kind and (e.t.hour, e.t.minute) == (only.hour, only.minute) for e in evs):
            continue  # 이미 시각이 있는 이벤트의 중복 기록
        ref = _ref_time(evs, kind, r)
        t = datetime.combine(ref.date(), only)
        if t < ref:
            t += timedelta(days=1)
        evs.append(Event(kind, t, r.seq, r.berth, r.cargo, r.work, r.event, "시각만(날짜 추정)", True))
        notes.append(f"순서 {r.seq} {r.event} {only:%H:%M} → {t:%Y-%m-%d %H:%M} 로 날짜 추정")
    evs.sort(key=lambda e: (e.t, e.seq))
    return Voyage(jid, rs[0].vessel, evs, rs, notes)


def build_voyages(rows: list[Row]) -> list[Voyage]:
    by: dict[str, list[Row]] = {}
    for r in rows:
        by.setdefault(r.jid, []).append(r)
    return [_build(jid, sorted(rs, key=lambda r: r.seq)) for jid, rs in by.items()]


# ----------------------------------------------------------------------------- 항차 → 계산 입력

def norm_berth(s: str) -> str:
    m = re.search(r"SK\s*#\s*(\d+(?:-\d+)?)", s or "")
    return f"SK #{m.group(1)}" if m else (s or "").strip()


def _fam(s: str) -> str:
    m = re.search(r"SK\s*#?\s*(\d)", s or "")
    return f"SK{m.group(1)}" if m else (s or "").strip()


@dataclass
class Call:
    jid: str
    vessel: str
    operation: str                 # LOAD | DISCHARGE
    berth: str
    cargo: str
    qty_t: float
    arrive: datetime
    nor_t: datetime
    nor_a: datetime | None
    allfast: datetime
    ops_start: datetime
    ops_end: datetime
    depart: datetime | None
    anchor_first: datetime | None  # 접안 전 첫 투묘
    shifts: list[tuple[datetime, datetime]]   # 양묘 → 접안
    gaps: list[tuple[datetime, datetime]]     # 하역 중단(이안 포함) 구간
    flags: list[str]
    notes: list[str]

    @property
    def nor_early(self) -> bool:
        return self.anchor_first is not None and self.nor_t < self.anchor_first


def extract_call(v: Voyage) -> Call | None:
    ev = v.events

    def of(*kinds: str) -> list[Event]:
        return [e for e in ev if e.kind in kinds]

    nors, os_, oe = of("NOR_T"), of("OPS_S"), of("OPS_E")
    if not (nors and os_ and oe):
        return None
    flags: list[str] = []
    notes = list(v.notes)
    nor_t = nors[0].t
    nor_a = next((e.t for e in of("NOR_A") if e.t >= nor_t), None)
    arrivals = [e.t for e in of("ARRIVE", "ANCHOR")]
    arrive = min(arrivals + [nor_t])
    first_os = min(e.t for e in os_)
    berths = [e for e in of("BERTH") if e.t <= first_os]
    if berths:
        allfast = max(e.t for e in berths)
    else:
        allfast = first_os
        notes.append("접안 이벤트가 없어 하역 개시를 접안 완료로 사용")
    ops_start = first_os
    ops_end = max(e.t for e in oe)
    operation = "LOAD" if os_[0].raw.startswith("선적") else "DISCHARGE"
    ops_berth = norm_berth(sorted(os_, key=lambda e: e.t)[0].berth)
    cargo = re.sub(r"\s+", " ", sorted(os_, key=lambda e: e.t)[0].cargo)
    fam = _fam(ops_berth)
    qty = sum(r.weight or 0.0 for r in v.rows if r.event == "화물정보" and _fam(r.berth) == fam)

    # 하역 중단(이안 포함) 구간과 레그
    unbert = [e.t for e in of("UNBERTH")]
    gaps: list[tuple[datetime, datetime]] = []
    leg_starts = [first_os]
    last_end = None
    for e in sorted(os_ + oe, key=lambda e: (e.t, e.seq)):
        if e.kind == "OPS_E":
            last_end = e.t if last_end is None else max(last_end, e.t)
        elif last_end is not None and any(last_end < u < e.t for u in unbert):
            gaps.append((last_end, e.t))
            leg_starts.append(e.t)
            last_end = None
    # 양묘 → 접안(이동) 구간: 레그마다 접안 직전의 마지막 양묘
    shifts: list[tuple[datetime, datetime]] = []
    lower = arrive
    for i, ls in enumerate(leg_starts):
        bs = [e.t for e in of("BERTH") if e.t <= ls]
        if not bs:
            continue
        af = max(bs)
        aws = [e.t for e in of("AWEIGH") if lower <= e.t < af]
        if aws:
            shifts.append((max(aws), af))
        if i < len(gaps):
            lower = gaps[i][0]
    anchors = sorted(e.t for e in of("ANCHOR") if e.t <= allfast)
    anchor_first = anchors[0] if anchors else None

    # 플래그
    if anchor_first is not None and nor_t < anchor_first:
        flags.append("NOR-EARLY")
    if any("가스부두" in e.berth for e in ev) or any(r.event == "화물정보" and "가스" in r.berth for r in v.rows):
        flags.append("MULTI-CALL")
    if gaps:
        flags.append("RE-BERTH")
    if len(anchors) >= 2:
        flags.append("RE-ANCHOR")
    if any(e.t < allfast for e in of("BERTH")):
        flags.append("WAIT-ALONGSIDE")
    if any(e.t < allfast and arrive <= e.t and _fam(e.berth) != fam and "SK" not in e.berth
           for e in of("MOVE")):
        flags.append("PIER-SHIFT")
    if any(e.inferred for e in ev):
        flags.append("INFERRED")
    depart = max((e.t for e in of("DEPART")), default=None)
    return Call(v.jid, v.vessel, operation, ops_berth, cargo, round(qty, 3), arrive, nor_t, nor_a, allfast,
                ops_start, ops_end, depart, anchor_first, shifts, gaps, flags, notes)


# ----------------------------------------------------------------------------- 계산식

@dataclass(frozen=True)
class Terms:
    """계약 조건. CSV에 없어서 기본값은 [가정] — prototype/data/golden/cases.json의 소형선 예(24h·26,000)."""
    laytime_hours: float = 24.0
    notice_hours: float = 6.0
    rate_usd_day: float = 26_000.0
    hose_lag_min: float = 0.0               # 마지막 완료 → 호스 분리 [가정: 기록이 없어 0]
    shift_counts_on_demurrage: bool = True  # 체선 중 이동 산입(once on demurrage, 엔진 기본)


def _m(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 60


def by_notice(recv: datetime, allfast: datetime, notice_min: float) -> tuple[datetime, str]:
    """엔진 by_notice와 같다. 접안이 NOR보다 먼저면 NOR 수령부터, 아니면 min(NOR+통지, 접안)."""
    exp = recv + timedelta(minutes=notice_min)
    if allfast < recv:
        return recv, "NOR_AFTER_BERTH"
    if allfast <= exp:
        return allfast, "ALL_FAST"
    return exp, "NOTICE_EXPIRY"


def walk(start: datetime, end: datetime, allowed_min: float,
         shifts: list[tuple[datetime, datetime]], excls: list[tuple[datetime, datetime]],
         shift_counts: bool) -> tuple[float, float, float, datetime | None]:
    """start→end를 구간으로 나눠 걷는다. 반환: (사용, 공제, 체선, 레이타임 만료 시각) — 분 단위.

    레이타임 중의 이동(shift)·제외 구간(excl)은 시계를 멈추고, 허용 시간을 다 쓴 뒤의 이동은 산입한다.
    """
    cuts = []
    for a, b in shifts:
        cuts.append((max(a, start), min(b, end), "shift"))
    for a, b in excls:
        cuts.append((max(a, start), min(b, end), "excl"))
    cuts = sorted(c for c in cuts if c[1] > c[0])
    segs, t = [], start
    for a, b, k in cuts:
        a = max(a, t)
        if b <= a:
            continue
        if a > t:
            segs.append((t, a, "count"))
        segs.append((a, b, k))
        t = b
    if end > t:
        segs.append((t, end, "count"))
    lay = allowed_min > 0
    used_lay = dem = ded = 0.0
    expiry = None if lay else start
    for a, b, k in segs:
        dur = _m(a, b)
        if lay:
            if k != "count":
                ded += dur
                continue
            if used_lay + dur >= allowed_min:
                need = allowed_min - used_lay
                expiry = a + timedelta(minutes=need)
                dem += dur - need
                used_lay, lay = allowed_min, False
            else:
                used_lay += dur
        elif k == "excl" or (k == "shift" and not shift_counts):
            ded += dur
        else:
            dem += dur
    return used_lay + dem, ded, dem, expiry


@dataclass
class Result:
    jid: str
    vessel: str
    operation: str
    berth: str
    cargo: str
    qty_t: float
    nor_t: datetime
    nor_a: datetime | None
    arrive: datetime
    allfast: datetime
    ops_start: datetime
    ops_end: datetime
    hose_off: datetime
    laytime_start: datetime
    start_rule: str
    laytime_expiry: datetime | None
    elapsed_h: float
    deducted_h: float
    used_h: float
    allowed_h: float
    demurrage_h: float
    margin_h: float | None
    amount_usd: float
    flags: list[str]
    alt: dict[str, dict] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def compute(call: Call, terms: Terms = Terms(), *, nor_basis: str = "tender", nor_validity: str = "lenient",
            gaps: str = "count") -> Result:
    """nor_basis: tender(NOR 제출 = 수령) | accepted(NOR 승인 = 수령).
    nor_validity: lenient(제출 시각 그대로 유효) | strict(투묘 전 제출 NOR은 무효 → 하역 개시부터).
    gaps: count(하역 중단 구간 산입) | exclude(제외)."""
    notice = terms.notice_hours * 60
    hose_off = call.ops_end + timedelta(minutes=terms.hose_lag_min)
    recv = call.nor_a if (nor_basis == "accepted" and call.nor_a) else call.nor_t
    if nor_validity == "strict" and call.nor_early:
        start, rule = call.ops_start, "OPS_COMMENCED"       # LAW-NOR-ARRIVAL + LAW-NOR-WAIVER
    else:
        start, rule = by_notice(recv, call.allfast, notice)
    if hose_off <= start:
        raise ValueError(f"[{call.jid}] 레이타임 개시 {start}가 종료 {hose_off}보다 늦거나 같음")
    allowed = terms.laytime_hours * 60
    used, ded, dem, expiry = walk(start, hose_off, allowed, call.shifts,
                                  call.gaps if gaps == "exclude" else [], terms.shift_counts_on_demurrage)
    elapsed = _m(start, hose_off)
    assert abs(used - (elapsed - ded)) < 1e-6 and abs(dem - max(0.0, used - allowed)) < 1e-6
    amount = round(dem / 60 * terms.rate_usd_day / 24, 2)
    margin = (allowed - used) / 60 if dem == 0 else None
    flags = list(call.flags)
    if margin is not None and margin * 60 < 120:
        flags.append("LOW-MARGIN")
    return Result(
        call.jid, call.vessel, call.operation, call.berth, call.cargo, call.qty_t, call.nor_t, call.nor_a,
        call.arrive, call.allfast, call.ops_start, call.ops_end, hose_off, start, rule, expiry,
        elapsed / 60, ded / 60, used / 60, terms.laytime_hours, dem / 60, margin, amount, flags,
        notes=list(call.notes))


def analyze(path: str | Path, terms: Terms = Terms(), per_call: dict[str, Terms] | None = None
            ) -> tuple[list[Result], list[Call]]:
    results, calls = [], []
    for v in build_voyages(load_rows(path)):
        c = extract_call(v)
        if c is None:
            continue
        t = (per_call or {}).get(c.jid, terms)
        r = compute(c, t)
        r.alt["accept_basis"] = _alt(compute(c, t, nor_basis="accepted"))
        if c.nor_early:
            r.alt["strict_nor"] = _alt(compute(c, t, nor_validity="strict"))
        if c.gaps:
            r.alt["no_gap"] = _alt(compute(c, t, gaps="exclude"))
        results.append(r)
        calls.append(c)
    return results, calls


def _alt(r: Result) -> dict:
    return {"laytime_start": r.laytime_start.isoformat(sep=" "), "demurrage_h": r.demurrage_h, "amount_usd": r.amount_usd}


# ----------------------------------------------------------------------------- 출력

def fmt_h(h: float) -> str:
    m = round(h * 60)
    return f"{m // 60}h{m % 60:02d}m"


def to_dict(r: Result) -> dict:
    d = {k: (v.isoformat(sep=" ") if isinstance(v, datetime) else v) for k, v in r.__dict__.items()}
    return d


CSV_COLS = [
    ("jid", "일정ID"), ("vessel", "선박명"), ("operation", "작업"), ("berth", "하역 부두"), ("cargo", "화물"),
    ("qty_t", "수량(톤)"), ("nor_t", "NOR 제출"), ("nor_a", "NOR 승인"), ("allfast", "접안 완료"),
    ("ops_start", "하역 개시"), ("ops_end", "하역 완료"), ("hose_off", "호스 분리(종료)"),
    ("laytime_start", "레이타임 개시"), ("start_rule", "개시 근거"), ("laytime_expiry", "레이타임 만료"),
    ("elapsed_h", "경과(h)"), ("deducted_h", "공제(h)"), ("used_h", "사용(h)"), ("allowed_h", "허용(h)"),
    ("demurrage_h", "체선(h)"), ("margin_h", "여유(h)"), ("amount_usd", "체선료(USD)"),
]


def write_csv(results: list[Result], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([h for _, h in CSV_COLS] + ["NOR 승인 기준 체선(h)", "NOR 승인 기준(USD)",
                                                "엄격 NOR 체선(h)", "엄격 NOR(USD)", "중단 제외 체선(h)",
                                                "중단 제외(USD)", "플래그"])
        for r in results:
            row = []
            for k, _ in CSV_COLS:
                v = getattr(r, k)
                row.append(v.strftime("%Y-%m-%d %H:%M") if isinstance(v, datetime) else ("" if v is None else v))
            for key in ("accept_basis", "strict_nor", "no_gap"):
                a = r.alt.get(key)
                row += [a["demurrage_h"], a["amount_usd"]] if a else ["", ""]
            row.append(" ".join(r.flags))
            w.writerow(row)


def print_report(results: list[Result], terms: Terms, out=sys.stdout) -> None:
    p = lambda *a: print(*a, file=out)  # noqa: E731
    p(f"계약 조건 [가정]: 허용 {terms.laytime_hours:g}h · 통지 {terms.notice_hours:g}h · 요율 {terms.rate_usd_day:,.0f} USD/일"
      f" · 호스 분리 지연 {terms.hose_lag_min:g}분")
    p()
    p(f"{'ID':<5}{'선박':<18}{'부두':<8}{'개시 근거':<14}{'사용':>9}{'체선':>9}{'체선료(USD)':>14}  플래그")
    for r in results:
        p(f"{r.jid:<5}{r.vessel:<18}{r.berth:<8}{r.start_rule:<14}{fmt_h(r.used_h):>9}"
          f"{fmt_h(r.demurrage_h):>9}{r.amount_usd:>14,.0f}  {' '.join(r.flags)}")
    tot = sum(r.amount_usd for r in results)
    hrs = sum(r.demurrage_h for r in results)
    p(f"\n합계: 체선 {fmt_h(hrs)} · {tot:,.0f} USD  ({sum(1 for r in results if r.demurrage_h > 0)}/{len(results)}항차 체선)")
    acc = sum(r.alt["accept_basis"]["amount_usd"] for r in results)
    strict = sum(r.alt["strict_nor"]["amount_usd"] if "strict_nor" in r.alt else r.amount_usd for r in results)
    p("\n해석이 갈리는 곳 (판정하지 않고 같이 낸다)")
    p(f"  NOR 승인 시각을 수령으로 볼 때            : {acc:>12,.0f} USD")
    p(f"  투묘 전 제출 NOR을 무효로 볼 때(엄격)     : {strict:>12,.0f} USD")
    for r in results:
        if "no_gap" in r.alt:
            p(f"  {r.jid} 하역 중단 구간을 제외할 때           : {r.alt['no_gap']['amount_usd']:>12,.0f} USD (기본 {r.amount_usd:,.0f})")


def load_terms_file(path: str | Path) -> dict[str, Terms]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    base = Terms()
    return {jid: Terms(**{**base.__dict__, **v}) for jid, v in raw.items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="vessel_journeys.csv → 항차별 체선료")
    ap.add_argument("csv")
    ap.add_argument("--laytime", type=float, default=Terms.laytime_hours, help="허용 레이타임(h)")
    ap.add_argument("--rate", type=float, default=Terms.rate_usd_day, help="체선료율(USD/일)")
    ap.add_argument("--notice", type=float, default=Terms.notice_hours, help="통지시간(h)")
    ap.add_argument("--lag", type=float, default=Terms.hose_lag_min, help="마지막 완료→호스 분리(분)")
    ap.add_argument("--terms", help='항차별 계약 조건 JSON {"J001": {"laytime_hours": 36, "rate_usd_day": 30000}}')
    ap.add_argument("--out-csv")
    ap.add_argument("--out-json")
    a = ap.parse_args(argv)
    terms = Terms(a.laytime, a.notice, a.rate, a.lag)
    per_call = load_terms_file(a.terms) if a.terms else None
    results, _ = analyze(a.csv, terms, per_call)
    print_report(results, terms)
    if a.out_csv:
        write_csv(results, a.out_csv)
    if a.out_json:
        Path(a.out_json).write_text(json.dumps([to_dict(r) for r in results], ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
