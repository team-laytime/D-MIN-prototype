<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { CircleAlert, CircleHelp, Layers, Minus, Network, Plus, UserRound } from 'lucide-vue-next'
import { SCENARIOS } from './lib/scenarios.js'
import { runSearch } from './lib/engine.js'
import ScenarioInput from './components/ScenarioInput.vue'
import CompareView from './components/CompareView.vue'
import RiskView from './components/RiskView.vue'
import ReportView from './components/ReportView.vue'
import VerifyView from './components/VerifyView.vue'
import VesselDrawer from './components/VesselDrawer.vue'
import MapHome from './components/MapHome.vue'
import Tour from './components/Tour.vue'
import WorkflowView from './components/WorkflowView.vue'
import AdminApprovals from './components/AdminApprovals.vue'
import AdminHistory from './components/AdminHistory.vue'

const scenarioId = ref('S1')
const scen = ref(SCENARIOS.S1())
const version = ref(1)
watch(scen, () => { version.value++ }, { deep: true })
watch(scenarioId, (id) => { scen.value = SCENARIOS[id]() })

// 탐색은 수천 번 시뮬레이션하므로 반응형 프록시 대신 평범한 복사본으로 돌린다.
const plain = computed(() => JSON.parse(JSON.stringify(scen.value)))
const result = computed(() => runSearch(plain.value))
const all = computed(() => (result.value.error ? [] : [result.value.fcfs, ...result.value.candidates]))

const tab = ref('home')
const focusId = ref('A')
watch(result, (r) => { if (!r.error && !r.candidates.some((c) => c.id === focusId.value)) focusId.value = r.candidates[0]?.id ?? 'FCFS' })

const drawer = ref(null)
// 선박 카드. at = 지도 시각(지도에서 열 때만), mode = 'card' | 'evidence'
const openVessel = (simId, vid, opts = {}) => { drawer.value = { simId, vid, at: opts.at ?? null, mode: opts.mode ?? 'card' } }
const drawerSim = computed(() => drawer.value && all.value.find((s) => s.id === drawer.value.simId))

// 시연용 사용자. 실제로는 로그인 계정이 정한다. 승인권자만 관리자메뉴를 쓴다.
const ROLES = {
  scheduler: { id: 'scheduler', name: '스케줄러 A', title: '접안 계획 담당', approve: false },
  approver: { id: 'approver', name: '승인권자 B', title: '생산조정 팀장', approve: true },
}
const roleId = ref('scheduler')
const role = computed(() => ROLES[roleId.value])

// 처리 기록. 추가만 하고 고치지 않는다(선택·요청 취소·승인·반려·현업 반영 완료).
// 스케줄러가 후보를 고르면 승인 요청 문서(RPT)가 생기고, 승인권자가 승인해야 접안 계획 버전이 올라간다.
const decisions = ref([])
const checks = reactive({})
const current = computed(() => {
  let state = null
  for (const d of decisions.value) {
    if (d.action === '선택') state = { ...d, status: '승인 대기' }
    else if (d.action === '요청 취소') state = null
    else if (d.action === '승인' && state?.reqId === d.reqId) state = { ...state, candId: d.candId, label: d.label, total: d.total, status: '승인 완료', planNo: d.planNo, approval: d }
    else if (d.action === '반려' && state?.reqId === d.reqId) state = { ...state, status: '반려', rejection: d }
    else if (d.action === '현업 반영 완료' && state?.status === '승인 완료') state = { ...state, status: '현업 반영 완료' }
  }
  return state
})
// 승인 요청 문서. 새로 요청하면 앞선 대기 문서는 '재요청으로 대체'된다.
const requests = computed(() => {
  const out = []
  for (const d of decisions.value) {
    const open = out.find((r) => r.status === '승인 대기')
    if (d.action === '선택') {
      if (open) open.status = '재요청으로 대체'
      out.push({ ...d, id: d.reqId, status: '승인 대기', decision: null })
    } else if (d.action === '요청 취소' && open) open.status = '요청 취소'
    else if ((d.action === '승인' || d.action === '반려')) {
      const r = out.find((x) => x.id === d.reqId)
      if (r) Object.assign(r, { status: d.action === '승인' ? '승인 완료' : '반려', decision: d })
    }
  }
  return out
})
const planVersions = computed(() => decisions.value.filter((d) => d.action === '승인'))
function decide(entry) {
  const at = new Date().toLocaleString('ko-KR', { hour12: false })
  const extra = {}
  if (entry.action === '선택') extra.reqId = `RPT-1114-${String(decisions.value.filter((d) => d.action === '선택').length + 1).padStart(2, '0')}`
  if (entry.action === '요청 취소' || entry.action === '현업 반영 완료') extra.reqId = current.value?.reqId
  if (entry.action === '승인') extra.planNo = planVersions.value.length + 1
  decisions.value.push({ ...entry, ...extra, at, version: version.value, who: role.value.name, roleTitle: role.value.title })
}

