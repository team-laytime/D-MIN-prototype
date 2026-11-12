"""남은 리스크 점검 (FR-40 5개 항목, FR-41 대안·주의 문구표, FR-43 민감도 연결).

후보마다 날씨 급변·설비·탱크·긴급 출하·현장 안전을 '해당 / 해당 없음 / 판단 불가'로 점검한다.
- 판단에 필요한 데이터가 아예 없으면 '판단 불가' (예: 예보가 없는 시나리오의 날씨)
- 근거가 있으면 관련 선박·부두·시각을 붙인다.
- 문구는 규칙 표(risk_phrases)에서 가져온다. '지금 확정' 같은 단정 표현은 쓰지 않는다.
판정 기준값(±6시간, 10%, 1시간)은 아래 THRESHOLDS 한 곳에 모았다 [가정 — 현업 확인 필요].
"""
from __future__ import annotations

from ..domain.timeutil import DAY, HOUR, day_start, fmt

THRESHOLDS = {
    "weather_window_h": 6,      # 강풍 제한 경계 ±6시간 안의 접안·이안
    "maintenance_window_h": 6,  # 정비 시작·종료 6시간 안
    "tank_margin_ratio": 0.10,  # 재고 여유 10% 미만
    "urgent_wait_h": 6,         # 긴급 출하 선박 대기 6시간 초과
    "deadline_slack_h": 12,     # 마감 여유 12시간 미만
    "close_maneuver_min": 60,   # 같은 조합 부두의 접·이안 1시간 안
}


def _item(phr, key, status, evidence, links):
    names = phr["status_names"]
    it = phr["items"][key]
    out = {"type": key, "name": it["name"], "status": status, "status_ko": names[status],
           "evidence": evidence, "links": links}
    if status != "NOT_APPLICABLE":
        out["alternative"] = it["alternative"]
        out["caution"] = it["caution"]
    return out


