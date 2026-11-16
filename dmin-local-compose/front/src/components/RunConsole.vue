<script setup>
// 데이터 넣기·실행: 실제 데이터(JSON·CSV)를 Spring에 넣고 → Python 엔진(팀원 코드 CP-SAT 또는 기존 HiGHS) → Spring 재검증 → 후보 공개까지 본다.
// 금액은 Spring이 PPT 식(Java)으로 다시 계산한 값을 보여 준다. 솔버 값과 1센트라도 다르면 그 후보는 '재검증 실패'로 막힌다.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { CircleAlert, RefreshCw, Upload } from 'lucide-vue-next'
import { api, signed, usd, when } from '../lib/api.js'
import { ROLES, ws } from '../lib/workspace.js'
import ViewHead from './ViewHead.vue'

const status = ref(null)
const offline = ref(null) // { text, static } — static이면 정적 사이트(GitHub Pages 등, 서버 없음), 아니면 서버 장애
const cases = ref([])
const runs = ref([])
const sel = ref(null) // 선택한 실행 상세
const msg = ref(null) // { kind: 'ok' | 'bad', head, text, list } — head가 없으면 kind로 정한다
const busy = ref(false)
const file = ref(null)
const planStart = ref('')
const planEnd = ref('')
const reason = ref('')
// 계산 엔진 · 규칙 해석. 팀 엔진(팀원 코드)은 팀 해석으로만 돈다. 기존 엔진을 팀 해석으로 돌리면 '같은 규칙, 다른 풀이 방법' 검산이 된다.
const ENGINES = [
  { key: 'team-cpsat|team', engine: 'team-cpsat', profile: 'team', label: '팀 엔진 (팀원 코드 · CP-SAT) · 팀 해석' },
  { key: 'ppt-milp|team', engine: 'ppt-milp', profile: 'team', label: '기존 엔진 (HiGHS) · 팀 해석 — 같은 규칙 검산' },
  { key: 'ppt-milp|ppt', engine: 'ppt-milp', profile: 'ppt', label: '기존 엔진 (HiGHS) · 기존 해석' },
]
const engineKey = ref(ENGINES[0].key)
const engineName = (r) => ({ 'team-cpsat|team': '팀 CP-SAT', 'ppt-milp|team': '기존·팀 해석', 'ppt-milp|ppt': '기존' })[`${r.engine}|${r.profile}`] ?? `${r.engine ?? '-'}`
let timer = null
let alive = true // 화면을 떠나면 false: 그 뒤에는 다시 예약하지도, 값을 넣지도 않는다

async function refresh() {
  if (!alive) return
  try {
    const st = await api.status()
    if (!alive) return
    status.value = st
    offline.value = null
    const [cs, rs] = await Promise.all([api.cases(), api.runs()])
    if (!alive) return
    cases.value = cs
    runs.value = rs
    const id = sel.value?.id
    if (id == null) return
    try {
      const d = await api.run(id)
      if (alive && sel.value?.id === id) sel.value = d // 기다리는 사이에 다른 실행을 골랐으면 덮어쓰지 않는다
    } catch (e) {
      if (!alive || e.status !== 404) throw e
      if (sel.value?.id === id) sel.value = null // DB를 비운 뒤 등: 그 실행이 없어졌으면 선택만 푼다(화면 전체를 '연결 안 됨'으로 바꾸지 않는다)
    }
  } catch (e) {
    if (alive) offline.value = { text: e.message, static: !!e.static }
  }
}

const active = computed(() => runs.value.some((r) => r.status === 'QUEUED' || r.status === 'RUNNING'))
function schedule() {
  clearTimeout(timer)
  if (!alive) return
  timer = setTimeout(async () => { await refresh(); schedule() }, active.value ? 2000 : 10000)
}
onMounted(async () => { await refresh(); schedule() })
onBeforeUnmount(() => { alive = false; clearTimeout(timer) })

