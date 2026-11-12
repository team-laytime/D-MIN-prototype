"""멘토링 PPT 06~12쪽의 계산식 P1~P19 — 한 척(입항 건)의 한 작업계획을 계산한다. 표준 라이브러리만 쓴다.

    P1   배정 가능 부두                     (12쪽 2)        eligible()
    P2   도착 기준 = ETA + Direction        (07쪽)          tau0()
    P3   앞 선박 기준 = 이안 + Switching     (07쪽)          release_after()
    P4   야간 도선 금지 구간                 (08쪽 ②)       night_windows()
    P5   부두 사용 제한 금지 구간            (08쪽 ③-1)     restriction_windows()
    P6   동시 접안 금지 기준 = 이안 − 2h     (08쪽 ③-2)     release_after()
    P7   ETB = 금지 구간을 피한 가장 이른 시각 (06쪽)        phi()
    P8   FIX 보호: 이안 + Switching < FIX 접안 (06·07쪽)    conflict()
    P9   작업시작 = ETB + 1h                 (09쪽)          timeline()
    P10  작업완료 = 작업시작 + 물량 ÷ 평균 Rate (09쪽)       timeline()
    P11  호스분리 = 작업완료 + 30분          (09쪽)          timeline()
    P12  이안 = 작업완료 + 2h                (09쪽)          timeline()
    P13  ETANR = NVL(NOR Tender, ETA)        (09쪽)          laytime_start()
    P14  정박개시, Daylight 미적용           (09쪽)          laytime_start()
    P15  정박개시, Daylight 적용             (10쪽)          laytime_start()
    P16  정박종료 = 정박개시 + Laytime × 배수 (10쪽)         make_plan()
    P17  기상체선 시간 ÷ 2                   (11쪽)          make_plan()
    P18  체선시간 = max(0, 호스분리 − 정박종료 − 공제) (11쪽) make_plan()
    P19  체선료 = 체선시간 × Rate ÷ 24       (11쪽)          make_plan()

시각은 2026-01-01 00:00(KST)부터 센 '분' 정수다. 금액은 센트 정수다(반올림은 마지막에 한 번).
규칙 값(표·상수·분기 시각)은 모두 rules/terminal.json에서 읽는다. 이 파일에는 숫자를 적지 않는다.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
EPOCH = datetime(2026, 1, 1)
DAY = 1440


# ----------------------------------------------------------------------------- 시각
def parse(s):
    if s is None or isinstance(s, int):
        return s
    return int((datetime.fromisoformat(s) - EPOCH).total_seconds() // 60)


def iso(t):
    return (EPOCH + timedelta(minutes=int(t))).strftime("%Y-%m-%dT%H:%M")


def fmt(t):
    return (EPOCH + timedelta(minutes=int(t))).strftime("%m/%d %H:%M")


def day0(t):
    return t - t % DAY


def hm(text):
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def mins(hours):
    return int(round(float(hours) * 60))


def frac(x):
    return Fraction(x) if isinstance(x, str) else Fraction(x).limit_denominator(1000)


def hours(m):
    """분 → '12.5h' 꼴 글자"""
    return f"{float(m) / 60:.2f}".rstrip("0").rstrip(".") + "h"


def usd(cents):
    return f"${cents / 100:,.2f}"


def solar(day_start, lat, lon, tz_hours):
    """그날의 일출·일몰(분). NOAA 근사식. 실서비스는 공공데이터(PPT 12쪽 3)를 표로 넣는다."""
    n = (EPOCH + timedelta(minutes=day_start)).timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(lat)
    ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(decl)) - math.tan(la) * math.tan(decl)))
    rise = 720 - 4 * (lon + ha) - eqtime + tz_hours * 60
    sset = 720 - 4 * (lon - ha) - eqtime + tz_hours * 60
    return day_start + int(round(rise)), day_start + int(round(sset))


# ----------------------------------------------------------------------------- 자료 구조
@dataclass
class Berth:
    id: str
    size: str
    direction: int          # 분
    switching: int          # 분
    max_dwt: float | None
    max_draft: float | None
    max_loa: float | None
    min_loa: float | None
    min_pbl: float | None
    groups: dict
    shift_assumed: bool = False


@dataclass
class Contract:
    laycan_from: int
    laycan_to: int
    laytime: int            # 분
    rate_cents: int         # 하루 요율(센트)
    cfr: bool = False
    weather_half: bool = True


@dataclass
class Arrival:
    id: str
    vessel: str
    vclass: str             # CR 원유선 · PP 석유제품선 · PC 화학제품선 · LB 윤활유제품선 · SP 특수제품선
    biz: str                # IM 수입 · EX 수출 · DI 내수 매입 · DO 내수 판매
    cargo: str              # 제품 그룹
    qty: float
    eta: int
    nor: int | None
    grt: float
    dwt: float
    loa: float
    pbl: float
    draft: float
    contract: Contract
    status: str = "PLANNED"                 # PLANNED(다시 짤 수 있음) · FIX · WORKING
    fix: dict | None = None                 # {"berth", "etb", "etu"(선택), "work_start"(선택)}
    berths: list | None = None              # 지정 부두(있으면 이 안에서만)
    work: dict = field(default_factory=dict)  # {"hours"} 또는 {"rate_per_h", "by_berth"}

    @property
    def movable(self):
        return self.status not in ("FIX", "WORKING")


@dataclass
class Restriction:
    id: str
    reason: str             # WEATHER(기상 악화, 전 부두) · WORK(공사 등, 부두별)
    berths: list            # ["*"] 또는 부두 목록
    start: int
    end: int

    def on(self, bid):
        return "*" in self.berths or bid in self.berths


@dataclass
class Tank:
    group: str              # 제품 그룹
    opening: float
    minimum: float
    maximum: float
    flows: list             # [(시작, 끝, 시간당 소비량)] — 생산이면 음수


@dataclass
class Plan:
    aid: str
    berth: str
    s: int                  # 접안 ETB
    a: int                  # 작업시작
    c: int                  # 작업완료
    h: int                  # 호스분리
    u: int                  # 이안 ETU
    lay_start: int          # 정박개시 ℓ
    lay_rule: str
    allowed: Fraction       # 적용 허용시간 A' (분)
    lay_end: Fraction       # 정박종료
    dt_raw: Fraction        # 호스분리 − 정박종료
    wx: Fraction            # 기상체선 시간
    ded: Fraction           # 공제시간 e
    dt: Fraction            # 체선시간
    cents: int              # 체선료
    fixed: bool = False
    why: str = ""           # 이 접안 시각이 나온 이유

    @property
    def key(self):
        return (self.aid, self.berth, self.s)

    @property
    def label(self):
        return f"{self.aid}@{self.berth} {fmt(self.s)}"


class Rules:
    """rules/terminal.json을 읽어 계산에 쓰는 값으로 바꾼다."""

    def __init__(self, raw=None, patch=None):
        raw = raw or json.loads((HERE / "rules" / "terminal.json").read_text(encoding="utf-8"))
        raw = json.loads(json.dumps(raw))
        for path, value in (patch or {}).items():           # "demurrage.weather_basis": "WAIT" 꼴
            node = raw
            keys = path.split(".")
            for k in keys[:-1]:
                node = node[int(k)] if isinstance(node, list) else node[k]
            node[keys[-1]] = value
        self.raw = raw
        self.version = raw["version"]
        self.berths = {b["id"]: Berth(b["id"], b.get("size"), mins(b["direction_h"]), mins(b["switching_h"]), b.get("max_dwt"), b.get("max_draft"),
                                      b.get("max_loa"), b.get("min_loa"), b.get("min_pbl"), b.get("groups", {}), b.get("shift_assumed", False))
                       for b in raw["berths"]}
        self.berth_order = [b["id"] for b in raw["berths"]]
        self.draft_biz = set(raw["eligibility"]["draft_check_biz"])
        np_ = raw["night_pilotage"]
        self.pob = np_["last_pob"]
        self.dawn = np_["dawn"]
        pr = raw["pair_rules"]
        self.fix_strict = pr["same_berth"]["fix_strict"]
        self.cargo_sets = [set(s) for s in pr["same_cargo_group"]["berth_sets"]]
        self.cargo_release = mins(pr["same_cargo_group"]["release_before_etu_h"])
        self.simul = [(set(s["berths"]), mins(s["release_before_etu_h"]), s.get("exempt_if_all_grt_le")) for s in pr["simultaneous"]]
        self.restriction_scope = raw["restriction"]["scope"]
        w = raw["work"]
        self.setup, self.hose, self.departure = mins(w["setup_h"]), mins(w["hose_h"]), mins(w["departure_h"])
        lt = raw["laytime"]
        self.daylight = set(lt["daylight_classes"])
        self.notice = mins(lt["notice_h"])
        self.early_hour, self.early_hour_dl, self.day_hour = lt["before_laycan_hour"] * 60, lt["before_laycan_hour_daylight"] * 60, lt["daylight_hour"] * 60
        self.factors = lt["factor"]
        self.wx_ratio = frac(raw["demurrage"]["weather_ratio"])
        self.wx_basis = raw["demurrage"]["weather_basis"]
        self.loc = raw["location"]


@dataclass
class Case:
    id: str
    title: str
    start: int
    end: int
    arrivals: dict
    restrictions: list
    tanks: list
    sun: dict                       # 날짜 0시(분) → (일출, 일몰)
    options: dict
    raw: dict

    def sun_of(self, t, rules):
        d = day0(t)
        if d not in self.sun:
            self.sun[d] = solar(d, rules.loc["lat"], rules.loc["lon"], rules.loc["tz_hours"])
        return self.sun[d]


def load_case(doc, rules=None):
    """입력 JSON(= 최적화 요청 본문과 같은 모양) → Case"""
    if not isinstance(doc, dict):
        doc = json.loads(Path(doc).read_text(encoding="utf-8"))
    arrivals = {}
    for v in doc["arrivals"]:
        c = v["contract"]
        arrivals[v["id"]] = Arrival(
            id=v["id"], vessel=v.get("vessel", v["id"]), vclass=v["class"], biz=v["biz"], cargo=v["cargo_group"], qty=v.get("qty", 0),
            eta=parse(v["eta"]), nor=parse(v.get("nor_tender")), grt=v["grt"], dwt=v["dwt"], loa=v["loa"], pbl=v["pbl"], draft=v["draft"],
            contract=Contract(parse(c["laycan_from"]), parse(c["laycan_to"]), mins(c["laytime_h"]), int(round(c["rate_usd_day"] * 100)),
                              bool(c.get("cfr", False)), bool(c.get("weather_half", True))),
            status=v.get("status", "PLANNED"),
            fix=({**v["fix"], "etb": parse(v["fix"]["etb"]), "etu": parse(v["fix"].get("etu")), "work_start": parse(v["fix"].get("work_start"))} if v.get("fix") else None),
            berths=v.get("berths"), work=v.get("work", {}))
    restrictions = [Restriction(r["id"], r["reason"], r.get("berths", ["*"]), parse(r["start"]), parse(r["end"])) for r in doc.get("restrictions", [])]
    tanks = [Tank(t["group"], t["opening"], t["min"], t["max"], [(parse(f["from"]), parse(f["to"]), f["use_per_h"]) for f in t.get("flows", [])])
             for t in doc.get("inventory", [])]
    sun = {parse(d + "T00:00"): (parse(f"{d}T{r}"), parse(f"{d}T{s}")) for d, (r, s) in doc.get("sun", {}).items()}
    return Case(doc.get("id", "case"), doc.get("title", ""), parse(doc["plan"]["start"]), parse(doc["plan"]["end"]), arrivals, restrictions, tanks, sun,
                doc.get("options", {}), doc)


# ----------------------------------------------------------------------------- P1 배정 가능 부두
def eligible(rules, a, bid):
    """P1 (PPT 12쪽 2, FR-14·15): 제품 그룹을 받고 제원 5종이 맞는 부두인가. 비어 있는 항목은 비교하지 않는다. Draft는 수입만 본다."""
    b = rules.berths[bid]
    bad = []
    if a.cargo not in b.groups:
        bad.append(f"제품 그룹 {a.cargo} 미취급")
    if b.max_dwt is not None and a.dwt > b.max_dwt:
        bad.append(f"DWT {a.dwt:,.0f} > 최대 {b.max_dwt:,.0f}")
    if b.max_loa is not None and a.loa > b.max_loa:
        bad.append(f"LOA {a.loa} > 최대 {b.max_loa}")
    if b.min_loa is not None and a.loa < b.min_loa:
        bad.append(f"LOA {a.loa} < 최소 {b.min_loa}")
    if b.min_pbl is not None and a.pbl < b.min_pbl:
        bad.append(f"PBL {a.pbl} < 최소 {b.min_pbl}")
    if a.biz in rules.draft_biz and b.max_draft is not None and a.draft > b.max_draft:
        bad.append(f"Draft {a.draft} > 최대 {b.max_draft}")
    return (not bad), bad


def eligible_berths(rules, a):
    if not a.movable:
        return [a.fix["berth"]]
    pool = a.berths or rules.berth_order
    return [bid for bid in pool if eligible(rules, a, bid)[0]]


# ----------------------------------------------------------------------------- P2~P7 접안 시각
def tau0(rules, a, bid):
    """P2 (PPT 07쪽): 부두가 비어 있을 때 ETB = ETA + Shifting(Direction)"""
    return a.eta + rules.berths[bid].direction


def pob_subject(rules, a):
    """야간 도선(Last POB) 대상 선박인가 — PPT 08쪽 '(GRT 7.5만톤 이상) OR (3만톤 이하 AND 수입선 AND Draft >= 10.5)'"""
    for cond in rules.pob["subject_any"]:
        if "grt_min" in cond and a.grt < cond["grt_min"]:
            continue
        if "grt_max" in cond and a.grt > cond["grt_max"]:
            continue
        if "biz" in cond and a.biz not in cond["biz"]:
            continue
        if "draft_min" in cond and a.draft < cond["draft_min"]:
            continue
        return True
    return False


def last_pob(rules, case, a, day_start):
    """그날의 Last POB = 일몰 − 1.5h(GRT 5만 이하) 또는 − 2h(5만 초과) — PPT 08쪽"""
    sunset = case.sun_of(day_start, rules)[1]
    for row in rules.pob["sunset_minus_h"]:
        if "grt_max" in row and a.grt > row["grt_max"]:
            continue
        if "grt_min_exclusive" in row and a.grt <= row["grt_min_exclusive"]:
            continue
        return sunset - mins(row["h"])
    return None


def night_windows(rules, case, a):
    """P4 (PPT 08쪽 ②): 이 선박이 접안할 수 없는 야간 구간 [시작, 끝). 끝은 '다가오는 오전 08시'다."""
    out = []
    rel = hm(rules.pob["release"])
    if pob_subject(rules, a):
        if rules.pob["compare"] == "ETA":                     # PPT 글자 그대로: '선박의 ETA >= Last POB 시간인 경우'
            d = day0(a.eta)
            if a.eta < d + rel:                               # 자정~08시 도착: 전날 Last POB 뒤에 도착한 것
                out.append((a.eta, d + rel, "Last POB 뒤 도착"))
            else:
                pob = last_pob(rules, case, a, d)
                if pob is not None and a.eta >= pob:
                    out.append((a.eta, d + DAY + rel, "Last POB 뒤 도착"))
        else:                                                 # 접안 시각으로 비교하는 해석(표에서 바꿀 수 있다)
            d = day0(case.start) - DAY
            while d <= case.end:
                pob = last_pob(rules, case, a, d)
                if pob is not None:
                    out.append((pob, d + DAY + rel, "Last POB ~ 08시"))
                d += DAY
    if a.grt >= rules.dawn["grt_min"]:                        # 'GRT 3만톤 이상 … 새벽 2시 이상 오전 8시 미만'
        d = day0(min(a.eta, case.start)) - DAY
        while d <= case.end + DAY:
            out.append((d + hm(rules.dawn["from"]), d + hm(rules.dawn["to"]), "새벽 02~08시"))
            d += DAY
    return out


def restriction_windows(rules, case, a, bid, stay=0):
    """P5 (PPT 08쪽 ③-1, 12쪽 4): 사용자 설정 부두 제약 → ETB = 종료시간 + Direction. 그래서 [시작, 종료 + Direction)에는 접안하지 못한다."""
    b = rules.berths[bid]
    lead = stay if rules.restriction_scope == "STAY" else 0   # STAY면 체류가 제약과 겹치는 것도 막는다
    return [(r.start - lead, r.end + b.direction, f"부두 제약 {r.id}") for r in case.restrictions if r.on(bid)]


def merge(windows):
    out = []
    for f0, f1, tag in sorted(windows):
        if f1 <= f0:
            continue
        if out and f0 <= out[-1][1]:
            if f1 > out[-1][1]:
                out[-1] = (out[-1][0], f1, tag)
        else:
            out.append((f0, f1, tag))
    return out


def phi(windows, tau):
    """P7 (PPT 06쪽): 모든 제약을 함께 만족하는 가장 이른 시각. windows는 merge()를 거친 금지 구간이다."""
    for f0, f1, tag in windows:
        if f0 <= tau < f1:
            return f1, tag
        if f0 > tau:
            break
    return tau, None


# ----------------------------------------------------------------------------- P9~P12 작업 시각
def work_minutes(a, bid):
    """P10 (PPT 09쪽): 작업시간 = 물량 ÷ 평균 Rate. 평균 Rate는 과거 Shipment에서 구해 입력으로 준다(1차 선박·자재·부두, 2차 자재·부두)."""
    w = a.work
    if "hours" in w:
        return mins(w["hours"])
    rate = (w.get("by_berth") or {}).get(bid, w.get("rate_per_h"))
    if not rate:
        raise ValueError(f"{a.id}: 작업시간도 평균 Rate도 없다")
    return math.ceil(a.qty / rate * 60)


def timeline(rules, a, bid, s, work_start=None, etu=None):
    """P9~P12 (PPT 09쪽): 작업시작 = ETB + 1h · 작업완료 = 작업시작 + 작업시간 · 호스분리 = 작업완료 + 30분 · 이안 = 작업완료 + 2h"""
    st = work_start if work_start is not None else s + rules.setup
    c = etu - rules.departure if etu is not None else st + work_minutes(a, bid)
    return st, c, c + rules.hose, c + rules.departure


def stay_minutes(rules, a, bid):
    return rules.setup + work_minutes(a, bid) + rules.departure


# ----------------------------------------------------------------------------- P13~P15 정박개시
def laytime_start(rules, case, a, s):
    """P13~P15 (PPT 09·10쪽). 위에서부터 차례로 따져 처음 맞는 갈래를 쓴다."""
    c = a.contract
    etanr = a.nor if a.nor is not None else a.eta                         # P13 ETANR = NVL(NR_TENDER, ETA)
    dl = a.vclass in rules.daylight                                       # Daylight 적용: 원유선·석유제품선
    page = "10쪽" if dl else "09쪽"
    if etanr < c.laycan_from and s < c.laycan_from:
        return s, "Early Loading", f"ETANR·ETB 모두 LayCan From 전 → 정박개시 = ETB ({page})"
    if etanr > c.laycan_to:
        return s, "LayCan Miss", f"ETANR이 LayCan To 뒤 → 정박개시 = ETB ({page})"
    if etanr < c.laycan_from:
        t = day0(c.laycan_from) + (rules.early_hour_dl if dl else rules.early_hour)
        return t, "조기 도착", f"ETANR이 LayCan From 전 → LayCan From의 오전 {'07' if dl else '06'}시 ({page})"
    if not dl:
        base, name = etanr + rules.notice, "ETANR + 6h"
    else:
        rise, sset = case.sun_of(etanr, rules)
        if rise < etanr < sset:
            base, name = etanr + rules.notice, "일출~일몰 사이 → ETANR + 6h"
        elif etanr <= rise:
            base, name = day0(etanr) + rules.day_hour, "일출 전 → ETANR 날의 07시"
        else:
            base, name = day0(etanr) + DAY + rules.day_hour, "일몰 뒤 → ETANR 다음 날의 07시"
    if s < base:
        return s, "ETB가 더 이름", f"{name} = {fmt(base)}보다 ETB가 이름 → 정박개시 = ETB ({page})"
    return base, ("Daylight" if dl else "LayCan 안"), f"{name} ({page})"


def laytime_factor(rules, a):
    """P16 (PPT 10쪽): '원유 && CFR False'이면 LayTime ÷ 2"""
    for row in rules.factors:
        if row.get("class", a.vclass) == a.vclass and row.get("cfr", a.contract.cfr) == a.contract.cfr:
            return frac(row["factor"])
    return Fraction(1)


def weather_windows(case, bid):
    out = []
    for s0, e0 in sorted((r.start, r.end) for r in case.restrictions if r.reason == "WEATHER" and r.on(bid)):
        if out and s0 <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e0))
        else:
            out.append((s0, e0))
    return out


def overlap(a0, a1, b0, b1):
    return max(Fraction(0), min(Fraction(a1), Fraction(b1)) - max(Fraction(a0), Fraction(b0)))


# ----------------------------------------------------------------------------- 작업계획 하나
def make_plan(rules, case, a, bid, s, why="", fixed=False):
    """접안 시각 s가 정해진 작업계획 하나를 끝까지 계산한다 (P9~P19)."""
    fx = a.fix or {}
    st, c, h, u = timeline(rules, a, bid, s, fx.get("work_start") if fixed else None, fx.get("etu") if fixed else None)
    ls, rule, text = laytime_start(rules, case, a, s)
    lam = laytime_factor(rules, a)
    allowed = Fraction(a.contract.laytime) * lam                          # P16
    le = ls + allowed
    dt_raw = Fraction(h) - le                                             # P18 호스분리 − 정박종료
    basis = case.options.get("weather_basis", rules.wx_basis)
    lo, hi = {"USED": (ls, h), "DEMURRAGE": (le, h), "WAIT": (ls, s)}[basis]
    ratio = rules.wx_ratio if a.contract.weather_half else Fraction(0)
    wx = sum((overlap(w0, w1, lo, hi) for w0, w1 in weather_windows(case, bid)), Fraction(0)) if dt_raw > 0 else Fraction(0)
    ded = wx * ratio                                                      # P17 기상체선 시간 ÷ 2
    dt = max(Fraction(0), dt_raw - ded)                                   # P18
    cents = int(math.floor(dt * a.contract.rate_cents / DAY + Fraction(1, 2)))   # P19 체선시간 × Rate ÷ 24
    return Plan(a.id, bid, s, st, c, h, u, ls, rule, allowed, le, dt_raw, wx, ded, dt, cents, fixed, why)


def explain(rules, case, plan):
    """작업계획 하나의 산출 근거 — [(계산식 번호, 숫자를 넣은 식)]. 화면의 '산출 근거'와 보고서에 그대로 쓴다 (FR-46)."""
    a = case.arrivals[plan.aid]
    fx = a.fix or {}
    lam = laytime_factor(rules, a)
    ratio = rules.wx_ratio if a.contract.weather_half else Fraction(0)
    text = laytime_start(rules, case, a, plan.s)[2]
    given = plan.fixed and fx.get("work_start") is not None
    return [
        ("P7", f"접안 ETB = {fmt(plan.s)} — {plan.why}"),
        ("P9", f"작업시작 = 입력값 {fmt(plan.a)}" if given else f"작업시작 = ETB {fmt(plan.s)} + {hours(rules.setup)} = {fmt(plan.a)}"),
        ("P10", f"작업완료 = {fmt(plan.a)} + 작업시간 {hours(plan.c - plan.a)} = {fmt(plan.c)}"),
        ("P11", f"호스분리 = 작업완료 + {hours(rules.hose)} = {fmt(plan.h)}"),
        ("P12", f"이안 ETU = 작업완료 + {hours(rules.departure)} = {fmt(plan.u)}"),
        ("P13", f"ETANR = {fmt(a.nor if a.nor is not None else a.eta)} ({'NOR Tender' if a.nor is not None else 'NOR 없음 → ETA'})"),
        ("P15" if a.vclass in rules.daylight else "P14", f"정박개시 = {fmt(plan.lay_start)} — {text}"),
        ("P16", f"정박종료 = 정박개시 + Laytime {hours(a.contract.laytime)}{' × ' + str(lam) if lam != 1 else ''} = {fmt(int(plan.lay_end))}"),
        ("P17", f"기상체선 시간 {hours(plan.wx)} × {ratio} = 공제 {hours(plan.ded)}"),
        ("P18", f"체선시간 = max(0, {fmt(plan.h)} − {fmt(int(plan.lay_end))} − {hours(plan.ded)}) = {hours(plan.dt)}"),
        ("P19", f"체선료 = {hours(plan.dt)} × {usd(a.contract.rate_cents)}/일 ÷ 24 = {usd(plan.cents)}"),
    ]


# ----------------------------------------------------------------------------- P3·P6·P8 두 작업계획 사이
def relation(rules, a1, b1, a2, b2):
    """두 입항 건이 이 부두 조합에서 서로 묶이는가 → (종류, 분) 또는 None"""
    if b1 == b2:
        return "같은 부두", rules.berths[b1].switching                     # P3 (PPT 07쪽)
    for bs in rules.cargo_sets:                                           # P6 (PPT 08쪽) 동일 화물 그룹
        if b1 in bs and b2 in bs and a1.cargo == a2.cargo:
            return "동일 화물 그룹", rules.cargo_release
    for bs, rel, exempt in rules.simul:                                   # P6 (PPT 08쪽) 부두 동시 접안
        if b1 in bs and b2 in bs and not (exempt is not None and a1.grt <= exempt and a2.grt <= exempt):
            return "부두 동시 접안", rel
    return None


def release_after(rules, case, p, a2, b2):
    """작업계획 p 뒤에 서는 입항 건 a2가 부두 b2에 댈 수 있는 가장 이른 시각 (P3: 이안 + Switching · P6: 이안 − 2h). 안 묶이면 None"""
    rel = relation(rules, case.arrivals[p.aid], p.berth, a2, b2)
    if rel is None:
        return None
    kind, v = rel
    return (p.u + v, kind) if kind == "같은 부두" else (p.u - v, kind)


def conflict(rules, case, p, q):
    """두 작업계획을 같이 고를 수 없는가 → 이유 글자 또는 None (팀 최종본 식 (18)의 자리, P8 포함)"""
    rel = relation(rules, case.arrivals[p.aid], p.berth, case.arrivals[q.aid], q.berth)
    if rel is None:
        return None
    kind, v = rel
    if kind == "같은 부두":
        # 뒤에 서는 쪽이 FIX이면 같은 시각도 불가 — PPT 07쪽 'FIX 선박의 ETB <= 예상 ETU + SWITCHING → 접안불가'
        q_after = q.s > p.u + v if (rules.fix_strict and q.fixed and not p.fixed) else q.s >= p.u + v
        p_after = p.s > q.u + v if (rules.fix_strict and p.fixed and not q.fixed) else p.s >= q.u + v
    else:
        q_after, p_after = q.s >= p.u - v, p.s >= q.u - v
    return None if (q_after or p_after) else kind
