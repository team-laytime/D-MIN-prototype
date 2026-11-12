"""팀 최종본 본체 식 (1)~(8)을 그대로 HiGHS(scipy.optimize.milp)에 넣는다. 식은 여기서 고치지 않는다 — 들어가는 값만 planner.py가 만든다.

    (1) min ΣΣ C[i,k]·z[i,k]
    (2) Σ_k z[i,k] = 1                      입항 건마다 작업계획 하나
    (3) z[i,k] + z[j,l] ≤ 1   ∀ F           충돌하는 작업계획은 같이 고르지 않는다
    (4) R[t+1] = R[t] + ΣΣ q·z − D[t]       재고 수지 (탱크 그룹마다 한 벌)
    (5) R[0] = R⁰
    (6) R_min ≤ R[t] ≤ R_max
    (7) z ∈ {0,1}
    (8) z[i,k_fix] = 1                      FIX 입항 건
    (+) Σ_{(i,k)∈S} z[i,k] ≤ |I| − 1        다음 스케줄 후보안을 낼 때만 더한다 (FR-42)

풀이 절차(식이 아니라 순서):
    1차 총 체선료 최소 → 2차 같은 금액 안에서 접안 시각의 합 최소 → 3차 작업계획 번호 → 고른 조합을 PPT 식으로 다시 계산·검사
    '일부러 기다리는 조합'(PPT 식으로 다시 계산한 ETB보다 늦게 댔고, 더 이른 작업계획으로 바꿔도 실행 가능한 것)은
    기본 설정에서 후보안으로 내지 않는다 — 접안 시각은 PPT 식이 정하고, 솔버는 부두 배정과 순서만 고른다.
"""
from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, vstack

from pptcalc import conflict, fmt
from planner import Model, place, signature, start_order, tank_violations, total_cents, verify


@dataclass
class Candidate:
    rank: int
    plans: list
    cents: int
    status: str                 # OPTIMAL · TIME_LIMIT
    solver_cents: int           # 솔버가 고른 조합의 금액 (GRID에서는 다시 계산하기 전 값)
    waits: list = field(default_factory=list)


@dataclass
class Outcome:
    candidates: list
    status: str                 # OK · INFEASIBLE
    notes: list
    size: dict
    seconds: float


class Body:
    def __init__(self, model: Model, form="auto"):
        self.model = model
        self.plans = model.all_plans
        self.col = {p.key: n for n, p in enumerate(self.plans)}
        self.nz = len(self.plans)
        self.rcol = []                                      # 탱크마다 R[0..T]의 열 번호
        n = self.nz
        for tank in model.tanks:
            self.rcol.append(list(range(n, n + len(tank["taus"]))))
            n += len(tank["taus"])
        self.n = n
        if form == "auto" or model.conflicts is None:
            form = "pairs" if (model.conflicts is not None and len(model.conflicts) <= 150000) else "cliques"
        self.form = form
        rows = self._rows()
        self.n_rows = len(rows)
        self.A, self.lo, self.hi = self._matrix(rows)

    # ---- 제약식 -------------------------------------------------------------------------
    def _rows(self):
        m, rows = self.model, []
        for aid, ps in m.plans.items():                                        # (2)
            rows.append(([self.col[p.key] for p in ps], [1.0] * len(ps), 1.0, 1.0))
        if self.form == "pairs":                                               # (3)
            for k1, k2, _ in m.conflicts:
                rows.append(([self.col[k1], self.col[k2]], [1.0, 1.0], -np.inf, 1.0))
        else:                                                                  # (3)과 같은 뜻: 같은 시각에 겹치는 계획을 한 줄로 묶는다
            for members in clique_rows(m):
                rows.append(([self.col[p.key] for p in members], [1.0] * len(members), -np.inf, 1.0))
        for tank, rc in zip(m.tanks, self.rcol):                               # (4) — R은 저장용량으로 나눈 값으로 넣는다(수치 안정)
            unit = 1.0 / max(1.0, tank["hi"])
            by_t = {}
            for key, q in tank["q"].items():
                for t, v in q.items():
                    by_t.setdefault(t, []).append((self.col[key], -v * unit))
            for t in range(len(tank["taus"]) - 1):
                cols, vals = [rc[t + 1], rc[t]], [1.0, -1.0]
                for c, v in by_t.get(t, ()):
                    cols.append(c)
                    vals.append(v)
                rows.append((cols, vals, -tank["d"][t] * unit, -tank["d"][t] * unit))
        return rows

    def _matrix(self, rows):
        ri, ci, va = [], [], []
        lo, hi = np.empty(len(rows)), np.empty(len(rows))
        for r, (cols, vals, l, h) in enumerate(rows):
            ri.extend([r] * len(cols))
            ci.extend(cols)
            va.extend(vals)
            lo[r], hi[r] = l, h
        return coo_matrix((va, (ri, ci)), shape=(len(rows), self.n)).tocsr(), lo, hi

    def bounds(self):
        lb, ub = np.zeros(self.n), np.ones(self.n)
        for f in self.model.fixed:                                             # (8)
            lb[self.col[f.key]] = 1.0
        for tank, rc in zip(self.model.tanks, self.rcol):
            unit = 1.0 / max(1.0, tank["hi"])
            lb[rc], ub[rc] = tank["lo"] * unit, tank["hi"] * unit              # (6)
            lb[rc[0]] = ub[rc[0]] = tank["r0"] * unit                          # (5)
        return lb, ub

    def run(self, cost, extra=(), time_limit=60.0):
        A, lo, hi = self.A, self.lo, self.hi
        if extra:
            B, lo2, hi2 = self._matrix(list(extra))
            A, lo, hi = vstack([A, B]).tocsr(), np.concatenate([lo, lo2]), np.concatenate([hi, hi2])
        integ = np.zeros(self.n)
        integ[:self.nz] = 1                                                    # (7)
        lb, ub = self.bounds()
        return milp(c=cost, constraints=LinearConstraint(A, lo, hi), integrality=integ, bounds=Bounds(lb, ub),
                    options={"time_limit": time_limit, "mip_rel_gap": 0.0, "disp": False})

    def chosen(self, x):
        return [p for p in self.plans if x[self.col[p.key]] > 0.5]

    def size(self):
        return {"variables": self.n, "z": self.nz, "R": self.n - self.nz, "rows": self.n_rows, "nonzeros": int(self.A.nnz), "form": self.form,
                "conflict_pairs": self.model.stats.get("conflicts")}


