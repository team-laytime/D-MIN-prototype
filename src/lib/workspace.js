// 이해관계자별 계정 · 메뉴 권한 · 업무 기록(시연용, 새로고침하면 사라짐).
// 근거: 팀 요구사항 docs/requirements/15-hidden-nfr-ux-500.md
//   HN-091 역할별 계정 · HN-092 확정·취소는 스케줄러만 · HN-094 작업 지시자는 확정본만 · HN-095 요율은 필요한 역할만 · HN-096 기준 정보 변경은 관리자만
// [V] 표시는 이해관계자 표에서 아직 확인 전인 권한이다.
import { reactive } from 'vue'

export const PASSWORD = '1234'
export const ROLES = {
  scheduler: { id: 'scheduler', name: '스케줄러 A', title: '선박 스케줄러', loginId: 'scheduler', home: 'home', desc: '부두별 계획 작성·수정·확정' },
  operator: { id: 'operator', name: '작업지시 C', title: '입출항 작업 지시자', loginId: 'ops', home: 'ops', desc: '확정 계획에 따른 작업 준비·실행' },
  production: { id: 'production', name: '생산 D', title: '생산 관련 부서', loginId: 'prod', home: 'prod', desc: '처리량·재고 확인, 우선순위 요청' },
  contract: { id: 'contract', name: '계약 E', title: '계약 담당 부서', loginId: 'contract', home: 'contract', desc: '계약 조건 관리, Laytime 확인·이의' },
  payment: { id: 'payment', name: '정산 F', title: '체선료 지불 담당', loginId: 'pay', home: 'settle', desc: '예상·청구 비용 확인, 지급 승인' },
  admin: { id: 'admin', name: '관리자 G', title: '기준 정보 관리자', loginId: 'admin', home: 'master', desc: '부두 제원·규칙 기준 정보, 계정 권한' },
}
const ALL = Object.keys(ROLES)
const NOT_OPS = ALL.filter((r) => r !== 'operator')

// GNB 메뉴 = LNB 묶음. roles에 없는 계정에게는 GNB에서 빼고 LNB에는 흐리게 남긴다(누르면 해당 계정 로그인).
export const NAV = [
  { key: 'DASHBOARD', gnb: '운영 현황', roles: NOT_OPS, items: [{ id: 'home', label: '운영 현황' }] },
  { key: 'BERTH PLANNING', gnb: '접안 계획', roles: ['scheduler'], items: [
    { id: 'input', label: '시나리오 입력' },
    { id: 'compare', label: '후보 비교' },
    { id: 'risk', label: '리스크·확정' },
    { id: 'requests', label: '요청 처리' },
  ] },
  { key: 'OPERATIONS', gnb: '작업 지시', roles: ['operator', 'scheduler'], items: [{ id: 'ops', label: '확정 접안 일정' }] },
  { key: 'PRODUCTION', gnb: '생산', roles: ['production'], items: [{ id: 'prod', label: '탱크·긴급 출하' }] },
  { key: 'CONTRACT', gnb: '계약', roles: ['contract'], items: [{ id: 'contract', label: '계약 조건·Laytime' }] },
  { key: 'SETTLEMENT', gnb: '정산', roles: ['payment'], items: [{ id: 'settle', label: '체선료 정산' }] },
  { key: 'REPORT', gnb: '보고서', roles: ['scheduler'], items: [{ id: 'report', label: '접안계획 보고서' }] },
  { key: 'QUALITY', gnb: '검증', roles: ['scheduler', 'admin'], items: [{ id: 'verify', label: '계산 검증' }] },
  { key: 'APPENDIX', gnb: '부록', roles: ALL, items: [{ id: 'workflow', label: 'Agent 워크플로우' }] },
  { key: '관리자메뉴', gnb: '관리자', roles: ['admin'], items: [
    { id: 'master', label: '기준 정보' },
    { id: 'users', label: '사용자·권한' },
    { id: 'log', label: '처리 이력' },
  ] },
]

