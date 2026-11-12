"""정박개시·정박종료·체선료 — 멘토링 PPT 09·11쪽, 팀 요구사항 FR-24~FR-30, FR-32.

  ETANR = NVL(NR_TENDER, ETA)                                                  LAY-01
  정박개시:
    ① ETANR < Laycan From 이고 ETB < Laycan From  → ETB          (Early Loading)  LAY-02
    ② ETANR > Laycan To                           → ETB          (Laycan Miss)    LAY-03
    ③ ETANR < Laycan From                         → Laycan From 당일 06:00        LAY-04
    ④ 그 밖(Laycan 안)                            → ETANR + 6h, ETB가 더 이르면 ETB LAY-05
       원유선·제품선(Daylight 적용)은 ④의 'ETANR + 6h' 대신                     LAY-06
       일출~일몰이면 ETANR + 6h, 일출 전이면 당일 07:00, 일몰 후면 다음 날 07:00
  정박종료 = 정박개시 + Laytime(계약 유형별 배수)                                  LAY-07
  Demurrage Time = 호스분리 − 정박종료                                           DEM-01
  Demurrage Time −= 기상 체선 시간 × 1/2  (0 미만이면 0)                         DEM-02
  체선료 = Demurrage Time × 하루 체선료 ÷ 24 (센트 반올림)                       DEM-03
"""
from __future__ import annotations

from fractions import Fraction

from ..domain.model import REASON_CATEGORY
from ..domain.money import demurrage_cents
from ..domain.timeutil import DAY, HOUR, day_start, fmt, fmt_hours, fmt_iso, hours_to_min, overlap


def notice_min(ctx, v) -> int:
    c = v.contract
    return c.notice_min if c.notice_min is not None else ctx.rules.notice_min


def weather_ratio(ctx, v) -> Fraction:
    c = v.contract
    return c.weather_ratio if c.weather_ratio is not None else ctx.rules.weather_ratio


def daylight_applies(ctx, v) -> bool:
    """주간 NOR: 계약서에 조항이 있으면 그대로, 없으면 선종 규칙(원유선·제품선, PPT 09쪽)."""
    c = v.contract
    if c.daylight_nor is not None:
        return bool(c.daylight_nor)
    return v.vessel_type in ctx.rules.daylight_types


def laytime_start(ctx, v, etb: int):
    """(정박개시, 규칙 ID, 설명, 단계별 값)."""
    rules = ctx.rules
    c = v.contract
    nmin = notice_min(ctx, v)
    etanr = c.nor_tender if c.nor_tender is not None else v.eta
    lf, lt = c.laycan_from, c.laycan_to
    steps = {"ETANR": etanr, "ETANR_rule": "LAY-01", "laycan_from": lf, "laycan_to": lt}
    if etanr < lf and etb < lf:
        return etb, "LAY-02", f"ETANR {fmt(etanr)}·ETB {fmt(etb)} 모두 Laycan From {fmt(lf)} 이전(Early Loading) → ETB", steps
    if etanr > lt:
        return etb, "LAY-03", f"ETANR {fmt(etanr)} > Laycan To {fmt(lt)}(Laycan Miss) → ETB", steps
    if etanr < lf:
        start = day_start(lf) + rules.early_start_min
        return start, "LAY-04", f"ETANR {fmt(etanr)} < Laycan From {fmt(lf)}(조기 도착) → Laycan From 당일 {fmt(start)[6:]}", steps
    if daylight_applies(ctx, v):
        dl = rules.daylight
        rise, sset = ctx.sun.get(day_start(etanr))
        inclusive = bool(dl.get("bounds_inclusive", True))
        within = (rise <= etanr <= sset) if inclusive else (rise < etanr < sset)
        if within:
            cand, how = etanr + nmin, f"일출 {fmt(rise)[6:]}~일몰 {fmt(sset)[6:]} 사이 → ETANR + {nmin / 60:g}h"
        elif etanr < rise:
            cand = day_start(etanr) + hours_to_min(dl["before_sunrise_start_hour"])
            how = f"일출 {fmt(rise)[6:]} 전 → 당일 {fmt(cand)[6:]}"
        else:
            cand = day_start(etanr) + DAY + hours_to_min(dl["after_sunset_next_day_start_hour"])
            how = f"일몰 {fmt(sset)[6:]} 후 → 다음 날 {fmt(cand)[6:]}"
        steps.update({"sunrise": rise, "sunset": sset, "daylight_candidate": cand})
        if etb < cand:
            return etb, "LAY-06", f"{how} = {fmt(cand)}보다 ETB {fmt(etb)}가 이름 → ETB", steps
        return cand, "LAY-06", f"{how} = {fmt(cand)}", steps
    cand = etanr + nmin
    steps["notice_candidate"] = cand
    if etb < cand:
        return etb, "LAY-05", f"ETANR + {nmin / 60:g}h = {fmt(cand)}보다 ETB {fmt(etb)}가 이름 → ETB", steps
    return cand, "LAY-05", f"ETANR {fmt(etanr)} + {nmin / 60:g}h = {fmt(cand)}", steps