def _sweep(items, add):
    """items = [(시작, 끝, 계획)] — 어느 시각에든 동시에 걸쳐 있는 계획 묶음을 시작 시각마다 하나씩 낸다."""
    items = sorted(items, key=lambda x: x[0])
    live, heap, i, n = {}, [], 0, len(items)
    while i < n:
        theta = items[i][0]
        while heap and heap[0][0] <= theta:
            _, k = heapq.heappop(heap)
            live.pop(k, None)
        while i < n and items[i][0] == theta:
            s, e, p = items[i]
            if e > s:
                live[p.key] = p
                heapq.heappush(heap, (e, p.key))
            i += 1
        add(list(live.values()))


def clique_rows(model):
    """식 (3)의 충돌 쌍을 '같은 시각에 겹치는 작업계획 묶음'으로 모은다. 정수해 집합은 식 (3)과 같고 줄 수만 준다."""
    rules, case = model.rules, model.case
    plans = [p for p in model.all_plans if not p.fixed]       # FIX와 충돌하는 계획은 이미 없다
    out = []

    def add(members):
        if len({p.aid for p in members}) >= 2:
            out.append(members)

    by_berth = {}
    for p in plans:
        by_berth.setdefault(p.berth, []).append(p)
    for b, lst in by_berth.items():                                            # 같은 부두: [접안, 이안 + Switching)
        sw = rules.berths[b].switching
        _sweep([(p.s, p.u + sw, p) for p in lst], add)
    for bs in rules.cargo_sets:                                                # 동일 화물 그룹: [접안, 이안 − 2h)
        by_cargo = {}
        for p in plans:
            if p.berth in bs:
                by_cargo.setdefault(case.arrivals[p.aid].cargo, []).append(p)
        for lst in by_cargo.values():
            if len({p.berth for p in lst}) >= 2:
                _sweep([(p.s, p.u - rules.cargo_release, p) for p in lst], add)
    for bs, rel, exempt in rules.simul:                                        # 부두 동시 접안: 소형선끼리는 예외
        lst = [p for p in plans if p.berth in bs]
        if len({p.berth for p in lst}) < 2:
            continue
        small = {p.key for p in lst if exempt is not None and case.arrivals[p.aid].grt <= exempt}

        def add_simul(members):
            big = [p for p in members if p.key not in small]
            add(big)
            for aid in {p.aid for p in members if p.key in small}:
                add(big + [p for p in members if p.aid == aid and p.key in small])
        _sweep([(p.s, p.u - rel, p) for p in lst], add_simul)
    return out


