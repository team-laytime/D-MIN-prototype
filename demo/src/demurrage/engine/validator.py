"""독립 제약 검증기 — 후보가 하드 제약을 하나라도 어기면 후보로 내보내지 않는다(FR-35·36, 성공기준 ②).

ETB를 '만드는' 코드(etb.py의 밀어내기)와 일부러 다른 방식으로 짰다. 여기서는 완성된 일정을 받아
두 선박씩 짝지어 구간이 겹치는지, 시각이 금지 구간에 들었는지만 본다. 같은 실수를 두 번 하기 어렵게 하려는 것이다.
규칙 표·제원 같은 '데이터'는 같이 쓰지만 판정식은 공유하지 않는다.
"""
from __future__ import annotations

from ..domain.timeutil import DAY, HOUR, day_start, fmt


def _v(code, rule_id, message, vessels=(), berth=None, at=None):
    return {"code": code, "rule_id": rule_id, "message": message, "vessels": list(vessels), "berth": berth,
            "at": fmt(at) if at is not None else None}


def _night_release(ctx, v):
    """Last POB 대상이면 해제 시각(검증기 쪽 독립 계산)."""
    cfg = ctx.rules.night["last_pob"]
    subj = False
    for c in cfg["subject_any"]:
        ok = True
        if "grt_min" in c and not v.grt >= c["grt_min"]:
            ok = False
        if "grt_max" in c and not v.grt <= c["grt_max"]:
            ok = False
        if "direction" in c and v.direction != c["direction"]:
            ok = False
        if "draft_min" in c and not v.draft >= c["draft_min"]:
            ok = False
        subj = subj or ok
    if not subj:
        return None
    minus = None
    for o in cfg["offsets"]:
        if ("grt_max" in o and v.grt <= o["grt_max"]) or ("grt_min_exclusive" in o and v.grt > o["grt_min_exclusive"]):
            minus = int(round(float(o["sunset_minus_h"]) * 60))
            break
    if minus is None:
        return None
    for back in (0, 1):
        d0 = day_start(v.eta) - back * DAY
        lp = ctx.sun.sunset(d0) - minus
        rel = d0 + DAY + int(cfg["release_hour"]) * HOUR
        if lp <= v.eta < rel:
            return rel
    return None


