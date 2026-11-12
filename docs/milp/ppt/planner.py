"""작업계획 만들기 (P20~P23) — 팀 최종본 본체 식 (1)~(8)에 넣을 값 Ω · F · C · q를 PPT 계산식으로 만든다.

    P20  작업계획 집합 Ω    입항 건 × 배정 가능 부두 × 접안 시각. 접안 시각은 PPT 식(P2~P7)을 지키는 값만 쓴다          generate()
    P21  충돌 쌍 F          같은 부두(Switching) · 동일 화물 그룹 · 부두 동시 접안(이안 − 2h) · FIX 보호              conflicts()
    P22  구간별 물량 q · D   하역은 +, 선적은 −, 공정 소비는 D                                                      tank_rows()
    P23  재계산 검사         고른 조합을 PPT 식으로 처음부터 다시 계산한다 (06쪽 '모든 조건 재확인')                    forward() · verify()

접안 시각을 만드는 방법은 둘이고, 식은 같다.
    EXACT  PPT 식이 낼 수 있는 값을 전부 만든다 (도착 기준, 다른 계획 뒤, 금지 구간 끝). 작은 문제에서 정확하다.
    GRID   금지 구간을 피한 시각을 Δ 간격으로 만든다 (기본 30분). 큰 문제용. 고른 뒤 PPT 식으로 다시 계산해 Δ만큼의 틈을 없앤다.

검산 도구:
    forward()      부두 배정과 순서를 주면 PPT 식대로 시각을 계산한다 (06쪽의 '시뮬레이션')
    brute_force()  부두 배정 × 순서를 전부 해 본다 (작은 문제의 정답)
    baseline()     기준안 = ETA 순서, 가장 이른 부두 (FR-41)
    verify()       일정 하나가 모든 규칙을 지키는지 다시 본다 (솔버 결과를 믿지 않기 위한 검사)
"""
from __future__ import annotations

import bisect
import itertools
from collections import deque
from dataclasses import dataclass, field

from pptcalc import (Case, Plan, Rules, conflict, eligible, eligible_berths, fmt, make_plan, merge, night_windows, phi, relation,
                     release_after, restriction_windows, stay_minutes, tau0)

INFLOW = {"IM": 1, "DI": 1, "EX": -1, "DO": -1}        # 하역(탱크로 들어감) +1 · 선적(탱크에서 나감) −1


@dataclass
class Model:
    """본체 식 (1)~(8)에 넣는 값"""
    case: Case
    rules: Rules
    plans: dict                     # 입항 건 → [Plan]      = Ω[i]
    conflicts: list | None          # [(key, key, 이유)]    = F  (너무 많으면 None — 솔버에는 묶음 식으로 넣는다)
    tanks: list                     # [{group, taus, q{key: {t: 물량}}, d[..], r0, lo, hi}]   = 식 (4)(5)(6)
    fixed: list                     # FIX·작업 중 입항 건의 작업계획 (식 (8))
    elig: dict
    excluded: dict                  # 입항 건 → {부두: [사유]}
    mode: str = "EXACT"
    stats: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)

    @property
    def all_plans(self):
        return [p for ps in self.plans.values() for p in ps]


# ----------------------------------------------------------------------------- 공통
def windows_of(rules, case, a, bid, cache):
    key = (a.id, bid)
    if key not in cache:
        cache[key] = merge(night_windows(rules, case, a) + restriction_windows(rules, case, a, bid, stay_minutes(rules, a, bid))
                           + [(-10 ** 9, case.start, "계획 시작 전")])
    return cache[key]


def fixed_plans(rules, case):
    """FIX 선박과 작업 중 선박은 부두와 시각이 입력값 그대로다 (PPT 06쪽 'FIX 선박은 자동 산출 대상에서 제외', FR-17·18)"""
    out = []
    for a in case.arrivals.values():
        if not a.movable:
            out.append(make_plan(rules, case, a, a.fix["berth"], a.fix["etb"], why="FIX (입력값)" if a.status == "FIX" else "작업 중 (입력값)", fixed=True))
    return out


def why_text(base, tag):
    return f"{base} → {tag}이라 그 끝으로" if tag else base


def link_text(p, kind):
    return f"{p.aid} 이안 + Switching" if kind == "같은 부두" else f"{p.aid} 이안 − 2h ({kind})"


