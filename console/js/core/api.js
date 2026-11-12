// 목업 API — 실제 솔루션의 REST 계약(docs/api.md)과 같은 일을 브라우저 안에서 한다.
// 서버가 붙으면 이 파일의 함수만 fetch 로 바꾼다. 화면 코드는 그대로 둔다.
//
//   함수                     실제 엔드포인트 (Spring)
//   vesselsNow()             GET  /api/v1/vessels            (AIS 마지막 위치 + PORT-MIS + 적용 계획)
//   etaAlerts()              GET  /api/v1/alerts/eta         (AIS ETA와 계획 입력 ETA 차이)
//   versions()               GET  /api/v1/schedule/versions
//   appliedSet()             GET  /api/v1/schedule?from&to   (승인되어 적용 중인 계획)
//   startRun()               POST /api/v1/optimizations      → 202 {job_id} · GET …/events (SSE)
//   reports() · report(id)   GET  /api/v1/reports[/{id}]
//   createReport(runId)      POST /api/v1/reports
//   submitReport(id)         POST /api/v1/reports/{id}/submit
//   decide(id, …)            POST /api/v1/approvals/{reportId}  (승인권자만, Agent 도구 목록에는 없음 — NFR-17)
//   sources()                GET  /api/v1/sources/status
import { DB, diffPlans } from './data.js';
import { state, update, appendLog, role } from './store.js';
import { nowMs, H, MIN, fmtDate, fmtDT } from './time.js';
import { aisOf } from './ais.js';

export const ETA_ALERT_H = 2; // AIS ETA가 계획 입력 ETA와 이만큼 넘게 다르면 '다시 계산 필요' (N-002)

export const appliedVersion = () => state().versions[state().versions.length - 1];
export const appliedSet = () => DB.sets[appliedVersion().set];
export const versions = () => state().versions;

/** 화면 표시용 계획: 적용 계획 + 지금 부두에서 작업 중인 배(이전 계획분) */
export function displaySet(set = appliedSet()) {
  const plans = [...DB.inportPlans, ...set.plans];
  return { ...set, plans, byId: { ...set.byId, ...Object.fromEntries(DB.inportPlans.map((p) => [p.id, p])) } };
}
export const latestRun = () => state().runs[state().runs.length - 1];

/** 선박 목록: 선박 · 적용 계획 줄 · AIS 상태 · ETA 차이 */
export function vesselsNow(now = nowMs()) {
  const set = displaySet();
  return DB.vessels
    .map((v) => {
      const plan = set.byId[v.id] ?? null;
      const ais = aisOf(v, plan, now);
      const diff = v.ais.etaMs - v.etaMs;
      const alert = Math.abs(diff) >= ETA_ALERT_H * H && ais.nav === 'underway';
      return { v, plan, ais, etaDiff: diff, alert };
    })
    .sort((a, b) => a.v.etaMs - b.v.etaMs);
}

export const etaAlerts = (now) => vesselsNow(now).filter((r) => r.alert);

/** 실행 결과가 지금 입력과 어긋나는가 (ETA 변경 감지) */
export function runIsStale() {
  return etaAlerts().length > 0;
}

export function reports() {
  return [...state().reports].sort((a, b) => b.created_at - a.created_at);
}
export const report = (id) => state().reports.find((r) => r.id === id);
export const pendingApprovals = () => reports().filter((r) => r.status === 'requested');

export function createReport(runId, recommended = 'c1') {
  const now = nowMs();
  const day = fmtDate(now).slice(5).replace('-', '');
  const n = state().reports.filter((r) => r.id.startsWith(`RPT-${day}`)).length + 1;
  const id = `RPT-${day}-${String(n).padStart(2, '0')}`;
  const run = state().runs.find((r) => r.run_id === runId) ?? latestRun();
  update((s) => {
    s.reports.push({
      id, run_id: run.run_id, title: '주간 접안 계획 검토', status: 'draft', recommended,
      created_at: now, created_by: role().name, submitted_at: null, input_at: run.input_at, note: '',
      llm: { calls: 2, tokens_in: 2874, tokens_out: 538, cost_usd: 0.04, fallback: false },
      decision: null,
    });
    appendLog({ action: '보고서 작성', target: id, detail: `실행 ${run.run_id} · 추천 ${DB.sets[recommended].label}` });
  });
  return id;
}

export function submitReport(id, note) {
  update((s) => {
    const r = s.reports.find((x) => x.id === id);
    r.status = 'requested';
    r.submitted_at = nowMs();
    if (note != null) r.note = note;
    appendLog({ action: '승인 요청', target: id, detail: `추천 ${DB.sets[r.recommended].label}` });
  });
}

