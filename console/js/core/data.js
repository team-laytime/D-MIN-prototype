// 목업 데이터 불러오기 · 화면용으로 다듬기
// data/run.json 은 팀 수리계획법(docs/milp/ppt, ppt-milp/1.0)이 샘플 주간 54건으로 낸 실제 응답에서 왔다.
// 선박 이름 · MMSI · 호출부호 · 계약값은 가상이다 (N-211).
import { initClock, t, shiftText, fmtDate, D } from './time.js';

export const DB = {};

const get = (u) =>
  fetch(u).then((r) => {
    if (!r.ok) throw new Error(`${u} 응답 ${r.status}`);
    return r.json();
  });

function convPlan(p) {
  return {
    id: p.arrival_id,
    berth: p.berth,
    status: p.status,
    eta: t(p.eta),
    etb: t(p.etb),
    ws: t(p.work_start),
    we: t(p.work_end),
    hose: t(p.hose_off),
    etu: t(p.etu),
    ls: t(p.laytime_start),
    le: t(p.laytime_end),
    lsRule: p.laytime_rule,
    allowed: p.allowed_hours,
    weatherH: p.weather_hours,
    deductH: p.deduction_hours,
    demH: p.demurrage_hours,
    dem: p.demurrage_usd,
    wait: p.wait_hours,
    why: shiftText(p.why_etb),
    trace: (p.trace || []).map((s) => ({ rule: s.rule, text: shiftText(s.text) })),
  };
}

function convSet(s, kind) {
  const plans = s.plans.map(convPlan);
  const byId = Object.fromEntries(plans.map((p) => [p.id, p]));
  const violById = {};
  for (const v of s.violations || []) {
    const m = /^(S\d+):\s*(.*)$/.exec(v);
    if (m) (violById[m[1]] ??= []).push(shiftText(m[2]));
  }
  return { ...s, kind, plans, byId, violById, violations: (s.violations || []).map(shiftText) };
}

export async function loadData() {
  const [master, vessels, run, coast] = await Promise.all([
    get('data/master.json'),
    get('data/vessels.json'),
    get('data/run.json'),
    get('data/coastline.json').catch(() => null),
  ]);
  const clock = initClock(master.scenario.base_date);
  DB.clock = clock;
  DB.master = master;
  DB.coast = coast;
  DB.berths = master.berths;
  DB.berthById = Object.fromEntries(master.berths.map((b) => [b.id, b]));
  DB.anchorages = master.anchorages;
  DB.vessels = vessels.map((v) => ({
    ...v,
    etaMs: t(v.eta),
    ais: { ...v.ais, etaMs: t(v.ais.eta) },
    contract: { ...v.contract, from: t(v.contract.laycan_from), to: t(v.contract.laycan_to) },
    fix: v.fix ? { ...v.fix, etbMs: t(v.fix.etb), etuMs: t(v.fix.etu) } : null,
    // 지금 부두에서 작업 중인 배(이전 계획분). 이번 최적화 대상이 아니다
    prev: v.prev_call
      ? { berth: v.prev_call.berth, etbMs: t(v.prev_call.etb), wsMs: t(v.prev_call.ws), weMs: t(v.prev_call.we), hoseMs: t(v.prev_call.hose), etuMs: t(v.prev_call.etu) }
      : null,
  }));
  DB.vesselById = Object.fromEntries(DB.vessels.map((v) => [v.id, v]));
  DB.planVessels = DB.vessels.filter((v) => !v.prev);
  // 화면 표 · 타임라인용: 작업 중(이전 계획) 배를 계획 줄 모양으로
  DB.inportPlans = DB.vessels.filter((v) => v.prev).map((v) => ({
    id: v.id, berth: v.prev.berth, status: 'IN_PORT', eta: v.etaMs, etb: v.prev.etbMs, ws: v.prev.wsMs, we: v.prev.weMs, hose: v.prev.hoseMs, etu: v.prev.etuMs,
    ls: v.prev.etbMs, le: v.prev.etbMs + v.contract.laytime_h * 3600e3, allowed: v.contract.laytime_h, weatherH: 0, deductH: 0, demH: 0, dem: 0,
    wait: Math.max(0, Math.round(((v.prev.etbMs - v.etaMs) / 3600e3) * 10) / 10), why: '이전 계획 (확정)', trace: [], inport: true,
  }));

  const sets = {};
  for (const [k, s] of Object.entries(run.reference)) sets[k] = convSet(s, 'reference');
  for (const c of run.candidates) sets[c.key] = convSet(c, 'candidate');
  DB.sets = sets;
  DB.run = {
    ...run,
    planStart: t(run.plan_window.start),
    planEnd: t(run.plan_window.end),
    candidateKeys: run.candidates.map((c) => c.key),
  };
  DB.tides = Object.fromEntries(master.tides.map((x) => [fmtDate(t(`${x.date}T00:00`)), x]));
  DB.planStart = clock.planStart;
  return DB;
}

export const vesselName = (id) => DB.vesselById[id]?.name ?? id;
export const berthLabel = (id) => DB.berthById[id]?.label ?? id;
export const setLabel = (k) => {
  const s = DB.sets[k];
  if (!s) return k;
  return s.kind === 'candidate' ? `${s.label} · ${s.name}` : s.label;
};

/** 두 계획 사이 바뀐 선박 (부두 · 접안 시각) */
export function diffPlans(fromSet, toSet) {
  const out = [];
  for (const p of toSet.plans) {
    const q = fromSet.byId[p.id];
    if (!q) continue;
    const berthChanged = q.berth !== p.berth;
    const timeChanged = q.etb !== p.etb;
    if (berthChanged || timeChanged) {
      out.push({ id: p.id, from: q, to: p, berthChanged, timeChanged, delta: Math.round((p.dem - q.dem) * 100) / 100 });
    }
  }
  out.sort((a, b) => a.delta - b.delta || a.id.localeCompare(b.id));
  return out;
}

export const dayStart = (ms) => Math.floor(ms / D) * D;
