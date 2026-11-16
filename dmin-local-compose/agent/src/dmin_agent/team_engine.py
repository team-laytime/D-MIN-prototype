"""팀 엔진 — 팀원 코드(berth_sim, OR-Tools CP-SAT)로 후보를 찾는다. 팀원 코드는 고치지 않는다(berth_sim/ 복사본).

이 파일이 하는 일 (어댑터)
  1. 규칙 확인   요청의 규칙(표 + rule_patch)이 팀원 코드가 코드에 고정해 둔 값과 같은가 → 하나라도 다르면 ValueError(422).
                 팀원 코드는 '팀 해석'(rules/terminal.json profiles.team)으로 짜여 있어서, 실행할 때 그 해석을 골라야 돈다.
  2. 바꾸기     우리 요청 JSON → 팀원 코드의 입력 (부두 이름 '#6' ↔ '6', 선박·계약 → VesselProfile, 부두 제약 → BerthBlock).
                 작업시간: 팀원 코드는 과거 실적에서 평균 Rate를 구한다. 우리 요청은 Rate(또는 작업시간)를 바로 주므로
                 '이 배·이 부두 과거 실적 한 줄'을 만들어 넣어, 팀원 식이 우리와 같은 분 단위 작업시간을 내게 한다.
  3. 풀기       feasibility.build_table → cost_table.build_costs → cpsat_model.solve_tiers (팀원 코드 그대로, 5분 칸)
  4. 돌려주기   고른 (부두, ETB)마다 팀원 계산식(after_etb.calc_after_etb)으로 시각·체선료를 내 우리 응답 모양으로 싣는다.
                 기준안·현행 계획은 비교용이라 기존 엔진(같은 규칙)으로 계산한다. Spring이 모든 일정을 Java로 다시 계산해 1분·1센트까지 대조한다.

팀원 코드에 없어 여기서 메우는 것
  - 작업 중·FIX 배에 작업시작·이안을 직접 준 경우: 팀원 모델에서는 그 배의 이안이 입력값과 같아지도록 작업시간을 맞춰 넣고
    (다른 배와 겹치는지 판단용), 화면에 내는 그 배의 시각·금액은 입력값으로 기존 엔진이 계산한다(어차피 고정된 배라 최적화 대상이 아니다).
  - 탱크 재고(inventory)는 아직 넘기지 않는다(notes에 적고, Spring 재검증이 재고 위반을 잡는다).
"""
from __future__ import annotations

import contextlib
import hashlib
import math
import platform
import time
from dataclasses import replace
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path

import ortools

from .berth_sim import cpsat_model, cost_table, feasibility, shifting
from .berth_sim import step2_night_pilot as night
from .berth_sim import step3_berth_pair as pair_rule
from .berth_sim import step3_cargo_group as cargo_rule
from .berth_sim.after_etb import pipeline as after_etb
from .berth_sim.after_etb import s1_work_start, s3_etu, s4_hose_off, s6_daylight, s7_laytime_start_no_daylight as s7
from .berth_sim.after_etb import s8_laytime_start_daylight as s8
from .berth_sim.after_etb.s2_work_finish import PastShipment
from .berth_sim.master_data import BerthSpec, MasterData, ProductGroup
from .berth_sim.models import Vessel
from .berth_sim.scenario import occupancy
from .berth_sim.step3_berth_block import BerthBlock, BlockKind
from .berth_sim.synth import SynthData, VesselProfile
from .engine.pptcalc import EPOCH, Rules, eligible, eligible_berths, iso, load_case, make_plan, work_minutes
from .engine.planner import baseline, verify
from .engine.run import current_plans, plan_json, schedule_json

HERE = Path(__file__).resolve().parent
_SRC = sorted([*(HERE / "berth_sim").glob("*.py"), *(HERE / "berth_sim" / "after_etb").glob("*.py")])
SOURCE_SHA = hashlib.sha256(b"".join(hashlib.sha256(p.read_bytes()).digest() for p in _SRC)).hexdigest()
ENGINE_VERSION = f"berth_sim-cpsat/{SOURCE_SHA[:12]}"
STEP = timedelta(minutes=5)                 # 팀원 코드의 시각 칸 (feasibility.SLOT)
MINUTE = timedelta(minutes=1)


