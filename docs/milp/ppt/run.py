"""최적화 서비스 입구 — 요청 JSON 하나를 받아 응답 JSON 하나를 돌려준다. Python 계산 서비스(FastAPI)가 이 함수를 그대로 부른다.

    python3 docs/milp/ppt/run.py cases/sample-week.json                  # 응답 JSON + 보고서 표를 out/에 쓴다
    python3 docs/milp/ppt/run.py cases/sample-week.json --compare        # 부두별 최적화·부두 고정 비교까지

    from run import optimize
    response = optimize(request_dict)                                      # 서비스에서 부를 때

요청(= cases/*.json)과 응답의 모양은 README의 '인프라와 주고받는 것' 절에 있다.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import heapq
import itertools
import json
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scipy                                                          # noqa: E402

from pptcalc import Rules, eligible_berths, explain, fmt, hours, iso, load_case, make_plan, parse, relation, usd   # noqa: E402
from planner import baseline, forward, generate, start_order, tank_profile, total_cents, verify   # noqa: E402
from solver import solve                                                  # noqa: E402

ENGINE_VERSION = "ppt-milp/1.0"


# ----------------------------------------------------------------------------- 묶음 나누기
def components(rules, case):
    """서로 영향을 주지 않는 입항 건 묶음으로 나눈다.

    두 입항 건은 ① 배정 가능 부두가 겹치거나 ② 부두 사이 제약(동일 화물 그룹·부두 동시 접안)으로 이어지거나
    ③ 같은 탱크를 쓰면 같은 묶음이다. 묶음끼리는 목적함수 (1)이 더하기로만 이어지므로 따로 풀어 더해도 전체 최적과 같다.
    """
    mov = [a for a in case.arrivals.values() if a.movable]
    el = {a.id: set(eligible_berths(rules, a)) for a in mov}
    parent = {a.id: a.id for a in mov}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    tanks = {t.group for t in case.tanks}
    for a, b in itertools.combinations(mov, 2):
        link = bool(el[a.id] & el[b.id]) or (a.cargo == b.cargo and a.cargo in tanks)
        if not link:
            link = any(relation(rules, a, b1, b, b2) for b1 in el[a.id] for b2 in el[b.id])
        if link:
            parent[find(a.id)] = find(b.id)
    out = {}
    for a in mov:
        out.setdefault(find(a.id), []).append(a.id)
    return sorted(out.values(), key=lambda ids: (-len(ids), ids[0]))


def sub_case(case, ids, rules):
    doc = copy.deepcopy(case.raw)
    keep = set(ids) | {a.id for a in case.arrivals.values() if not a.movable}
    doc["arrivals"] = [v for v in doc["arrivals"] if v["id"] in keep]
    groups = {v["cargo_group"] for v in doc["arrivals"] if v["id"] in ids}
    doc["inventory"] = [t for t in doc.get("inventory", []) if t["group"] in groups]
    return load_case(doc, rules)


def merge_best(parts, fixed_cents, top):
    """묶음마다의 후보 목록에서 합계가 작은 순으로 top개 조합을 고른다 (묶음마다 하나씩)."""
    if any(not p for p in parts):
        return []
    lists = [[(c.cents - fixed_cents, c) for c in p] for p in parts]
    start = tuple(0 for _ in lists)
    heap = [(sum(l[0][0] for l in lists), start)]
    seen, out = {start}, []
    while heap and len(out) < top:
        tot, idx = heapq.heappop(heap)
        out.append((tot + fixed_cents, [lists[k][i][1] for k, i in enumerate(idx)]))
        for k in range(len(lists)):
            if idx[k] + 1 < len(lists[k]):
                nxt = idx[:k] + (idx[k] + 1,) + idx[k + 1:]
                if nxt not in seen:
                    seen.add(nxt)
                    heapq.heappush(heap, (sum(lists[j][i][0] for j, i in enumerate(nxt)), nxt))
    return out


# ----------------------------------------------------------------------------- 응답 만들기
def plan_json(rules, case, p, with_trace=True):
    a = case.arrivals[p.aid]
    out = {
        "arrival_id": p.aid, "vessel": a.vessel, "class": a.vclass, "biz": a.biz, "cargo_group": a.cargo, "status": a.status,
        "berth": p.berth, "eta": iso(a.eta), "etb": iso(p.s), "work_start": iso(p.a), "work_end": iso(p.c), "hose_off": iso(p.h), "etu": iso(p.u),
        "laytime_start": iso(p.lay_start), "laytime_rule": p.lay_rule, "laytime_end": iso(int(p.lay_end)),
        "allowed_hours": round(float(p.allowed) / 60, 4), "weather_hours": round(float(p.wx) / 60, 4), "deduction_hours": round(float(p.ded) / 60, 4),
        "demurrage_hours": round(float(p.dt) / 60, 4), "demurrage_usd": p.cents / 100, "wait_hours": round((p.s - max(a.eta, case.start)) / 60, 2),
        "why_etb": p.why,
    }
    if with_trace:
        out["trace"] = [{"rule": r, "text": t} for r, t in explain(rules, case, p)]
    return out


def changes(base, cand):
    b = {p.aid: p for p in base}
    out = []
    for p in sorted(cand, key=lambda x: x.s):
        q = b.get(p.aid)
        if q is None or p.fixed:
            continue
        if q.berth != p.berth or q.s != p.s:
            out.append({"arrival_id": p.aid, "from": {"berth": q.berth, "etb": iso(q.s), "usd": q.cents / 100},
                        "to": {"berth": p.berth, "etb": iso(p.s), "usd": p.cents / 100}, "delta_usd": (p.cents - q.cents) / 100})
    return out


def schedule_json(rules, case, plans, ref=None, trace=True):
    return {"total_usd": total_cents(plans) / 100, "plans": [plan_json(rules, case, p, trace) for p in sorted(plans, key=lambda x: (rules.berth_order.index(x.berth), x.s))],
            "violations": verify(rules, case, plans), **({"changes_vs_baseline": changes(ref, plans)} if ref else {})}


def current_plans(rules, case):
    """요청에 '현행 계획'(사람이 짠 부두·ETB)이 있으면 같은 PPT 식으로 금액을 계산한다. 규칙 위반도 그대로 센다."""
    cur = {c["id"]: c for c in case.raw.get("current_plan", [])}
    if not cur:
        return None
    out = []
    for a in case.arrivals.values():
        c = cur.get(a.id)
        if c is None:
            return None
        p = make_plan(rules, case, a, c["berth"], parse(c["etb"]), why="현행 계획 (입력값)", fixed=not a.movable)
        out.append(p)
    return out


def optimize(request, top=3, compare=False, time_limit=120.0):
    """요청 dict → 응답 dict. 숫자는 모두 결정론적 계산이다 (LLM 호출 없음)."""
    t0 = time.time()
    rules = Rules(patch=request.get("rule_patch"))
    case = load_case(request, rules)
    req_hash = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    comps = components(rules, case)
    fixed_cents = sum(make_plan(rules, case, a, a.fix["berth"], a.fix["etb"], fixed=True).cents for a in case.arrivals.values() if not a.movable)
    parts, sizes, notes = [], [], []
    for ids in comps:
        sc = sub_case(case, ids, rules)
        model = generate(rules, sc)
        out = solve(model, top=top, time_limit=time_limit)
        parts.append(out.candidates)
        sizes.append({**model.stats, **out.size, "ids": ids, "seconds": round(out.seconds, 2), "status": out.status})
        notes += out.notes
    merged = merge_best(parts, fixed_cents, top)
    base = baseline(rules, case)
    cur = current_plans(rules, case)
    resp = {
        "request_id": request.get("request_id", case.id), "request_hash": req_hash, "case_id": case.id, "title": case.title,
        "engine": {"version": ENGINE_VERSION, "rules_version": rules.version, "solver": f"HiGHS (scipy {scipy.__version__})", "python": platform.python_version(),
                   "formulas": "팀 최종본 본체 식 (1)~(8) — 변경 없음", "objective": "전체 입항 건의 총 예상 체선료 최소화 (부두별 합이 아님)"},
        "status": "OK" if merged else "INFEASIBLE",
        "plan_window": {"start": iso(case.start), "end": iso(case.end)},
        "baseline": schedule_json(rules, case, base) if base else None,
        "current_plan": schedule_json(rules, case, cur) if cur else None,
        "candidates": [],
        "components": sizes,
        "notes": notes,
    }
    for rank, (cents, picks) in enumerate(merged, 1):
        plans = {p.key: p for c in picks for p in c.plans}
        plans = list(plans.values())
        resp["candidates"].append({"rank": rank, "status": "OPTIMAL" if all(c.status == "OPTIMAL" for c in picks) else "TIME_LIMIT",
                                   **schedule_json(rules, case, plans, base),
                                   "delta_vs_baseline_usd": (cents - total_cents(base)) / 100 if base else None})
    if compare and merged:
        resp["comparison"] = compare_scopes(rules, case, cur, time_limit)
    resp["elapsed_seconds"] = round(time.time() - t0, 2)
    return resp


# ----------------------------------------------------------------------------- 부두별 최적화 vs 전체 최적화
def compare_scopes(rules, case, cur, time_limit):
    """같은 식·같은 입력으로 최적화 범위만 바꿔 본다.

    A 전체 최적화        부두 배정과 순서를 함께, 부두 사이 제약·탱크까지 한 번에 (= 후보 1안)
    B 부두 배정 고정     현행 계획의 부두는 그대로 두고 순서·시각만 최적화 (부두 사이 제약·탱크는 그대로 지킨다)
    C 부두별 따로        부두마다 그 부두의 배만 놓고 따로 최적화. 다른 부두와의 제약·탱크는 보지 않는다 → 합친 뒤 실제 규칙으로 검사
    """
    out = {}
    if not cur:
        return out
    curb = {p.aid: p.berth for p in cur}
    # B: 부두 배정 고정
    doc = copy.deepcopy(case.raw)
    for v in doc["arrivals"]:
        if v.get("status", "PLANNED") not in ("FIX", "WORKING"):
            v["berths"] = [curb[v["id"]]]
    t = time.time()
    caseB = load_case(doc, rules)
    oB = solve(generate(rules, caseB), top=1, time_limit=time_limit)
    out["B_berth_fixed"] = {"total_usd": oB.candidates[0].cents / 100 if oB.candidates else None, "status": oB.status, "seconds": round(time.time() - t, 1),
                            "plans": [plan_json(rules, caseB, p, False) for p in (oB.candidates[0].plans if oB.candidates else [])]}
    # C: 부두별 따로 (부두 사이 제약·탱크를 끈 규칙으로 부두 하나씩)
    t = time.time()
    loose = Rules(patch={"pair_rules.same_cargo_group.berth_sets": [], "pair_rules.simultaneous": []})
    per, plans_c, berth_rows = 0, [], []
    for b in sorted(set(curb.values()), key=rules.berth_order.index):
        ids = [aid for aid, bb in curb.items() if bb == b]
        d = copy.deepcopy(case.raw)
        d["arrivals"] = [v for v in d["arrivals"] if v["id"] in ids]
        for v in d["arrivals"]:
            if v.get("status", "PLANNED") not in ("FIX", "WORKING"):
                v["berths"] = [b]
        d["inventory"] = []
        cb = load_case(d, loose)
        ob = solve(generate(loose, cb), top=1, time_limit=time_limit)
        if not ob.candidates:
            berth_rows.append({"berth": b, "arrivals": len(ids), "total_usd": None})
            continue
        per += ob.candidates[0].cents
        berth_rows.append({"berth": b, "arrivals": len(ids), "total_usd": ob.candidates[0].cents / 100})
        plans_c += ob.candidates[0].plans
    by_id = {p.aid: p for p in plans_c}
    rebuilt = [make_plan(rules, case, case.arrivals[aid], p.berth, p.s, why=p.why, fixed=p.fixed) for aid, p in by_id.items()]
    viol = verify(rules, case, rebuilt)
    order = [p.aid for p in start_order(rebuilt)]
    repaired = forward(rules, case, {p.aid: p.berth for p in rebuilt}, order)       # 같은 부두·같은 순서로 실제 규칙에 맞춰 다시 계산
    rep_viol = verify(rules, case, repaired) if repaired else ["다시 계산 불가"]
    out["C_per_berth"] = {"sum_usd": per / 100, "seconds": round(time.time() - t, 1), "violations": viol, "by_berth": berth_rows,
                          "repaired_total_usd": total_cents(repaired) / 100 if repaired else None, "repaired_violations": rep_viol}
    return out


# ----------------------------------------------------------------------------- 보고서 표 (markdown)
def report_md(resp):
    L = []
    c1 = resp["candidates"][0] if resp["candidates"] else None
    L.append(f"# {resp['title']} — 결과\n")
    L.append(f"- 요청 {resp['request_id']} · 입력 지문 {resp['request_hash']} · 엔진 {resp['engine']['version']} · 규칙 {resp['engine']['rules_version']} · {resp['engine']['solver']}")
    L.append(f"- 목적: {resp['engine']['objective']} · 식: {resp['engine']['formulas']} · 걸린 시간 {resp['elapsed_seconds']}초\n")
    L.append("| 일정 | 총 예상 체선료 | 기준안 대비 | 규칙 위반 |")
    L.append("|---|---:|---:|---:|")
    base = resp["baseline"]["total_usd"] if resp["baseline"] else None
    rows = []
    if resp.get("current_plan"):
        rows.append(("현행 계획 (샘플의 부두·ETB)", resp["current_plan"]))
    if resp.get("baseline"):
        rows.append(("기준안 (ETA 순서, 가장 이른 부두)", resp["baseline"]))
    for c in resp["candidates"]:
        rows.append((f"{c['rank']}안 (수리계획법)", c))
    for name, s in rows:
        d = "" if base is None else f"{s['total_usd'] - base:+,.2f}"
        L.append(f"| {name} | ${s['total_usd']:,.2f} | {d} | {len(s['violations'])} |")
    for comp in resp["components"]:
        L.append(f"\n- 묶음 {len(comp['ids'])}건: 작업계획 {comp['plans']:,}개({comp['mode']}{'' if comp['mode'] == 'EXACT' else ' ' + str(comp['grid_min']) + '분 눈금'}) · "
                 f"변수 {comp.get('variables', 0):,} · 제약식 {comp.get('rows', 0):,} · 풀이 {comp['rounds']}회 · {comp['seconds']}초")
    for n in resp["notes"]:
        L.append(f"- {n}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--out", default=str(HERE / "out"))
    args = ap.parse_args()
    path = Path(args.case)
    if not path.is_absolute() and not path.exists():
        path = HERE / args.case
    req = json.loads(path.read_text(encoding="utf-8"))
    resp = optimize(req, top=args.top, compare=args.compare)
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    (out / f"{req['id']}.response.json").write_text(json.dumps(resp, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md = report_md(resp)
    (out / f"{req['id']}.summary.md").write_text(md, encoding="utf-8")
    print(md)
    if "comparison" in resp:
        print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("plans",)} for k, v in resp["comparison"].items()}, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