def laytime_minutes(ctx, v):
    """(Laytime 분, 계약 규칙 이름, 상태)."""
    ct = ctx.rules.contract_types[v.contract.type]
    mult = Fraction(str(ct.get("laytime_multiplier", 1)))
    applies = ct.get("applies_to_vessel_types")
    if applies and v.vessel_type not in applies:
        mult = Fraction(1)
    minutes = hours_to_min(v.contract.laytime_h * mult)
    note = v.contract.laytime_basis or f"{ct['name']} Laytime {fmt_hours(hours_to_min(v.contract.laytime_h))}"
    if mult != 1:
        note += f" × {mult} = {fmt_hours(minutes)}"
    return minutes, note, ct.get("status", "가정")


def _money(ctx, v, start, lay_min, etb, hose_off, etb_nowx):
    """DEM-01~03 한 곳에서만 계산한다 — 계산서와 최적화가 같은 숫자를 쓰게."""
    end = start + lay_min
    dt_raw = hose_off - end
    wx_min = overlap(etb_nowx, etb, end, hose_off) if dt_raw > 0 else 0
    deduction = Fraction(wx_min) * weather_ratio(ctx, v)
    dt = Fraction(dt_raw) - deduction
    if dt < 0:
        dt = Fraction(0)
    return end, dt_raw, wx_min, deduction, dt, demurrage_cents(dt, v.contract.rate_usd_day)


def amount_cents(ctx, v, p) -> int:
    """최적화용 빠른 계산 — compute()와 같은 식, 같은 결과."""
    start = laytime_start(ctx, v, p.etb)[0]
    lay_min = ctx.laytime_cache.get(v.id)
    if lay_min is None:
        lay_min = ctx.laytime_cache[v.id] = laytime_minutes(ctx, v)[0]
    etb_nowx = p.etb_nowx if p.etb_nowx is not None else p.etb
    return _money(ctx, v, start, lay_min, p.etb, p.hose_off, etb_nowx)[5]


