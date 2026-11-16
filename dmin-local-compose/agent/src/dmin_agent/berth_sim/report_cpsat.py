"""CP-SAT 결과 시각화 (docs/cpsat.html · serve_cpsat.py).

  요약 · 순위(1~N) 선택 · 부두별 간트(최적화 전 / 선택 순위, 같은 시간축) · 바뀐 선박 표 · 선박별 체선료 곡선
  서버(serve_cpsat.py)로 열면 '최적화 실행' 버튼으로 바로 CP-SAT을 돌릴 수 있다.
"""

import json
from datetime import timedelta

from .cost_table import CostRow
from .cpsat_model import BAND, MIN_DIFF, PER_TIER, TIERS, TIME_LIMIT_S, SolveResult
from .feasibility import FeasibilityTable
from .scenario import ScenarioResult
from .shifting import direction
from .tanks import simulate, work_from_outcomes
from .typhoon import status_at
from .weather import HOUR, THRESHOLDS, berth_group, typhoon_text

CURVE_EVERY = 6  # 체선료 곡선은 30분(5분 × 6)마다 한 점


def _tank_series(ts, work) -> dict:
    """탱크별 시간당 재고(톤)와 범위 밖 구간."""
    traces = simulate(ts, work, step=timedelta(hours=1))
    return {n: {"lv": [round(x) for x in t.levels], "viol": t.violations} for n, t in traces.items()}


def plan_work(table: FeasibilityTable, costs, res: SolveResult, data=None) -> dict:
    """선박별 (작업시작, 작업완료, 그 부두의 기상 하역 중단 구간)."""
    return {vid: (a.etb + timedelta(hours=1), table.start + timedelta(minutes=costs[(vid, a.berth)].etu[a.slot]) - timedelta(hours=2),
                  data.stops(a.berth) if data is not None else ())
            for vid, a in res.assignments.items()}