def place(rules, case, a, bid, placed, fixed, cache):
    """입항 건 a를 부두 bid에 '이미 놓인 계획들 뒤'로 놓는다 — PPT 06~08쪽의 ETB 산정 그대로.

    ETB = 모든 제약을 함께 만족하는 가장 이른 시각. 놓을 수 없으면 None.
    """
    win = windows_of(rules, case, a, bid, cache)
    tau, base = tau0(rules, a, bid), "ETA + Direction"
    for p in placed:
        r = release_after(rules, case, p, a, bid)
        if r is not None and r[0] > tau:
            tau, base = r[0], link_text(p, r[1])
    for _ in range(len(fixed) + 2):
        s, tag = phi(win, tau)
        plan = make_plan(rules, case, a, bid, s, why=why_text(base, tag))
        hit = [f for f in fixed if conflict(rules, case, plan, f)]
        if not hit:
            return plan if plan.u <= case.end else None
        nxt = max(release_after(rules, case, f, a, bid)[0] for f in hit)      # FIX 앞에 못 끼면 그 뒤로 (PPT 07쪽 '접안불가')
        if nxt <= tau:
            return None
        tau, base = nxt, "FIX 선박 뒤"
    return None


def forward(rules, case, assign, order, cache=None):
    """P23 · PPT 06쪽: 부두 배정(assign)과 순서(order)를 주면 식대로 시각이 따라 나온다. 불가하면 None."""
    cache = {} if cache is None else cache
    fixed = fixed_plans(rules, case)
    placed = []
    for aid in order:
        plan = place(rules, case, case.arrivals[aid], assign[aid], placed, fixed, cache)
        if plan is None:
            return None
        placed.append(plan)
    return fixed + placed


def movable_ids(case):
    return [a.id for a in case.arrivals.values() if a.movable]


def start_order(plans):
    return sorted((p for p in plans if not p.fixed), key=lambda p: (p.s, p.aid))


def baseline(rules, case):
    """기준안 (FR-41): ETA 순서로, 그때 가장 이르게 댈 수 있는 부두에 놓는다."""
    cache, fixed, placed = {}, fixed_plans(rules, case), []
    for a in sorted((case.arrivals[i] for i in movable_ids(case)), key=lambda x: (x.eta, x.id)):
        best = None
        for n, bid in enumerate(eligible_berths(rules, a)):
            plan = place(rules, case, a, bid, placed, fixed, cache)
            if plan is not None and (best is None or (plan.s, plan.cents, n) < best[0]):
                best = ((plan.s, plan.cents, n), plan)
        if best is None:
            return None
        placed.append(best[1])
    return fixed + placed


# ----------------------------------------------------------------------------- P22 재고
def flow_of(case, plan):
    """작업계획이 탱크에 넣는(+)·빼는(−) 시간당 물량과 구간 [작업시작, 작업완료)"""
    a = case.arrivals[plan.aid]
    dur = plan.c - plan.a
    return (INFLOW[a.biz] * a.qty / dur * 60 if dur > 0 else 0.0), plan.a, plan.c


def tank_profile(case, tank, plans):
    """재고 궤적 [(시각, 재고)] — 평가 시점은 계획 시작·종료, 작업시작·완료, 소비속도가 바뀌는 시각"""
    mine = [flow_of(case, p) for p in plans if case.arrivals[p.aid].cargo == tank.group]
    pts = sorted({case.start, case.end} | {t for _, a0, c0 in mine for t in (a0, c0) if case.start < t < case.end}
                 | {t for f0, f1, _ in tank.flows for t in (f0, f1) if case.start < t < case.end})
    level = tank.opening                                   # 계획 시작 전의 하역·소비는 처음 재고 R⁰에 이미 들어 있다 (식 (5))
    out = [(pts[0], level)]
    for t0, t1 in zip(pts, pts[1:]):
        level += sum(rate * max(0, min(c0, t1) - max(a0, t0)) / 60 for rate, a0, c0 in mine)
        level -= sum(use * max(0, min(f1, t1) - max(f0, t0)) / 60 for f0, f1, use in tank.flows)
        out.append((t1, level))
    return out


def tank_violations(case, plans, eps=1e-6):
    out = []
    for tank in case.tanks:
        for t, level in tank_profile(case, tank, plans):
            if level > tank.maximum + eps:
                out.append(f"{tank.group} 재고 {level:,.0f} > 저장용량 {tank.maximum:,.0f} ({fmt(t)})")
                break
            if level < tank.minimum - eps:
                out.append(f"{tank.group} 재고 {level:,.0f} < 최소 허용 재고 {tank.minimum:,.0f} ({fmt(t)})")
                break
    return out


