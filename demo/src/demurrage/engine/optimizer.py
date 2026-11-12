"""접안 순서·부두 배정 후보 생성 (FR-34 기준안, FR-35 후보 최대 3개, FR-36 후보 없음, NFR-08 제한시간·최적성 갭).

문제: 이동 가능 선박마다 (부두, 그 부두에서의 순서)를 정해 총 예상 체선료 Σ_i 체선료_i 를 최소화.
      시각은 정하지 않는다 — 순서·부두가 정해지면 ETB 엔진(etb.place)이 '가장 이른 가능 시각'을 정한다.

방법 (트레이드오프는 docs/adr/ADR-004 참고):
  1) 기준안(FCFS)과 지역 탐색으로 좋은 해를 빨리 하나 얻는다(상한).
  2) 분기한정 탐색(Branch & Bound): 'ETB가 늦어지지 않는 순서'로 한 척씩 붙여 나간다.
     · 그 순서로만 붙여도 가능한 모든 일정을 빠짐없이 만든다(증명 요지는 docs/05-optimization.md §4).
     · 하한 = 지금까지 금액 + 남은 선박마다 '가장 빨리 붙었을 때'의 체선료 하한(lower_bound_cents)
     · 하한 ≥ 지금까지 찾은 3번째 후보 금액이면 그 가지는 버린다.
  3) 제한시간 안에 끝나면 1안은 '최적 증명', 못 끝나면 '최선 탐색 결과'와 갭(= (1안 − 하한) ÷ 1안)을 낸다.
  4) 모든 후보는 독립 검증기(validator)를 통과해야 후보로 남는다.
"""
from __future__ import annotations

import itertools
import random
import time
from dataclasses import dataclass, field

from ..domain.model import Infeasible
from .etb import place
from .laytime import amount_cents, lower_bound_cents
from .schedule import Schedule, decode, evaluate, fcfs, initial_state
from .validator import validate


@dataclass
class SearchResult:
    baseline: Schedule
    candidates: list
    status: str                 # OPTIMAL / BEST_FOUND / NO_IMPROVEMENT / NO_FEASIBLE
    proven_optimal: bool
    lower_bound_cents: int
    gap: float
    stats: dict = field(default_factory=dict)
    rejected: list = field(default_factory=list)


class TopK:
    """금액이 낮은 서로 다른 일정 K개(부두별 순서가 1척이라도 다르면 다른 일정)."""

    def __init__(self, k: int):
        self.k = k
        self.items = []  # (cost, signature, plan)

    def threshold(self):
        return self.items[-1][0] if len(self.items) >= self.k else float("inf")

    def offer(self, cost: int, sig: tuple, plan: list) -> bool:
        for i, (c, s, _) in enumerate(self.items):
            if s == sig:
                if cost < c:
                    self.items[i] = (cost, sig, plan)
                    self.items.sort(key=lambda x: (x[0], x[1]))
                    return True
                return False
        if len(self.items) < self.k or cost < self.threshold():
            self.items.append((cost, sig, plan))
            self.items.sort(key=lambda x: (x[0], x[1]))
            del self.items[self.k:]
            return True
        return False


def _signature(st) -> tuple:
    per = {}
    for vid, p in sorted(st.pl.items(), key=lambda kv: (kv[1].etb, kv[0])):
        if p.kind == "MOVABLE":
            per.setdefault(p.berth, []).append(vid)
    return tuple(sorted((b, tuple(vs)) for b, vs in per.items()))


def _plan_cost(ctx, plan, base):
    st, bad = decode(ctx, plan, base=base)
    if bad:
        return None, st
    return sum(amount_cents(ctx, ctx.vessels[vid], p) for vid, p in st.pl.items()), st


def local_search(ctx, plan, base, deadline: float, top: "TopK" = None):
    """최초 개선 지역 탐색: 부두 바꾸기 → 앞뒤 맞바꾸기 → 끼워 넣기. 결정론(같은 입력이면 같은 결과)."""
    best_cost, best_st = _plan_cost(ctx, plan, base)
    if best_cost is None:
        return None, None, None
    best = list(plan)
    improved = True
    evals = 0
    while improved and time.perf_counter() < deadline:
        improved = False
        n = len(best)
        moves = []
        for i, (vid, bid) in enumerate(best):
            for nb in ctx.eligible[vid]:
                if nb != bid:
                    moves.append(("berth", i, nb))
        for i in range(n):
            for j in range(i + 1, n):
                moves.append(("swap", i, j))
        for i in range(n):
            for j in range(n):
                if abs(i - j) > 1:
                    moves.append(("move", i, j))
        for kind, a, b in moves:
            if time.perf_counter() > deadline:
                break
            cand = list(best)
            if kind == "berth":
                cand[a] = (cand[a][0], b)
            elif kind == "swap":
                cand[a], cand[b] = cand[b], cand[a]
            else:
                item = cand.pop(a)
                cand.insert(b, item)
            evals += 1
            c, st = _plan_cost(ctx, cand, base)
            if c is not None and top is not None:
                top.offer(c, _signature(st), cand)
            if c is not None and c < best_cost:
                best, best_cost, best_st = cand, c, st
                improved = True
                break
    return best, best_cost, {"evals": evals}


