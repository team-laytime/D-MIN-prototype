"""탐색기 화면(explorer.html)의 계산이 Python과 같은지 — 화면 코어(JavaScript)를 node로 돌려 대조한다.

화면에 내장한 골든(make_explorer.golden)은 열 때마다 브라우저에서 대조하고, 여기서는 그것과 다른 무작위 조건으로 다시 확인한다.
"""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

import berth_milp as bm
import laytime_csv as lc
import make_explorer as me

CSV = Path(__file__).resolve().parents[1] / "data" / "vessel_journeys.csv"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node가 없어 화면 코어를 돌릴 수 없음")

DRIVER = """
const fs = require('fs');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
%s
const out = { voy: [], ord: [] };
for (const cfg of payload.cfgs) out.voy.push(payload.data.map(c => { const r = compute(c, cfg); return [r.dem, r.amount, r.used, r.ded, r.start, r.rule]; }));
for (const p of payload.orders) {
  const X = { name: 'X', ...p.X }, Y = { name: 'Y', ...p.Y };
  out.ord.push([scheduleOrder(X, Y, p).cost, scheduleOrder(Y, X, p).cost]);
}
const inf = x => (Number.isFinite(x) ? x : null);
out.models = (payload.insts || []).map(inst => {
  const m = buildModel(inst);
  return { vars: m.vars.map(v => [v.name, v.lb, inf(v.ub), v.kind, v.cost]), rows: m.rows.map(r => [r.name, r.coefs, inf(r.lo), inf(r.hi)]),
           big: m.big, lp: toLP(m, 'test') };
});
out.plans = (payload.plans || []).map(([inst, plan]) => {
  const m = buildModel(inst), vals = planValues(inst, plan);
  const varViol = Math.max(0, ...m.vars.map(v => Math.max(v.lb - vals[v.name], vals[v.name] - v.ub, 0)).filter(Number.isFinite));
  return { viol: Math.max(0, ...m.rows.map(r => rowSlack(r, vals).viol)), varViol, obj: objective(m, vals) };
});
out.enums = (payload.enums || []).map(inst => {
  const m = buildModel(inst);
  return enumPlans2(inst).map(p => { const vals = planValues(inst, p); return { cost: p.cost, viol: Math.max(0, ...m.rows.map(r => rowSlack(r, vals).viol)), obj: objective(m, vals) }; });
});
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def html():
    return me.build(CSV, out=None)


@pytest.fixture(scope="module")
def calls():
    return lc.analyze(CSV)[1]


def run_node(html, tmp_path_factory, cfgs, orders, calls, insts=(), plans=(), enums=()):
    js = tmp_path_factory.mktemp("explorer") / "driver.js"
    js.write_text(DRIVER % me.core_js(html), encoding="utf-8")
    payload = {"data": [me.voyage(c) for c in calls], "cfgs": cfgs, "orders": orders, "insts": list(insts), "plans": list(plans), "enums": list(enums)}
    done = subprocess.run(["node", str(js)], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def random_cfgs(n, seed):
    rng = random.Random(seed)
    return [dict(L=rng.choice([6, 12, 18, 24, 24.5, 30, 36, 48, 72]), rate=rng.randrange(1000, 200001, 500),
                 notice=rng.choice([0, 0.5, 3, 6, 6, 9, 12]), lag=rng.choice([0, 5, 20, 45, 90, 180]),
                 norBasis=rng.choice(["tender", "accepted"]), norValidity=rng.choice(["lenient", "strict"]),
                 shiftCounts=rng.random() < 0.5, gaps=rng.choice(["count", "exclude"])) for _ in range(n)]


def random_orders(n, seed):
    rng = random.Random(seed)
    v = lambda: {"a": round(rng.uniform(0, 15), 2), "sigma": rng.choice([0, 0, 0.5, 1, 1.5]),  # noqa: E731
                 "p": round(rng.uniform(3, 25), 2), "L": rng.choice([4, 12, 24, 36]), "rate": rng.choice([8000, 26000, 48000, 120000])}
    return [{"X": v(), "Y": v(), "free": round(rng.uniform(-2, 12), 2), "gout": rng.choice([0, 0.5, 1]),
             "gin": rng.choice([0, 1, 2.5]), "notice": rng.choice([0, 6, 12])} for _ in range(n)]


def random_model_instance(seed, n=None):
    """무작위 문제(선석 2~3개, 이동 σ, 선석 가용 시각 일부) — 주간 접안(C7)은 화면에 없어 제외."""
    rng = random.Random(seed)
    n = n or rng.randint(2, 4)
    berths = ["A", "B", "C"]
    vs = [bm.Vessel(f"V{i}", nor=round(rng.uniform(0, 20), 2), p=round(rng.uniform(5, 20), 2), L=rng.choice([12, 24, 36]),
                    rate=rng.choice([10_000, 26_000, 55_000]), berths=tuple(rng.sample(berths, rng.randint(1, 3))),
                    sigma=rng.choice([0, 0, 0.5, 1.0, 1.5])) for i in range(n)]
    free = {k: round(rng.uniform(0, 12), 2) for k in berths if rng.random() < 0.7}
    return vs, bm.Params(notice=rng.choice([0, 6, 12]), g_out=rng.choice([0.5, 1.0]), g_in=rng.choice([0.5, 1.0, 1.5]), berth_free=free)


def py_model(vessels, prm):
    m = bm.build_model(vessels, prm)
    inf = lambda x: None if abs(x) == bm.INF else x  # noqa: E731
    vars_ = {nm: (lb, inf(ub), "bin" if integ else "cont", c) for nm, lb, ub, integ, c in zip(m.names, m.lb, m.ub, m.integ, m.c)}
    rows = {name: ({m.names[j]: c for j, c in co.items()}, inf(lo), inf(hi)) for co, lo, hi, name in m.rows}
    return vars_, rows


def test_voyage_math_matches_python_on_random_conditions(html, calls, tmp_path_factory):
    cfgs = random_cfgs(80, seed=1234) + [dict(me.BASE_CFG)]
    got = run_node(html, tmp_path_factory, cfgs, [], calls)["voy"]
    checked = 0
    for cfg, rows in zip(cfgs, got):
        terms = lc.Terms(laytime_hours=cfg["L"], notice_hours=cfg["notice"], rate_usd_day=cfg["rate"],
                         hose_lag_min=cfg["lag"], shift_counts_on_demurrage=cfg["shiftCounts"])
        for c, (dem, amount, used, ded, start, rule) in zip(calls, rows):
            try:
                r = lc.compute(c, terms, nor_basis=cfg["norBasis"], nor_validity=cfg["norValidity"], gaps=cfg["gaps"])
            except ValueError:
                continue
            checked += 1
            assert dem == pytest.approx(r.demurrage_h * 60, abs=1e-6), (cfg, c.jid)
            assert used == pytest.approx(r.used_h * 60, abs=1e-6), (cfg, c.jid)
            assert ded == pytest.approx(r.deducted_h * 60, abs=1e-6), (cfg, c.jid)
            assert amount == pytest.approx(r.amount_usd, abs=0.011), (cfg, c.jid)
            assert start == me.mins(r.laytime_start), (cfg, c.jid)
            assert rule == {"OPS_COMMENCED": "OPS_COMMENCED"}.get(r.start_rule, r.start_rule), (cfg, c.jid)
    assert checked > 80 * 23 * 0.95


def test_default_screen_total_is_the_readme_number(html, calls, tmp_path_factory):
    got = run_node(html, tmp_path_factory, [dict(me.BASE_CFG)], [], calls)["voy"][0]
    assert round(sum(row[0] for row in got) / 60, 2) == 1091.80
    assert round(sum(row[1] for row in got)) == 1182783


def test_two_vessel_order_math_matches_python(html, calls, tmp_path_factory):
    orders = random_orders(60, seed=99) + [me.SC01_P]
    got = run_node(html, tmp_path_factory, [], orders, calls)["ord"]
    for p, (a, b) in zip(orders, got):
        pa, pb = me.order_cost(p)
        assert a == pytest.approx(pa, abs=0.01), p
        assert b == pytest.approx(pb, abs=0.01), p
    assert got[-1] == pytest.approx([52000, 6000])          # SC-01 손계산 정답


def test_embedded_goldens_are_current(html):
    """화면에 내장한 골든이 지금 Python 결과와 같아야 한다(오래된 explorer.html 방지)."""
    built = (me.HERE / "explorer.html")
    if built.exists():
        assert built.read_text(encoding="utf-8") == html, "explorer.html이 오래됨 — python3 -I journeys/make_explorer.py"


def test_no_innerhtml_in_screen(html):
    """CSV에서 온 이름·값은 신뢰하지 않는 데이터라 innerHTML로 넣지 않는다(textContent·createTextNode만)."""
    assert "innerHTML" not in html and "insertAdjacentHTML" not in html


def test_js_model_rows_equal_python_model_rows(html, calls, tmp_path_factory):
    """화면이 조립하는 모델(변수·제약 행의 이름·계수·하한·상한)이 berth_milp.build_model과 한 행도 다르지 않다."""
    cases = [([bm.Vessel("X", 2, 16, 24, 48000, ("SK7",)), bm.Vessel("Y", 4, 10, 12, 96000, ("SK7",))], bm.Params(berth_free={"SK7": 6.0}))]
    cases += [random_model_instance(seed) for seed in range(40)]
    cases += [(vs, prm) for vs, prm in (me.rm.stress_scenario(calls, lc.Terms(), 1.0, False),)]
    got = run_node(html, tmp_path_factory, [], [], calls, insts=[me.inst_of(vs, prm) for vs, prm in cases])["models"]
    n_rows = 0
    for (vs, prm), g in zip(cases, got):
        pv, pr = py_model(vs, prm)
        assert {v[0] for v in g["vars"]} == set(pv)
        for name, lb, ub, kind, cost in g["vars"]:
            plb, pub, pkind, pcost = pv[name]
            assert (kind, ub is None) == (pkind, pub is None), name
            assert lb == pytest.approx(plb, abs=1e-9) and cost == pytest.approx(pcost, abs=1e-9), name
            if ub is not None:
                assert ub == pytest.approx(pub, abs=1e-9), name
        assert {r[0] for r in g["rows"]} == set(pr)
        for name, coefs, lo, hi in g["rows"]:
            n_rows += 1
            pco, plo, phi = pr[name]
            assert set(coefs) == set(pco), name
            for k, c in coefs.items():
                assert c == pytest.approx(pco[k], abs=1e-9), (name, k)
            assert (lo is None, hi is None) == (plo is None, phi is None), name
            if lo is not None:
                assert lo == pytest.approx(plo, abs=1e-9), name
            if hi is not None:
                assert hi == pytest.approx(phi, abs=1e-9), name
        assert g["big"] > 0
    assert n_rows > 500


def test_python_milp_solutions_satisfy_js_model_rows(html, calls, tmp_path_factory):
    """Python MILP가 푼 해를 화면의 모델에 넣으면 모든 제약 행·변수 범위를 만족하고 목적함수가 같다."""
    cases, plans, costs = [], [], []
    for seed in range(40):
        vs, prm = random_model_instance(seed, n=random.Random(seed).randint(2, 4))
        sol = bm.solve_milp(vs, prm)
        assert sol.status == "최적"
        cases.append((vs, prm))
        plans.append([me.inst_of(vs, prm), me.plan_of(sol)])
        costs.append(sol.milp_cost)
    got = run_node(html, tmp_path_factory, [], [], calls, plans=plans)["plans"]
    for g, cost in zip(got, costs):
        assert g["viol"] < 5e-6 and g["varViol"] < 5e-6      # 솔버 해는 제약을 허용오차(1e-6)만큼 어길 수 있다
        assert g["obj"] == pytest.approx(cost, abs=0.01)


def test_embedded_stress_plans_are_feasible_and_cost_matches(html, calls, tmp_path_factory):
    models = me.stress_models(calls)
    plans = [[m["inst"], m[key]["plan"]] for m in models for key in ("milp", "fcfs")]
    costs = [m[key]["cost"] for m in models for key in ("milp", "fcfs")]
    got = run_node(html, tmp_path_factory, [], [], calls, plans=plans)["plans"]
    for g, cost in zip(got, costs):
        assert g["viol"] < 1e-9 and g["varViol"] < 1e-9      # 내장한 해는 정확히 다시 계산한 일정이라 위반이 없다
        assert g["obj"] == pytest.approx(cost, abs=0.01)


def test_js_lp_text_is_wellformed(html, calls, tmp_path_factory):
    vs, prm = random_model_instance(3, n=3)
    g = run_node(html, tmp_path_factory, [], [], calls, insts=[me.inst_of(vs, prm)])["models"][0]
    lp = g["lp"]
    sections = [ln for ln in lp.splitlines() if ln in ("Minimize", "Subject To", "Bounds", "Binaries", "End")]
    assert sections[:3] == ["Minimize", "Subject To", "Bounds"] and sections[-1] == "End"
    body = lp.split("Subject To\n")[1].split("\nBounds")[0].splitlines()
    assert len(body) == len(g["rows"])
    names = [ln.split(":")[0].strip() for ln in body]
    assert len(set(names)) == len(names)
    assert lp.count("\\ test") == 1


# ---------------------------------------------------------------- 기호 ↔ 한글 일치

FORMULA_DRIVER = """
const fs = require('fs');
%s
const strip = dsl => parseFx(dsl).map(x => (x.t != null ? x.t : x.v)).join('');
const all = [...FORMULAS_VOY.map(f => ['VOY', f.dsl, f.ko]), ['OBJ', OBJ.dsl, OBJ.ko], ...MODEL_TAGS.map(t => [t[0], t[1], t[2]])];
console.log(JSON.stringify({
  formulas: all.map(([tag, dsl, ko]) => ({ tag, dsl, ko, tokens: parseFx(dsl), korean: ko || koOf(dsl), plain: strip(dsl) })),
  symKo: SYM_KO, legend: LP_LEGEND,
}));
"""


@pytest.fixture(scope="module")
def formulas(html, tmp_path_factory):
    js = tmp_path_factory.mktemp("fx") / "fx.js"
    js.write_text(FORMULA_DRIVER % me.core_js(html), encoding="utf-8")
    done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_every_variable_in_every_formula_has_a_korean_name(formulas):
    n = 0
    for f in formulas["formulas"]:
        for t in f["tokens"]:
            if "v" in t:
                n += 1
                assert t["ko"].strip() and "{" not in t["ko"] and "_" not in t["ko"], (f["tag"], t)
        assert "{" not in f["plain"] and "}" not in f["plain"], (f["tag"], f["plain"])      # 짝이 안 맞는 중괄호가 없다
        assert "{" not in f["korean"] and "}" not in f["korean"] and "_" not in f["korean"], f["tag"]
    assert n >= 80


def test_korean_formula_contains_every_symbols_korean_name(formulas):
    """한글 식에 그 식의 모든 변수의 한글 이름이 들어 있다 — 기호식과 한글 식이 항별로 대응한다."""
    for f in formulas["formulas"]:
        for t in f["tokens"]:
            if "v" in t:
                assert t["ko"] in f["korean"], (f["tag"], t["ko"], f["korean"])


def test_plain_symbolic_formula_is_what_the_readme_shows(formulas):
    """'sym{한글}'에서 한글을 떼면 기존 기호식이 된다(식 자체는 바뀌지 않았다)."""
    plain = {f["tag"]: f["plain"] for f in formulas["formulas"]}
    assert plain["C3"] == "s_i ≥ F_k + g_in − M( 1 − x_ik )"
    assert plain["C5a"] == "d_i ≥ s_i + p_i − c_i − L_i − δ_i"
    assert plain["C5b"] == "d_i ≥ max( 0, p_i − L_i )"
    assert plain["C6e"] == "s_i ≤ c_i + L_i + σ_i − ε + M( 1 − z_i )"
    assert plain["OBJ"] == "min Σ_i ( r_i / 24 ) · d_i"
    voy = [f["plain"] for f in formulas["formulas"] if f["tag"] == "VOY"]
    assert voy == ["t_0 = min( a + n, f )", "t_1 = h", "U = ( t_1 − t_0 ) − δ", "D = max( 0, U − L )", "C = D × r / 24"]


def test_same_symbol_same_korean_name_except_documented_roles(formulas):
    """같은 기호는 어디서나 같은 한글 이름이다. 예외는 앞 배/뒤 배를 가르는 C4뿐이다."""
    seen = {}
    for f in formulas["formulas"]:
        if f["tag"] in ("C4a", "C4b"):
            continue
        for t in f["tokens"]:
            if "v" in t:
                assert seen.setdefault(t["v"], t["ko"]) == t["ko"], (f["tag"], t["v"], seen[t["v"]], t["ko"])
    # 목록에 쓰는 한글 이름(SYM_KO)도 식의 이름과 같다
    for sym, ko in formulas["symKo"].items():
        if sym in seen:
            assert seen[sym] == ko, (sym, seen[sym], ko)


def test_c4_roles_are_labelled_front_and_back(formulas):
    by = {f["tag"]: {t["v"]: t["ko"] for t in f["tokens"] if "v" in t} for f in formulas["formulas"]}
    assert (by["C4a"]["s_i"], by["C4a"]["s_j"]) == ("앞배접안", "뒤배접안")      # C4a: i가 앞
    assert (by["C4b"]["s_i"], by["C4b"]["s_j"]) == ("뒤배접안", "앞배접안")      # C4b: j가 앞


def test_lp_legend_matches_python_and_js(formulas):
    assert tuple(formulas["legend"]) == bm.LP_LEGEND
    vs = [bm.Vessel("X", 2, 16, 24, 48000, ("SK7",)), bm.Vessel("Y", 4, 10, 12, 96000, ("SK7",))]
    lp = bm.build_model(vs, bm.Params(berth_free={"SK7": 6.0})).to_lp("t")
    assert all(f"\\ {line}" in lp for line in bm.LP_LEGEND)


def test_readme_korean_formulas_are_the_ones_on_screen(formulas):
    """README의 한글 식이 화면의 한글 식과 글자 하나까지 같다 (한쪽만 고치면 여기서 걸린다)."""
    readme = " ".join((Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8").split())
    for f in formulas["formulas"]:
        assert " ".join(f["korean"].split()) in readme, (f["tag"], f["korean"])


def random_two_vessel_berth_instance(seed):
    """두 척 · 선석 SK7·SK8 — 선박마다 들어갈 수 있는 선석(접근 가능 a_ik)이 다르다."""
    rng = random.Random(seed)
    ber = ["SK7", "SK8"]
    vs = [bm.Vessel(nm, nor=round(rng.uniform(0, 12), 2), p=round(rng.uniform(4, 20), 2), L=rng.choice([6, 12, 24, 36]),
                    rate=rng.choice([10_000, 26_000, 48_000, 96_000]), berths=tuple(rng.sample(ber, rng.randint(1, 2))),
                    sigma=rng.choice([0, 0, 0.5, 1.0, 1.5])) for nm in ("X", "Y")]
    prm = bm.Params(notice=rng.choice([0, 6, 12]), g_out=rng.choice([0.5, 1.0]), g_in=rng.choice([0.5, 1.0, 1.5]),
                    berth_free={k: round(rng.uniform(0, 10), 2) for k in ber})
    return vs, prm


def test_two_vessel_berth_enumeration_matches_python_brute_force_and_milp(html, calls, tmp_path_factory):
    """화면이 열거하는 (선석 배정 × 순서) 조합의 최솟값 = Python 완전 탐색 = Python MILP. 접근 불가 선석은 가지로 만들지 않는다."""
    cases = [random_two_vessel_berth_instance(seed) for seed in range(60)]
    got = run_node(html, tmp_path_factory, [], [], calls, enums=[me.inst_of(vs, prm) for vs, prm in cases])["enums"]
    multi = 0
    for (vs, prm), plans in zip(cases, got):
        costs = [p["cost"] for p in plans]
        assert min(costs) == pytest.approx(bm.brute_force(vs, prm).cost, abs=0.01)
        assert min(costs) == pytest.approx(bm.solve_milp(vs, prm).cost, abs=0.01)
        assert all(p["viol"] < 1e-6 and p["obj"] == pytest.approx(p["cost"], abs=0.01) for p in plans)
        expect = sum(2 if kx == ky else 1 for kx in vs[0].berths for ky in vs[1].berths)       # 같은 선석이면 순서 2가지
        assert len(plans) == expect
        multi += len({b for v in vs for b in v.berths}) > 1
    assert multi > 20          # 선석이 둘 다 쓰이는 문제가 충분히 섞여 있다