async function put(fn) {
  busy.value = true
  msg.value = null
  try {
    const c = await fn()
    msg.value = { kind: 'ok', head: c.duplicate ? '이미 있음' : '저장됨', text: `${c.duplicate ? '같은 내용이라 새로 만들지 않음 — ' : ''}#${c.id} ${c.case_key} · 입항 ${c.arrivals}건 · ${c.plan_start} ~ ${c.plan_end} · 지문 ${c.payload_hash}`, list: c.warnings }
    await refresh()
  } catch (e) {
    msg.value = { kind: 'bad', text: e.message, list: e.data?.errors ?? [] }
  } finally {
    busy.value = false
  }
}
const upload = () => file.value && put(() => api.importFile(file.value, { plan_start: planStart.value, plan_end: planEnd.value }))
// 예시 파일이 없으면 정적 서버가 404나 index.html(200, HTML)을 주므로 JSON인지 확인하고 읽는다.
const sample = (name) => put(async () => {
  const r = await fetch(`./samples/${name}`)
  if (!r.ok || !(r.headers.get('content-type') || '').includes('json')) throw new Error(`예시 파일을 찾지 못함 (./samples/${name})`)
  return api.createCase(await r.json())
})

async function start(caseId) {
  busy.value = true
  try {
    const e = ENGINES.find((x) => x.key === engineKey.value)
    const r = await api.startRun(caseId, { engine: e.engine, profile: e.profile })
    await refresh()
    sel.value = await api.run(r.run_id)
    schedule()
  } catch (e) {
    msg.value = { kind: 'bad', text: e.message }
  } finally {
    busy.value = false
  }
}
async function show(id) {
  try {
    sel.value = await api.run(id)
  } catch (e) {
    msg.value = { kind: 'bad', head: '불러오지 못함', text: `실행 #${id}: ${e.message}` }
  }
}
async function decide(rank, action) {
  try {
    await api.decide(sel.value.id, { rank, action, actor: ROLES[ws.roleId].title, reason: reason.value })
    reason.value = ''
    sel.value = await api.run(sel.value.id)
  } catch (e) {
    msg.value = { kind: 'bad', text: e.message }
  }
}

const STATUS = { QUEUED: '대기', RUNNING: '실행 중', SUCCEEDED: '완료', PARTIAL: '일부 통과', FAILED: '실패' }
const STEP = { INPUT: '입력 검사 (Spring)', SOLVE: '후보 탐색 (Python 엔진)', VERIFY: '재검증 (Spring · PPT 식 Java판)', PUBLISH: '후보 공개' }
const first = (r) => r.summary?.schedules?.find((s) => s.rank === 1)
const verifyOf = (name) => sel.value?.verification?.schedules?.find((s) => s.name === name)
const selected = computed(() => {
  const d = sel.value?.decisions ?? []
  const last = d[d.length - 1]
  return last && last.action === 'SELECT' ? last.candidate_rank : null
})
const rowsOk = (st) => ({ dot: { OK: 'ok', FAILED: 'bad', RUNNING: 'run' }[st] })
</script>