# ----------------------------------------------------------------------------- P20 작업계획 집합 Ω
def generate(rules, case, mode="auto", grid_min=None, cap=1500):
    """P20: 입항 건마다 고를 수 있는 작업계획을 만든다.

    mode "EXACT": PPT 식이 낼 수 있는 접안 시각을 전부 만든다.
         "GRID" : 금지 구간을 피한 시각을 grid_min분 간격으로 만든다.
         "auto" : EXACT로 만들다가 계획이 cap개를 넘으면 GRID로 바꾼다.
    """
    mode = case.options.get("generation", mode)
    grid_min = grid_min or int(case.options.get("grid_min", 30))
    arr = case.arrivals
    mov = [arr[i] for i in movable_ids(case)]
    fixed = fixed_plans(rules, case)
    elig, excluded = {}, {}
    for a in mov:
        elig[a.id] = eligible_berths(rules, a)
        excluded[a.id] = {bid: eligible(rules, a, bid)[1] for bid in (a.berths or rules.berth_order)
                          if bid not in elig[a.id] and a.cargo in rules.berths[bid].groups}
    cache = {}
    plans, used = None, "GRID"
    if mode in ("auto", "EXACT"):
        plans = _closure(rules, case, mov, fixed, elig, cache, cap if mode == "auto" else 10 ** 9)
        used = "EXACT"
    if plans is None:
        plans = _grid(rules, case, mov, fixed, elig, cache, grid_min)
        used = "GRID"
    by = {a.id: sorted((p for p in plans.values() if p.aid == a.id), key=lambda p: (rules.berth_order.index(p.berth), p.s)) for a in mov}
    for f in fixed:
        by[f.aid] = [f]
    model = Model(case, rules, by, [], [], fixed, elig, excluded, used, cache=cache)
    model.stats = {"mode": used, "grid_min": grid_min if used == "GRID" else None, "arrivals": len(arr), "movable": len(mov),
                   "plans": sum(len(v) for v in by.values()), "no_plan": [a.id for a in mov if not by[a.id]]}
    model.conflicts = conflicts(rules, case, model)
    model.tanks = tank_rows(case, model)
    return model


def _closure(rules, case, mov, fixed, elig, cache, cap):
    """EXACT: 한 척의 접안 시각은 '무엇 뒤에 서느냐'로 정해진다.

      ① 아무도 없을 때: ETA + Direction (P2)
      ② 같은 부두의 다른 작업계획 뒤: 그 이안 + Switching (P3)
      ③ 동시 접안이 금지된 다른 부두의 작업계획 뒤: 그 이안 − 2h (P6)
    를 출발점으로 삼고, 야간 도선·부두 제약 구간이면 그 끝으로 민다 (P4·P5·P7). 새 계획이 생기면 그 뒤에 서는 계획을 또 만든다.
    재고 제약이 걸린 화물은 '탱크에 자리가 날 때까지 기다렸다 대는' 계획을 일정 간격으로 더 만든다 (PPT에 식이 없는 부분).
    """
    plans, anc, dead = {}, {}, set()
    queue = deque()

    def push(a, bid, tau, base, ancestors):
        t0 = tau0(rules, a, bid)
        if tau < t0:
            tau, base = t0, "ETA + Direction"
        s, tag = phi(windows_of(rules, case, a, bid, cache), tau)
        key = (a.id, bid, s)
        if key in dead:
            return
        if key in plans:
            new = anc[key] & ancestors                 # 이 계획에 닿는 모든 길에 공통으로 든 입항 건만 '앞선 것'으로 본다
            if new != anc[key]:
                anc[key] = new
                queue.append(plans[key])
            return
        plan = make_plan(rules, case, a, bid, s, why=why_text(base, tag))
        if plan.u > case.end or any(conflict(rules, case, plan, f) for f in fixed):
            dead.add(key)                              # 계획기간을 넘거나 FIX 선박을 침범 → 만들지 않는다
            return
        plans[key], anc[key] = plan, ancestors
        queue.append(plan)

    for a in mov:
        for bid in elig[a.id]:
            push(a, bid, tau0(rules, a, bid), "ETA + Direction", frozenset())
    step, limit = int(case.options.get("inventory_wait_step_h", 2) * 60), int(case.options.get("inventory_wait_max_h", 48) * 60)
    tank_groups = {t.group for t in case.tanks}
    for a in mov:
        if a.cargo in tank_groups and step > 0:
            for bid in elig[a.id]:
                for k in range(step, limit + 1, step):
                    push(a, bid, tau0(rules, a, bid) + k, f"재고 대기 +{k // 60}h", frozenset())
    for f in fixed:
        queue.append(f)
    while queue:
        if len(plans) > cap:
            return None
        p = queue.popleft()
        before = anc.get(p.key, frozenset()) | {p.aid}
        for a in mov:
            if a.id in before:
                continue
            for bid in elig[a.id]:
                r = release_after(rules, case, p, a, bid)
                if r is not None:
                    push(a, bid, r[0], link_text(p, r[1]), before)
    return plans