# ----------------------------------------------------------------------------- 1. 규칙 확인
def rule_mismatches(rules: Rules, case) -> list[str]:
    """팀원 코드가 고정해 둔 값과 요청 규칙이 다른 곳. 비어 있어야 팀 엔진을 쓸 수 있다."""
    bad = []

    def same(what, ours, team):
        if ours != team:
            bad.append(f"{what}: 규칙 {ours!r} ≠ 팀원 코드 {team!r}")

    h = 60
    same("작업시작 = ETB + (분)", rules.setup, int(s1_work_start.ETB_TO_START / MINUTE))
    same("호스분리 = 작업완료 + (분)", rules.hose, int(s4_hose_off.FINISH_TO_HOSE_OFF / MINUTE))
    same("이안 = 작업완료 + (분)", rules.departure, int(s3_etu.FINISH_TO_ETU / MINUTE))
    same("정박개시 ETANR + (분)", rules.notice, int(s7.NOTICE_TIME / MINUTE))
    same("조기 도착 → LayCan From (시, Daylight 미적용)", rules.early_hour, s7.LAYCAN_FROM_HOUR.hour * h)
    same("조기 도착 → LayCan From (시, Daylight 적용)", rules.early_hour_dl, s8.LAYCAN_FROM_HOUR.hour * h)
    same("일출 전·일몰 뒤 → (시)", rules.day_hour, s8.MORNING.hour * h)
    names = rules.raw["product_classes"]
    same("Daylight 적용 선종", sorted(names[c] for c in rules.daylight), sorted(s6_daylight.DAYLIGHT_APPLIED))
    same("LayTime 절반 조건", [(f.get("class"), f.get("cfr"), str(f.get("factor"))) for f in rules.factors], [("CR", False, "1/2")])
    same("기상체선 공제 비율", rules.wx_ratio, Fraction(1, 2))
    basis = (case.options or {}).get("weather_basis", rules.wx_basis)
    same("기상체선 세는 구간", basis, "DEMURRAGE")
    same("Draft 비교 업무 구분", sorted(rules.draft_biz), sorted(rules.raw["biz"]))
    same("부두별 최소 DWT", {k: float(v) for k, v in rules.min_dwt.items()}, {"BUOY2": 80000.0, "BUOY3": 80000.0})
    pob = rules.pob
    team_subject = [{"grt_min": night.GRT_ALWAYS}, {"grt_min": night.GRT_MIN, "biz": ["IM"], "draft_min": night.DRAFT_MIN}]
    same("야간 도선 대상", pob["subject_any"], team_subject)
    same("Last POB = 일몰 − (시간)", pob["sunset_minus_h"],
         [{"grt_max": night.GRT_POB_2H, "h": night.POB_BEFORE_SUNSET_SMALL / timedelta(hours=1)},
          {"grt_min_exclusive": night.GRT_POB_2H, "h": night.POB_BEFORE_SUNSET_LARGE / timedelta(hours=1)}])
    same("Last POB 비교", pob["compare"], "ETA_DAY")
    same("야간 도선 해제 시각", pob["release"], night.RELEASE.strftime("%H:%M"))
    d = rules.dawn
    same("새벽 금지", (d["grt_min"], d.get("scope", "GRT"), d["from"], d["to"]),
         (night.GRT_MIN, "SUBJECT", night.NIGHT_START.strftime("%H:%M"), night.RELEASE.strftime("%H:%M")))
    same("부두 제약 범위", rules.restriction_scope, "BERTHING")
    same("FIX 앞 끼어들기 금지", rules.fix_strict, True)
    same("동일 화물 그룹 부두", sorted(sorted(_norm(b) for b in s) for s in rules.cargo_sets),
         sorted(sorted(g) for g in cargo_rule.SAME_CARGO_BERTH_GROUPS))
    same("동일 화물 그룹 ETU − (분)", rules.cargo_release, int(cargo_rule.ETU_TO_WORK_END / MINUTE))
    same("동시 접안 부두·예외 GRT", sorted((sorted(_norm(b) for b in bs), rel, ex) for bs, rel, ex in rules.simul),
         sorted((sorted(g), int(cargo_rule.ETU_TO_WORK_END / MINUTE), pair_rule.SMALL_GRT) for g in pair_rule.SIMULTANEOUS_BERTH_PAIRS))
    for bid, b in rules.berths.items():
        n = _norm(bid)
        same(f"{bid} Direction (분)", b.direction, int(shifting.direction(n) / MINUTE))
        same(f"{bid} Switching (분)", b.switching, int(shifting.switching(n) / MINUTE))
        if b.max_dwt is None or b.max_draft is None:
            bad.append(f"{bid}: 팀원 코드는 Max DWT·Max Draft가 꼭 있어야 함")
    return bad