// GNB 메뉴 = LNB 묶음. 화면(tab)은 묶음 안의 하위 메뉴다.
const NAV = [
  { key: 'DASHBOARD', gnb: '운영 현황', items: [{ id: 'home', label: '운영 현황' }] },
  { key: 'BERTH PLANNING', gnb: '접안 계획', items: [
    { id: 'input', label: '시나리오 입력' },
    { id: 'compare', label: '후보 비교' },
    { id: 'risk', label: '리스크·선택' },
  ] },
  { key: 'REPORT', gnb: '보고서', items: [{ id: 'report', label: '접안계획 보고서' }] },
  { key: 'QUALITY', gnb: '검증', items: [{ id: 'verify', label: '계산 검증' }] },
  { key: 'APPENDIX', gnb: '부록', items: [{ id: 'workflow', label: 'Agent 워크플로우' }] },
  { key: '관리자메뉴', gnb: '관리자', admin: true, items: [{ id: 'approvals', label: '승인 관리' }, { id: 'history', label: '승인 이력' }] },
]
// 관리자메뉴는 승인권자만 연다. 다른 계정에서는 LNB에 흐리게 남기고 GNB에서는 뺀다.
const canSee = (g) => !g.admin || role.value.approve
const pending = computed(() => requests.value.filter((r) => r.status === '승인 대기').length)
watch(role, (r) => { if (!r.approve && group.value?.admin) tab.value = 'home' })
const group = computed(() => NAV.find((g) => g.items.some((i) => i.id === tab.value)))
const open = reactive(Object.fromEntries(NAV.map((g) => [g.key, false])))
// 화면을 옮기면 그 묶음만 펼친다(펼침 버튼으로 다른 묶음도 열 수 있다).
watch(group, (g) => { for (const k of Object.keys(open)) open[k] = k === g?.key }, { immediate: true })
function resetDemo() {
  decisions.value = []
  for (const k of Object.keys(checks)) delete checks[k]
  scen.value = SCENARIOS[scenarioId.value]()
  tab.value = 'home'
}