<template>
  <div class="stack">
    <ViewHead title="데이터 넣기·실행" crumb="SERVER RUN > 데이터 넣기·실행"
      desc="실제 데이터를 넣으면 Spring이 검사·저장하고, Python 엔진(기본: 팀원 코드 berth_sim · CP-SAT)이 후보를 찾고, Spring이 같은 식으로 다시 계산해 맞는 후보만 공개합니다." />

    <div v-if="offline" class="notice danger">
      <CircleAlert class="ico" :size="18" />
      <span v-if="offline.static"><b>서버가 없는 곳에서 열었습니다.</b> {{ offline.text }}<br />
        이 화면은 Spring 서버가 있어야 동작합니다. GitHub Pages(정적 사이트)에는 서버가 없습니다.
        로컬 실행판(<code>make up</code>)을 띄운 뒤 <code>http://127.0.0.1:18089</code>에서 여십시오.</span>
      <span v-else><b>서버에 연결되지 않습니다.</b> {{ offline.text }}<br />
        Spring이 응답하지 않습니다. 터미널에서 <code>make status</code>로 컨테이너 상태를 보고, <code>make logs</code>로 오류를 확인하십시오.</span>
    </div>

    <template v-else-if="status">
      <section class="panel">
        <div class="panel-head">
          <h2>▶ 시스템 상태</h2>
          <span class="muted">Caddy → Spring → (DB · Python 에이전트 · 공공데이터포털)</span>
          <button class="btn ghost right" @click="refresh"><RefreshCw :size="13" />새로고침</button>
        </div>
        <table class="grid">
          <thead><tr><th>구분</th><th>상태</th><th>내용</th></tr></thead>
          <tbody>
            <tr><td class="strong">Spring 서버</td><td class="c"><b class="ok">정상</b></td>
              <td>컨테이너 {{ status.server.pod }} · 규칙 표 {{ status.server.rules_version }} ({{ status.server.rules_sha256.slice(0, 12) }})</td></tr>
            <tr><td class="strong">DB (PostgreSQL + pgvector)</td><td class="c"><b :class="status.db.ok ? 'ok' : 'bad'">{{ status.db.ok ? '정상' : '오류' }}</b></td>
              <td>스키마 v{{ status.db.schema_version }} · 데이터 {{ status.db.counts?.cases }}건 · 실행 {{ status.db.counts?.runs }}건 · ETA 스냅숏 {{ status.db.counts?.eta_snapshots }}줄</td></tr>
            <tr><td class="strong">Python 에이전트</td><td class="c"><b :class="status.agent.ok ? 'ok' : 'bad'">{{ status.agent.ok ? (status.agent.busy ? '계산 중' : '정상') : '응답 없음' }}</b></td>
              <td v-if="status.agent.ok">{{ status.agent.engines ? `팀 엔진 ${status.agent.engines['team-cpsat']} · 기존 엔진 ${status.agent.engines['ppt-milp']}` : status.agent.engine }} · 규칙 표 {{ status.agent.rules_same ? 'Spring과 같음' : 'Spring과 다름 — 재검증이 모두 막힘' }}</td>
              <td v-else class="bad">{{ status.agent.error }}</td></tr>
            <tr><td class="strong">공공데이터 키</td><td class="c"><b :class="status.public_data.configured ? 'ok' : 'warn'">{{ status.public_data.configured ? '있음' : '없음' }}</b></td>
              <td>{{ status.public_data.configured ? '실시간 AIS·입항 신고 ETA 사용 가능 (운영 현황 지도의 실시간 보기)' : '.env의 PUBLIC_DATA_SERVICE_KEY가 비어 있음 → 실시간 기능만 꺼지고 계산은 그대로 동작' }}</td></tr>
          </tbody>
        </table>
      </section>

      <section class="panel">
        <div class="panel-head"><h2>▶ 데이터 넣기</h2><span class="muted">JSON = 요청 계약 그대로 · CSV = 입항 건 표(data/templates/arrivals.csv)</span></div>
        <table class="grid form">
          <tbody>
            <tr>
              <th>파일</th>
              <td><input type="file" accept=".json,.csv" @change="file = $event.target.files[0]" /></td>
              <th>CSV 기간</th>
              <td><input v-model="planStart" class="input sm" placeholder="시작 2026-11-10T00:00" /> ~ <input v-model="planEnd" class="input sm" placeholder="끝 (비우면 +7일)" /></td>
              <td class="c"><button class="btn primary" :disabled="!file || busy" @click="upload"><Upload :size="13" />올리기</button></td>
            </tr>
            <tr>
              <th>예시</th>
              <td colspan="4">
                <button class="btn" :disabled="busy" @click="sample('example-3.json')">예시 3척 + FIX 1척 (팀 해석 $9,252.07 · 기존 해석 $7,192.30)</button>
                <button class="btn" :disabled="busy" @click="sample('team-week-54.json')">팀원 가상 데이터 54척 (팀원 코드 data/dummy)</button>
                <button class="btn" :disabled="busy" @click="sample('sample-week-54.json')">샘플 주간 54건 (기존 해석 $216,985.68 · 팀 해석은 후보 없음)</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="msg" :class="['notice', msg.kind === 'ok' ? 'done' : 'danger']">
          <span><b>{{ msg.head ?? (msg.kind === 'ok' ? '저장됨' : '넣지 못함') }}</b> {{ msg.text }}
            <ul v-if="msg.list?.length" class="errs"><li v-for="(m, i) in msg.list" :key="i">{{ m }}</li></ul></span>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h2>▶ 데이터 목록</h2><span class="muted">최근 <b class="red">{{ cases.length }}</b>건</span>
          <label class="right engine">계산 엔진
            <select v-model="engineKey" class="input sm"><option v-for="e in ENGINES" :key="e.key" :value="e.key">{{ e.label }}</option></select>
          </label>
        </div>
        <table class="grid">
          <thead><tr><th>번호</th><th>데이터</th><th>제목</th><th>입항 건</th><th>계획 기간</th><th>형식</th><th>경고</th><th>들어온 시각</th><th>실행</th></tr></thead>
          <tbody>
            <tr v-for="c in cases" :key="c.id">
              <td class="c">{{ c.id }}</td><td class="strong">{{ c.case_key }}</td><td>{{ c.title }}</td><td class="c num">{{ c.arrivals }}</td>
              <td class="c num">{{ c.plan_start.slice(5).replace('T', ' ') }} ~ {{ c.plan_end.slice(5).replace('T', ' ') }}</td>
              <td class="c">{{ c.source.toUpperCase() }}</td><td class="c" :class="{ warn: c.warnings.length }">{{ c.warnings.length || '-' }}</td>
              <td class="c num">{{ when(c.created_at) }}</td>
              <td class="c"><button class="btn primary sm" :disabled="busy" @click="start(c.id)">후보 계산</button></td>
            </tr>
            <tr v-if="!cases.length"><td colspan="9" class="c muted">아직 넣은 데이터가 없습니다.</td></tr>
          </tbody>
        </table>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>▶ 실행 목록</h2><span class="muted">최근 <b class="red">{{ runs.length }}</b>건</span>
          <span class="legend right"><i class="q" />대기 <i class="r" />실행 중 <i class="s" />완료 <i class="p" />일부 통과 <i class="f" />실패</span>
        </div>
        <table class="grid">
          <thead><tr><th>번호</th><th>데이터</th><th>엔진</th><th>상태</th><th>1안 총 예상 체선료</th><th>기준안 대비</th><th>재검증</th><th>솔버</th><th>처리 컨테이너</th><th>접수</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in runs" :key="r.id" :class="['st-' + r.status, { picked: sel?.id === r.id }]">
              <td class="c">{{ r.id }}</td><td class="strong">{{ r.case_key }} <small class="muted">({{ r.arrivals }}건)</small></td>
              <td class="c small">{{ engineName(r) }}</td>
              <td class="c strong">{{ STATUS[r.status] }}</td>
              <td class="r num strong">{{ usd(first(r)?.total_usd) }}</td>
              <td class="r num" :class="{ ok: first(r)?.delta_vs_baseline_usd < 0 }">{{ signed(first(r)?.delta_vs_baseline_usd) }}</td>
              <td class="c">{{ r.summary ? `${r.summary.verified_candidates} / ${r.summary.candidates}` : '-' }}</td>
              <td class="c num">{{ r.summary ? `${r.summary.solve_seconds}초` : '-' }}</td>
              <td class="c small">{{ r.worker ?? '-' }}</td>
              <td class="c num">{{ when(r.created_at) }}</td>
              <td class="c"><button class="btn sm" @click="show(r.id)">보기</button></td>
            </tr>
            <tr v-if="!runs.length"><td colspan="11" class="c muted">아직 실행이 없습니다. 데이터 목록에서 「후보 계산」을 누르십시오.</td></tr>
          </tbody>
        </table>
      </section>

      <section v-if="sel" class="panel">
        <div class="panel-head">
          <h2>▶ 실행 #{{ sel.id }} — {{ sel.case_key }}</h2>
          <span class="muted">{{ sel.case_title }}</span>
          <b class="right" :class="{ ok: sel.status === 'SUCCEEDED', bad: sel.status === 'FAILED', warn: sel.status === 'PARTIAL' }">{{ STATUS[sel.status] }}</b>
        </div>
        <p class="small muted">엔진 <b>{{ sel.engine === 'team-cpsat' ? '팀 엔진 — 팀원 코드 berth_sim (OR-Tools CP-SAT, 5분 칸)' : '기존 엔진 — docs/milp/ppt (HiGHS)' }}</b>
          · 규칙 해석 <b>{{ sel.summary?.profile?.title ?? sel.profile }}</b>
          <template v-if="sel.summary?.engine?.version"> · {{ sel.summary.engine.version }}</template></p>
        <div v-if="sel.error" class="notice" :class="sel.status === 'FAILED' ? 'danger' : ''"><span>{{ sel.error }}</span></div>
        <ul v-if="sel.summary?.notes?.length" class="notes small"><li v-for="(n, i) in sel.summary.notes" :key="i">{{ n }}</li></ul>

        <h3>처리 단계</h3>
        <table class="grid">
          <thead><tr><th>순서</th><th>단계</th><th>상태</th><th>걸린 시간</th><th>내용</th></tr></thead>
          <tbody>
            <tr v-for="s in sel.steps" :key="s.seq">
              <td class="c">{{ s.seq }}</td><td class="strong">{{ STEP[s.name] ?? s.name }}</td>
              <td class="c"><b :class="rowsOk(s.status).dot">{{ s.status === 'OK' ? '완료' : s.status === 'FAILED' ? '실패' : '진행 중' }}</b></td>
              <td class="c num">{{ s.seconds }}초</td><td class="pre">{{ s.detail }}</td>
            </tr>
            <tr v-if="!sel.steps.length"><td colspan="5" class="c muted">대기 중 — 다른 실행이 끝나면 시작합니다(동시 계산 1건).</td></tr>
          </tbody>
        </table>

        <template v-if="sel.summary">
          <h3>후보 비교 <small class="muted">금액 = Spring이 다시 계산한 값 · 솔버 {{ sel.summary.engine?.solver }} · 데이터 지문 {{ sel.payload_hash ?? '-' }} · 엔진 지문 {{ sel.summary.request_hash ?? '-' }}</small></h3>
          <table class="grid">
            <thead><tr><th>일정</th><th>총 예상 체선료</th><th>기준안 대비</th><th>규칙 위반</th><th>바뀐 배</th><th>솔버 상태</th><th>Spring 재검증</th><th>선택</th></tr></thead>
            <tbody>
              <tr v-for="s in sel.summary.schedules" :key="s.name" :class="{ chosen: selected === s.rank && s.rank > 0 }">
                <td class="strong">{{ s.name }}<small v-if="s.name === '기준안'" class="muted"> (ETA 순서, 비교용)</small></td>
                <td class="r num strong">{{ usd(s.total_usd) }}</td>
                <td class="r num" :class="{ ok: s.delta_vs_baseline_usd < 0 }">{{ s.rank ? signed(s.delta_vs_baseline_usd) : '' }}</td>
                <td class="c" :class="{ bad: s.violations }">{{ s.violations }}</td>
                <td class="c">{{ s.rank ? `${s.changes}척` : '' }}</td>
                <td class="c small">{{ s.status ?? '' }}</td>
                <td class="c">
                  <b :class="s.verified ? 'ok' : 'bad'">{{ s.verified ? '통과' : '실패' }}</b>
                  <small class="muted"> {{ verifyOf(s.name)?.mismatches.length ? `불일치 ${verifyOf(s.name).mismatches.length}` : '불일치 0' }}</small>
                </td>
                <td class="c">
                  <template v-if="s.rank > 0">
                    <button v-if="selected !== s.rank" class="btn sm" :disabled="!s.verified" @click="decide(s.rank, 'SELECT')">이 안 선택</button>
                    <button v-else class="btn sm warn" @click="decide(s.rank, 'CANCEL')">선택 취소</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="small muted">재검증: 일정 {{ sel.verification?.schedules?.length }}개 · 작업계획 {{ sel.verification?.checked_plans }}개 · 불일치 {{ sel.verification?.mismatches }} ·
            규칙 표 Spring {{ sel.verification?.spring_rules }} / Python {{ sel.verification?.agent_rules }}</p>
          <div class="row reason"><input v-model="reason" class="input" placeholder="선택·취소 사유 (결정 이력에 그대로 남습니다)" /></div>

          <h3>결정 이력 <small class="muted">추가만 됩니다(수정·삭제 불가)</small></h3>
          <table class="grid">
            <thead><tr><th>번호</th><th>시각</th><th>후보</th><th>동작</th><th>담당</th><th>사유</th></tr></thead>
            <tbody>
              <tr v-for="d in sel.decisions" :key="d.id">
                <td class="c">{{ d.id }}</td><td class="c num">{{ when(d.created_at) }}</td><td class="c">{{ d.candidate_rank }}안</td>
                <td class="c strong">{{ d.action === 'SELECT' ? '선택' : '취소' }}</td><td class="c">{{ d.actor }}</td><td>{{ d.reason || '-' }}</td>
              </tr>
              <tr v-if="!sel.decisions.length"><td colspan="6" class="c muted">아직 결정이 없습니다. 확정과 현업 반영은 사람이 합니다.</td></tr>
            </tbody>
          </table>
        </template>
      </section>
    </template>
    <p v-else class="muted">서버 상태를 확인하는 중…</p>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.r { text-align: right; white-space: nowrap; }