def lower_bound_cents(ctx, v, bid: str, t: int) -> int:
    """ETB가 t 이후일 때 이 선박 체선료의 하한(분기한정 탐색용).

    ETB가 늦어질수록 체선료는 줄지 않는다 — 단 하나의 예외: Laycan From 직전(Early Loading, 정박개시 = ETB)에서
    Laycan From 이후(정박개시 = From 06:00)로 넘어가면 정박개시가 늦어져 체선 시간이 줄 수 있다. 그래서 두 점 중 작은 값.
    기상 공제는 '기다린 시간이 전부 기상 탓'인 최대치로 잡아 하한이 실제보다 크지 않게 한다.
    """
    wp = ctx.work[(v.id, bid)]
    lay_min = ctx.laytime_cache.get(v.id)
    if lay_min is None:
        lay_min = ctx.laytime_cache[v.id] = laytime_minutes(ctx, v)[0]
    lb0 = v.eta + ctx.berths[bid].direction
    weather = ctx.has_weather.get(bid, False)

    def g(tt):
        start = laytime_start(ctx, v, tt)[0]
        end = start + lay_min
        hose = tt + wp.etb_to_hose
        dt_raw = hose - end
        if dt_raw <= 0:
            return 0
        wmax = overlap(lb0, tt, end, hose) if weather else 0
        dt = Fraction(dt_raw) - Fraction(wmax) * weather_ratio(ctx, v)
        return demurrage_cents(dt, v.contract.rate_usd_day) if dt > 0 else 0

    best = g(t)
    c = v.contract
    etanr = c.nor_tender if c.nor_tender is not None else v.eta
    if etanr < c.laycan_from and t < c.laycan_from:
        best = min(best, g(c.laycan_from))
    return best


def compute(ctx, v, p) -> dict:
    """선박 한 척의 계산서 — 근거 조회(FR-39)에 그대로 보인다."""
    rules = ctx.rules
    start, branch, start_note, steps = laytime_start(ctx, v, p.etb)
    lay_min, lay_note, ct_status = laytime_minutes(ctx, v)
    etb_nowx = p.etb_nowx if p.etb_nowx is not None else p.etb
    end, dt_raw, wx_min, deduction, dt, cents = _money(ctx, v, start, lay_min, p.etb, p.hose_off, etb_nowx)

    statuses = []
    if branch == "LAY-06":
        statuses.append("가정값 포함")
    if ct_status == "미확정":
        statuses.append("미확정 규칙 포함")
    if any(x.rule_id == "ETB-03" for x in p.pushes):
        statuses.append("확인 필요 규칙 포함")

    rule_ids = ["LAY-01", branch, "LAY-07", "DEM-01", "DEM-02", "DEM-03", "WRK-01", "WRK-02", "WRK-03", "WRK-04"]
    rule_ids += sorted({x.rule_id for x in p.pushes})
    return {
        "vessel_id": v.id,
        "berth": p.berth,
        "kind": p.kind,
        "eta": v.eta,
        "etanr": steps["ETANR"],
        "laycan_from": v.contract.laycan_from,
        "laycan_to": v.contract.laycan_to,
        "etb": p.etb,
        "etb_without_weather": etb_nowx,
        "work_start": p.work_start,
        "work_end": p.work_end,
        "hose_off": p.hose_off,
        "etu": p.etu,
        "laytime_start": start,
        "laytime_start_rule": branch,
        "laytime_start_note": start_note,
        "laytime_minutes": lay_min,
        "laytime_note": lay_note,
        "laytime_end": end,
        "demurrage_raw_minutes": dt_raw,
        "weather_minutes": wx_min,
        "weather_deduction_minutes": deduction,
        "demurrage_minutes": dt,
        "rate_usd_day": v.contract.rate_usd_day,
        "amount_cents": cents,
        "rule_ids": rule_ids,
        "statuses": statuses,
        "steps": steps,
        "pushes": [x.as_dict() for x in p.pushes],
        "work_basis": p.work_basis,
        "reasons": reason_breakdown(ctx, v, p, end, dt_raw),
    }


def reason_breakdown(ctx, v, p, end: int, dt_raw: int) -> list:
    """체선 시간(공제 전)을 사유별로 나눈다(FR-32). 합은 늘 체선 시간과 같다."""
    if dt_raw <= 0:
        return []
    segs = [(v.eta, p.lb0, "APPROACH")]
    t_nowx = p.etb_nowx if p.etb_nowx is not None else p.etb
    for x in (p.pushes_nowx if p.pushes_nowx is not None else p.pushes):
        segs.append((x.frm, min(x.to, t_nowx), x.reason))
    if t_nowx < p.etb:
        segs.append((t_nowx, p.etb, "WEATHER"))
    segs.append((p.etb, p.hose_off, "AT_BERTH"))
    acc = {}
    covered = 0
    for s, e, reason in segs:
        if e <= s:
            continue
        m = overlap(s, e, end, p.hose_off)
        if m:
            cat = REASON_CATEGORY.get(reason, "미상")
            acc[cat] = acc.get(cat, 0) + m
            covered += m
    if covered < dt_raw:
        acc["미상"] = acc.get("미상", 0) + (dt_raw - covered)
    rate = v.contract.rate_usd_day
    out = []
    for cat, m in sorted(acc.items(), key=lambda kv: -kv[1]):
        out.append({"category": cat, "minutes": m, "hours": fmt_hours(m), "amount_cents_before_deduction": demurrage_cents(m, rate)})
    return out