// 사용법 투어. 자동으로 시작하지 않고, 사용자가 이전/다음으로 넘긴다.
const sampleVessel = () => {
  const a = result.value.candidates[0]
  return (a.placements.find((p) => p.dem.cents > 0) ?? a.placements[0]).vid
}
const TOUR = [
  { section: '현황 지도', tab: 'home', target: '.plan-table', title: '안별 체선료',
    body: '도착순 기준안과 후보 A·B·C의 총 예상 체선료, 기준안 대비 차이, 선택한 시각까지 쌓인 금액입니다. 행을 누르면 지도와 선박 목록이 그 안으로 바뀝니다.' },
  { section: '현황 지도', tab: 'home', target: '.time-dock', title: '시각 이동',
    body: '막대를 끌면 그 시각의 선박 위치가 지도에 표시됩니다. 빨간 구간은 기상 악화로 접안할 수 없는 시간입니다.',
    try: '재생 버튼을 누르면 30분씩 진행합니다.' },
  { section: '현황 지도', tab: 'home', target: '.vessel-list', title: '선박 상태',
    body: '정박지 대기, 작업 중, 체선 발생으로 구분합니다. 선박을 누르면 지도가 그 위치로 이동하고, 「근거」는 계산 과정을 엽니다.' },
  { section: '공통', tab: 'home', target: '#scen', title: '시나리오 전환',
    body: '데모 시나리오 3개 중 하나를 고릅니다. 바꾸면 모든 화면을 다시 계산합니다.' },
  { section: '시나리오 입력', tab: 'input', target: '.inputs', title: '선박·계약 조건',
    body: '도착 예정 시각, 허용 시간, 하루 체선료, 기상 조항을 수정할 수 있습니다. 수정 즉시 후보를 다시 계산합니다.',
    try: 'GOLDEN STAR 도착 시각을 몇 시간 늦춰 후보 변화 확인' },
  { section: '시나리오 입력', tab: 'input', target: '.env', title: '기상·조석',
    body: '기상 악화 예보를 끄거나 시간을 바꿉니다. 만조와 일출·일몰은 대형선의 접안 가능 시간을 정합니다.' },
  { section: '후보 비교', tab: 'compare', target: '.cards', title: '기준안과 후보',
    body: '맨 왼쪽은 도착순 기준안(비교용, 현행 실적 아님)이고 나머지는 체선료가 낮은 후보입니다.',
    try: '후보를 누르면 아래 표가 그 후보로 바뀝니다.' },
  { section: '후보 비교', tab: 'compare', target: '.tl-row.on', title: '부두별 타임라인',
    body: '막대 하나가 선박 한 척의 접안부터 작업 종료까지입니다. 주황은 체선 발생, 빗금은 기상 악화, 회색 띠는 야간, 점선은 도착 후 대기입니다.' },
  { section: '후보 비교', tab: 'compare', target: '.drawer', title: '산출 근거',
    body: '정박시간 개시, 기상 공제, 적용한 계약 규칙, 접안이 밀린 이유를 단계별로 보여 줍니다.',
    do: () => openVessel(result.value.candidates[0].id, sampleVessel(), { mode: 'evidence' }) },
  { section: '리스크·선택', tab: 'risk', target: '.risks', title: '남은 리스크',
    body: '날씨 급변, 설비, 탱크, 긴급 출하, 현장 안전을 해당 / 해당 없음 / 판단 불가로 판정하고 대안을 붙입니다.',
    try: '「해당」 항목을 읽고 「확인」 체크' },
  { section: '리스크·선택', tab: 'risk', target: '.decide', title: '선택 · 승인 요청',
    body: '사유를 적고 선택하면 승인 요청이 올라갑니다. 확인하지 않은 리스크가 있으면 한 번 더 묻습니다. 승인은 오른쪽 위 사용자를 「승인권자 B」로 바꾸면 열리는 관리자메뉴에서 합니다. Agent는 계획을 확정하지 않습니다.' },
  { section: '보고서', tab: 'report', target: '.cols > .panel:first-child', title: '메일·보고서 초안',
    body: '선택한 후보로 초안을 만듭니다. 금액은 계산 결과를 그대로 넣고 자동 대조합니다.' },
  { section: '검증', tab: 'verify', target: '.answer-set', title: '계산 검증',
    body: '손계산 정답과의 일치 건수, 시나리오별 절감액, 제약 위반 수입니다.' },
  { section: '끝', tab: 'home', target: '.help-btn', title: '다시 보기',
    body: '오른쪽 위 「사용법」에서 이 안내를 다시 열 수 있습니다.' },
]
const tourIdx = ref(null)
function showTourStep(i) {
  tourIdx.value = i
  const s = TOUR[i]
  drawer.value = null
  if (s.tab === 'compare') focusId.value = result.value.candidates[0]?.id ?? 'FCFS'
  tab.value = s.tab
  s.do?.()
}
const startTour = () => showTourStep(0)
const endTour = () => { tourIdx.value = null; drawer.value = null }
const tourNext = () => (tourIdx.value < TOUR.length - 1 ? showTourStep(tourIdx.value + 1) : endTour())
const tourPrev = () => tourIdx.value > 0 && showTourStep(tourIdx.value - 1)
</script>

