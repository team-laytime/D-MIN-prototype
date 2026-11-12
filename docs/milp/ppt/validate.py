"""무작위 사례로 검산한다 — 식으로 푼 답이 '하나씩 다 해 본 답'과 같은가.

    python3 docs/milp/ppt/validate.py --n 300

    검사 A  생성 완전성   본체 식으로 푼 1·2·3안 금액 = 부두 배정 × 순서를 전부 PPT 식으로 계산한 1·2·3안 금액   (재고 없는 사례)
    검사 B  풀이 정확성   본체 식으로 푼 1·2·3안 금액 = 작업계획의 모든 조합을 하나씩 해 본 1·2·3안 금액            (대기 허용 설정)
    검사 C  묶음 식       식 (3)을 쌍으로 넣은 답 = 겹치는 계획 묶음으로 넣은 답
    검사 D  규칙 재검사   모든 후보안을 verify()로 다시 계산 (solve() 안에서 어기면 바로 멈춘다)
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pptcalc import Rules, iso, load_case, parse       # noqa: E402
from planner import brute_force, generate              # noqa: E402
from solver import exhaustive, solve                   # noqa: E402
import fleet                                           # noqa: E402

CLUSTERS = {
    "대형 부두 #6·#7·#8": ["MR-DSL", "MR-DSL", "MR-RG", "MR-NAPH", "LR1-DSL", "LR1-JET"],
    "원유 #8·Buoy": ["AFRA-CR", "AFRA-CR", "SUEZ-CR", "VLCC-CR", "LR1-DSL"],
    "화학 #4-1·#4-2": ["CHEM-BZ", "CHEM-XYL", "CHEM-TOL", "CHEM-BZ"],
    "제품 #1-1·#1-2·#2-7": ["SP-ASPH", "SP-ASPH", "SP-ASPH"],
}
T0 = parse("2026-11-10T00:00")


def random_case(rng, seed):
    name = rng.choice(list(CLUSTERS))
    n = rng.choice([2, 3, 3, 4, 4, 5])
    ships = []
    for k in range(n):
        tpl = rng.choice(CLUSTERS[name])
        eta = T0 + rng.randrange(0, 60 * 60, 10)                       # 첫 60시간 안, 10분 단위
        kind = rng.random()
        if kind < 0.65:                                                # LayCan 안
            lay = (eta - rng.randrange(0, 36 * 60, 60), eta + rng.randrange(60, 48 * 60, 60))
        elif kind < 0.85:                                              # 조기 도착
            lay = (eta + rng.randrange(60, 30 * 60, 60), eta + rng.randrange(40 * 60, 72 * 60, 60))
        else:                                                          # LayCan Miss
            lay = (eta - rng.randrange(60 * 60, 90 * 60, 60), eta - rng.randrange(60, 20 * 60, 60))
        nor = eta + rng.randrange(0, 180, 10) if rng.random() < 0.4 else None
        ships.append(fleet.make(f"V{k + 1}", tpl, iso(eta), laycan=(iso(lay[0]), iso(lay[1])), nor=iso(nor) if nor else None,
                                cfr=rng.random() < 0.3, laytime=rng.choice([24, 36, 48, 72]),
                                qty=int(fleet.TEMPLATES[tpl][5] * rng.uniform(0.6, 1.1))))
    doc = {"id": f"R{seed}", "title": name, "plan": {"start": iso(T0), "end": iso(T0 + 10 * 1440)}, "arrivals": ships, "restrictions": [],
           "options": {"max_wait_h": 96}}
    if rng.random() < 0.45:
        s0 = T0 + rng.randrange(6 * 60, 70 * 60, 30)
        doc["restrictions"].append({"id": "W1", "reason": "WEATHER", "berths": ["*"], "start": iso(s0), "end": iso(s0 + rng.randrange(4 * 60, 20 * 60, 30))})
    rules = Rules()
    case = load_case(doc, rules)
    from pptcalc import eligible_berths
    pool = sorted({b for a in case.arrivals.values() for b in eligible_berths(rules, a)})
    if pool and rng.random() < 0.25:
        s0 = T0 + rng.randrange(0, 60 * 60, 30)
        doc["restrictions"].append({"id": "M1", "reason": "WORK", "berths": [rng.choice(pool)], "start": iso(s0), "end": iso(s0 + rng.randrange(3 * 60, 12 * 60, 30))})
    if pool and rng.random() < 0.35:                                   # FIX 선박 하나
        tpl = rng.choice(CLUSTERS[name])
        fx = fleet.make("F1", tpl, iso(T0), laycan=(iso(T0 - 1440), iso(T0 + 6 * 1440)))
        b = [x for x in eligible_berths(rules, load_case({**doc, "arrivals": [fx]}, rules).arrivals["F1"])]
        if b:
            etb = T0 + rng.randrange(20 * 60, 80 * 60, 30)
            fx.update({"status": "FIX", "fix": {"berth": rng.choice(b), "etb": iso(etb)}, "eta": iso(etb - 600)})
            doc["arrivals"].append(fx)
    if name.startswith("원유") and rng.random() < 0.6:                  # 원유 탱크
        total = sum(v["qty"] for v in doc["arrivals"] if v["cargo_group"] == "CRUDE")
        if total:
            use = rng.choice([20000, 30000, 35000])
            doc["inventory"] = [{"group": "CRUDE", "opening": 5_000_000 + rng.randrange(0, 3_600_000, 100_000), "min": 3_000_000, "max": 10_000_000,
                                 "flows": [{"from": doc["plan"]["start"], "to": doc["plan"]["end"], "use_per_h": use}]}]
    return doc


def costs(cands):
    return [c.cents for c in cands]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    rules = Rules()
    tally = {"A": [0, 0], "B": [0, 0], "C": [0, 0], "G": [0, 0, 0], "infeasible": 0, "wait_cheaper": 0, "skipped": 0, "tank": 0, "fix": 0, "weather": 0, "exact": 0}
    gaps, worst_time, t_start, fails = [], 0.0, time.time(), []
    for k in range(args.n):
        seed = args.seed + k
        doc = random_case(random.Random(seed), seed)
        case = load_case(doc, rules)
        model = generate(rules, case)                       # auto: 작으면 EXACT, 크면 GRID
        t0 = time.time()
        strict = solve(model, top=3)
        worst_time = max(worst_time, time.time() - t0)
        tally["tank"] += bool(case.tanks)
        tally["fix"] += any(not a.movable for a in case.arrivals.values())
        tally["weather"] += any(r.reason == "WEATHER" for r in case.restrictions)
        tally["skipped"] += strict.size.get("skipped_waits", 0)
        tally["wait_cheaper"] += bool(strict.status == "OK" and any(n.startswith("참고") for n in strict.notes))
        tally["infeasible"] += strict.status != "OK"
        tally["exact"] += model.mode == "EXACT"
        bf = None
        if not case.tanks:                                  # 순서 전수 계산 = 정답 (재고가 있으면 '기다리는 계획' 때문에 식 쪽이 더 넓다)
            bf = [c for c, _, _ in brute_force(rules, case, top=3)[0]]
        if model.mode == "EXACT":
            if bf is not None:                              # A: EXACT로 푼 1·2·3안 = 순서 전수 계산의 1·2·3안
                ok = costs(strict.candidates) == bf
                tally["A"][0 if ok else 1] += 1
                if not ok:
                    fails.append(("A", seed, costs(strict.candidates), bf))
            allow = solve(model, top=3, wait_policy="ALLOW")
            ex = exhaustive(model, top=3, limit=300000)
            if ex is not None:                              # B: 솔버 = 작업계획 조합 전수
                ok = costs(allow.candidates) == [c for c, _ in ex[0]]
                tally["B"][0 if ok else 1] += 1
                if not ok:
                    fails.append(("B", seed, costs(allow.candidates), [c for c, _ in ex[0]]))
            if model.conflicts is not None and len(model.conflicts) <= 150000:
                cl = solve(model, top=3, form="cliques")    # C: 쌍으로 넣은 답 = 묶음으로 넣은 답
                ok = costs(cl.candidates) == costs(strict.candidates)
                tally["C"][0 if ok else 1] += 1
                if not ok:
                    fails.append(("C", seed, costs(strict.candidates), costs(cl.candidates)))
        if bf is not None:                                  # G: GRID(30분) + PPT 재계산의 1안 vs 정답 1안
            grid = solve(generate(rules, case, mode="GRID"), top=1)
            if grid.candidates and bf:
                g, b = grid.candidates[0].cents, bf[0]
                tally["G"][0 if g == b else (1 if g > b else 2)] += 1
                if g != b:
                    gaps.append((g - b) / 100)
                    if g < b:
                        fails.append(("G<", seed, g, b))
            elif bool(grid.candidates) != bool(bf):
                fails.append(("G?", seed, costs(grid.candidates), bf))
        if args.verbose:
            print(seed, doc["title"], model.mode, model.stats["plans"], model.stats["conflicts"], costs(strict.candidates), bf)
    print(f"무작위 {args.n}건 (seed {args.seed}~) · {time.time() - t_start:.0f}초 · 한 건 풀이 최대 {worst_time:.2f}초")
    print(f"  재고 있는 사례 {tally['tank']} · FIX 있는 사례 {tally['fix']} · 기상 제약 있는 사례 {tally['weather']} · 실행 가능한 후보 없음 {tally['infeasible']} · EXACT로 만든 사례 {tally['exact']}")
    print(f"  검사 A (EXACT 1·2·3안 = 순서 전수 계산)      통과 {tally['A'][0]} · 다름 {tally['A'][1]}")
    print(f"  검사 B (솔버 = 작업계획 조합 전수)            통과 {tally['B'][0]} · 다름 {tally['B'][1]}")
    print(f"  검사 C (쌍으로 넣은 답 = 묶음으로 넣은 답)    통과 {tally['C'][0]} · 다름 {tally['C'][1]}")
    print(f"  검사 G (GRID 30분 + 재계산 1안 vs 정답 1안)   같음 {tally['G'][0]} · 더 비쌈 {tally['G'][1]} · 더 쌈 {tally['G'][2]}"
          + (f" · 차이 평균 ${sum(gaps) / len(gaps):,.0f}, 최대 ${max(gaps):,.0f}" if gaps else ""))
    print(f"  일부러 기다리면 더 싼 조합이 있던 사례 {tally['wait_cheaper']} · 걸러 낸 조합 {tally['skipped']}")
    for f in fails[:12]:
        print("  다름:", f)
    return 1 if [f for f in fails if f[0] in "ABC"] else 0


if __name__ == "__main__":
    sys.exit(main())