def evidence_rows(ctx, calc: dict) -> list:
    """사람이 읽는 근거 표(FR-39): 이 값들만으로 손계산하면 같은 금액이 나와야 한다."""
    rn = ctx.rules.rule_name
    rows = [
        ("ETA", fmt(calc["eta"]), "입력"),
        ("ETANR", fmt(calc["etanr"]), rn("LAY-01")),
        ("Laycan", f"{fmt(calc['laycan_from'])} ~ {fmt(calc['laycan_to'])}", "입력(계약)"),
        ("ETB", fmt(calc["etb"]), " · ".join(sorted({rn(x["rule_id"]) for x in calc["pushes"]})) or rn("ETB-01")),
        ("작업시작", fmt(calc["work_start"]), rn("WRK-01")),
        ("작업완료", fmt(calc["work_end"]), rn("WRK-02")),
        ("호스분리", fmt(calc["hose_off"]), rn("WRK-03")),
        ("이안(ETU)", fmt(calc["etu"]), rn("WRK-04")),
        ("정박개시", fmt(calc["laytime_start"]), f"{rn(calc['laytime_start_rule'])}: {calc['laytime_start_note']}"),
        ("Laytime", fmt_hours(calc["laytime_minutes"]), calc["laytime_note"]),
        ("정박종료", fmt(calc["laytime_end"]), rn("LAY-07")),
        ("체선 시간(공제 전)", fmt_hours(max(0, calc["demurrage_raw_minutes"])), rn("DEM-01")),
        ("기상 체선 시간", fmt_hours(calc["weather_minutes"]), "기상 제한이 없었다면 ETB "
         + fmt(calc["etb_without_weather"]) + " → 체선 기간과 겹친 시간"),
        ("기상 공제", fmt_hours(calc["weather_deduction_minutes"]), rn("DEM-02")),
        ("체선 시간(공제 후)", fmt_hours(calc["demurrage_minutes"]), "max(0, 공제 전 − 공제)"),
        ("하루 체선료", f"${calc['rate_usd_day']:,}", "입력(계약)"),
        ("예상 체선료", f"${calc['amount_cents'] / 100:,.2f}", rn("DEM-03")),
    ]
    return [{"item": a, "value": b, "basis": c} for a, b, c in rows]


def _h(m) -> str:
    """분 → '12.75h' (정수면 '12h')."""
    h = Fraction(m) / 60
    if h.denominator == 1:
        return f"{h.numerator}h"
    return f"{float(h):.2f}".rstrip("0").rstrip(".") + "h"


def wait_breakdown(p) -> list:
    """ETA + Direction 이후 접안이 밀린 시간을 사유별로 더한다 → [(사유, 분)], 긴 순."""
    acc = {}
    if p.kind == "MOVABLE":
        for x in p.pushes:
            cat = REASON_CATEGORY.get(x.reason, "미상")
            acc[cat] = acc.get(cat, 0) + (x.to - x.frm)
    return sorted(acc.items(), key=lambda kv: -kv[1])


