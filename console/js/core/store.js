// 화면 상태 (역할 · 적용 계획 버전 · 보고서 · 승인 기록)
// 실제 솔루션에서는 Spring 업무 DB(app 스키마)가 가진다. 프로토타입은 브라우저 localStorage에 둔다.
// 기록은 덧붙이기만 한다: 승인 · 반려 · 적용은 지우거나 고치지 않고 새 줄로 쌓인다 (N-004 · N-033).
import { nowMs, H, MIN, fmtDate } from './time.js';
import { DB } from './data.js';

const KEY = 'berth-console/v1';

export const ROLES = {
  scheduler: { id: 'scheduler', name: '스케줄러 A', title: '접안 계획 담당', can: { run: true, report: true, submit: true, approve: false } },
  approver: { id: 'approver', name: '승인권자 B', title: '생산조정 팀장', can: { run: false, report: false, submit: false, approve: true } },
  viewer: { id: 'viewer', name: '조회 C', title: '작업 지시 · 조회 전용', can: { run: false, report: false, submit: false, approve: false } },
};

let S = null;
const listeners = new Set();

function seed() {
  const now = nowMs();
  const runId = DB.run.run_id;
  const day = fmtDate(now).slice(5).replace('-', '');
  const reportId = `RPT-${day}-01`;
  const inputAt = now - 3 * H - 15 * MIN;
  return {
    planStart: DB.planStart,
    role: 'scheduler',
    showReq: false,
    versions: [
      {
        no: 1, set: 'current', label: '현행 계획 (엑셀 입력)', applied_at: now - 20 * H, applied_by: '입력 담당 (엑셀 업로드)', role: '입력',
        run_id: null, report_id: null, reason: '주간 계획 회의 뒤 올린 ETB', input_at: now - 20 * H,
      },
    ],
    runs: [
      {
        run_id: runId, created_at: now - 3 * H - 10 * MIN, created_by: '스케줄러 A', input_at: inputAt, status: 'done',
        elapsed: DB.run.stats.elapsed_seconds, request_hash: DB.run.request_hash,
      },
    ],
    reports: [
      {
        id: reportId, run_id: runId, title: '주간 접안 계획 검토', status: 'requested', recommended: 'c1',
        created_at: now - 2 * H - 40 * MIN, created_by: '스케줄러 A', submitted_at: now - 2 * H - 20 * MIN,
        input_at: inputAt,
        note: '1안 승인 요청. 2안은 총액이 같고 바뀌는 배가 1척 적다 (현장 판단 부탁)',
        llm: { calls: 2, tokens_in: 2874, tokens_out: 538, cost_usd: 0.04, fallback: false },
        decision: null,
      },
    ],
    log: [
      { at: now - 20 * H, who: '입력 담당', role: '입력', action: '계획 적용', target: 'v1 현행 계획 (엑셀 입력)', detail: '엑셀 업로드 54건' },
      { at: now - 3 * H - 10 * MIN, who: '스케줄러 A', role: '접안 계획 담당', action: '후보 계산', target: runId, detail: `입력 기준 ${fmtDate(inputAt)} · 54건 · 97초` },
      { at: now - 2 * H - 40 * MIN, who: '스케줄러 A', role: '접안 계획 담당', action: '보고서 작성', target: reportId, detail: 'LLM 문장 초안 2회 호출 · 숫자 대조 불일치 0' },
      { at: now - 2 * H - 20 * MIN, who: '스케줄러 A', role: '접안 계획 담당', action: '승인 요청', target: reportId, detail: '추천 1안' },
    ],
  };
}

export function initStore() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const st = JSON.parse(raw);
      // 계획 창이 바뀌었으면(날짜가 넘어감) 처음 상태로 돌린다
      if (st.planStart === DB.planStart) S = st;
    }
  } catch {
    /* 저장소를 못 쓰면 메모리에만 둔다 */
  }
  if (!S) S = seed();
  save();
  return S;
}

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(S));
  } catch {
    /* noop */
  }
}

export const state = () => S;
export const role = () => ROLES[S.role];

export function update(fn) {
  fn(S);
  save();
  for (const l of listeners) l(S);
}
export const onChange = (fn) => (listeners.add(fn), () => listeners.delete(fn));

export function resetStore() {
  S = seed();
  save();
  for (const l of listeners) l(S);
}

export function appendLog(entry) {
  S.log.push({ at: nowMs(), who: role().name, role: role().title, ...entry });
}