def _weather_payload(table: FeasibilityTable, data) -> dict | None:
    fc = getattr(data, "weather", None)
    if fc is None:
        return None
    s0, end = table.start, table.start + table.step * table.n_slots
    mins = lambda t: int((t - s0).total_seconds() // 60)  # noqa: E731
    hours = [h for h in fc.hours if s0 <= h.time < end]
    groups = {}
    for g in THRESHOLDS:
        rep = "1-1" if g.startswith("#1") else "6"
        groups[g] = {"stop": [[mins(a), mins(b)] for a, b in fc.stops(rep)], "unberth": [[mins(a), mins(b)] for a, b in fc.unberths(rep)],
                     "thr": THRESHOLDS[g]}
    span = lambda ps: [[mins(a), mins(b)] for a, b in ps]  # noqa: E731
    track_by = {b: fc.track_unberths(b) for b in table.berths}
    hit = lambda h: any(s < h.time + HOUR and h.time < e for ps in track_by.values() for s, e in ps)  # noqa: E731
    same: dict[tuple, list[str]] = {}  # 태풍 경로로 같은 시간 접안 불가인 부두끼리
    for b, ps in track_by.items():
        if ps:
            same.setdefault(ps, []).append(b)
    summary = " / ".join(
        (f"{len(bs)}개 부두" if len(bs) > 3 else "·".join("#" + b for b in bs)) + " " + ", ".join(f"{s:%m/%d %H:%M}~{e:%m/%d %H:%M}" for s, e in ps)
        for ps, bs in sorted(same.items(), key=lambda x: -len(x[1])))
    return {
        "source": fc.source, "t0": mins(hours[0].time) if hours else 0,
        "wind": [h.wind for h in hours], "thunder": [int(h.thunder) for h in hours],
        "stagnation": [int(h.stagnation) for h in hours], "typhoon": [int(h.typhoon or hit(h)) for h in hours],
        "groups": groups, "berth_group": {b: berth_group(b) for b in table.berths},
        "berths": {b: {"stop": span(fc.stops(b)), "unberth": span(fc.unberths(b))} for b in table.berths},
        "typhoon_text": typhoon_text(fc.typhoons),
        "track": None if fc.track is None else {
            "source": fc.track.source, "summary": summary,
            "status": [status_at(fc.track, h.time) for h in hours],  # 정시 보간 위치 · SK 부두 대표 지점 기준 (hourly.csv와 같음)
        },
    }


def base_payload(table: FeasibilityTable, costs: dict[tuple[str, str], CostRow], base: ScenarioResult, ts=None,
                 data=None) -> dict:
    s = table.start
    mins = lambda t: int((t - s).total_seconds() // 60)  # noqa: E731
    before = []
    for o in base.outcomes:
        a = o.after
        before.append({"v": o.vessel.vessel_id, "b": o.vessel.berth, "eta": mins(o.vessel.eta), "etb": mins(o.etb),
                       "dir": int(direction(o.vessel.berth).total_seconds() // 60),
                       "ws": mins(a.work_start) if a else None, "wf": mins(a.work_finish) if a else None,
                       "etu": mins(a.etu) if a else None, "le": mins(a.laytime_end) if a else None,
                       "hose": mins(a.hose_off) if a else None, "fee": round(o.fee),
                       "cls": o.profile.ship_class, "cargo": o.profile.cargo_group})
    curves = {}
    for (vid, b), c in costs.items():
        curves.setdefault(vid, {})[b] = [[i * 5, c.fee[i]] for i in c.feasible_slots() if i % CURVE_EVERY == 0]
    return {
        "start": [s.year, s.month, s.day, s.hour, s.minute], "n_min": table.n_slots * int(table.step.total_seconds() // 60),
        "fee_before": round(base.total_fee), "before": before, "curves": curves,
        "weather": _weather_payload(table, data),
        "tanks": None if ts is None else {
            "meta": [{"name": t.name, "n": t.n_tanks, "cap": t.capacity, "lo": t.lo, "hi": t.hi, "init": t.initial,
                      "rate": round(t.rate_per_h, 1), "in": t.inflow, "out": t.outflow} for t in ts.tanks.values()],
            "before": _tank_series(ts, work_from_outcomes(base.outcomes, data)),
        },
        "defaults": {"tiers": TIERS, "per_tier": PER_TIER, "band": BAND, "min_diff": MIN_DIFF, "time_limit": TIME_LIMIT_S},
    }


def tier_payload(table: FeasibilityTable, costs: dict[tuple[str, str], CostRow], res: SolveResult, ts=None,
                 data=None) -> dict:
    """체선료 구간 계획 하나 (CP-SAT 결과 · 비용표 값)."""
    step_min = int(table.step.total_seconds() // 60)
    after = []
    for vid, a in res.assignments.items():
        c, i = costs[(vid, a.berth)], a.slot
        after.append({"v": vid, "b": a.berth, "etb": i * step_min,
                      "dir": int(direction(a.berth).total_seconds() // 60),
                      "ws": i * step_min + 60, "wf": c.etu[i] - 120,
                      "etu": c.etu[i], "le": c.laytime_end[i],
                      "hose": c.hose_off[i], "fee": a.fee})
    return {
        "tier": res.tier, "alt": res.alt, "diff_rep": res.diff_rep, "fee": res.total_fee, "moves": res.moves,
        "status": res.status, "proven": res.status == "OPTIMAL", "bound": res.best_bound, "wall": round(res.wall_s, 1),
        "waits": res.waits, "source": "CP-SAT", "infeasible": 0, "after": after,
        "tanks": None if ts is None else _tank_series(ts, plan_work(table, costs, res, data)),
    }


def build_html(base: dict, plans: list[dict], server: bool = False, band: float | None = None) -> str:
    data = {**base, "plans": plans, "server": server, "band_used": band}
    return PAGE.replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


PAGE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>체선료 구간 최적화</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#16202c;--mut:#667085;--line:#d0d5dd;--accent:#1d5fd1;--ok:#2e9e5b;--bad:#d64545;--wait:#98a2b3;--sel:#16202c;--berth:#7b61c9;--pump:#2e9e5b;--hose:#e3a008;--depart:#64748b}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f141a;--card:#161d25;--ink:#e6eaf0;--mut:#93a0b0;--line:#2c3743;--accent:#7aa7f5;--ok:#46c07c;--bad:#ef6b6b;--wait:#5d6b7c;--sel:#e6eaf0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif}
main{max-width:1440px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:0 0 4px}
.lead,.sub{color:var(--mut);margin:0 0 12px;font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-top:16px}
.run{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:end}.run label{display:flex;flex-direction:column;font-size:12px;color:var(--mut);gap:3px}
.run input.wide{width:340px}.run input{font:inherit;width:96px;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
button.primary{font:inherit;font-weight:600;padding:9px 18px;border-radius:10px;border:0;background:var(--accent);color:#fff;cursor:pointer}
button.primary:disabled{opacity:.5;cursor:default}
#progress{font-size:13px;color:var(--mut);min-height:20px;margin-top:8px}
.bar{height:6px;background:var(--line);border-radius:999px;overflow:hidden;margin-top:6px;max-width:520px}.bar i{display:block;height:100%;background:var(--accent);width:0;transition:width .4s}
.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;height:48px;padding:0 16px;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
.topbar h1{margin:0;font-size:18px}.topbar .cur{margin-left:auto;font-size:13px;color:var(--mut);font-variant-numeric:tabular-nums}.topbar .cur b{color:var(--ink)}
.layout{display:grid;grid-template-columns:300px minmax(0,1fr);align-items:start}
.side{position:sticky;top:48px;height:calc(100vh - 48px);display:flex;flex-direction:column;background:var(--card);border-right:1px solid var(--line)}
.side header{padding:14px 16px 6px}.side header h2{margin:0;display:flex;align-items:center;gap:8px}
.badge{min-width:20px;padding:0 6px;border-radius:999px;background:var(--accent);color:#fff;font-size:11px;line-height:20px;text-align:center}
.side .hint{padding:0 16px 10px;font-size:12px;color:var(--mut);border-bottom:1px solid var(--line)}
.ranks{list-style:none;margin:0;padding:8px;overflow-y:auto;flex:1}
.layout main{max-width:none;margin:0;min-width:0}
@media (max-width:900px){.layout{grid-template-columns:1fr}.side{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}.ranks{max-height:320px}}
.rank{display:grid;grid-template-columns:38px 1fr;gap:2px 10px;width:100%;text-align:left;font:inherit;color:inherit;background:none;border:1px solid transparent;border-radius:10px;padding:10px;cursor:pointer}
.rank:hover{background:var(--bg)}.rank[aria-current=true]{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 9%,transparent)}
.rank .no{grid-row:1/4;align-self:center;width:34px;height:34px;border-radius:9px;display:grid;place-items:center;font-weight:700;background:var(--bg);border:1px solid var(--line)}
.rank[aria-current=true] .no{background:var(--accent);color:#fff;border-color:var(--accent)}
.rank b{font-size:17px;font-variant-numeric:tabular-nums}.rank .m{font-size:12px;color:var(--mut)}.rank .st{font-size:11px;color:var(--ok);font-weight:600}
.ranks .empty{margin:8px}
.tier{margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--line)}.tier:last-child{border-bottom:0}
.tier-h{font-size:12px;font-weight:700;padding:4px 10px;color:var(--ink)}.tier-h span{font-weight:400;color:var(--mut);margin-left:6px}
.more{font:inherit;font-size:12px;color:var(--accent);background:none;border:0;padding:4px 10px 4px 58px;cursor:pointer;text-align:left;width:100%}
.more:hover{text-decoration:underline}.alts{padding-left:14px}.none{font-size:12px;color:var(--mut);padding:2px 10px 2px 58px}
.rank.sub .no{width:30px;height:30px;font-size:11px}.rank .st.alt{color:var(--mut)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.stat{border:1px solid var(--line);border-radius:12px;padding:10px 14px}.stat b{display:block;font-size:20px;font-variant-numeric:tabular-nums}.stat span{font-size:12px;color:var(--mut)}.stat.hero b{color:var(--ok)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12px;margin:6px 0 10px;align-items:center}
.legend i{display:inline-block;width:14px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.canvaswrap{overflow-x:auto}canvas{display:block}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);font-size:12px;padding:6px 8px;border-radius:6px;display:none;z-index:9;max-width:340px;white-space:pre-line}
.tablewrap{overflow:auto;max-height:560px;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:12.5px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{position:sticky;top:0;background:var(--card)}td.n{text-align:right;font-variant-numeric:tabular-nums}td.id{font-family:ui-monospace,Menlo,monospace;cursor:pointer;color:var(--accent)}
td.down{color:var(--ok)}td.up{color:var(--bad)}.mut{color:var(--mut)}.empty{color:var(--mut);padding:24px;text-align:center;border:1px dashed var(--line);border-radius:12px}
select{font:inherit;padding:5px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
h3{font-size:13px;margin:10px 0 2px}
.tanks{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.tank{border:1px solid var(--line);border-radius:10px;padding:10px}.tank b{font-size:13px}.tank .m{font-size:11.5px;color:var(--mut);margin:2px 0 6px}
.tank canvas{width:100%;height:120px}.tank .bad{color:var(--bad);font-size:11.5px;margin-top:4px}.tank .good{color:var(--ok);font-size:11.5px;margin-top:4px}
</style></head><body>
<div class="topbar"><h1>체선료 구간 최적화</h1><div class="cur" id="cur"></div></div>
<div class="layout"><aside class="side" aria-label="체선료 구간 목록"><header><h2>체선료 구간<span class="badge" id="badge" hidden></span></h2></header>
<div class="hint">구간마다 대표 1개, ▸를 누르면 같은 구간 대안. 누르면 오른쪽이 그 계획으로 바뀐다. 최적화 전(실제 부두·순서, 규칙 ETB) 체선료 <b id="fb"></b></div>
<ol class="ranks" id="ranks"></ol></aside>
<main>
<p class="lead">모든 계획을 CP-SAT으로 풀고, 모든 선박은 막는 이유(같은 부두 앞 선박 · 동일 화물 · #4 동시 접안 · 야간 도선 등)가 없으면 가장 이르게 접안한다(불필요한 대기 금지).
대표 = 체선료가 가장 적은 최적해(같으면 부두 변경 적은 것), 대안 = 체선료가 최적해 + 허용 범위 안이면서 최적해와 선박 위치(부두)가 가장 많이 다른 순. 체선료는 가상 계약 데이터 기준이라 금액보다 비교로 본다.</p>

<section class="card"><h2>최적화 실행</h2>
<div class="run"><input id="k" type="hidden">
<label>계획 수 (최적해 포함)<input id="pt" type="number" min="1" max="5"></label>
<label>대안 허용 범위($)<input id="band" type="number" min="1" step="100"></label>
<label>계획 간 최소 차이(척)<input id="md" type="number" min="1" max="54"></label>
<label>계획 하나당 제한 시간(초)<input id="tl" type="number" min="5" max="600"></label>
<label>태풍 오는 시간 (그 시간 전 부두 접안 불가 · 여러 개는 쉼표)<input id="ty" type="text" class="wide" placeholder="예: 11/14 18:00~11/15 06:00"></label>
<button class="primary" id="go">최적화 실행</button></div>
<div id="progress"></div><div class="bar" id="bar" hidden><i></i></div></section>


<div id="detail">
<section class="card"><h2 id="dtitle">선택한 계획</h2><div class="stats" id="stats"></div></section>
<section class="card"><h2>1. 부두별 접안 일정 — 최적화 전 vs 선택한 계획</h2>
<p class="sub">회색 가는 선 = 도착 후 순수 대기, 보라색 = 이동·접안(Direction), 노란색 = 호스 연결·분리, 초록색 = 하역, 회색 막대 = 이안 준비. 막대 위 빨간 선은 체선료가 발생한 정박종료 이후 구간에만 표시되며 진할수록 금액이 큽니다. 점선 테두리 = 최적화 전과 부두가 다른 선박. 막대를 누르면 체선료 곡선으로 이동합니다.</p>
<div class="legend" id="legend"></div>
<p class="sub">간트 위에서 <b>Alt + 휠</b>로 마우스 위치 중심 가로 확대·축소 · 가로 스크롤로 이동 · 선박 클릭 시 체선료 곡선으로 이동</p>
<h3>최적화 전</h3><div class="canvaswrap"><canvas id="g0"></canvas></div>
<h3 id="g1t">선택한 계획</h3><div class="canvaswrap"><canvas id="g1"></canvas></div></section>
<section class="card"><h2>2. 바뀐 선박</h2><p class="sub">최적화 전 대비. 체선료 차이가 큰 순. '구간 대표와 다른 부두' 열은 대안을 볼 때 대표와 무엇이 다른지 보여준다.</p><div class="tablewrap" id="changes"></div></section>
<section class="card"><h2>3. 선박별 체선료 곡선</h2>
<p class="sub">후보 부두마다 "그 시각에 접안하면 체선료가 얼마인가"(비용표, 30분 간격). ○ 최적화 전, ◆ 선택한 계획. 끊긴 구간 = 접안 불가(야간 도선 등).</p>
<select id="pick" aria-label="선박 선택"></select><div class="legend" id="clegend"></div><div class="canvaswrap"><canvas id="curve"></canvas></div></section>
<section class="card" id="wxsec"><h2>4. 기상 예보 (풍속)</h2>
<p class="sub" id="wxsub"></p>
<div class="legend"><span><i style="background:var(--accent);height:3px"></i>풍속 (m/s)</span><span><i style="background:#e3a008;height:2px"></i>하역작업 중단 기준 (#3~7 14 · #1~2·GAS 18)</span><span><i style="background:#d64545;height:2px"></i>접안 불가 기준 (#1~2·GAS 20 · #3~7 21)</span><span><i style="background:rgba(123,127,224,.35)"></i>심한 뇌우 · 대기 정체 (하역 중단)</span><span><i style="background:rgba(214,69,69,.4)"></i>태풍 (전 부두 접안 불가)</span></div>
<div class="canvaswrap"><canvas id="wx"></canvas></div></section>
<section class="card" id="tanksec"><h2>5. 탱크 재고</h2>
<p class="sub">탱크 1개 = 60만 배럴(≈ 8.2만 톤). 반입 탱크는 공정 처리량만큼 시간당 일정하게 줄고, 반출 탱크는 생산량만큼 일정하게 늘며, 선박 하역·선적은 작업 시간 동안 일정 속도로 반영. 초록 띠 = 안전 범위(20% 이상 80% 미만) — 최적화는 이 범위를 제약으로 지킨다.</p>
<div class="legend"><span><i style="background:var(--wait);height:2px"></i>최적화 전</span><span><i style="background:var(--accent);height:3px"></i>선택한 계획</span><span><i style="background:color-mix(in srgb,var(--ok) 18%,transparent)"></i>안전 범위</span></div>
<div class="tanks" id="tanks"></div></section>
</div>
<div id="tip"></div>
<script type="application/json" id="data">/*DATA*/</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
let S = Date.UTC(D.start[0], D.start[1]-1, D.start[2], D.start[3], D.start[4]);
const $ = id => document.getElementById(id);
const pad = x => String(x).padStart(2,'0');
const fmt = m => { const t = new Date(S + m*60000); return `${pad(t.getUTCMonth()+1)}/${pad(t.getUTCDate())} ${pad(t.getUTCHours())}:${pad(t.getUTCMinutes())}`; };
const money = x => (x < 0 ? '−$' : '$') + Math.abs(Math.round(x)).toLocaleString();
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const tip = $('tip');
const showTip = (e, t) => { tip.textContent = t; tip.style.display = 'block'; tip.style.left = Math.min(e.clientX + 12, innerWidth - 350) + 'px'; tip.style.top = (e.clientY + 12) + 'px'; };
const hideTip = () => tip.style.display = 'none';
let B = Object.fromEntries(D.before.map(x => [x.v, x]));
let plans = D.plans || [], sel = plans.length ? 0 : -1;
$('fb').textContent = money(D.fee_before);
$('ty').value = (D.weather && D.weather.typhoon_text) || '';
// 서버에서 태풍 입력이 바뀌면 최적화 전 계획 · 비용표 · 예보가 새로 만들어진다 → 화면 기준 데이터 교체
function applyBase(nb) {
  for (const k of ['start', 'n_min', 'fee_before', 'before', 'curves', 'weather', 'tanks', 'base_ver']) D[k] = nb[k];
  S = Date.UTC(D.start[0], D.start[1]-1, D.start[2], D.start[3], D.start[4]);
  B = Object.fromEntries(D.before.map(x => [x.v, x]));
  $('fb').textContent = money(D.fee_before);
  const keep = $('pick').value; fillPick(); if (B[keep]) $('pick').value = keep;
}
for (const [id, k] of [['k', 'tiers'], ['pt', 'per_tier'], ['band', 'band'], ['md', 'min_diff'], ['tl', 'time_limit']]) $(id).value = D.defaults[k];
D.band_used = D.band_used || D.defaults.band;

// ── 실행 버튼 ──
const SERVER = D.server && location.protocol.startsWith('http');
if (!SERVER) { $('go').disabled = true; $('progress').innerHTML = '버튼을 쓰려면 서버로 여세요: <code>.venv/bin/python serve_cpsat.py</code> → http://127.0.0.1:8765 (지금은 마지막 실행 결과만 표시)'; }
const params = () => ({tiers: +$('k').value, per_tier: +$('pt').value, band: +$('band').value, min_diff: +$('md').value,
  time_limit: +$('tl').value, typhoon: $('ty').value});
if (!SERVER) $('ty').disabled = true;
$('go').onclick = async () => {
  $('go').disabled = true; plans = []; sel = -1; render();
  const r = await fetch('/api/optimize', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(params())});
  if (!r.ok) { $('progress').textContent = '실행 실패: ' + await r.text(); $('go').disabled = false; return; }
  poll();
};
async function poll() {
  const st = await (await fetch('/api/status')).json();
  if (st.base_ver !== undefined && st.base_ver !== D.base_ver) applyBase(await (await fetch('/api/base')).json());
  plans = st.plans; if (sel < 0 && plans.length) sel = 0; if (st.band) D.band_used = st.band;
  if (st.state === 'running') { $('bar').hidden = false; $('bar').firstElementChild.style.width = (100 * (st.frac || 0)) + '%'; }
  $('progress').textContent = st.state === 'running' ? `${st.message || '실행 중'}… (경과 ${st.elapsed.toFixed(0)}초)` :
    st.state === 'done' ? `완료 · 체선료 구간 ${new Set(plans.map(p => p.tier)).size}개 · 계획 ${plans.length}개 · ${st.elapsed.toFixed(0)}초 (${st.message})` :
    st.state === 'idle' ? '조건을 정하고 최적화 실행을 누르세요.' : st.message;
  render();
  if (st.state === 'running') { $('go').disabled = true; setTimeout(poll, 1000); } else { $('go').disabled = false; setTimeout(() => $('bar').hidden = true, 800); }
}

// ── 체선료 구간 목록 (왼쪽 고정): 구간마다 대표 1개, 대안은 펼쳐서 ──
const open = new Set();
function item(p, i) {
  const rep = plans.find(q => q.tier === p.tier && q.alt === 0);
  const head = p.alt === 0 ? `<span class="st">${p.proven ? '최적 증명' : '시간 제한 내 최선'}</span>` : `<span class="st alt">대안 ${p.alt} · 대표와 ${p.diff_rep}척 다름${p.proven ? '' : ' · 시간 제한 내 최선'}</span>`;
  const sub = p.alt === 0
    ? (p.tier === 1 ? `부두 변경 ${p.moves}척 · 최적화 전 대비 ${money(p.fee - D.fee_before)}` : `부두 변경 ${p.moves}척 · 1구간 대비 +${money(p.fee - plans[0].fee).slice(1)}`)
    : `부두 변경 ${p.moves}척 · 대표 대비 ${p.fee - rep.fee >= 0 ? '+' : ''}${money(p.fee - rep.fee)}`;
  return `<button class="rank${p.alt ? ' sub' : ''}" aria-current="${i === sel}" data-i="${i}"><span class="no">${p.alt ? p.tier + '-' + (p.alt + 1) : p.tier}</span>${head}<b>${money(p.fee)}</b><span class="m">${sub}</span></button>`;
}
function renderRanks() {
  const tiers = [...new Set(plans.map(p => p.tier))];
  $('ranks').innerHTML = plans.length ? tiers.map(t => {
    const members = plans.map((p, i) => [p, i]).filter(([p]) => p.tier === t), [rep, ri] = members[0], alts = members.slice(1);
    const isOpen = open.has(t) || alts.some(([, i]) => i === sel);
    return `<li class="tier"><div class="tier-h">${t}구간 <span>${money(rep.fee)} ~ ${money(rep.fee + D.band_used - 1)}</span></div>${item(rep, ri)}` +
      (alts.length ? `<button class="more" data-t="${t}" aria-expanded="${isOpen}">${isOpen ? '▾' : '▸'} 같은 구간 대안 ${alts.length}개 (선박 위치가 많이 바뀐 순)</button>` +
        `<div class="alts"${isOpen ? '' : ' hidden'}>${alts.map(([p, i]) => item(p, i)).join('')}</div>` : '<div class="none">같은 구간 대안 없음</div>') + '</li>';
  }).join('') : `<li class="empty">아직 결과가 없습니다.${SERVER ? ' 최적화 실행을 누르세요.' : ''}</li>`;
  $('ranks').querySelectorAll('.rank').forEach(b => b.onclick = () => { sel = +b.dataset.i; render(); });
  $('ranks').querySelectorAll('.more').forEach(b => b.onclick = () => { const t = +b.dataset.t; open.has(t) ? open.delete(t) : open.add(t); renderRanks(); });
  $('badge').hidden = !plans.length; $('badge').textContent = tiers.length;
  $('cur').innerHTML = sel >= 0 ? `보는 중 <b>${label(plans[sel])} · ${money(plans[sel].fee)}</b> · 부두 변경 ${plans[sel].moves}척` : '';
}
const label = p => p.alt ? `${p.tier}구간 대안 ${p.alt}` : `${p.tier}구간 대표`;

function render() {
  renderRanks();
  $('detail').hidden = sel < 0; if (sel < 0) return;
  const P = plans[sel], A = Object.fromEntries(P.after.map(x => [x.v, x]));
  $('dtitle').textContent = `${label(P)} 상세`; $('g1t').textContent = label(P);
  const cut = D.fee_before - P.fee;
  $('stats').innerHTML = [
    ['', money(D.fee_before), '최적화 전 체선료 합계'],
    ['hero', money(P.fee), `${label(P)} 체선료 (−${money(cut).slice(1)}, −${(cut / D.fee_before * 100).toFixed(0)}%)`],
    ['', P.proven ? '최적 증명' : '시간 제한 내 최선', P.alt ? `조건(같은 구간 · 대표와 최대한 다르게) 안에서 · ${P.wall}초` : (P.bound != null ? `CP-SAT 하한 ${money(P.bound)} · ${P.wall}초` : `${P.wall}초`)],
    ['', P.moves + '척', `부두 변경 / ${P.after.length}척`],
    P.alt ? ['', P.diff_rep + '척', '구간 대표와 부두가 다른 선박'] : ['', P.waits + '척', '불필요한 대기 (결과 직접 검사)'],
  ].map(([c, b, s]) => `<div class="stat ${c}"><b>${b}</b><span>${s}</span></div>`).join('');
  drawAll(A, P);
}

// ── 간트 ──
const GUT = 70, AX = 26, RH = 26;
let GZOOM = 1, LAST_GANTT = null;
function feeColorFn(maxFee) { return f => f <= 0 ? css('--ok') : `color-mix(in srgb, ${css('--bad')} ${Math.round(35 + 65 * Math.sqrt(f / maxFee))}%, ${css('--card')})`; }
function gantt(id, rows, isAfter, berths, t0, t1, feeColor, maxFee) {
  const cv = $(id), dpr = devicePixelRatio || 1, W = Math.round(Math.max(cv.parentElement.clientWidth, 1000) * GZOOM), H = AX + berths.length * RH + 6;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + 'px'; cv.style.height = H + 'px';
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
  const X = m => GUT + (W - GUT - 8) * (m - t0) / (t1 - t0);
  ctx.font = '11px -apple-system, sans-serif'; ctx.strokeStyle = css('--line'); ctx.fillStyle = css('--mut');
  const off = D.start[3]*60 + D.start[4], day0 = Math.ceil((t0 + off) / 1440) * 1440 - off;
  for (let m = day0; m < t1; m += 1440) { ctx.beginPath(); ctx.moveTo(X(m), AX - 4); ctx.lineTo(X(m), H); ctx.stroke(); ctx.fillText(fmt(m).slice(0, 5), X(m) + 3, AX - 8); }
  if (D.weather) berths.forEach((b, k) => { const g = (D.weather.berths || {})[b] || D.weather.groups[D.weather.berth_group[b]]; if (!g) return;
    for (const [s, e] of g.stop) { ctx.fillStyle = 'rgba(227,160,8,.16)'; ctx.fillRect(X(s), AX + k * RH, X(e) - X(s), RH); }
    for (const [s, e] of g.unberth) { ctx.fillStyle = 'rgba(214,69,69,.28)'; ctx.fillRect(X(s), AX + k * RH, X(e) - X(s), RH); } });
  berths.forEach((b, k) => { ctx.fillStyle = css('--ink'); ctx.font = '12px ui-monospace, Menlo, monospace'; ctx.fillText('#' + b, 6, AX + k * RH + 17);
    ctx.strokeStyle = css('--line'); ctx.globalAlpha = .5; ctx.beginPath(); ctx.moveTo(GUT, AX + (k + 1) * RH); ctx.lineTo(W, AX + (k + 1) * RH); ctx.stroke(); ctx.globalAlpha = 1; });
  const hits = [];
  for (const r of rows) { if (r.etu == null) continue; const k = berths.indexOf(r.b), y = AX + k * RH + 4, eta = B[r.v].eta;
    const dirStart = Math.max(eta, r.etb - r.dir);
    ctx.strokeStyle = css('--wait'); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(X(eta), y + 9); ctx.lineTo(X(dirStart), y + 9); ctx.stroke();
    ctx.fillStyle = css('--berth'); ctx.fillRect(X(dirStart), y, Math.max(3, X(r.etb) - X(dirStart)), RH - 8);
    const x0 = X(r.etb), w = Math.max(2, X(r.etu) - x0), phases = [
      [r.etb, r.ws, '--hose'], [r.ws, r.wf, '--pump'], [r.wf, r.hose, '--hose'], [r.hose, r.etu, '--depart']
    ];
    for (const [s, e, color] of phases) { if (s == null || e == null || e <= s) continue; ctx.fillStyle = css(color); ctx.fillRect(X(s), y, Math.max(1, X(e) - X(s)), RH - 8); }
    const feeStart = Math.max(r.etb, r.le), feeEnd = Math.min(r.hose, r.etu);
    if (r.fee > 0 && feeEnd > feeStart) { ctx.fillStyle = feeColor(r.fee); ctx.fillRect(X(feeStart), y, Math.max(2, X(feeEnd) - X(feeStart)), 3); }
    if (isAfter && r.b !== B[r.v].b) { ctx.strokeStyle = css('--sel'); ctx.lineWidth = 2; ctx.setLineDash([4, 3]); ctx.strokeRect(x0 + 1, y + 1, w - 2, RH - 10); ctx.setLineDash([]); }
    if (w > 34) { ctx.fillStyle = r.fee > maxFee * .3 ? '#fff' : css('--ink'); ctx.font = '10.5px ui-monospace, Menlo, monospace'; ctx.fillText(r.v, x0 + 3, y + 12); }
    hits.push({r, x0, x1: x0 + w, y0: y, y1: y + RH - 8}); }
  const find = e => { const bb = cv.getBoundingClientRect(), x = e.clientX - bb.left, y = e.clientY - bb.top; return hits.find(h => x >= h.x0 && x <= h.x1 && y >= h.y0 && y <= h.y1); };
  cv.onmousemove = e => { const h = find(e); if (!h) return hideTip(); const r = h.r, b0 = B[r.v];
    const ds = Math.max(b0.eta, r.etb-r.dir); showTip(e, `${r.v} · ${b0.cls} · ${b0.cargo}\n#${r.b}${isAfter && r.b !== b0.b ? ` (전 #${b0.b})` : ''}\nETA ${fmt(b0.eta)} · 순수 대기 ${((ds-b0.eta)/60).toFixed(1)}h\n이동·접안 ${fmt(ds)}~${fmt(r.etb)} (${((r.etb-ds)/60).toFixed(1)}h) · ETB ${fmt(r.etb)}\n호스 연결·준비 ${fmt(r.etb)}~${fmt(r.ws)} (${((r.ws-r.etb)/60).toFixed(1)}h)\n하역 ${fmt(r.ws)}~${fmt(r.wf)} (${((r.wf-r.ws)/60).toFixed(1)}h)\n호스 분리 ${fmt(r.wf)}~${fmt(r.hose)} (${((r.hose-r.wf)/60).toFixed(1)}h)\n이안 준비 ${fmt(r.hose)}~${fmt(r.etu)} · ETU ${fmt(r.etu)}\n정박종료 ${fmt(r.le)} · 체선료 ${money(r.fee)}`); };
  cv.onmouseleave = hideTip; cv.onclick = e => { const h = find(e); if (h) show(h.r.v); };
  cv.onwheel = e => { if (!e.altKey || !LAST_GANTT) return; e.preventDefault();
    const wrap = cv.parentElement, rect = wrap.getBoundingClientRect(), px = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, (wrap.scrollLeft + px - GUT) / Math.max(1, W - GUT - 8)));
    const next = Math.max(1, Math.min(8, GZOOM * (e.deltaY < 0 ? 1.25 : .8))); if (next === GZOOM) return;
    GZOOM = next; const state = LAST_GANTT; drawGantts(state.P);
    const nw = cv.getBoundingClientRect().width; wrap.scrollLeft = Math.max(0, GUT + ratio * (nw - GUT - 8) - px); };
}

// ── 바뀐 선박 표 ──
function changes(P, A) {
  const repP = plans.find(q => q.tier === P.tier && q.alt === 0) || P, first = Object.fromEntries(repP.after.map(a => [a.v, a.b]));
  const rows = P.after.map(a => ({a, b: B[a.v], d: a.fee - B[a.v].fee})).filter(x => x.a.b !== x.b.b || x.a.etb !== x.b.etb || x.d || first[x.a.v] !== x.a.b).sort((x, y) => x.d - y.d);
  $('changes').innerHTML = '<table><thead><tr><th>선박</th><th>등급 · 화물</th><th>부두</th><th>구간 대표와 다른 부두</th><th>ETA</th><th>ETB 전 → 후</th><th>대기 전 → 후</th><th>체선료 전</th><th>체선료 후</th><th>차이</th></tr></thead><tbody>' +
    rows.map(({a, b, d}) => `<tr><td class="id" data-v="${a.v}">${a.v}</td><td class="mut">${b.cls} · ${b.cargo}</td><td>${a.b !== b.b ? `#${b.b} → <b>#${a.b}</b>` : '#' + a.b}</td>` +
      `<td>${P.alt && first[a.v] !== a.b ? `대표 #${first[a.v]}` : '<span class="mut">—</span>'}</td><td>${fmt(b.eta)}</td>` +
      `<td>${fmt(b.etb)} → <b>${fmt(a.etb)}</b></td><td class="n">${((b.etb - b.eta)/60).toFixed(1)}h → ${((a.etb - b.eta)/60).toFixed(1)}h</td>` +
      `<td class="n">${money(b.fee)}</td><td class="n"><b>${money(a.fee)}</b></td><td class="n ${d < 0 ? 'down' : d > 0 ? 'up' : ''}">${d > 0 ? '+' : ''}${money(d)}</td></tr>`).join('') + '</tbody></table>';
  $('changes').onclick = e => { const td = e.target.closest('td[data-v]'); if (td) show(td.dataset.v); };
}

// ── 체선료 곡선 ──
const PAL = ['#1d5fd1', '#e3a008', '#2e9e5b', '#d64545', '#7b5cd6', '#0e9aa7', '#c2410c', '#64748b', '#be185d'];
function show(v) { $('pick').value = v; curve(v); $('curve').scrollIntoView({behavior: 'smooth', block: 'center'}); }
function curve(v) {
  if (sel < 0) return; const A = Object.fromEntries(plans[sel].after.map(x => [x.v, x]));
  const cv = $('curve'), dpr = devicePixelRatio || 1, W = Math.max(cv.parentElement.clientWidth, 900), H = 320, L = 70, R = 12, T = 14, Bm = 30;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + 'px'; cv.style.height = H + 'px';
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
  const C = D.curves[v], bs = Object.keys(C), b0 = B[v], a = A[v];
  const x0 = b0.eta - 120, x1 = Math.min(D.n_min, Math.max(a.etb, b0.etb) + 2 * 1440);
  const pts = bs.flatMap(b => C[b]).filter(p => p[0] <= x1), ymax = Math.max(1, ...pts.map(p => p[1]), b0.fee, a.fee) * 1.08;
  const X = m => L + (W - L - R) * (m - x0) / (x1 - x0), Y = f => T + (H - T - Bm) * (1 - f / ymax);
  ctx.strokeStyle = css('--line'); ctx.fillStyle = css('--mut'); ctx.font = '11px -apple-system, sans-serif';
  for (let k = 0; k <= 4; k++) { const f = ymax * k / 4; ctx.globalAlpha = .5; ctx.beginPath(); ctx.moveTo(L, Y(f)); ctx.lineTo(W - R, Y(f)); ctx.stroke(); ctx.globalAlpha = 1; ctx.fillText(money(f), 4, Y(f) + 4); }
  const off = D.start[3]*60 + D.start[4];
  for (let m = Math.ceil((x0 + off) / 720) * 720 - off; m < x1; m += 720) ctx.fillText(fmt(m), X(m) - 28, H - 10);
  $('clegend').innerHTML = bs.map((b, k) => `<span><i style="background:${PAL[k % PAL.length]}"></i>#${b}${b === b0.b ? ' (실제)' : ''}${b === a.b ? ' ★' : ''}</span>`).join('');
  bs.forEach((b, k) => { ctx.strokeStyle = PAL[k % PAL.length]; ctx.lineWidth = 2; ctx.beginPath(); let prev = null;
    for (const [m, f] of C[b]) { if (m > x1) break; if (prev === null || m - prev > 30) ctx.moveTo(X(m), Y(f)); else ctx.lineTo(X(m), Y(f)); prev = m; } ctx.stroke(); });
  const mark = (m, f, shape, b) => { const k = bs.indexOf(b); ctx.fillStyle = PAL[k % PAL.length]; ctx.strokeStyle = css('--ink'); ctx.lineWidth = 2; ctx.beginPath();
    if (shape === 'o') ctx.arc(X(m), Y(f), 6, 0, 7); else { ctx.moveTo(X(m), Y(f) - 8); ctx.lineTo(X(m) + 8, Y(f)); ctx.lineTo(X(m), Y(f) + 8); ctx.lineTo(X(m) - 8, Y(f)); ctx.closePath(); }
    ctx.fill(); ctx.stroke(); };
  ctx.strokeStyle = css('--wait'); ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(X(b0.eta), T); ctx.lineTo(X(b0.eta), H - Bm); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = css('--mut'); ctx.fillText('ETA', X(b0.eta) + 4, T + 10);
  if (C[b0.b]) mark(b0.etb, b0.fee, 'o', b0.b); mark(a.etb, a.fee, 'd', a.b);
  cv.onmousemove = e => { const bb = cv.getBoundingClientRect(), m = x0 + (e.clientX - bb.left - L) / (W - L - R) * (x1 - x0);
    const lines = bs.map(b => { const p = C[b].reduce((best, q) => Math.abs(q[0] - m) < Math.abs(best[0] - m) ? q : best, C[b][0]); return Math.abs(p[0] - m) <= 30 ? `#${b}: ${money(p[1])}` : `#${b}: 접안 불가`; });
    showTip(e, `${fmt(Math.round(m / 5) * 5)} 접안 시\n` + lines.join('\n')); };
  cv.onmouseleave = hideTip;
}
function fillPick() { $('pick').innerHTML = D.before.map(x => `<option value="${x.v}">${x.v} · ${x.cls} · ${x.cargo} · 최적화 전 ${money(x.fee)}</option>`).join(''); }
fillPick();
$('pick').onchange = () => curve($('pick').value);

function drawAll(A, P) {
  LAST_GANTT = {A, P};
  drawGantts(P);
  changes(P, A);
  tanksDraw(P);
  weatherDraw();
  if (!$('pick').dataset.init) { const best = [...P.after].sort((x, y) => (x.fee - B[x.v].fee) - (y.fee - B[y.v].fee))[0]; $('pick').value = best.v; $('pick').dataset.init = 1; }
  curve($('pick').value);
}
function drawGantts(P) {
  const rowsAll = [...D.before, ...P.after], berths = [...new Set(rowsAll.map(x => x.b))].sort((a, b) => a.localeCompare(b, 'en', {numeric: true}));
  const t0 = Math.min(0, ...D.before.map(x => x.eta)), t1 = Math.max(...rowsAll.map(x => x.etu || 0)) + 60;
  const maxFee = Math.max(1, ...rowsAll.map(x => x.fee)), feeColor = feeColorFn(maxFee);
  $('legend').innerHTML = `<span><i style="background:var(--berth)"></i>이동·접안(Direction)</span><span><i style="background:var(--hose)"></i>호스 연결·분리</span><span><i style="background:var(--pump)"></i>하역</span><span><i style="background:var(--depart)"></i>이안 준비</span>` +
    `<span><i style="background:var(--wait);height:2px"></i>도착 후 대기</span><span><i style="background:none;border:2px dashed var(--sel);height:12px"></i>부두 변경</span>` +
    `<span><i style="background:${feeColor(maxFee)};height:3px"></i>빨간 선 = 체선 발생 구간(정박종료→호스분리)</span>` +
    (D.weather ? `<span><i style="background:rgba(227,160,8,.35)"></i>하역작업 중단 (기상)</span><span><i style="background:rgba(214,69,69,.45)"></i>접안 불가 (강풍·태풍)</span>` : '');
  gantt('g0', D.before, false, berths, t0, t1, feeColor, maxFee); gantt('g1', P.after, true, berths, t0, t1, feeColor, maxFee);
}
function weatherDraw() {
  const Wx = D.weather; $('wxsec').hidden = !Wx; if (!Wx) return;
  $('wxsub').textContent = `${Wx.source} · 하역 중단: 접안은 되고 작업만 멈춤(탱크 흐름 없음, 그만큼 ETU 지연) · 접안 불가: 그 시간에 부두에 있을 수 없음 (#8 · BUOY는 #3~7 기준 가정)` +
    (Wx.track ? ` · 태풍 경로 강풍반경 안 접안 불가: ${Wx.track.summary || '반경 안에 드는 부두 없음'}` : '');
  const cv = $('wx'), dpr = devicePixelRatio || 1, W = Math.max(cv.parentElement.clientWidth, 900), H = 200, L = 40, R = 10, T = 10, B = 26;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + 'px'; cv.style.height = H + 'px';
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
  const n = Wx.wind.length, ymax = Math.max(25, ...Wx.wind) * 1.05, X = k => L + (W - L - R) * k / Math.max(1, n - 1), Y = v => T + (H - T - B) * (1 - v / ymax);
  Wx.wind.forEach((_, k) => {
    const c = Wx.typhoon[k] ? 'rgba(214,69,69,.28)' : (Wx.thunder[k] || Wx.stagnation[k]) ? 'rgba(123,127,224,.25)' : null;
    if (c) { ctx.fillStyle = c; ctx.fillRect(X(k), T, (W - L - R) / n, H - T - B); } });
  ctx.font = '11px -apple-system, sans-serif'; ctx.fillStyle = css('--mut');
  for (const [v, c] of [[14, '#e3a008'], [18, '#e3a008'], [20, '#d64545'], [21, '#d64545']]) { ctx.strokeStyle = c; ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.moveTo(L, Y(v)); ctx.lineTo(W - R, Y(v)); ctx.stroke(); ctx.setLineDash([]); ctx.fillText(v, 8, Y(v) + 4); }
  const off = D.start[3] * 60 + D.start[4];
  for (let k = 0; k < n; k++) { const m = Wx.t0 + k * 60; if ((m + off) % 1440 === 0) { ctx.fillStyle = css('--mut'); ctx.fillText(fmt(m).slice(0, 5), X(k) + 2, H - 8); ctx.strokeStyle = css('--line'); ctx.beginPath(); ctx.moveTo(X(k), T); ctx.lineTo(X(k), H - B); ctx.stroke(); } }
  ctx.strokeStyle = css('--accent'); ctx.lineWidth = 2; ctx.beginPath(); Wx.wind.forEach((v, k) => k ? ctx.lineTo(X(k), Y(v)) : ctx.moveTo(X(k), Y(v))); ctx.stroke(); ctx.lineWidth = 1;
  cv.onmousemove = e => { const r = cv.getBoundingClientRect(), k = Math.max(0, Math.min(n - 1, Math.round((e.clientX - r.left - L) / (W - L - R) * (n - 1))));
    const flags = [Wx.thunder[k] && '심한 뇌우', Wx.stagnation[k] && '대기 정체', Wx.typhoon[k] && '태풍 경로'].filter(Boolean).join(' · ');
    const ty = Wx.track && Wx.track.status[k];
    const tyText = ty ? `\n태풍 ${ty.name}: SK 부두까지 ${ty.dist.toLocaleString()} km · 강풍반경 ${ty.rad.toLocaleString()} km${ty.dist <= ty.rad ? ' → 반경 안 (접안 불가)' : ''}` : '';
    showTip(e, `${fmt(Wx.t0 + k * 60)}  풍속 ${Wx.wind[k]} m/s${flags ? '\n' + flags : ''}${tyText}`); };
  cv.onmouseleave = hideTip;
}
function tanksDraw(P) {
  const T = D.tanks; $('tanksec').hidden = !T; if (!T) return;
  $('tanks').innerHTML = T.meta.map((t, i) => {
    const lv = (P.tanks || {})[t.name] ? P.tanks[t.name].lv : [], viol = (P.tanks || {})[t.name] ? P.tanks[t.name].viol : [];
    const pct = lv.length ? `${(Math.min(...lv) / t.cap * 100).toFixed(0)}% ~ ${(Math.max(...lv) / t.cap * 100).toFixed(0)}%` : '-';
    return `<div class="tank"><b>${t.name}</b> <span class="mut">${t.n}개 · ${(t.cap / 1000).toFixed(0)}천 t</span>` +
      `<div class="m">${t.rate < 0 ? '공정 처리' : '제품 생산'} ${Math.abs(t.rate).toLocaleString()} t/h · 기간 중 반입 ${t.in.toLocaleString()} t · 반출 ${t.out.toLocaleString()} t · 선택 계획 ${pct}</div>` +
      `<canvas id="tk${i}"></canvas>${viol.length ? `<div class="bad">범위 밖 ${viol.length}건: ${viol[0]}</div>` : '<div class="good">안전 범위 유지</div>'}</div>`;
  }).join('');
  T.meta.forEach((t, i) => {
    const cv = $('tk' + i), dpr = devicePixelRatio || 1, W = cv.clientWidth || 320, H = 120;
    cv.width = W * dpr; cv.height = H * dpr; const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const before = T.before[t.name].lv, after = (P.tanks || {})[t.name] ? P.tanks[t.name].lv : [];
    const n = before.length, X = k => 4 + (W - 8) * k / Math.max(1, n - 1), Y = v => 4 + (H - 8) * (1 - v / t.cap);
    ctx.fillStyle = `color-mix(in srgb, ${css('--ok')} 18%, transparent)`; ctx.fillRect(4, Y(t.hi), W - 8, Y(t.lo) - Y(t.hi));
    ctx.strokeStyle = css('--line'); ctx.strokeRect(4, 4, W - 8, H - 8);
    const line = (arr, color, w) => { if (!arr.length) return; ctx.strokeStyle = color; ctx.lineWidth = w; ctx.beginPath();
      arr.forEach((v, k) => k ? ctx.lineTo(X(k), Y(v)) : ctx.moveTo(X(k), Y(v))); ctx.stroke(); };
    line(before, css('--wait'), 1.5); line(after, css('--accent'), 2);
    cv.onmousemove = e => { const r = cv.getBoundingClientRect(), k = Math.max(0, Math.min(n - 1, Math.round((e.clientX - r.left - 4) / (W - 8) * (n - 1))));
      showTip(e, `${t.name} · ${fmt(k * 60)}\n최적화 전 ${Math.round(before[k]).toLocaleString()} t (${(before[k] / t.cap * 100).toFixed(0)}%)` +
        (after.length ? `\n선택 계획 ${Math.round(after[k]).toLocaleString()} t (${(after[k] / t.cap * 100).toFixed(0)}%)` : '')); };
    cv.onmouseleave = hideTip;
  });
}
render();
if (SERVER) poll(+$('k').value);  // 새로고침해도 진행 중이거나 끝난 결과를 이어서 보여줌
addEventListener('resize', render); matchMedia('(prefers-color-scheme: dark)').addEventListener('change', render);
</script></main></div></body></html>
"""