def _summary(v, p, b, calc, ratio) -> str:
    """계산서 맨 위 한 줄: 언제 와서, 무엇 때문에 얼마나 기다렸고, 그래서 얼마인가."""
    end, hose = calc["laytime_end"], p.hose_off
    waits = wait_breakdown(p)
    why = " · ".join(f"{k} {_h(m)}" for k, m in waits[:2])
    if p.kind == "FIX":
        head = f"FIX 일정대로 {b.id} {fmt(p.etb)} 접안"
    elif p.kind == "WORKING":
        head = f"{b.id}에서 작업 중({fmt(p.etb)} 접안)"
    elif why:
        head = f"{fmt(v.eta)} 도착 → {why} 기다려 {b.id} {fmt(p.etb)} 접안"
    else:
        head = f"{fmt(v.eta)} 도착 → 바로 {b.id} {fmt(p.etb)} 접안"
    if calc["amount_cents"] == 0:
        if hose == end:
            return f"{head}. 정박종료와 같은 시각({fmt(end)})에 호스 분리 — 체선료 없음."
        if hose > end:   # 늦었지만 기상 공제로 0이 된 경우
            return f"{head}. 정박종료({fmt(end)})를 넘긴 시간이 모두 기상 공제 대상 — 체선료 없음."
        return f"{head}. 정박종료({fmt(end)}) 전에 호스 분리({fmt(hose)}) — 체선료 없음."
    tail = f"정박종료({fmt(end)})보다 {_h(hose - end)} 늦게 호스 분리({fmt(hose)})"
    if calc["weather_minutes"]:
        wx = _h(calc["weather_minutes"])
        if ratio == 0:
            tail += f"(기상 대기 {wx}도 그대로 셈 — 기상 감면 조항 없음)"
        elif ratio == Fraction(1, 2):
            tail += f"(그중 기상 대기 {wx}는 계약서대로 절반만 셈)"
        else:
            tail += f"(그중 기상 대기 {wx}는 {ratio} 공제)"
    return f"{head}. {tail} → 체선 {_h(calc['demurrage_minutes'])}, ${calc['amount_cents'] / 100:,.0f}."