/**
 * 승인 · 반려. 승인하면 새 계획 버전이 생기고 Berthing Schedule이 그 버전을 보여 준다.
 * 결정 기록은 그때의 입력 기준 시각 · 실행 ID · 규칙 · 엔진 버전에 묶인다 (N-004).
 */
export async function decide(id, { action, candidate, reason, reasonType, risksChecked = [], staleAck = false }) {
  if (!role().can.approve) throw new Error('승인 권한이 없습니다');
  await new Promise((r) => setTimeout(r, 450));
  const now = nowMs();
  let newVersion = null;
  update((s) => {
    const r = s.reports.find((x) => x.id === id);
    r.decision = { action, candidate, reason, reason_type: reasonType, by: role().name, role: role().title, at: now, risks_checked: risksChecked, stale_ack: staleAck };
    if (action === 'approve') {
      r.status = 'approved';
      const set = DB.sets[candidate];
      newVersion = {
        no: s.versions.length + 1, set: candidate, label: `${set.label} · ${set.name}`, applied_at: now, applied_by: role().name, role: role().title,
        run_id: r.run_id, report_id: r.id, reason, reason_type: reasonType, input_at: r.input_at,
        rules_version: DB.run.engine.rules_version, engine_version: DB.run.engine.version, stale_ack: staleAck,
      };
      s.versions.push(newVersion);
      appendLog({ action: '승인', target: id, detail: `${set.label}(${set.name}) · 사유 유형 ${reasonType} · ${reason}` });
      appendLog({ action: '계획 적용', target: `v${newVersion.no} ${newVersion.label}`, detail: `실행 ${r.run_id} · 입력 기준 ${fmtDT(r.input_at)}` });
    } else {
      r.status = 'rejected';
      appendLog({ action: '반려', target: id, detail: reason });
    }
  });
  return newVersion;
}

/** 후보 계산 (목업): 진행 단계를 SSE처럼 흘리고, 미리 계산해 둔 결과를 돌려준다 */
export async function startRun(onEvent) {
  const steps = [
    ['입력 모으기', '입항 건 54 · 부두 24 · 계약 54 · 부두 제약 시간'],
    ['입력 검증', '필수 칸 · 단위 · 시각 순서 검사'],
    ['수리계획법 (본체 식 1~8)', '작업계획 39,477개 · 30분 눈금 · HiGHS'],
    ['규칙식으로 다시 계산 (P23)', '고른 배정 · 순서의 금액과 제약을 다시 계산'],
    ['산출 근거 만들기', '선박마다 규칙 ID가 붙은 계산 순서'],
  ];
  for (let i = 0; i < steps.length; i++) {
    onEvent({ step: i, total: steps.length, name: steps[i][0], detail: steps[i][1] });
    await new Promise((r) => setTimeout(r, 650));
  }
  const runId = DB.run.run_id;
  update((s) => {
    appendLog({ action: '후보 계산', target: runId, detail: '프로토타입: 미리 계산한 결과를 다시 불러옴 (엔진 미연결)' });
  });
  onEvent({ step: steps.length, total: steps.length, done: true, runId });
  return runId;
}

/** 데이터 연계 상태 (NFR-11 · N01) */
export function sources() {
  const now = nowMs();
  return [
    { key: 'ais', name: 'AIS 선박 위치·항해정보', src: '해양수산부 T-AIS · S-AIS', state: 'ok', at: now - 25 * 1000, every: '연속 수신' },
    { key: 'pmis', name: 'PORT-MIS 입출항·시설사용', src: '해양수산부 · 울산항만공사 API', state: 'ok', at: now - 6 * MIN, every: '10분' },
    { key: 'restr', name: '부두 제약 시간 (기상·공사)', src: '담당자 입력', state: 'ok', at: now - 19 * H, every: '수동' },
    { key: 'ctr', name: '계약 조건 (Laytime·요율)', src: '계약 DB', state: 'ok', at: now - 26 * H, every: '변경 시' },
    { key: 'engine', name: '계산 엔진', src: `수리계획법 ${DB.run.engine.version}`, state: 'ok', at: now - 3 * H - 10 * MIN, every: '요청 시' },
    { key: 'llm', name: '보고서 문장 (LLM)', src: '응답 없으면 템플릿 문장', state: 'warn', at: now - 2 * H - 40 * MIN, every: '요청 시', note: '프로토타입은 템플릿' },
  ];
}

export { diffPlans };