// 사용자·권한 화면의 표. open = 확인 전 항목([V]).
export const PERMS = [
  { act: '후보 계산 · 비교 · 보고서 초안', roles: ['scheduler'] },
  { act: '접안 계획 확정 · 확정 취소', roles: ['scheduler'], src: 'HN-092' },
  { act: '확정 계획 조회', roles: ALL },
  { act: '검토 중 후보 조회', roles: NOT_OPS, src: 'HN-094' },
  { act: '계약 단가 · 체선료 금액 조회', roles: ['scheduler', 'contract', 'payment'], src: 'HN-095', open: '계약 담당 포함 여부' },
  { act: '현장 변경 요청', roles: ['operator'], open: '현장 변경 승인 주체' },
  { act: '긴급 출하 · 우선순위 요청', roles: ['production'], open: '재고 부족 시 지시 방식' },
  { act: 'Laytime 확인 · 이의', roles: ['contract'], open: 'NOR · Laytime 분쟁 · 변경 승인' },
  { act: '체선료 청구 확인 · 지급 승인', roles: ['payment'], open: '승인 · 정산 권한' },
  { act: '기준 정보(부두 제원) 변경', roles: ['admin'], src: 'HN-096' },
]

export const canUse = (roleId, group) => group.roles.includes(roleId)
export const groupOf = (tab) => NAV.find((g) => g.items.some((i) => i.id === tab))
export const nowText = () => new Date().toLocaleString('ko-KR', { hour12: false })

const fresh = () => ({
  roleId: 'scheduler',
  plans: [], // 확정 이력 {no, candId, label, total, reason, uncheckedRisks, at, who, version, placements, cancelled, fieldDone}
  requests: [], // 다른 부서가 스케줄러에게 보낸 요청
  reviews: {}, // 계약 담당 Laytime 확인 · 이의  key = `${planNo}:${vid}`
  claims: {}, // 지불 담당 청구 · 지급  key = `${planNo}:${vid}`
  prep: {}, // 작업 지시자 준비 체크  key = `${planNo}:${vid}:${item}`
  log: [], // 모든 처리 기록(추가만)
})
export const ws = reactive(fresh())
export function resetWorkspace() { Object.assign(ws, fresh()) }

export const role = () => ROLES[ws.roleId]
export function addLog(action, target, detail = '') {
  const r = role()
  ws.log.push({ at: nowText(), who: r.name, roleTitle: r.title, action, target, detail })
}

/** 지금 적용 중인 확정 계획(마지막 확정, 취소 안 됨). */
export const activePlan = () => {
  const p = ws.plans.at(-1)
  return p && !p.cancelled ? p : null
}

/** 스케줄러 확정. 이후 입력이 바뀌어도 다른 부서는 확정 당시 일정을 본다(스냅숏). */
export function fixPlan({ cand, scen, version, reason, uncheckedRisks }) {
  const v = Object.fromEntries(scen.vessels.map((x) => [x.id, x]))
  const bn = (id) => scen.berths.find((b) => b.id === id)?.name
  const plan = {
    no: ws.plans.length + 1, candId: cand.id, label: cand.label, total: cand.total, reason, uncheckedRisks,
    at: nowText(), who: role().name, version, cancelled: false, fieldDone: false,
    placements: [...cand.placements].sort((a, b) => a.etb - b.etb).map((p) => ({
      vid: p.vid, name: v[p.vid].name, product: v[p.vid].product, dir: v[p.vid].dir, ton: v[p.vid].ton, dwt: v[p.vid].dwt,
      eta: v[p.vid].eta, bid: p.bid, berth: bn(p.bid), etb: p.etb, etu: p.etu, contract: { ...v[p.vid].contract },
      dem: JSON.parse(JSON.stringify(p.dem)),
    })),
  }
  ws.plans.push(plan)
  addLog('계획 확정', `접안 계획 v${plan.no} · ${cand.label}`, reason)
  return plan
}
export function cancelPlan(reason) {
  const p = activePlan()
  if (!p) return
  p.cancelled = true
  addLog('확정 취소', `접안 계획 v${p.no} · ${p.label}`, reason)
}
export function markFieldDone() {
  const p = activePlan()
  if (!p) return
  p.fieldDone = true
  addLog('현업 반영 완료', `접안 계획 v${p.no} · ${p.label}`, '현업 시스템(Seagate)에 반영함')
}

export function addRequest({ type, vid, vname, text }) {
  const r = { id: `REQ-${String(ws.requests.length + 1).padStart(2, '0')}`, type, vid, vname, text, from: ws.roleId, who: role().name, roleTitle: role().title, at: nowText(), status: '접수', reply: '', repliedAt: '' }
  ws.requests.push(r)
  addLog(type, `${r.id} · ${vname}`, text)
  return r
}
export function answerRequest(id, status, reply) {
  const r = ws.requests.find((x) => x.id === id)
  if (!r) return
  Object.assign(r, { status, reply, repliedAt: nowText(), repliedBy: role().name })
  addLog(`요청 ${status}`, `${r.id} · ${r.vname}`, reply)
}