<template>
  <div class="util">
    <span><b>{{ role.name }}</b>({{ role.title }})님</span>
    <span class="sep" />
    <button class="util-link" @click="resetDemo">시연 초기화</button>
    <button class="util-link" @click="tab = 'home'">Home</button>
  </div>
  <header class="gnb">
    <button class="brand" @click="tab = 'home'"><b>D-</b><span>MIN</span><small>체선료 비교</small></button>
    <nav class="gnb-nav" aria-label="주 메뉴">
      <button v-for="g in NAV.filter(canSee)" :key="g.key" :class="{ on: group?.key === g.key }" @click="tab = g.items[0].id">{{ g.gnb }}</button>
    </nav>
    <div class="gnb-right">
      <label class="scen-pill" title="사용자 (시연용 · 실제로는 로그인 계정)">
        <UserRound :size="14" />
        <select id="role" v-model="roleId" aria-label="사용자">
          <option v-for="r in ROLES" :key="r.id" :value="r.id">{{ r.name }}</option>
        </select>
      </label>
      <label class="scen-pill">
        <Layers :size="14" />
        <select id="scen" v-model="scenarioId" aria-label="시나리오">
          <option value="S1">S1 기상 악화일 집중</option>
          <option value="S2">S2 평시</option>
          <option value="S3">S3 대형선 지연</option>
        </select>
      </label>
      <button class="map-btn help-btn" @click="startTour"><CircleHelp :size="14" />사용법</button>
      <button class="map-btn" @click="tab = 'workflow'"><Network :size="14" />사이트맵</button>
    </div>
  </header>

  <div class="body">
    <aside class="lnb" aria-label="하위 메뉴">
      <div v-for="g in NAV" :key="g.key" :class="['lnb-group', { on: group?.key === g.key, off: !canSee(g) }]">
        <button v-if="!canSee(g)" class="lnb-head" disabled title="승인권자만 사용할 수 있습니다">
          <span>{{ g.key }}</span>
          <span class="tog"><Plus :size="10" :stroke-width="3" /></span>
        </button>
        <button v-else class="lnb-head" :aria-expanded="open[g.key]" @click="open[g.key] = !open[g.key]">
          <span>{{ g.key }}</span>
          <span class="tog"><Minus v-if="open[g.key]" :size="10" :stroke-width="3" /><Plus v-else :size="10" :stroke-width="3" /></span>
        </button>
        <ul v-if="open[g.key] && canSee(g)" class="lnb-sub">
          <li v-for="item in g.items" :key="item.id">
            <button :class="{ on: tab === item.id }" :aria-current="tab === item.id ? 'page' : null" @click="tab = item.id">
              {{ item.label }}<span v-if="item.id === 'approvals' && pending" class="cnt">{{ pending }}</span>
            </button>
          </li>
        </ul>
      </div>
      <div class="lnb-status">
        <p class="small muted">결재 상태</p>
        <p v-if="current" class="strong" :class="current.version !== version || current.status === '반려' ? 'warn' : current.status === '승인 대기' ? '' : 'ok'">
          {{ current.label }} {{ current.status }}<span v-if="current.version !== version" class="small"> · 재확인 필요</span>
        </p>
        <p v-else class="strong muted">선택 전</p>
      </div>
    </aside>

    <main class="main">
      <div v-if="result.error && tab !== 'input' && tab !== 'verify'" class="notice danger">
        <CircleAlert class="ico" :size="18" /><span><b>후보 계산 불가</b> — {{ result.error }}</span>
      </div>
      <MapHome v-else-if="tab === 'home'" :result="result" :scen="plain" :current="current" :version="version"
        @go="tab = $event" @focus="focusId = $event" @open="openVessel" />
      <WorkflowView v-else-if="tab === 'workflow'" :result="result" :scen="plain" :current="current" :version="version"
        @go="tab = $event" />
      <ScenarioInput v-else-if="tab === 'input'" :scen="scen" :result="result" @run="tab = 'compare'" />
      <CompareView v-else-if="tab === 'compare'" :result="result" :scen="plain" :focus-id="focusId"
        @focus="focusId = $event" @open="openVessel" @next="tab = 'risk'" />
      <RiskView v-else-if="tab === 'risk'" :result="result" :scen="plain" :focus-id="focusId" :checks="checks"
        :version="version" :current="current" :decisions="decisions" :role="role"
        @focus="focusId = $event" @decide="decide" @next="tab = 'report'" @open="openVessel" @go="tab = $event" />
      <ReportView v-else-if="tab === 'report'" :result="result" :scen="plain" :focus-id="focusId" :current="current" :version="version" />
      <VerifyView v-else-if="tab === 'verify'" />
      <AdminApprovals v-else-if="tab === 'approvals'" :requests="requests" :result="result" :scen="plain" :version="version"
        :role="role" :plan-versions="planVersions" @decide="decide" @open="openVessel" @go="tab = $event" />
      <AdminHistory v-else-if="tab === 'history'" :plan-versions="planVersions" :decisions="decisions" :requests="requests" />
    </main>
  </div>

  <footer class="foot">
    <div class="foot-in">
      <b class="foot-brand">D-MIN</b>
      <div>
        <p class="foot-links"><span class="red">개인정보처리방침</span><span>이용안내</span><span>관련 사이트</span><span>사이트맵</span></p>
        <p>울산 CLX 액체부두 접안 계획 · 체선료 비교 (프로토타입) — 선박명·계약·조석·기상 값은 가상 데이터이며, 화면의 금액은 의사결정 보조용 예상값입니다.</p>
        <p>부두 위치·제원: 공개 자료 수준 · 지도 © OpenStreetMap contributors</p>
      </div>
    </div>
  </footer>

  <VesselDrawer v-if="drawer && drawerSim" :key="`${drawer.simId}-${drawer.vid}-${drawer.mode}`" :sim="drawerSim" :vid="drawer.vid" :scen="plain" :fcfs="result.fcfs"
    :at="drawer.at" :mode="drawer.mode" @close="drawer = null" />
  <Tour v-if="tourIdx !== null" :steps="TOUR" :index="tourIdx" @next="tourNext" @prev="tourPrev" @close="endTour" />