# ----------------------------------------------------------------------------- 2. 바꾸기
def _norm(bid: str) -> str:
    return shifting.normalize_berth(bid)


def _dt(m: int) -> datetime:
    return EPOCH + timedelta(minutes=m)


def _mins(t: datetime, what: str) -> int:
    """팀원 코드가 낸 시각 → 분. 우리 입력은 분 단위라 결과도 분 단위여야 한다(부동소수 찌꺼기 1ms까지만 반올림)."""
    m = round((t - EPOCH) / MINUTE)
    if abs((t - EPOCH) - m * MINUTE) > timedelta(milliseconds=1):
        raise RuntimeError(f"{what} {t}가 분 단위가 아님 — 팀원 식과 우리 입력의 단위가 어긋남")
    return m


@contextlib.contextmanager
def _sun(case, rules):
    """팀원 코드의 일출·일몰(울산 NOAA 근사식)을 요청의 sun 표(없으면 같은 근사식)로 바꿔 끼운다 — Spring과 같은 값을 쓰게.
    팀원 코드는 함수 기본값으로 받으므로 기본값만 잠깐 바꾸고 되돌린다(에이전트는 한 번에 한 계산만 한다)."""
    def day_start(day: date) -> int:
        return int((datetime.combine(day, datetime.min.time()) - EPOCH) / MINUTE)

    def rise(day: date) -> datetime:
        return _dt(case.sun_of(day_start(day), rules)[0])

    def sset(day: date) -> datetime:
        return _dt(case.sun_of(day_start(day), rules)[1])

    saved = (after_etb.calc_after_etb.__defaults__, night.make_night_pilot_adjuster.__defaults__)
    after_etb.calc_after_etb.__defaults__ = ((), rise, sset)
    night.make_night_pilot_adjuster.__defaults__ = (sset,)
    try:
        yield
    finally:
        after_etb.calc_after_etb.__defaults__, night.make_night_pilot_adjuster.__defaults__ = saved