def iterated_local_search(ctx, plan, cost, base, deadline: float, top: "TopK", seed: int):
    """반복 지역 탐색: 지금 해를 조금 흔들고(부두 바꾸기·맞바꾸기 2~3번) 다시 지역 탐색. 시드를 고정해 재현 가능."""
    rng = random.Random(seed)
    best, best_cost = list(plan), cost
    rounds = 0
    while time.perf_counter() < deadline:
        rounds += 1
        cand = list(best)
        for _ in range(rng.choice([2, 3])):
            i = rng.randrange(len(cand))
            if rng.random() < 0.5 and len(ctx.eligible[cand[i][0]]) > 1:
                cand[i] = (cand[i][0], rng.choice([b for b in ctx.eligible[cand[i][0]] if b != cand[i][1]]))
            else:
                j = rng.randrange(len(cand))
                cand[i], cand[j] = cand[j], cand[i]
        p2, c2, _ = local_search(ctx, cand, base, deadline, top)
        if p2 is not None and c2 < best_cost:
            best, best_cost = p2, c2
    return best, best_cost, {"rounds": rounds}


def branch_and_bound(ctx, base, top: TopK, deadline: float, node_limit: int):
    """ETB가 줄지 않는 순서로 한 척씩 붙이는 깊이 우선 분기한정 탐색."""
    remaining0 = frozenset(ctx.movable)
    nodes = 0
    pruned = 0
    timed_out = False
    # 스택 원소: (상태, 남은 선박, 지금까지 금액, 마지막 ETB, 계획, 자식 목록, 다음 자식 위치)
    stack = []

    def children(st, remaining, cost_so_far, last_t):
        opts = {}
        for vid in remaining:
            lst = []
            for bid in ctx.eligible[vid]:
                p = place(ctx, vid, bid, st)
                if isinstance(p, Infeasible):
                    continue
                lst.append((bid, p))
            if not lst:
                return None  # 이 선박은 어디에도 못 붙음 → 막힌 가지
            opts[vid] = lst
        kids = []
        for vid, lst in opts.items():
            for bid, p in lst:
                if p.etb < last_t:
                    continue
                c = amount_cents(ctx, ctx.vessels[vid], p)
                rest = 0
                for rv, rl in opts.items():
                    if rv == vid:
                        continue
                    rest += min(lower_bound_cents(ctx, ctx.vessels[rv], rb, max(rp.etb, p.etb)) for rb, rp in rl)
                kids.append((cost_so_far + c + rest, p.etb, vid, bid, p, c))
        kids.sort(key=lambda k: (k[0], k[1], k[2], k[3]))
        return kids

    has_inv = bool(ctx.sc.inventory)
    memo = {}
    merged = 0

    def state_key(st, last_t):
        """앞으로의 배정에 영향을 주는 것만 모은 상태 열쇠 — 열쇠가 같으면 남은 선박의 가능한 미래가 같다."""
        live = tuple(sorted((p.berth, p.vid, p.etb) for p in st.pl.values() if p.kind == "MOVABLE" and p.excl_end > last_t))
        lastmov = tuple(sorted((b, p.vid, p.etu) for b, p in st.last_mov.items() if p is not None))
        placed = frozenset(v for v, p in st.pl.items() if p.kind == "MOVABLE")
        inv = tuple(sorted((g, tuple(sorted(d.items()))) for g, d in st.inv.items())) if has_inv else ()
        return (placed, lastmov, live, last_t, inv)

    # 고정(FIX·작업 중) 선박의 체선료는 어느 후보에서나 같다 → 시작 금액으로 더해 둔다
    const = sum(amount_cents(ctx, ctx.vessels[vid], p) for vid, p in base.pl.items())
    root_kids = children(base, remaining0, const, -10 ** 12)
    if root_kids is None:
        return {"nodes": 0, "pruned": 0, "timed_out": False, "frontier_lb": None, "root_lb": None}
    root_lb = root_kids[0][0] if root_kids else const
    stack.append([base, remaining0, const, -10 ** 12, [], root_kids, 0])
    while stack:
        if nodes >= node_limit or time.perf_counter() > deadline:
            timed_out = True
            break
        frame = stack[-1]
        st, remaining, cost_so_far, last_t, plan, kids, idx = frame
        if idx >= len(kids):
            stack.pop()
            continue
        frame[6] = idx + 1
        lb, etb, vid, bid, p, c = kids[idx]
        if lb >= top.threshold():
            pruned += len(kids) - idx  # 정렬돼 있으므로 뒤는 모두 버린다
            frame[6] = len(kids)
            continue
        nodes += 1
        nst = st.copy()
        nst.add(p)
        nrem = remaining - {vid}
        nplan = plan + [(vid, bid)]
        ncost = cost_so_far + c
        if not nrem:
            top.offer(ncost, _signature(nst), nplan)
            continue
        key = state_key(nst, etb)
        seen = memo.get(key)
        if seen is not None and len(seen) >= top.k and ncost >= seen[-1]:
            merged += 1          # 같은 상태를 더 싸게 이미 K번 만났다 → 이 가지의 미래는 그쪽이 더 낫다
            continue
        seen = sorted((seen or []) + [ncost])[:top.k]
        memo[key] = seen
        kk = children(nst, nrem, ncost, etb)
        if kk:
            stack.append([nst, nrem, ncost, etb, nplan, kk, 0])
    frontier = None
    if timed_out:
        for frame in stack:
            kids, idx = frame[5], frame[6]
            for k in kids[idx:]:
                frontier = k[0] if frontier is None else min(frontier, k[0])
    return {"nodes": nodes, "pruned": pruned, "merged_states": merged, "timed_out": timed_out, "frontier_lb": frontier, "root_lb": root_lb}