def calc_sheet(ctx, v, p, calc: dict) -> dict:
    """체선료 계산서 — 단계마다 '식에 숫자를 넣은 줄'과 근거(계약 조항·운영 기준·부두 기준·입력·실적)를 붙인다.

    화면의 계산서 창과 보고서가 이 구조를 그대로 쓴다. 이 값들만으로 손계산하면 같은 금액이 나와야 한다(FR-39).
    """
    rules = ctx.rules
    c = v.contract
    b = ctx.berths[p.berth]

    def rule_chip(rid):
        r = rules.rule(rid)
        src = r.get("source", "")
        return {"kind": "운영 기준", "text": f"{rid} {r.get('name', '')}", "detail": src, "rule_id": rid}

    def contract_chip(rid, fallback=None):
        refs = c.ref(rid) if c.id else ()
        if refs:
            return {"kind": "계약", "text": f"계약서 {c.id} {' · '.join(refs)}", "contract_id": c.id, "rule_id": rid,
                    "clauses": list(refs)}
        if fallback:
            return {"kind": "계약", "text": fallback, "contract_id": c.id}
        return {"kind": "계약", "text": "계약 조건(입력값)", "contract_id": c.id}

    steps = []
    etanr = calc["etanr"]
    # 1. 도착·NOR
    if c.nor_tender is not None:
        f1 = f"NOR 제출 {fmt(c.nor_tender)} (ETA {fmt(v.eta)})"
    else:
        f1 = f"NOR 제출 시각 없음 → ETA {fmt(v.eta)}를 씀"
    steps.append({"title": "도착 · NOR (ETANR)", "value": fmt(etanr), "formula": f1,
                  "basis": [contract_chip("LAY-01"), rule_chip("LAY-01"), {"kind": "입력", "text": "입항 예정 시각(ETA)"}]})
    # 2. 접안 시각
    if p.kind == "MOVABLE":
        parts = [f"ETA {fmt(v.eta)} + Direction {b.direction / 60:g}h = {fmt(p.lb0)}"]
        for x in p.pushes:
            parts.append(f"{x.rule_id} {rules.rule(x.rule_id).get('name', '')}: {fmt(x.frm)} → {fmt(x.to)}")
        basis = [{"kind": "부두 기준", "text": f"{b.id} Shifting 표 · Direction {b.direction / 60:g}h · Switching {b.switching / 60:g}h",
                  "detail": "멘토링 PPT 06쪽"}]
        seen = set()
        for x in p.pushes:
            if x.rule_id not in seen:
                seen.add(x.rule_id)
                basis.append(rule_chip(x.rule_id))
        if not p.pushes:
            basis.append(rule_chip("ETB-01"))
        steps.append({"title": "접안 시각 (ETB)", "value": fmt(p.etb), "formula": " → ".join(parts), "basis": basis,
                      "pushes": [x.as_dict() for x in p.pushes]})
    else:
        what = "FIX(일정 고정)" if p.kind == "FIX" else "작업 중"
        steps.append({"title": "접안 시각 (ETB)", "value": fmt(p.etb), "formula": f"{what} 선박 — 입력된 {b.id} {fmt(p.etb)} 그대로",
                      "basis": [{"kind": "입력", "text": f"{what} 일정"}, rule_chip("ETB-02")]})
    # 3. 작업
    wb = p.work_basis.get("work", {})
    if wb.get("stage") == "입력값":
        wchip = {"kind": "입력", "text": f"작업시간 {wb.get('hours')}h (입력)"}
    else:
        wchip = {"kind": "실적", "text": f"{wb.get('stage', '')} {wb.get('records', '')}건",
                 "detail": f"평균 Rate {wb.get('rate_per_h', 0):,.0f}/h × 물량 {wb.get('qty', 0):,.0f}"}
    work_min = p.work_end - p.work_start
    steps.append({"title": "작업 (하역·선적)", "value": f"{fmt(p.work_start)} ~ {fmt(p.work_end)}",
                  "formula": f"작업시작 = ETB + {(p.work_start - p.etb) / 60:g}h = {fmt(p.work_start)} · 작업 {_h(work_min)} → 작업완료 {fmt(p.work_end)}",
                  "basis": [rule_chip("WRK-01"), rule_chip("WRK-02"), wchip]})
    # 4. 호스분리·이안
    hb = p.work_basis.get("hose", {})
    if hb.get("stage") == "입력값":
        hchip = {"kind": "입력", "text": f"호스분리 소요 {hb.get('hours')}h (입력)"}
    else:
        hchip = {"kind": "실적", "text": f"호스분리 소요 최빈값 {hb.get('mode_minutes', 0)}분", "detail": f"{hb.get('stage', '')} {hb.get('records', '')}건"}
    steps.append({"title": "호스분리 · 이안", "value": f"{fmt(p.hose_off)} · {fmt(p.etu)}",
                  "formula": f"호스분리 = 작업완료 + {_h(p.hose_off - p.work_end)} = {fmt(p.hose_off)} · 이안(ETU) = 작업완료 + 2h = {fmt(p.etu)}",
                  "basis": [contract_chip("WRK-03", "정박시간 종료 = 호스 분리"), rule_chip("WRK-03"), rule_chip("WRK-04"), hchip]})
    # 5. 정박개시
    br = calc["laytime_start_rule"]
    sb = [contract_chip(br), rule_chip(br)]
    if br == "LAY-06":
        sb.append({"kind": "계산", "text": "일출·일몰", "detail": "시나리오 값 → 저장본 → NOAA 태양 위치식"})
    steps.append({"title": "정박개시", "value": fmt(calc["laytime_start"]), "formula": calc["laytime_start_note"], "basis": sb})
    # 6. 허용 정박시간
    lb = [contract_chip("LAY-07")]
    ct = rules.contract_types.get(c.type, {})
    if Fraction(str(ct.get("laytime_multiplier", 1))) != 1 and (not ct.get("applies_to_vessel_types") or v.vessel_type in ct["applies_to_vessel_types"]):
        lb.append({"kind": "운영 기준", "text": f"{ct.get('name')} 배수 {ct.get('laytime_multiplier')}", "detail": f"상태: {ct.get('status')}"})
    steps.append({"title": "허용 정박시간 (Laytime)", "value": _h(calc["laytime_minutes"]), "formula": calc["laytime_note"], "basis": lb})
    # 7. 정박종료
    steps.append({"title": "정박종료", "value": fmt(calc["laytime_end"]),
                  "formula": f"정박개시 {fmt(calc['laytime_start'])} + {_h(calc['laytime_minutes'])} = {fmt(calc['laytime_end'])}",
                  "basis": [rule_chip("LAY-07")]})
    # 8. 체선 시간
    raw = calc["demurrage_raw_minutes"]
    ratio = weather_ratio(ctx, v)
    f8 = f"호스분리 {fmt(p.hose_off)} − 정박종료 {fmt(calc['laytime_end'])} = {_h(raw) if raw > 0 else '0h(시간 안에 끝남)'}"
    if calc["weather_minutes"] and ratio:
        f8 += f" − 기상 {_h(calc['weather_minutes'])} × {ratio} = {_h(calc['demurrage_minutes'])}"
    elif calc["weather_minutes"]:
        f8 += f" (기상 대기 {_h(calc['weather_minutes'])}는 공제 없음)"
    if c.id and c.weather_ratio is not None and c.weather_ratio == 0:
        wchip2 = {"kind": "계약", "text": f"계약서 {c.id}: 기상 공제 조항 없음", "contract_id": c.id}
    else:
        wchip2 = contract_chip("DEM-02", "기상 체선 1/2 공제")
    steps.append({"title": "체선 시간", "value": _h(calc["demurrage_minutes"]), "formula": f8,
                  "basis": [contract_chip("DEM-01"), wchip2, rule_chip("DEM-01"), rule_chip("DEM-02")],
                  "note": (f"기상 대기 {_h(calc['etb'] - calc['etb_without_weather'])} 중 체선 기간에 든 {_h(calc['weather_minutes'])}에 공제 비율 {ratio} 적용"
                           if calc["etb"] > calc["etb_without_weather"] else None)})
    # 9. 체선료
    steps.append({"title": "예상 체선료", "value": f"${calc['amount_cents'] / 100:,.2f}",
                  "formula": f"{_h(calc['demurrage_minutes'])} × ${c.rate_usd_day:,} ÷ 24 = ${calc['amount_cents'] / 100:,.2f}",
                  "basis": [contract_chip("DEM-03"), rule_chip("DEM-03")]})

    summary = _summary(v, p, b, calc, ratio)
    return {"summary": summary, "steps": steps,
            "contract": {"id": c.id, "title": c.title, "type": c.type, "counterparty": c.counterparty,
                         "laytime": _h(calc["laytime_minutes"]), "rate_usd_day": c.rate_usd_day,
                         "notice_hours": notice_min(ctx, v) / 60, "weather_ratio": float(ratio),
                         "daylight_nor": daylight_applies(ctx, v)}}


def serialize(calc: dict) -> dict:
    """JSON으로 내보낼 형태(시각 문자열, 분 → 시간)."""
    out = dict(calc)
    for k in ("eta", "etanr", "laycan_from", "laycan_to", "etb", "etb_without_weather", "work_start", "work_end",
              "hose_off", "etu", "laytime_start", "laytime_end"):
        out[k] = fmt_iso(calc[k])
    for k in ("demurrage_minutes", "weather_deduction_minutes"):
        out[k] = float(calc[k])
    out["demurrage_hours"] = float(Fraction(calc["demurrage_minutes"]) / HOUR)
    out["amount_usd"] = calc["amount_cents"] / 100
    steps = dict(calc["steps"])
    for k, val in list(steps.items()):
        if isinstance(val, int) and k not in ("ETANR_rule",):
            steps[k] = fmt_iso(val)
    out["steps"] = steps
    return out