def _inputs(rules: Rules, case):
    """우리 Case → (기준정보, 부두별 선박, 선박·계약·과거 실적, 부두 제약, 집(현행·FIX 부두))"""
    names = rules.raw["product_classes"]
    master = MasterData(
        berths={_norm(b.id): BerthSpec(_norm(b.id), b.max_dwt, b.max_draft, b.max_loa, b.min_loa, b.min_pbl, b.size,
                                       rules.min_dwt.get(b.id)) for b in rules.berths.values()},
        products={_norm(b.id): tuple(ProductGroup(g, c) for g, c in b.groups.items()) for b in rules.berths.values()},
        vessel_type_by_class=dict(names), buckets=())
    current = {c["id"]: c["berth"] for c in case.raw.get("current_plan", []) or []}
    profiles, history, sequences, home = {}, [], {}, {}
    given_times = set()                                                   # 작업시작·이안을 입력으로 준 작업 중·FIX 배
    hist_t0 = datetime(2025, 1, 1)
    for k, a in enumerate(case.arrivals.values()):
        code, material = f"REQ:{a.id}", f"MAT:{a.cargo}"
        mins = {bid: work_minutes(a, bid) for bid in rules.berths}       # 우리 P10 (분 단위 올림) — Spring과 같은 값
        if not a.movable and (a.fix.get("work_start") is not None or a.fix.get("etu") is not None):
            # 작업 중·FIX 배에 작업시작·이안을 직접 준 경우: 팀원 모델의 이안(ETB + 1h + 작업 + 2h)이 입력 이안과 같도록 작업시간을 맞춘다
            fb, fe = a.fix["berth"], a.fix["etb"]
            target = a.fix["etu"] if a.fix.get("etu") is not None else a.fix["work_start"] + mins[fb] + rules.departure
            w = target - rules.departure - (fe + rules.setup)
            if w < 0:
                raise ValueError(f"{a.id}: 입력한 이안 {iso(target)}이 ETB + 3h보다 이르다 — 팀원 모델로 나타낼 수 없음")
            mins[fb] = w
            given_times.add(a.id)
        q = (1.0 if any(mins.values()) else 0.0) if "hours" in a.work else float(a.qty)
        for bid, w in mins.items():                                       # 평균 Rate = q ÷ (w/60) → 팀원 식 작업시간 = w분
            if a.movable and a.berths and bid not in a.berths:
                continue                                                  # 지정 부두(berths) 밖 = 과거 실적 없음 → 팀원 코드가 스스로 막는다(NO_HISTORY)
            span, qty = (w, q) if w > 0 else (60, 1.0)
            history.append(PastShipment(code, material, _norm(bid), hist_t0 + timedelta(days=k),
                                        hist_t0 + timedelta(days=k, minutes=span), qty))
        if a.movable:
            pool = eligible_berths(rules, a)
            hb = current.get(a.id) or (pool[0] if pool else rules.berth_order[0])
        else:
            hb = a.fix["berth"]
            if a.fix["etb"] % 5:
                raise ValueError(f"{a.id}: 팀 엔진은 5분 칸이라 FIX·작업 중 ETB가 5분 단위여야 한다 ({iso(a.fix['etb'])})")
        if a.id in current or not a.movable:
            home[a.id] = _norm(hb)
        profiles[a.id] = VesselProfile(
            vessel_id=a.id, vessel_code=code, ship_class="", dwt=a.dwt, grt=a.grt, draft=a.draft, loa=a.loa, pbl=a.pbl,
            cargo_group=a.cargo, product_class=a.vclass, vessel_type=names[a.vclass], material_code=material, qty=q,
            work_hours=mins.get(hb, 0) / 60, demurrage_rate=a.contract.rate_cents / 100,
            laycan_from=_dt(a.contract.laycan_from), laycan_to=_dt(a.contract.laycan_to), laycan_case="",
            nr_tender=_dt(a.nor) if a.nor is not None else None, laytime=timedelta(minutes=a.contract.laytime), cfr=a.contract.cfr)
        sequences.setdefault(_norm(hb), []).append(Vessel(
            a.id, _norm(hb), _dt(a.eta), timedelta(0), is_fix=not a.movable,
            fixed_etb=_dt(a.fix["etb"]) if not a.movable else None, biz=a.biz))
    data = SynthData(profiles, tuple(history), seed=0, weather=None)
    sequences = {b: [replace(v, stay=occupancy(profiles[v.vessel_id], b, history)) for v in vs] for b, vs in sequences.items()}
    blocks = [BerthBlock(_dt(r.start), _dt(r.end), BlockKind.WEATHER if r.reason == "WEATHER" else BlockKind.CONSTRUCTION,
                         None if "*" in r.berths else frozenset(_norm(b) for b in r.berths)) for r in case.restrictions]
    return master, sequences, data, blocks, home, given_times