def _grid(rules, case, mov, fixed, elig, cache, grid_min):
    """GRID: 가장 이른 시각(ETA + Direction)부터 grid_min분 간격. 금지 구간 안의 눈금은 구간 끝(08시, 제약 종료 + Direction)으로 간다."""
    plans = {}
    max_wait = case.options.get("max_wait_h")
    for a in mov:
        for bid in elig[a.id]:
            win = windows_of(rules, case, a, bid, cache)
            t0 = tau0(rules, a, bid)
            first = phi(win, t0)[0]                        # 가장 이른 접안 가능 시각 (계획 시작·야간·부두 제약을 피한 뒤)
            last = case.end - stay_minutes(rules, a, bid)
            if max_wait is not None:
                last = min(last, first + int(max_wait * 60))
            taus = [(t0, "ETA + Direction")]
            g = (t0 // grid_min + 1) * grid_min
            while g <= last:
                taus.append((g, "눈금"))
                g += grid_min
            for f in fixed:                                # FIX 선박 바로 뒤는 눈금이 아니어도 넣는다
                r = release_after(rules, case, f, a, bid)
                if r is not None and r[0] > t0:
                    taus.append((r[0], "FIX 선박 뒤"))
            for tau, base in taus:
                s, tag = phi(win, tau)
                key = (a.id, bid, s)
                if key in plans or s > last:
                    continue
                plan = make_plan(rules, case, a, bid, s, why=why_text(base, tag))
                if plan.u <= case.end and not any(conflict(rules, case, plan, f) for f in fixed):
                    plans[key] = plan
    return plans


# ----------------------------------------------------------------------------- P21 충돌 쌍 F
def conflicts(rules, case, model, cap=400000, scan=6000):
    """P21: 서로 다른 입항 건의 두 작업계획이 같이 설 수 없으면 F에 넣는다 (팀 최종본 식 (18)의 자리).

    FIX·작업 중 계획과 충돌하는 계획은 generate()가 이미 만들지 않았으므로, 여기서는 움직일 수 있는 계획끼리만 본다.
    계획이 scan개를 넘거나 쌍이 cap개를 넘으면 목록을 만들지 않는다(None). 그때 솔버에는 '겹치는 계획 묶음'으로 넣는다.
    """
    model.stats["fixed_clash"] = [f"{p.aid}·{q.aid}" for p, q in itertools.combinations(model.fixed, 2) if conflict(rules, case, p, q)]
    if model.stats["plans"] > scan:
        model.stats["conflicts"] = None
        return None
    by_berth = {}
    for p in model.all_plans:
        if not p.fixed:
            by_berth.setdefault(p.berth, []).append(p)
    for lst in by_berth.values():
        lst.sort(key=lambda p: p.s)
    out, count = [], 0
    arr = case.arrivals
    for b, lst in by_berth.items():                           # 같은 부두: 접안 ~ 이안 + Switching이 겹치면 충돌
        sw = rules.berths[b].switching
        starts = [p.s for p in lst]
        for i, p in enumerate(lst):
            for q in lst[i + 1:bisect.bisect_left(starts, p.u + sw)]:
                if q.aid != p.aid:
                    count += 1
                    if count <= cap:
                        out.append((p.key, q.key, "같은 부두") if p.key < q.key else (q.key, p.key, "같은 부두"))
    linked = [(bs, rules.cargo_release) for bs in rules.cargo_sets] + [(bs, rel) for bs, rel, _ in rules.simul]
    rel_cache = {}
    for bs, rel in linked:                                    # 묶인 부두: 접안 ~ 이안 − 2h가 겹치면 충돌
        bl = sorted(b for b in bs if b in by_berth)
        for x, b1 in enumerate(bl):
            for b2 in bl[x + 1:]:
                l2 = by_berth[b2]
                s2 = [q.s for q in l2]
                for p in by_berth[b1]:
                    for q in l2[:bisect.bisect_left(s2, p.u - rel)]:
                        if q.aid == p.aid or p.s >= q.u - rel:
                            continue
                        k = (p.aid, b1, q.aid, b2)
                        if k not in rel_cache:
                            rel_cache[k] = relation(rules, arr[p.aid], b1, arr[q.aid], b2)
                        if rel_cache[k] is not None:
                            count += 1
                            if count <= cap:
                                out.append((p.key, q.key, rel_cache[k][0]) if p.key < q.key else (q.key, p.key, rel_cache[k][0]))
    model.stats["conflicts"] = count
    return out if count <= cap else None


def tank_rows(case, model):
    """P22: 식 (4)(5)(6)에 넣는 값 — 평가 시점 τ, 구간별 물량 q[i,k,t], 공정 소비 D[t]."""
    out = []
    for tank in case.tanks:
        mine = [(p, *flow_of(case, p)) for p in model.all_plans if case.arrivals[p.aid].cargo == tank.group]
        taus = sorted({case.start, case.end} | {t for _, _, a0, c0 in mine for t in (a0, c0) if case.start < t < case.end}
                      | {t for f0, f1, _ in tank.flows for t in (f0, f1) if case.start < t < case.end})
        q = {}
        for p, rate, a0, c0 in mine:
            i0, i1 = bisect.bisect_right(taus, a0) - 1, bisect.bisect_left(taus, c0)
            row = {}
            for t in range(max(0, i0), min(len(taus) - 1, i1)):
                v = rate * max(0, min(c0, taus[t + 1]) - max(a0, taus[t])) / 60
                if v:
                    row[t] = v
            q[p.key] = row
        d = [sum(use * max(0, min(f1, t1) - max(f0, t0)) / 60 for f0, f1, use in tank.flows) for t0, t1 in zip(taus, taus[1:])]
        out.append({"group": tank.group, "taus": taus, "q": q, "d": d, "r0": tank.opening, "lo": tank.minimum, "hi": tank.maximum})
    return out


# ----------------------------------------------------------------------------- 검산 도구
def verify(rules, case, plans):
    """일정 하나(입항 건마다 작업계획 하나)가 PPT 규칙을 모두 지키는지 다시 계산해 본다. 위반 목록을 돌려준다."""
    bad = []
    cache = {}
    got = {p.aid: p for p in plans}
    for a in case.arrivals.values():
        p = got.get(a.id)
        if p is None:
            bad.append(f"{a.id}: 작업계획 없음")
            continue
        if a.movable:
            ok, why = eligible(rules, a, p.berth)
            if not ok:
                bad.append(f"{a.id}: {p.berth} 배정 불가 — {'; '.join(why)}")
            if p.s < tau0(rules, a, p.berth):
                bad.append(f"{a.id}: ETB {fmt(p.s)} < ETA + Direction")
            s2, tag = phi(windows_of(rules, case, a, p.berth, cache), p.s)
            if s2 != p.s:
                bad.append(f"{a.id}: ETB {fmt(p.s)}가 금지 구간 안 ({tag})")
            if p.u > case.end:
                bad.append(f"{a.id}: 이안 {fmt(p.u)}이 계획 종료 뒤")
        again = make_plan(rules, case, a, p.berth, p.s, fixed=not a.movable)
        if (again.a, again.c, again.h, again.u, again.lay_start, again.cents) != (p.a, p.c, p.h, p.u, p.lay_start, p.cents):
            bad.append(f"{a.id}: 다시 계산한 값과 다름")
    for p, q in itertools.combinations(plans, 2):
        why = conflict(rules, case, p, q)
        if why:
            bad.append(f"{p.aid}·{q.aid}: {why} 충돌")
    return bad + tank_violations(case, plans)


def total_cents(plans):
    return sum(p.cents for p in plans)


def signature(plans):
    return tuple(sorted(p.key for p in plans))


def brute_force(rules, case, top=3, limit=400000):
    """작은 문제의 정답: 부두 배정 × 순서를 전부 PPT 식으로 계산한다. (금액, 접안 시각 합, 일정) 상위 top개 — 서로 다른 일정만."""
    ids = movable_ids(case)
    elig = [eligible_berths(rules, case.arrivals[i]) for i in ids]
    cache, best, count = {}, {}, 0
    for berths in itertools.product(*elig):
        assign = dict(zip(ids, berths))
        for order in itertools.permutations(ids):
            count += 1
            if count > limit:
                raise RuntimeError("전수 탐색 한도 초과")
            plans = forward(rules, case, assign, order, cache)
            if plans is None or tank_violations(case, plans):
                continue
            sig = signature(plans)
            if sig not in best:
                best[sig] = (total_cents(plans), sum(p.s for p in plans), plans)
    ranked = sorted(best.values(), key=lambda x: (x[0], x[1], signature(x[2])))
    return ranked[:top], count