</template>

<style scoped>
.util { height: 30px; display: flex; align-items: center; justify-content: flex-end; gap: 14px; padding: 0 48px; background: #fff; border-bottom: 1px solid #eee; font-size: 12px; color: #555; }
.util .sep { width: 1px; height: 10px; background: #ddd; }
.util-link { border: 0; background: none; padding: 0; color: #777; font-size: 12px; }
.util-link:hover { color: var(--text); }
.gnb { height: 82px; display: grid; grid-template-columns: 260px 1fr auto; align-items: center; padding: 0 48px; background: #fff; border-bottom: 1px solid var(--line-strong); }
.brand { display: flex; align-items: baseline; border: 0; background: none; padding: 0; text-align: left; white-space: nowrap; }
.brand b { font-size: 23px; font-weight: 800; color: var(--accent); letter-spacing: -0.6px; }
.brand span { font-size: 23px; color: #23a3a8; font-weight: 500; letter-spacing: -0.6px; }
.brand small { margin-left: 8px; font-size: 12.5px; color: #777; }
.gnb-nav { display: flex; justify-content: center; gap: 44px; }
.gnb-nav button { border: 0; background: none; padding: 0; font-size: 16px; font-weight: 500; color: #333; height: 82px; border-bottom: 2px solid transparent; }
.gnb-nav button:hover { color: var(--accent); }
.gnb-nav button.on { color: var(--accent); }
.gnb-right { display: flex; align-items: center; gap: 8px; }
.scen-pill { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 6px 0 14px; border-radius: 15px; background: #888c92; color: #fff; }
.scen-pill select { border: 0; background: transparent; color: #fff; font-size: 12px; height: 28px; cursor: pointer; }
.scen-pill select option { color: var(--text); }
.map-btn { display: inline-flex; align-items: center; gap: 5px; height: 30px; padding: 0 12px; border-radius: 15px; border: 1px solid #cfd2d6; background: #fff; font-size: 12px; color: #444; }
.map-btn:hover { border-color: #999; }
.body { display: grid; grid-template-columns: 260px 1fr; min-height: calc(100vh - 112px); }
.lnb { padding: 34px 22px 60px 40px; border-right: 1px solid var(--line-strong); background: var(--bg); }
.lnb-group + .lnb-group { margin-top: 0; }
.lnb-head { width: 100%; height: 44px; display: flex; align-items: center; justify-content: space-between; border: 0; background: none; padding: 0; font-size: 14.5px; letter-spacing: 0.2px; color: #333; text-align: left; }
.lnb-group.on .lnb-head { color: var(--accent); }
.tog { width: 14px; height: 14px; display: grid; place-items: center; background: #c8cbd0; color: #fff; }
.lnb-group.on .tog { background: var(--accent); }
.lnb-group.off .lnb-head { color: #aaa; cursor: not-allowed; }
.lnb-group.off .tog { background: #d5d8dc; }
.lnb-sub { list-style: none; margin: 2px 0 12px -14px; padding: 4px 0 6px 14px; background: #fff; border-left: 2px solid var(--accent); }
.lnb-sub button { width: 100%; border: 0; background: none; text-align: left; padding: 3px 0 3px 12px; font-size: 12px; color: #777; }
.lnb-sub button::before { content: '· '; color: #aaa; }
.lnb-sub button.on { color: var(--text); font-weight: 700; }
.lnb-sub button:hover { color: var(--text); }
.cnt { display: inline-grid; place-items: center; min-width: 16px; height: 16px; padding: 0 4px; margin-left: 6px; border-radius: 8px; background: var(--bad); color: #fff; font-size: 10.5px; font-weight: 700; vertical-align: 1px; }
.lnb-status { margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--line-strong); }
.lnb-status .ok { color: var(--ok); }
.lnb-status .warn { color: var(--warn); }
.main { padding: 34px 28px 60px; min-width: 0; }
.main > * { max-width: 1400px; }
.foot { background: #3a3a3a; color: #bbb; font-size: 12px; }
.foot-in { display: flex; gap: 36px; align-items: center; padding: 28px 48px 30px; }
.foot-brand { font-size: 18px; color: #888; font-weight: 700; }
.foot p + p { margin-top: 4px; }
.foot-links { display: flex; gap: 0; margin-bottom: 6px; }
.foot-links span { padding: 0 12px; border-left: 1px solid #666; color: #ddd; }
.foot-links span:first-child { padding-left: 0; border-left: 0; }
.foot-links .red { color: #7fd0d3; }
</style>