def deliberate_waits(model, chosen):
    """'일부러 기다린' 입항 건을 찾는다 → [(고른 계획, 더 이른 계획)].

    앞서 접안한 계획들을 그대로 두고 PPT 식으로 다시 계산한 ETB보다 늦게 댔고, 그 사이의 더 이른 작업계획으로 바꿔도
    (충돌·재고 모두) 실행 가능하면 일부러 기다린 것이다. 재고 때문에 늦춘 것, 눈금 간격만큼 늦은 것은 여기에 들지 않는다.
    """
    rules, case, out = model.rules, model.case, []
    order = start_order(chosen)
    for idx, p in enumerate(order):
        f = place(rules, case, case.arrivals[p.aid], p.berth, order[:idx], model.fixed, model.cache)
        if f is None or f.s >= p.s:
            continue
        rest = [x for x in chosen if x.aid != p.aid]
        for q in model.plans[p.aid]:
            if q.berth != p.berth or q.s < f.s or q.s >= p.s:
                continue
            if all(conflict(rules, case, q, x) is None for x in rest) and not tank_violations(case, rest + [q]):
                out.append((p, q))
                break
    return out


def recompute(model, chosen):
    """P23: 고른 부두 배정과 순서를 PPT 식으로 처음부터 다시 계산한다. 눈금 간격 때문에 생긴 틈이 없어진다.

    다시 계산한 시각이 재고 범위를 벗어나게 하면 그 입항 건은 솔버가 고른 시각을 그대로 둔다(재고 대기).
    """
    rules, case = model.rules, model.case
    order = start_order(chosen)
    placed = []
    for idx, p in enumerate(order):
        f = place(rules, case, case.arrivals[p.aid], p.berth, placed, model.fixed, model.cache)
        if f is not None and f.s < p.s and not tank_violations(case, model.fixed + placed + [f] + order[idx + 1:]):
            placed.append(f)
        elif f is not None and f.s == p.s:
            placed.append(f)
        else:
            if f is not None:
                p.why = f"PPT 식으로는 {fmt(f.s)} ({f.why}) — 재고 때문에 {fmt(p.s)}까지 대기"
            placed.append(p)
    return model.fixed + placed