.right { margin-left: auto; }
.ok { color: var(--ok); }
.bad { color: var(--bad); }
.warn { color: var(--warn); }
.red { color: var(--bad); }
.run { color: var(--warn); }
h3 { margin: 18px 0 6px; font-size: 13.5px; }
.form th { width: 90px; background: var(--sunken); text-align: left; }
.form .input.sm { width: 190px; }
.errs { margin: 6px 0 0 16px; }
.pre { white-space: pre-wrap; font-size: 12px; }
.reason { margin-top: 8px; }
.engine { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); }
.engine select { width: 320px; height: 26px; }
.notes { margin: 4px 0 0 16px; color: var(--muted); }
.reason .input { width: 100%; }
.btn.sm { height: 24px; padding: 0 10px; font-size: 12px; }
.legend { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--muted); }
.legend i { display: inline-block; width: 12px; height: 12px; margin-left: 8px; border: 1px solid #ccc; }
.legend .q, tr.st-QUEUED td { background: #f4f5f7; }
.legend .r, tr.st-RUNNING td { background: var(--warn-weak); }
.legend .s, tr.st-SUCCEEDED td { background: #eaf4fb; }
.legend .p, tr.st-PARTIAL td { background: #fff1e0; }
.legend .f, tr.st-FAILED td { background: var(--bad-weak); }
tr.picked td { box-shadow: inset 0 -2px 0 var(--accent); }
tr.chosen td { background: var(--accent-weak); }
code { font-size: 12px; background: #fff; padding: 0 4px; }
</style>