def optimize(ctx, k: int = 3, time_limit_s: float = 20.0, node_limit: int = 2_000_000, use_bnb: bool = True) -> SearchResult:
    t0 = time.perf_counter()
    deadline = t0 + time_limit_s
    base = initial_state(ctx)
    baseline = fcfs(ctx)
    baseline.violations = validate(ctx, baseline.state.pl) if baseline.complete else []
    top = TopK(max(k, 1) + 2)  # 검증에서 떨어질 경우를 대비해 여분 2개
    stats = {"time_limit_s": time_limit_s, "k": k}

    if baseline.complete:
        top.offer(baseline.total_cents, baseline.signature(), list(baseline.plan))
        big = len(ctx.movable) >= 10
        ls_deadline = t0 + (time_limit_s * 0.4 if big else min(3.0, time_limit_s * 0.2))
        ls_plan, ls_cost, ls_stats = local_search(ctx, baseline.plan, base, ls_deadline, top)
        stats["local_search"] = ls_stats
        if ls_plan is not None and big:
            seed = int(ctx.sc.source_hash[:8], 16) if ctx.sc.source_hash else 7
            _, _, ils = iterated_local_search(ctx, ls_plan, ls_cost, base, ls_deadline, top, seed)
            stats["iterated_local_search"] = ils

    bnb = {"nodes": 0, "pruned": 0, "merged_states": 0, "timed_out": False, "frontier_lb": None, "root_lb": None}
    if use_bnb and ctx.movable:
        bnb = branch_and_bound(ctx, base, top, deadline, node_limit)
    stats.update({"bnb": bnb, "elapsed_s": round(time.perf_counter() - t0, 3)})

    cands, rejected = [], []
    for cost, sig, plan in top.items:
        st, bad = decode(ctx, plan, base=base)
        sch = evaluate(ctx, st, plan, "", bad)
        sch.violations = validate(ctx, st.pl)
        if bad or sch.violations:
            rejected.append({"plan": plan, "violations": sch.violations, "infeasible": [b.detail for b in bad]})
            continue
        cands.append(sch)
        if len(cands) >= k:
            break
    cands.sort(key=lambda s: (s.total_cents, s.signature()))

    if not cands:
        return SearchResult(baseline, [], "NO_FEASIBLE", False, 0, 1.0, stats, rejected)
    best = cands[0].total_cents
    if bnb.get("timed_out"):
        lb = min(best, bnb["frontier_lb"]) if bnb.get("frontier_lb") is not None else 0
        proven = False
    elif use_bnb:
        lb = best
        proven = True
    else:
        lb, proven = 0, False
    gap = 0.0 if best == 0 else max(0.0, (best - lb) / best)
    status = "OPTIMAL" if proven else "BEST_FOUND"
    if baseline.complete and best >= baseline.total_cents:
        status = "NO_IMPROVEMENT"
    for i, s in enumerate(cands):
        s.label = f"{i + 1}안"
        s.meta.update({"rank": i + 1,
                       "optimality": "최적 증명" if (proven and i == 0) else ("탐색 완료(전체 중 상위)" if proven else "최선 탐색 결과"),
                       "savings_cents": (baseline.total_cents - s.total_cents) if baseline.complete else None})
    return SearchResult(baseline, cands, status, proven, lb, gap, stats, rejected)


def brute_force(ctx, k: int = 3, max_vessels: int = 6):
    """가능한 배정을 모두 탐색(FR-51 최적성 검증용, 6척 이하). 순서 n! × 부두 조합을 전부 디코딩한다."""
    mv = list(ctx.movable)
    if len(mv) > max_vessels:
        raise ValueError(f"완전 탐색은 {max_vessels}척 이하만 (지금 {len(mv)}척)")
    base = initial_state(ctx)
    top = TopK(k)
    count = 0
    for perm in itertools.permutations(mv):
        for berths in itertools.product(*[ctx.eligible[v] for v in perm]):
            plan = list(zip(perm, berths))
            st, bad = decode(ctx, plan, base=base)
            count += 1
            if bad:
                continue
            if validate(ctx, st.pl):
                continue
            cost = sum(amount_cents(ctx, ctx.vessels[vid], p) for vid, p in st.pl.items())
            top.offer(cost, _signature(st), plan)
    return [(c, s) for c, s, _ in top.items], count