def validate(ctx, placements: dict) -> list:
    rules = ctx.rules
    out = []
    vs = ctx.vessels

    # 0. 모든 이동 가능 선박이 배정됐나(FR-36)
    for vid in ctx.movable:
        if vid not in placements:
            out.append(_v("UNASSIGNED", "OPT-02", f"{vid} 미배정", [vid]))

    for vid, p in placements.items():
        v = vs[vid]
        b = rules.berths[p.berth]
        wp = ctx.work[(vid, p.berth)]
        # 1. 고정 선박은 입력 그대로(FR-10·11)
        if p.kind in ("FIX", "WORKING"):
            if p.berth != v.fixed_berth or p.etb != v.fixed_etb:
                out.append(_v("FIX_MOVED", "ETB-02", f"{vid} 고정 부두·ETB가 바뀜", [vid], p.berth, p.etb))
            continue
        # 2. 부두 적합성(ELG-01·02)
        if v.cargo_group not in b.cargo_groups:
            out.append(_v("CARGO", "ELG-02", f"{vid} {v.cargo_group}는 {b.id} 취급 불가", [vid], b.id))
        if v.dwt > b.max_dwt or not (b.min_loa <= v.loa <= b.max_loa) or v.pbl < b.min_pbl or (v.direction == "IMPORT" and v.draft > b.max_draft):
            out.append(_v("SPEC", "ELG-01", f"{vid} 제원이 {b.id} 허용 범위 밖", [vid], b.id))
        if b.id not in ctx.sc.active_berths or (v.allowed_berths and b.id not in v.allowed_berths):
            out.append(_v("BERTH_SCOPE", "SCN", f"{vid}는 {b.id}에 배정할 수 없음(시나리오·지정 부두)", [vid], b.id))
        # 3. 시각 정합(WRK-01~04)
        ws = p.etb + wp.start_delay
        if not (p.work_start == ws and p.work_end == ws + wp.work and p.hose_off == p.work_end + wp.hose_term
                and p.etu == p.work_end + wp.etu_after_work):
            out.append(_v("TIMES", "WRK-01", f"{vid} 작업·호스분리·ETU 시각이 규칙과 다름", [vid], b.id, p.etb))
        # 4. ETA + Direction 이전 접안 불가(ETB-01)
        if p.etb < v.eta + b.direction:
            out.append(_v("BEFORE_ETA", "ETB-01", f"{vid} ETB {fmt(p.etb)} < ETA + Direction", [vid], b.id, p.etb))
        # 5. 야간 도선(ETB-03·04)
        rel = _night_release(ctx, v)
        if rel is not None and p.etb < rel:
            out.append(_v("NIGHT_POB", "ETB-03", f"{vid} Last POB 이후 도착인데 ETB {fmt(p.etb)} < {fmt(rel)}", [vid], b.id, p.etb))
        dw = rules.night["dawn_window"]
        mod = p.etb % DAY
        if v.grt >= dw["grt_min"] and dw["from_hour"] * HOUR <= mod < dw["to_hour"] * HOUR:
            out.append(_v("NIGHT_DAWN", "ETB-04", f"{vid} GRT {v.grt:,} 선박이 {fmt(p.etb)}(02~08시) 접안", [vid], b.id, p.etb))
        # 6. 부두 사용 제한(ETB-07)
        for r in ctx.restrictions:
            if r.covers(b.id) and r.start <= p.etb < r.end + b.direction:
                out.append(_v("RESTRICTED", "ETB-07", f"{vid} ETB {fmt(p.etb)}가 {r.id}({r.reason}) 제한 구간", [vid], b.id, p.etb))
        # 7. 조석(ETB-08)
        if b.tide_draft_threshold is not None and v.draft >= b.tide_draft_threshold:
            wins = ctx.tide.get(b.id, [])
            if not any(s <= p.etb <= e for s, e in wins):
                out.append(_v("TIDE", "ETB-08", f"{vid} ETB {fmt(p.etb)}가 조석 시간창 밖", [vid], b.id, p.etb))
        # 8. 출하 마감(ETB-11)
        if v.deadline is not None and p.etb > v.deadline:
            out.append(_v("DEADLINE", "ETB-11", f"{vid} ETB {fmt(p.etb)} > 마감 {fmt(v.deadline)}", [vid], b.id, p.etb))

    # 9. 같은 부두 순서(ETB-01·02): 시각순으로 이웃한 두 선박
    by_berth = {}
    for p in placements.values():
        by_berth.setdefault(p.berth, []).append(p)
    for bid, lst in by_berth.items():
        b = rules.berths[bid]
        lst.sort(key=lambda p: (p.etb, p.vid))
        for a, c in zip(lst, lst[1:]):
            if a.kind != "MOVABLE" and c.kind != "MOVABLE":
                continue
            if c.kind == "FIX" and a.kind == "MOVABLE":
                if not a.etu + b.switching < c.etb:
                    out.append(_v("FIX_COLLIDE", "ETB-02", f"{a.vid} ETU {fmt(a.etu)} + Switching ≥ FIX {c.vid} ETB {fmt(c.etb)}", [a.vid, c.vid], bid, c.etb))
            elif c.etb < a.etu + b.switching:
                out.append(_v("OVERLAP", "ETB-01", f"{c.vid} ETB {fmt(c.etb)} < {a.vid} ETU {fmt(a.etu)} + Switching", [a.vid, c.vid], bid, c.etb))

    # 10. 동시 접안 제한(ETB-05·06): 다른 부두의 두 선박
    items = list(placements.values())
    release = rules.release_min
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            p, q = items[i], items[j]
            if p.berth == q.berth or (p.kind != "MOVABLE" and q.kind != "MOVABLE"):
                continue
            vp, vq = vs[p.vid], vs[q.vid]
            rule = None
            for combo in rules.combos:
                if p.berth in combo and q.berth in combo and vp.cargo_group == vq.cargo_group:
                    rule = "ETB-05"
            for pair, exempt in rules.pairs:
                if p.berth in pair and q.berth in pair and not (vp.grt <= exempt and vq.grt <= exempt):
                    rule = "ETB-06"
            if rule is None:
                continue
            a0, a1 = p.etb, p.etu - release
            b0, b1 = q.etb, q.etu - release
            if a0 < b1 and b0 < a1:
                out.append(_v("SIMULTANEOUS", rule, f"{p.vid}({p.berth})와 {q.vid}({q.berth}) 동시 작업 구간이 겹침", [p.vid, q.vid], f"{p.berth}/{q.berth}", max(a0, b0)))

    # 11. 재고(ETB-09): 일말 재고가 범위 안인가
    for g, inv in ctx.sc.inventory.items():
        delta = {}
        movers = []
        first_import = first_export = None
        for p in placements.values():
            v = vs[p.vid]
            if v.cargo_group != g:
                continue
            d = day_start(p.work_start)
            delta[d] = delta.get(d, 0.0) + (v.qty if v.direction == "IMPORT" else -v.qty)
            if p.kind == "MOVABLE":
                movers.append(p.vid)
            if v.direction == "IMPORT":
                first_import = d if first_import is None else min(first_import, d)
            else:
                first_export = d if first_export is None else min(first_export, d)
        if not movers:
            continue
        level = inv.opening
        d = day_start(ctx.sc.horizon_start)
        while d <= day_start(ctx.sc.horizon_end):
            level += inv.daily_net + delta.get(d, 0.0)
            over = first_import is not None and d >= first_import and level > inv.capacity + 1e-9
            under = first_export is not None and d >= first_export and level < inv.minimum - 1e-9
            if over or under:
                out.append(_v("INVENTORY", "ETB-09", f"{g} {fmt(d)[:5]} 일말 재고 {level:,.0f}가 범위({inv.minimum:,.0f}~{inv.capacity:,.0f}) 밖", movers, None, d))
            d += DAY
    return out
