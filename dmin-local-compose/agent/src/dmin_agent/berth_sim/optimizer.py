"""최적화: 부두 배정과 부두 안 접안 순서를 바꿔 시나리오 전체 체선료를 줄인다.

결정 변수
  선박마다 어느 부두에 접안할지 + 그 부두 안에서 몇 번째로 접안할지. FIX 선박은 움직이지 않는다.

후보 부두 (부두 적합성 필터)
  선박 제원(DWT · LOA · PBL · Draft)과 화물이 맞는 부두만 (berth_fit.allowed_berths)
  ∩ 그 부두에서 평균 Rate를 구할 수 있는 부두 (장표: 선박코드+자재코드+부두 → 부두+자재코드 과거 Shipment)
  → 과거 실적이 없으면 작업시간을 계산할 수 없으므로 옮기지 않는다.

평가
  바뀐 계획을 그대로 ETB 산정 ①②③ → ETB 이후 계산 → 체선료 합계 (scenario.evaluate_rules).
  부두 사용 가능 시각(berth_availability)을 넘기면 데이터 이전 시간대로 당기지 않는다.
  접안불가(FIX 충돌)나 Alert가 난 선박이 있으면 큰 벌점을 더한다.

탐색 (담금질 기법, simulated annealing)
  이웃 계획 = 아래 셋 중 하나를 무작위로 적용
    SWAP     같은 부두 안 두 선박 순서 맞바꾸기
    REINSERT 같은 부두 안 한 선박을 다른 순번으로
    RELOCATE 한 선박을 다른 후보 부두로 (ETA 순서에 맞는 자리에 끼움)
  좋아지면 채택, 나빠져도 exp(-증가액 / 온도) 확률로 채택해 지역 최적에서 빠져나온다. 온도는 점점 낮춘다.
"""

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from .after_etb.s2_work_finish import find_past
from .berth_fit import allowed_berths
from .master_data import MasterData
from .models import Vessel
from .scenario import ScenarioResult, evaluate_rules
from .step3_berth_block import BerthBlock
from .synth import SynthData
from .validate import dims_of

ITERATIONS = 3000
SEED = 7
T_START = 5_000.0  # 시작 온도 ($): 이 정도 악화는 초반에 자주 받아들인다
T_END = 20.0  # 끝 온도 ($)
MOVE_WEIGHTS = {"SWAP": 0.35, "REINSERT": 0.25, "RELOCATE": 0.40}
INFEASIBLE_PENALTY = 10_000_000.0  # 접안불가 · Alert 선박 1척당 벌점 ($)

Plan = dict[str, list[Vessel]]  # 부두 → 접안 순서


@dataclass(frozen=True)
class Candidates:
    berths: dict[str, list[str]]  # 선박 → 옮길 수 있는 부두 (현재 부두 포함)
    excluded: dict[str, dict[str, str]]  # 선박 → {부두: 제외 사유} (적합하지만 과거 실적 없음)


def candidate_berths(plan: Plan, master: MasterData, data: SynthData) -> Candidates:
    berths, excluded = {}, {}
    for seq in plan.values():
        for v in seq:
            p = data.profiles[v.vessel_id]
            ok, out = [], {}
            for b in allowed_berths(dims_of(p), master):
                if b == v.berth or find_past(data.history, p.vessel_code, p.material_code, b)[0]:
                    ok.append(b)
                else:
                    out[b] = "과거 Shipment 없음 → 평균 Rate 산출 불가"
            berths[v.vessel_id] = [v.berth] if v.is_fix else ok
            excluded[v.vessel_id] = out
    return Candidates(berths, excluded)


def cost(result: ScenarioResult) -> float:
    bad = sum(1 for o in result.outcomes if not o.berthable or o.after is None)
    return result.total_fee + bad * INFEASIBLE_PENALTY


def _copy(plan: Plan) -> Plan:
    return {b: list(seq) for b, seq in plan.items()}


