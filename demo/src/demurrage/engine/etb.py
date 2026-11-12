"""ETB(예상 접안 시각) 통합 산정 — 멘토링 PPT 06~08쪽, 팀 요구사항 FR-09~FR-20.

ETB는 '조건별 접안 가능시각의 교집합'에서 정한다(PPT 06쪽). 구현은 '밀어내기'다.
  1) 출발점 t = ETA + Direction, 앞 선박이 있으면 max(t, 앞 선박 ETU + Switching)       ETB-01
  2) 아래 규칙을 차례로 검사해, 어긴 규칙이 있으면 t를 그 규칙이 허락하는 가장 이른 시각으로 민다
       Last POB(ETB-03) · 새벽 02~08시(ETB-04) · 부두 사용 제한(ETB-07) · 조석(ETB-08)
       FIX·작업 중 선박(ETB-01/02) · 동시 접안 제한(ETB-05/06) · 재고(ETB-09)
  3) 한 바퀴 동안 아무 규칙도 t를 밀지 않으면 끝 → 그 t가 ETB (ETB-10: 모든 제약 AND)
각 규칙은 '어긴 구간 안의 시각은 모두 불가'인 곳까지만 밀기 때문에, 결과는 모든 조건을 만족하는 가장 이른 시각이다.
밀 때마다 Push(규칙 ID, 어디서, 어디로, 사유)를 남긴다 → 근거 조회(FR-39)와 체선 사유 분해(FR-32)에 쓴다.
"""
from __future__ import annotations

from ..domain.model import Infeasible, Placement, Push
from ..domain.timeutil import DAY, day_start, fmt

MAX_ROUNDS = 200


class SchedState:
    """지금까지 정한 배정들. 탐색 중 복사해서 쓰므로 가볍게 둔다."""

    __slots__ = ("ctx", "pl", "by_berth", "last_mov", "order", "inv")

    def __init__(self, ctx, _empty=False):
        self.ctx = ctx
        if _empty:
            return
        self.pl = {}
        self.by_berth = {bid: [] for bid in ctx.berths}
        self.last_mov = {bid: None for bid in ctx.berths}
        self.order = []
        self.inv = {g: {} for g in ctx.sc.inventory}

    def copy(self):
        s = SchedState(self.ctx, _empty=True)
        s.pl = dict(self.pl)
        s.by_berth = {k: list(v) for k, v in self.by_berth.items()}
        s.last_mov = dict(self.last_mov)
        s.order = list(self.order)
        s.inv = {g: dict(d) for g, d in self.inv.items()}
        return s

    def add(self, p: Placement):
        self.pl[p.vid] = p
        lst = self.by_berth[p.berth]
        lst.append(p)
        lst.sort(key=lambda x: (x.etb, x.vid))
        if p.kind == "MOVABLE":
            self.last_mov[p.berth] = p
            self.order.append((p.vid, p.berth))
        v = self.ctx.vessels[p.vid]
        if v.cargo_group in self.inv:
            d = day_start(p.work_start)
            self.inv[v.cargo_group][d] = self.inv[v.cargo_group].get(d, 0.0) + _signed_qty(v)


def _signed_qty(v) -> float:
    return v.qty if v.direction == "IMPORT" else -v.qty


def inventory_ok(ctx, st: SchedState, v, day0: int):
    """그날 작업을 시작해도 되는지. (가능 여부, 문제 날짜, 넘치거나 모자란 양)."""
    g = ctx.sc.inventory.get(v.cargo_group)
    if g is None:
        return True, None, 0.0
    h_day0 = day_start(ctx.sc.horizon_start)
    h_last = day_start(ctx.sc.horizon_end)
    deltas = dict(st.inv.get(v.cargo_group, {}))
    deltas[day0] = deltas.get(day0, 0.0) + _signed_qty(v)
    level = g.opening
    d = h_day0
    while d <= h_last:
        level += g.daily_net + deltas.get(d, 0.0)
        if d >= day0:
            if v.direction == "IMPORT" and level > g.capacity + 1e-9:
                return False, d, level - g.capacity
            if v.direction == "EXPORT" and level < g.minimum - 1e-9:
                return False, d, g.minimum - level
        d += DAY
    return True, None, 0.0