def solve(model: Model, top=3, wait_policy="PPT", time_limit=120.0, form="auto", max_rounds=None) -> Outcome:
    """스케줄 후보안을 총 체선료가 낮은 순으로 top개까지 낸다.

    wait_policy "PPT"  : 접안 시각은 PPT 식이 정한다 (기본)
                         EXACT — 일부러 기다리는 조합은 후보안으로 내지 않고 참고로만 남긴다
                         GRID  — 고른 부두 배정·순서를 PPT 식으로 다시 계산해 낸다 (눈금 간격만큼의 틈이 없어진다)
                "ALLOW": 솔버가 고른 조합을 그대로 낸다 (일부러 기다리는 조합 포함)
    다음 후보안 식 (+): EXACT는 '작업계획이 하나라도 다르게', GRID는 '부두 배정이 1척 이상 다르게'(FR-42).
    """
    t0 = time.time()
    notes = []
    if model.stats["no_plan"]:
        return Outcome([], "INFEASIBLE", [f"작업계획을 하나도 만들 수 없는 입항 건: {', '.join(model.stats['no_plan'])}"], {}, time.time() - t0)
    if model.stats.get("fixed_clash"):
        return Outcome([], "INFEASIBLE", [f"FIX·작업 중 입항 건끼리 겹친다: {', '.join(model.stats['fixed_clash'])}"], {}, time.time() - t0)
    grid = model.mode == "GRID"
    max_rounds = max_rounds or (top + 6 if grid else 300)
    body = Body(model, form)
    cost, early, order = np.zeros(body.n), np.zeros(body.n), np.zeros(body.n)
    for n, p in enumerate(body.plans):
        cost[body.col[p.key]] = p.cents / 100.0
        early[body.col[p.key]] = (p.s - model.case.start) / 60.0
        order[body.col[p.key]] = n / max(1, body.nz)
    n_arr = len(model.plans)
    zs = list(range(body.nz))
    cuts, cands, skipped, seen, rounds = [], [], [], set(), 0
    limited, gaps = False, []
    while len(cands) < top and rounds < max_rounds:
        rounds += 1
        r1 = body.run(cost, cuts, time_limit)                                   # 1차: 총 체선료
        if r1.x is None:
            break
        if r1.status != 0:
            limited = True
            gaps.append(float(getattr(r1, "mip_gap", 0.0) or 0.0))
        x = r1.x
        cap = [(zs, list(cost[:body.nz]), -np.inf, float(r1.fun) + 0.004)]
        r2 = body.run(early, cuts + cap, time_limit)                            # 2차: 같은 금액 안에서 일찍 대는 쪽
        if r2.x is not None:
            x = r2.x
            if not grid:
                cap.append((zs, list(early[:body.nz]), -np.inf, float(r2.fun) + 1e-6))
                r3 = body.run(order, cuts + cap, time_limit)                    # 3차: 그래도 같으면 작업계획 번호가 앞선 쪽 (같은 입력 → 같은 순위)
                if r3.x is not None:
                    x = r3.x
        chosen = body.chosen(x)
        bad = verify(model.rules, model.case, chosen)                           # 솔버 결과를 그대로 믿지 않는다
        if bad:
            raise RuntimeError("솔버가 낸 조합이 규칙을 어김: " + "; ".join(bad[:3]))
        cents = total_cents(chosen)
        if grid:                                                                # (+) 부두 배정이 1척 이상 다르게
            mine = {p.aid: p.berth for p in chosen}
            cuts.append(([body.col[p.key] for p in body.plans if mine.get(p.aid) == p.berth], [1.0] * sum(1 for p in body.plans if mine.get(p.aid) == p.berth),
                         -np.inf, n_arr - 1.0))
        else:                                                                   # (+) 작업계획이 하나라도 다르게
            cuts.append(([body.col[p.key] for p in chosen], [1.0] * len(chosen), -np.inf, n_arr - 1.0))
        waits = deliberate_waits(model, chosen) if not grid else []
        if wait_policy == "PPT":
            if grid:
                final = recompute(model, chosen)
                bad = verify(model.rules, model.case, final)
                if bad:
                    raise RuntimeError("다시 계산한 일정이 규칙을 어김: " + "; ".join(bad[:3]))
                if total_cents(final) > cents:
                    skipped.append((cents, chosen, []))
            else:
                if waits:
                    skipped.append((cents, chosen, waits))
                    continue
                final = chosen
        else:
            final = chosen
        sig = signature(final)
        if sig in seen:
            continue
        seen.add(sig)
        cands.append(Candidate(0, sorted(final, key=lambda p: (model.rules.berth_order.index(p.berth), p.s)), total_cents(final),
                               "OPTIMAL" if r1.status == 0 else "TIME_LIMIT", cents, waits))
    cands.sort(key=lambda c: (c.cents, sum(p.s for p in c.plans)))
    for n, c in enumerate(cands):
        c.rank = n + 1
    cheaper = [k for k in skipped if not cands or k[0] < cands[0].cents]
    if cheaper:
        cents, chosen, waits = min(cheaper, key=lambda k: k[0])
        text = ", ".join(f"{p.aid}를 {fmt(q.s)} 대신 {fmt(p.s)}에" for p, q in waits) if waits else "PPT 식의 ETB보다 늦게 대는 배가 있음"
        notes.append(f"참고: 일부러 기다리면 총액이 ${cents / 100:,.2f}까지 내려가는 조합이 있다 ({text}). PPT 식의 접안 시각이 아니어서 후보안에는 넣지 않았다.")
    if limited:
        notes.append(f"제한시간 안에 최적임을 증명하지 못한 풀이가 있다 (최적성 갭 최대 {max(gaps):.2%}) → 그때까지의 최선안이다 (NFR-09).")
    size = {**body.size(), "rounds": rounds, "skipped_waits": len(skipped), "mode": model.mode}
    if not cands:
        return Outcome([], "INFEASIBLE", notes + ["식 (2)(3)(6)(8)을 모두 지키는 조합이 없다 → '실행 가능한 후보 없음' (FR-43)"], size, time.time() - t0)
    return Outcome(cands, "OK", notes, size, time.time() - t0)


def exhaustive(model: Model, top=3, limit=3_000_000):
    """작업계획의 모든 조합을 하나씩 해 본다 (작은 문제에서 솔버의 답을 검산). ([(금액, 일정)], 조합 수)"""
    import itertools
    if model.conflicts is None:
        return None
    groups = list(model.plans.values())
    n = 1
    for g in groups:
        n *= len(g)
    if n > limit:
        return None
    bad = {(a, b) for a, b, _ in model.conflicts} | {(b, a) for a, b, _ in model.conflicts}
    found = []
    for combo in itertools.product(*groups):
        keys = [p.key for p in combo]
        if any((keys[i], keys[j]) in bad for i in range(len(keys)) for j in range(i + 1, len(keys))):
            continue
        if tank_violations(model.case, list(combo)):
            continue
        found.append((total_cents(combo), sum(p.s for p in combo), signature(combo), list(combo)))
    found.sort(key=lambda x: x[:3])
    return [(c, plans) for c, _, _, plans in found[:top]], n