# ----------------------------------------------------------------------------- 4. 돌려주기
def _cents(dem: timedelta, rate_cents: int) -> int:
    """체선료 = 체선시간 × 하루 요율 ÷ 24 (팀원 s12와 같은 식) — 마이크로초 정수로 정확히 계산하고 반 센트는 올린다(Spring과 같다)."""
    x = Fraction(dem // timedelta(microseconds=1) * rate_cents, 86_400_000_000)
    return math.floor(x + Fraction(1, 2))


def _blocked_text(table, costs, res, vid, berth, slot) -> str:
    """이 칸에 댄 이유: 바로 앞 칸은 왜 안 됐나 (팀원 접안 가능 표의 사유, 또는 겹치는 다른 배)."""
    feas = costs[(vid, berth)].feasible_slots()
    when = f"{table.time(slot):%m/%d %H:%M}"
    if slot == feas[0]:
        row = table.row(vid, berth)
        prev = feasibility.REASON_LABEL[row.codes[slot - 1]] if slot > 0 else "표 시작"
        return f"ETB {when} — 이 부두에 댈 수 있는 가장 이른 5분 칸 (바로 앞 칸: {prev})"
    prev = max(t for t in feas if t < slot)
    sw = math.ceil(shifting.switching(berth) / table.step)
    back = math.ceil(cargo_rule.ETU_TO_WORK_END / table.step)
    my_end = costs[(vid, berth)].etu[prev] // 5        # 분 → 칸 (cost_table의 ETU는 분 올림이고 5분 칸 시작에 맞춰져 있다)
    who = []
    for q in res.assignments.values():
        if q.vessel_id == vid:
            continue
        q_end = costs[(q.vessel_id, q.berth)].etu[q.slot] // 5
        if q.berth == berth and q.slot < my_end + sw and prev < q_end + sw:
            who.append(f"#{berth} {q.vessel_id} (같은 부두 점유 ~ ETU + Switching)")
        elif any(berth in g and q.berth in g for g in cargo_rule.SAME_CARGO_BERTH_GROUPS) and q.slot < my_end - back and prev < q_end - back:
            who.append(f"#{q.berth} {q.vessel_id} (동일 화물 그룹 작업 구간)")
        elif any(berth in g and q.berth in g for g in pair_rule.SIMULTANEOUS_BERTH_PAIRS) and q.slot < my_end - back and prev < q_end - back:
            who.append(f"#{q.berth} {q.vessel_id} (#4 동시 접안)")
    tail = ", ".join(who) if who else "앞 칸에 대면 다른 배와 겹침"
    return f"ETB {when} — 앞 칸 {table.time(prev):%m/%d %H:%M}에 대면 {tail} (불필요한 대기 금지 검사 통과)"


def _plan_json(rules, case, data, blocks_for, table, costs, res, vid, asg, given_times):
    a = case.arrivals[vid]
    p = data.profiles[vid]
    bid = next(b for b in rules.berth_order if _norm(b) == asg.berth)
    if vid in given_times:                                # 작업 중·FIX 배의 입력 시각 그대로 — 기존 엔진 식으로 계산 (최적화 대상 아님)
        ours = make_plan(rules, case, a, bid, _mins(asg.etb, f"{vid} ETB"), why="작업 중·FIX (입력값)", fixed=True)
        j = plan_json(rules, case, ours)
        j["why_etb"] = "작업 중·FIX (입력한 ETB·작업시작·이안 그대로 — 기존 엔진 식으로 계산, 팀원 모델에는 같은 이안으로 넣음)"
        return j, ours
    plan = after_etb.ShipmentPlan(
        etb=asg.etb, berth=asg.berth, vessel_code=p.vessel_code, material_code=p.material_code, qty=p.qty,
        vessel_type=p.vessel_type, laycan_from=p.laycan_from, laycan_to=p.laycan_to, eta=_dt(a.eta), nr_tender=p.nr_tender,
        laytime=p.laytime, cfr=p.cfr, demurrage_rate=p.demurrage_rate, stops=())
    r = after_etb.calc_after_etb(plan, data.history, blocks_for(vid))
    cents = _cents(r.demurrage_time, a.contract.rate_cents)
    if abs(r.demurrage_fee * 100 - cents) > 1:
        raise RuntimeError(f"{vid}: 팀원 식 체선료 {r.demurrage_fee:.4f}와 정확 계산 {cents}센트가 1센트 넘게 다름")
    s = _mins(asg.etb, f"{vid} ETB")
    ws, wf, ho, u = (_mins(t, f"{vid} {n}") for t, n in ((r.work_start, "작업시작"), (r.work_finish, "작업완료"),
                                                         (r.hose_off, "호스분리"), (r.etu, "이안")))
    ls, le = _mins(r.laytime_start.at, f"{vid} 정박개시"), (r.laytime_end - EPOCH) / MINUTE
    allowed = (r.laytime_end - r.laytime_start.at) / timedelta(hours=1)
    why = (f"FIX (입력값) {asg.etb:%m/%d %H:%M}" if not a.movable else _blocked_text(table, costs, res, vid, asg.berth, asg.slot))
    hrs = lambda td: round(td / timedelta(hours=1), 4)  # noqa: E731
    f = lambda t: f"{t:%m/%d %H:%M}"  # noqa: E731
    trace = [
        {"rule": "ETB", "text": why, "src": "berth_sim/feasibility.py · cpsat_model.py"},
        {"rule": "P9", "text": f"작업시작 = ETB {f(asg.etb)} + 1h = {f(r.work_start)}", "src": "after_etb/s1_work_start.py"},
        {"rule": "P10", "text": f"작업완료 = 작업시작 + 물량 ÷ 평균 Rate {r.rate.rate:,.2f}/h = {f(r.work_finish)} "
                               f"(평균 Rate는 요청의 Rate·작업시간을 과거 실적 한 줄로 넣어 구함 — 팀원 코드는 원래 과거 Shipment에서 구한다)",
         "src": "after_etb/s2_work_finish.py"},
        {"rule": "P11", "text": f"호스분리 = 작업완료 + 30분 = {f(r.hose_off)}", "src": "after_etb/s4_hose_off.py"},
        {"rule": "P12", "text": f"이안 ETU = 작업완료 + 2h = {f(r.etu)}", "src": "after_etb/s3_etu.py"},
        {"rule": "P13", "text": f"ETANR = NVL(NOR, ETA) = {f(r.etanr)}", "src": "after_etb/s5_etanr.py"},
        {"rule": "P14·P15", "text": f"정박개시 {f(r.laytime_start.at)} — {r.laytime_start.reason}"
                                    f" ({'Daylight 적용' if r.daylight else 'Daylight 미적용'})",
         "src": "after_etb/s8_laytime_start_daylight.py" if r.daylight else "after_etb/s7_laytime_start_no_daylight.py"},
        {"rule": "P16", "text": f"정박종료 = 정박개시 + 허용 {allowed:g}h = {f(r.laytime_end)}", "src": "after_etb/s9_laytime_end.py"},
        {"rule": "P17", "text": f"기상체선 = 기상 제약 ∩ [정박종료, 호스분리] = {hrs(r.weather):g}h → ½ 공제", "src": "after_etb/s10_weather_hours.py"},
        {"rule": "P18", "text": f"체선시간 = max(0, 호스분리 − 정박종료 − 기상체선/2) = {hrs(r.demurrage_time):g}h", "src": "after_etb/s11_demurrage_time.py"},
        {"rule": "P19", "text": f"체선료 = 체선시간 × ${a.contract.rate_cents / 100:,.0f}/일 ÷ 24 = ${cents / 100:,.2f}", "src": "after_etb/s12_demurrage_fee.py"},
    ]
    return {
        "arrival_id": vid, "vessel": a.vessel, "class": a.vclass, "biz": a.biz, "cargo_group": a.cargo, "status": a.status,
        "berth": bid, "eta": iso(a.eta), "etb": iso(s), "work_start": iso(ws), "work_end": iso(wf), "hose_off": iso(ho), "etu": iso(u),
        "laytime_start": iso(ls), "laytime_rule": r.laytime_start.reason, "laytime_end": iso(int(le)) if float(le).is_integer() else iso(int(le)),
        "allowed_hours": round(allowed, 4), "weather_hours": hrs(r.weather), "deduction_hours": hrs(r.weather / 2),
        "demurrage_hours": hrs(r.demurrage_time), "demurrage_usd": cents / 100,
        "wait_hours": round((s - max(a.eta, case.start)) / 60, 2), "why_etb": why, "trace": trace,
    }, make_plan(rules, case, a, bid, s, fixed=not a.movable)


def _changes(base_plans, ours):
    b = {p.aid: p for p in base_plans}
    out = []
    for p in sorted(ours, key=lambda x: x.s):
        q = b.get(p.aid)
        if q is None or p.fixed:
            continue
        if q.berth != p.berth or q.s != p.s:
            out.append({"arrival_id": p.aid, "from": {"berth": q.berth, "etb": iso(q.s), "usd": q.cents / 100},
                        "to": {"berth": p.berth, "etb": iso(p.s), "usd": p.cents / 100}, "delta_usd": (p.cents - q.cents) / 100})
    return out


# ----------------------------------------------------------------------------- 3. 풀기
def optimize(request: dict, top: int = 3, time_limit: float = 120.0) -> dict:
    t0 = time.time()
    rules = Rules(patch=request.get("rule_patch"))
    case = load_case(request, rules)
    bad = rule_mismatches(rules, case)
    if bad:
        raise ValueError("팀 엔진은 팀원 코드에 고정된 해석으로만 돈다 — 실행할 때 규칙 해석 'team'을 고른다. 다른 곳: " + " · ".join(bad))
    notes = []
    if case.tanks:
        notes.append("팀 엔진 어댑터는 탱크 재고(inventory)를 아직 팀원 코드에 넘기지 않는다 — Spring 재검증이 재고 위반을 잡으면 그 후보는 실패")
    master, sequences, data, blocks, home, given_times = _inputs(rules, case)
    no_half = {a.id for a in case.arrivals.values() if not a.contract.weather_half}
    plain = [b for b in blocks if b.kind is not BlockKind.WEATHER]
    blocks_for = lambda vid: plain if vid in no_half else blocks  # noqa: E731  기상 공제를 안 받는 계약은 기상 제약을 공제에서 뺀다
    fixed_etbs = [a.fix["etb"] for a in case.arrivals.values() if not a.movable]
    start = min([case.start, *fixed_etbs])
    with _sun(case, rules):
        avail = {b: _dt(case.start) for b in master.berths}
        table = feasibility.build_table(sequences, data, master, avail, blocks, start=_dt(start), end=_dt(case.end), step=STEP)
        costs = cost_table.build_costs(table, data, blocks)
        if no_half and len(plain) != len(blocks):
            sub = replace(table, rows=tuple(r for r in table.rows if r.vessel_id in no_half))
            costs.update(cost_table.build_costs(sub, data, plain))
        end = int((_dt(case.end) - table.start) / MINUTE)
        dropped = []
        for (vid, b) in list(costs):
            a = case.arrivals[vid]
            bid = next(x for x in rules.berth_order if _norm(x) == b)
            if a.movable and (not eligible(rules, a, bid)[0] or (a.berths and bid not in a.berths)):
                del costs[(vid, b)]                       # 팀원 코드는 됐는데 우리 규칙(Spring 재검증)으로 배정 불가 — 해석을 맞췄으니 0건이어야 한다
                dropped.append(f"{vid}@{bid}")
                continue
            c = costs[(vid, b)]
            if a.movable:
                for i in c.feasible_slots():
                    if c.etu[i] > end:                    # 이안이 계획 종료 뒤인 칸은 뺀다 (Spring: '이안이 계획 종료 뒤' 위반)
                        c.fee[i] = c.fee_c[i] = -1
            if not c.feasible_slots():
                del costs[(vid, b)]
        if dropped:
            notes.append("팀원 코드는 됐지만 우리 규칙으로 배정 불가라 뺀 (배, 부두): " + ", ".join(dropped[:10]) + (" …" if len(dropped) > 10 else ""))
        no_pair = [vid for vid in case.arrivals if not any(k[0] == vid for k in costs)]
        base = baseline(rules, case)
        cur = current_plans(rules, case)
        resp = {
            "request_id": request.get("request_id", case.id),
            "request_hash": hashlib.sha256(repr(sorted(request.items(), key=lambda kv: kv[0])).encode()).hexdigest()[:16],
            "case_id": case.id, "title": case.title,
            "engine": {"version": ENGINE_VERSION, "rules_version": rules.version, "solver": f"OR-Tools CP-SAT {ortools.__version__}",
                       "python": platform.python_version(),
                       "formulas": "팀원 코드 berth_sim 그대로 — ETB 규칙 step1~3 · ETB 이후 after_etb s1~s12 · cpsat_model (고치지 않음)",
                       "objective": "체선료 합 최소 ≫ 부두 변경 최소 ≫ 일찍 접안 (팀원 코드 그대로, 5분 칸, 불필요한 대기 금지)",
                       "source_sha256": SOURCE_SHA},
            "status": "OK",
            "plan_window": {"start": iso(case.start), "end": iso(case.end)},
            "baseline": schedule_json(rules, case, base) if base else None,
            "current_plan": schedule_json(rules, case, cur) if cur else None,
            "candidates": [],
            "components": [],
            "notes": notes + ["기준안·현행 계획은 비교용이라 기존 엔진(같은 규칙)으로 계산했다. 후보 1~N안만 팀원 코드가 찾았다."],
        }
        if no_pair:
            resp["status"] = "INFEASIBLE"
            resp["notes"].append("접안 가능한 (부두, 5분 칸)이 하나도 없는 입항 건: " + ", ".join(no_pair))
            resp["elapsed_seconds"] = round(time.time() - t0, 2)
            return resp
        per_plan = max(5.0, time_limit / max(1, top))
        stays = cpsat_model.stays_for(table, costs)
        hint = {p.aid: (_norm(p.berth), _dt(p.s)) for p in base} if base else None
        t1 = time.time()
        results = cpsat_model.solve_tiers(table, costs, data, stays, home, hint, tiers=1, per_tier=top, time_limit_s=per_plan)
        solve_s = time.time() - t1
        if not results:                                   # 왜 없나: 정말 불가능(INFEASIBLE)인지, 시간 안에 못 찾았는지(UNKNOWN)
            probe = cpsat_model.BerthModel(table, costs, data, stays, home).solve_once(1, per_plan)
            resp["status"] = "INFEASIBLE" if probe.status == "INFEASIBLE" else "NO_SOLUTION"
            resp["notes"].append(f"CP-SAT 상태 {probe.status} — " + ("모든 제약을 지키는 조합이 없음" if probe.status == "INFEASIBLE"
                                                                   else f"계획 하나당 {per_plan:g}초 안에 해를 못 찾음 (불가능하다는 뜻은 아님)"))
        for rank, res in enumerate(results, 1):
            rows = [_plan_json(rules, case, data, blocks_for, table, costs, res, vid, asg, given_times)
                    for vid, asg in res.assignments.items()]
            order = {b: i for i, b in enumerate(rules.berth_order)}
            rows.sort(key=lambda x: (order[x[0]["berth"]], x[0]["etb"]))
            ours = [o for _, o in rows]
            mism = [f"{j['arrival_id']}: 팀원 ${j['demurrage_usd']:,.2f} ≠ 기존 엔진 ${o.cents / 100:,.2f}"
                    for j, o in rows if round(j["demurrage_usd"] * 100) != o.cents]
            if mism:
                resp["notes"].append(f"{rank}안 에이전트 자체 대조(기존 엔진과 같은 규칙): " + "; ".join(mism))
            total = sum(round(j["demurrage_usd"] * 100) for j, _ in rows)
            base_c = sum(p.cents for p in base) if base else None
            resp["candidates"].append({
                "rank": rank, "status": "OPTIMAL" if res.status == "OPTIMAL" else "TIME_LIMIT",
                "total_usd": total / 100, "plans": [j for j, _ in rows], "violations": verify(rules, case, ours),
                "changes_vs_baseline": _changes(base, ours) if base else [],
                "delta_vs_baseline_usd": (total - base_c) / 100 if base_c is not None else None,
                "team": {"tier": res.tier, "alt": res.alt, "diff_from_first": res.diff_rep, "moves_vs_current": res.moves,
                         "needless_waits": res.waits, "seconds": round(res.wall_s, 2), "proven_optimal": res.status == "OPTIMAL",
                         "bound_usd": res.best_bound},
            })
        resp["components"] = [{"mode": "CP-SAT 5분 칸", "pairs": len(costs), "slots": table.n_slots,
                               "feasible_slots": sum(len(c.feasible_slots()) for c in costs.values()),
                               "constraints": results[0].n_constraints if results else {}, "seconds": round(solve_s, 2),
                               "per_plan_limit_s": per_plan, "status": results[0].status if results else resp["status"]}]
    resp["elapsed_seconds"] = round(time.time() - t0, 2)
    return resp