def make_placement(ctx, v, bid: str, etb: int, kind: str, pushes, lb0, work_start_actual=None) -> Placement:
    wp = ctx.work[(v.id, bid)]
    ws = work_start_actual if work_start_actual is not None else etb + wp.start_delay
    we = ws + wp.work
    return Placement(vid=v.id, berth=bid, etb=etb, work_start=ws, work_end=we, hose_off=we + wp.hose_term,
                     etu=we + wp.etu_after_work, excl_end=we + wp.etu_after_work - ctx.rules.release_min,
                     lb0=lb0, kind=kind, pushes=list(pushes), work_basis=wp.basis)


def immovable_placement(ctx, v) -> Placement:
    """FIX·WORKING 선박 — 입력된 부두·ETB 그대로(자동 산출 대상에서 제외, PPT 06쪽)."""
    b = ctx.berths[v.fixed_berth]
    return make_placement(ctx, v, b.id, v.fixed_etb, "FIX" if v.status == "FIX" else "WORKING", [],
                          v.eta + b.direction, work_start_actual=v.work_start_actual)


def _search(ctx, v, b, st: SchedState, wp, with_weather: bool):
    """밀어내기 반복. (ETB, pushes) 또는 Infeasible."""
    bid = b.id
    pushes = []
    lb0 = v.eta + b.direction
    t = lb0
    prev = st.last_mov[bid]
    if prev is not None and prev.etu + b.switching > t:
        nt = prev.etu + b.switching
        pushes.append(Push("ETB-01", t, nt, "PREV", f"선행 선박 {prev.vid} ETU {fmt(prev.etu)} + Switching {b.switching / 60:g}h"))
        t = nt
    etb_to_etu = wp.etb_to_etu
    etb_to_excl = etb_to_etu - ctx.rules.release_min
    pob = ctx.last_pob.get(v.id)
    restr = ctx.restr_by_berth[bid]
    need_tide = ctx.requires_tide(v, bid)
    windows = ctx.tide.get(bid, []) if need_tide else None
    others = [p for p in st.pl.values() if p.berth != bid]
    blocks = [p for p in st.by_berth[bid] if p.kind != "MOVABLE"]
    has_inv = v.cargo_group in ctx.sc.inventory

    for _ in range(MAX_ROUNDS):
        t0 = t
        # ETB-03 Last POB (ETA 기준이라 고정된 하한)
        if pob is not None and t < pob[0]:
            pushes.append(Push("ETB-03", t, pob[0], "NIGHT_POB", pob[2]))
            t = pob[0]
        # ETB-04 새벽 02~08시
        if v.grt >= ctx.dawn_grt:
            m = t % DAY
            if ctx.dawn_from <= m < ctx.dawn_to:
                nt = day_start(t) + ctx.dawn_release
                pushes.append(Push("ETB-04", t, nt, "NIGHT_DAWN", f"GRT {v.grt:,} ≥ {ctx.dawn_grt:,}: {fmt(t)}는 02:00~08:00 → 08:00"))
                t = nt
        # ETB-07 부두 사용 제한(기상·정비·사용자)
        for r in restr:
            if r.reason == "WEATHER" and not with_weather:
                continue
            if r.start <= t < r.end + b.direction:
                nt = r.end + b.direction
                kind = r.reason if r.reason in ("WEATHER", "MAINTENANCE") else "USER"
                pushes.append(Push("ETB-07", t, nt, kind, f"{r.id} {fmt(r.start)}~{fmt(r.end)} {r.note} → 종료 + Direction"))
                t = nt
        # ETB-08 조석 시간창
        if windows is not None:
            if not any(s <= t <= e for s, e in windows):
                nxt = [s for s, e in windows if s > t]
                if not nxt:
                    return Infeasible(v.id, bid, "조석 시간창 없음", "ETB-08", f"{fmt(t)} 이후 {bid} 조석 시간창이 없음")
                pushes.append(Push("ETB-08", t, nxt[0], "TIDE", f"흘수 {v.draft:g} m ≥ {b.tide_draft_threshold:g} m → 다음 조석 시간창"))
                t = nxt[0]
        # ETB-01/02 FIX·작업 중 선박(같은 부두)
        for k in blocks:
            if k.etb <= t:
                need = k.etu + b.switching
                if t < need:
                    pushes.append(Push("ETB-01", t, need, "FIX" if k.kind == "FIX" else "PREV",
                                       f"{'FIX' if k.kind == 'FIX' else '작업 중'} 선박 {k.vid} ETU {fmt(k.etu)} + Switching"))
                    t = need
            elif t + etb_to_etu + b.switching >= k.etb:
                need = k.etu + b.switching
                pushes.append(Push("ETB-02", t, need, "FIX",
                                   f"다음 FIX 선박 {k.vid} ETB {fmt(k.etb)} ≤ 예상 ETU {fmt(t + etb_to_etu)} + Switching → 접안 불가, FIX 뒤로"))
                t = need
        # ETB-05/06 동시 접안 제한(다른 부두)
        for k in sorted(others, key=lambda p: (p.etb, p.vid)):
            rid = ctx.conflict_rule(v, bid, ctx.vessels[k.vid], k.berth)
            if rid is None:
                continue
            if t < k.excl_end and t + etb_to_excl > k.etb:
                what = "동일 화물 그룹" if rid == "ETB-05" else "부두 동시 접안"
                pushes.append(Push(rid, t, k.excl_end, "SAME_GROUP" if rid == "ETB-05" else "SIMUL",
                                   f"{what}: {k.berth} {k.vid} 접안 중 → ETU {fmt(k.etu)} − 2h"))
                t = k.excl_end
        # ETB-09 재고 (작업시작일 기준)
        if has_inv:
            ws = t + wp.start_delay
            d = day_start(ws)
            ok, bad_day, amount = inventory_ok(ctx, st, v, d)
            while not ok:
                d += DAY
                if d > ctx.limit_end:
                    return Infeasible(v.id, bid, "재고 제약", "ETB-09", f"{v.cargo_group} 재고 때문에 기간 안 작업 불가")
                ok, _, _ = inventory_ok(ctx, st, v, d)
            if d > day_start(ws):
                nt = d - wp.start_delay
                pushes.append(Push("ETB-09", t, nt, "INVENTORY",
                                   f"{v.cargo_group} {fmt(bad_day)[:5]} {'용량 초과' if v.direction == 'IMPORT' else '재고 부족'} {amount:,.0f} → 작업시작 {fmt(d)[:5]}로"))
                t = nt
        if t > ctx.limit_end:
            return Infeasible(v.id, bid, "기간 초과", "ETB-10", f"{fmt(ctx.limit_end)}까지 접안 불가")
        if t == t0:
            break
    else:  # pragma: no cover - 규칙이 서로 미는 경우를 막는 안전장치
        return Infeasible(v.id, bid, "수렴 실패", "ETB-10", "제약 검사가 끝나지 않음")
    if v.deadline is not None and t > v.deadline:
        return Infeasible(v.id, bid, "출하 마감 초과", "ETB-11", f"ETB {fmt(t)} > 마감 {fmt(v.deadline)}")
    return t, pushes, lb0


def place(ctx, vid: str, bid: str, st: SchedState):
    """선박 vid를 부두 bid의 '다음 순서'로 붙였을 때의 배정. 불가면 Infeasible."""
    v = ctx.vessels[vid]
    b = ctx.berths[bid]
    wp = ctx.work[(vid, bid)]
    res = _search(ctx, v, b, st, wp, True)
    if isinstance(res, Infeasible):
        return res
    t, pushes, lb0 = res
    p = make_placement(ctx, v, bid, t, "MOVABLE", pushes, lb0)
    if ctx.has_weather[bid] and any(x.reason == "WEATHER" for x in pushes):
        alt = _search(ctx, v, b, st, wp, False)
        if isinstance(alt, Infeasible):  # 기상 없이도 불가면 기상 탓으로 보지 않는다
            p.etb_nowx, p.pushes_nowx = t, pushes
        else:
            p.etb_nowx, p.pushes_nowx = min(alt[0], t), alt[1]
    else:
        p.etb_nowx, p.pushes_nowx = t, pushes
    return p