def assess(ctx, sch, sensitivity_flags=None) -> list:
    phr = ctx.rules.phrases
    pl = sch.state.pl
    vs = ctx.vessels
    items = []

    # 1. 날씨 급변
    wx = [r for r in ctx.restrictions if r.reason == "WEATHER"]
    if not ctx.sc.weather_segments:
        items.append(_item(phr, "WEATHER", "UNKNOWN", ["기상 예보 데이터가 없어 판단할 수 없음"], []))
    else:
        w = THRESHOLDS["weather_window_h"] * HOUR
        ev, links = [], []
        seen = set()
        for p in sorted(pl.values(), key=lambda p: p.etb):
            if p.kind == "MOVABLE":
                continue
            for r in wx:
                if r.covers(p.berth) and r.start <= p.etb < r.end + ctx.berths[p.berth].direction:
                    ev.append(f"고정 선박 {p.vid}의 접안 {fmt(p.etb)}이 강풍 제한 구간({fmt(r.start)}~{fmt(r.end)}) 안 — 고정 일정 재확인 필요")
                    links.append({"vessel": p.vid, "berth": p.berth, "at": fmt(p.etb)})
                    seen.add((p.vid, "접안"))
                    break
        for p in sorted(pl.values(), key=lambda p: p.etb):
            for r in wx:
                if not r.covers(p.berth):
                    continue
                for label, t in (("접안", p.etb), ("이안", p.etu)):
                    for edge_name, edge in (("시작", r.start), ("종료", r.end)):
                        if abs(t - edge) <= w and (p.vid, label) not in seen:
                            seen.add((p.vid, label))
                            ev.append(f"{p.vid} {label} {fmt(t)}가 강풍 제한 {edge_name} {fmt(edge)}와 {abs(t - edge) / 60:.1f}시간 차이")
                            links.append({"vessel": p.vid, "berth": p.berth, "at": fmt(t)})
        for f in (sensitivity_flags or []):
            if "강풍" in f["input"]:
                ev.append(f"예보 변경({f['input']}) 시 이 후보 순위 {f['rank_from']}위 → {f['rank_to']}위")
        items.append(_item(phr, "WEATHER", "APPLIES" if ev else "NOT_APPLICABLE",
                           ev or [f"강풍 제한 경계 ±{THRESHOLDS['weather_window_h']}시간 안의 접안·이안 없음"], links))

    # 2. 설비(정비)
    mt = [r for r in ctx.restrictions if r.reason == "MAINTENANCE"]
    if not mt:
        items.append(_item(phr, "EQUIPMENT", "NOT_APPLICABLE", ["등록된 설비 정비 일정 없음"], []))
    else:
        w = THRESHOLDS["maintenance_window_h"] * HOUR
        ev, links = [], []
        for p in sorted(pl.values(), key=lambda p: p.etb):
            for r in mt:
                if not r.covers(p.berth):
                    continue
                if p.etb < r.start < p.etu:
                    ev.append(f"{p.vid}가 {p.berth} 정비 시작({fmt(r.start)}) 때 아직 접안 중(이안 {fmt(p.etu)}) — 작업은 계속되지만 정비 준비와 겹침")
                    links.append({"vessel": p.vid, "berth": p.berth, "at": fmt(r.start)})
                elif 0 <= r.start - p.etu <= w:
                    ev.append(f"{p.vid} 이안 {fmt(p.etu)} 뒤 {(r.start - p.etu) / 60:.1f}시간 만에 {p.berth} 정비 시작 — 작업이 늦어지면 겹침")
                    links.append({"vessel": p.vid, "berth": p.berth, "at": fmt(p.etu)})
                elif p.kind == "MOVABLE" and 0 <= p.etb - (r.end + ctx.berths[p.berth].direction) <= w:
                    ev.append(f"{p.vid} 접안 {fmt(p.etb)}이 {p.berth} 정비 종료 직후 — 정비가 늦어지면 접안도 늦어짐")
                    links.append({"vessel": p.vid, "berth": p.berth, "at": fmt(p.etb)})
        items.append(_item(phr, "EQUIPMENT", "APPLIES" if ev else "NOT_APPLICABLE",
                           ev or ["정비 일정과 가까운 접안·이안 없음"], links))

    # 3. 탱크(재고)
    if not ctx.sc.inventory:
        items.append(_item(phr, "TANK", "UNKNOWN", ["탱크 재고 데이터가 없어 판단할 수 없음"], []))
    else:
        ev, links = [], []
        ratio = THRESHOLDS["tank_margin_ratio"]
        for g, inv in ctx.sc.inventory.items():
            delta, movers = {}, []
            for p in pl.values():
                v = vs[p.vid]
                if v.cargo_group == g:
                    d = day_start(p.work_start)
                    delta[d] = delta.get(d, 0.0) + (v.qty if v.direction == "IMPORT" else -v.qty)
                    movers.append(p.vid)
            level = inv.opening
            d = day_start(ctx.sc.horizon_start)
            while d <= day_start(ctx.sc.horizon_end):
                level += inv.daily_net + delta.get(d, 0.0)
                room = inv.capacity - level
                stock = level - inv.minimum
                if delta.get(d) and (room < inv.capacity * ratio or stock < inv.capacity * ratio):
                    which = f"빈 용량 {room:,.0f} {inv.unit}" if room < inv.capacity * ratio else f"재고 {stock:,.0f} {inv.unit}"
                    ev.append(f"{g} {fmt(d)[:5]} 일말 {which} — 용량 {inv.capacity:,.0f}의 {ratio * 100:.0f}% 미만")
                    links += [{"vessel": vid, "berth": pl[vid].berth, "at": fmt(d)[:5]} for vid in movers if day_start(pl[vid].work_start) == d]
                d += DAY
        not_covered = sorted({vs[p.vid].cargo_group for p in pl.values()} - set(ctx.sc.inventory))
        tail = [f"재고 데이터가 없는 화물({', '.join(not_covered)})은 점검하지 않음"] if not_covered else []
        items.append(_item(phr, "TANK", "APPLIES" if ev else "NOT_APPLICABLE", (ev or ["재고 여유 10% 이상 유지"]) + tail, links))

    # 4. 긴급 출하
    urgent = [vid for vid, v in vs.items() if (v.priority == "URGENT" or v.deadline is not None) and vid in pl]
    if not urgent:
        items.append(_item(phr, "URGENT", "NOT_APPLICABLE", ["긴급 출하·출하 마감이 지정된 선박 없음"], []))
    else:
        ev, links = [], []
        for vid in urgent:
            v, p = vs[vid], pl[vid]
            wait = p.etb - (v.eta + ctx.berths[p.berth].direction)
            if v.priority == "URGENT" and wait > THRESHOLDS["urgent_wait_h"] * HOUR:
                ev.append(f"긴급 출하 {vid}가 {wait / 60:.1f}시간 대기(ETB {fmt(p.etb)})")
                links.append({"vessel": vid, "berth": p.berth, "at": fmt(p.etb)})
            if v.deadline is not None and v.deadline - p.etb < THRESHOLDS["deadline_slack_h"] * HOUR:
                ev.append(f"{vid} 접안 마감 {fmt(v.deadline)}까지 여유 {(v.deadline - p.etb) / 60:.1f}시간")
                links.append({"vessel": vid, "berth": p.berth, "at": fmt(p.etb)})
        items.append(_item(phr, "URGENT", "APPLIES" if ev else "NOT_APPLICABLE",
                           ev or [f"긴급 출하 선박({', '.join(urgent)})이 크게 기다리지 않음"], links))

    # 5. 현장 안전
    ev, links = [], []
    for p in sorted(pl.values(), key=lambda p: p.etb):
        if p.kind != "MOVABLE":
            continue
        for label, t in (("접안", p.etb), ("이안", p.etu)):
            rise, sset = ctx.sun.get(day_start(t))
            if t < rise or t > sset:
                ev.append(f"{p.vid} 야간 {label} {fmt(t)} (일출 {fmt(rise)[6:]}·일몰 {fmt(sset)[6:]})")
                links.append({"vessel": p.vid, "berth": p.berth, "at": fmt(t)})
    events = sorted([(t, p.vid, p.berth, lab) for p in pl.values() for lab, t in (("접안", p.etb), ("이안", p.etu))])
    close = THRESHOLDS["close_maneuver_min"]
    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            ti, vi, bi, li = events[i]
            tj, vj, bj, lj = events[j]
            if tj - ti > close:
                break
            if vi != vj and bi != bj and any(bi in c and bj in c for c in ctx.rules.combos):
                ev.append(f"같은 조합 부두 근접 작업: {vi} {li}({bi}) {fmt(ti)} · {vj} {lj}({bj}) {fmt(tj)}")
                links.append({"vessel": vj, "berth": bj, "at": fmt(tj)})
    items.append(_item(phr, "SAFETY", "APPLIES" if ev else "NOT_APPLICABLE", ev or ["야간 접·이안과 근접 작업 없음"], links))
    return items