def _movable(seq: list[Vessel]) -> list[int]:
    return [i for i, v in enumerate(seq) if not v.is_fix]


def neighbor(plan: Plan, cands: Candidates, rng: random.Random) -> tuple[Plan, str] | None:
    new = _copy(plan)
    move = rng.choices(list(MOVE_WEIGHTS), weights=list(MOVE_WEIGHTS.values()))[0]

    if move in ("SWAP", "REINSERT"):
        berths = [b for b, seq in new.items() if len(_movable(seq)) >= 2]
        if not berths:
            return None
        b = rng.choice(berths)
        seq = new[b]
        i, j = rng.sample(_movable(seq), 2)
        if move == "SWAP":
            seq[i], seq[j] = seq[j], seq[i]
            return new, f"SWAP #{b}: {seq[j].vessel_id} ↔ {seq[i].vessel_id}"
        v = seq.pop(i)
        seq.insert(j, v)
        return new, f"REINSERT #{b}: {v.vessel_id} {i + 1}번 → {j + 1}번"

    pool = [(b, i) for b, seq in new.items() for i in _movable(seq) if len(cands.berths[seq[i].vessel_id]) > 1]
    if not pool:
        return None
    b, i = rng.choice(pool)
    v = new[b].pop(i)
    target = rng.choice([x for x in cands.berths[v.vessel_id] if x != b])
    moved = replace(v, berth=target)
    seq = new.setdefault(target, [])
    pos = next((k for k, w in enumerate(seq) if w.eta > moved.eta), len(seq))
    seq.insert(pos, moved)
    return new, f"RELOCATE {v.vessel_id}: #{b} → #{target}"


@dataclass(frozen=True)
class OptimizeResult:
    baseline: ScenarioResult  # 실제 부두 배정·순서 + 규칙 ETB
    best: ScenarioResult
    best_plan: Plan
    candidates: Candidates
    trace: tuple[tuple[int, float, float], ...]  # (반복, 현재 비용, 최고 비용)
    accepted_moves: tuple[str, ...]
    iterations: int
    seed: int


def optimize(
    plan: Plan, data: SynthData, master: MasterData, blocks: Sequence[BerthBlock] = (),
    iterations: int = ITERATIONS, seed: int = SEED, available_from: dict[str, datetime] | None = None,
    on_eval: Callable[[Plan, ScenarioResult], None] | None = None,
) -> OptimizeResult:
    """on_eval: 평가한 모든 이웃 계획을 받는다 (계획 모음 수집용)."""
    rng = random.Random(seed)
    cands = candidate_berths(plan, master, data)
    baseline = evaluate_rules(plan, data, blocks, "최적화 전 (실제 배정 · 규칙 ETB)", available_from)
    cur_plan, cur_cost = plan, cost(baseline)
    best_plan, best_res, best_cost = plan, baseline, cur_cost
    trace = [(0, cur_cost, best_cost)]
    accepted: list[str] = []

    for it in range(1, iterations + 1):
        temp = T_START * (T_END / T_START) ** (it / iterations)
        found = neighbor(cur_plan, cands, rng)
        if found is None:
            continue
        new_plan, desc = found
        res = evaluate_rules(new_plan, data, blocks, "최적화 후", available_from)
        if on_eval:
            on_eval(new_plan, res)
        new_cost = cost(res)
        delta = new_cost - cur_cost
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            cur_plan, cur_cost = new_plan, new_cost
            if delta < 0:
                accepted.append(f"{it}: {desc} ({delta:+,.0f})")
            if new_cost < best_cost:
                best_plan, best_res, best_cost = new_plan, res, new_cost
        if it % max(1, iterations // 100) == 0:
            trace.append((it, cur_cost, best_cost))

    best_plan = {b: seq for b, seq in best_plan.items() if seq}
    return OptimizeResult(baseline, best_res, best_plan, cands, tuple(trace), tuple(accepted), iterations, seed)
