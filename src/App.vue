<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { SCENARIOS } from './lib/scenarios.js'
import { runSearch } from './lib/engine.js'
import { money } from './lib/time.js'
import ScenarioInput from './components/ScenarioInput.vue'
import CompareView from './components/CompareView.vue'
import RiskView from './components/RiskView.vue'
import ReportView from './components/ReportView.vue'
import VerifyView from './components/VerifyView.vue'
import VesselDrawer from './components/VesselDrawer.vue'
import HomeView from './components/HomeView.vue'
import Tour from './components/Tour.vue'
import WorkflowView from './components/WorkflowView.vue'

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
const openVessel = (simId, vid) => { drawer.value = { simId, vid } }
const drawerSim = computed(() => drawer.value && all.value.find((s) => s.id === drawer.value.simId))

// 담당자 선택 이력. 추가만 하고 고치지 않는다.
const decisions = ref([])
const checks = reactive({})
const current = computed(() => {
  let state = null
  for (const d of decisions.value) {
    if (d.action === '선택') state = { ...d, status: '선택됨' }
    else if (d.action === '취소') state = null
    else if (d.action === '현업 반영 완료' && state) state = { ...state, status: '현업 반영 완료' }
  }
  return state
})
function decide(entry) {
  decisions.value.push({ ...entry, at: new Date().toLocaleString('ko-KR', { hour12: false }), version: version.value })
}

const tabs = [
  { id: 'home', label: '홈' },
  { id: 'input', label: '시나리오 입력', n: 1 },
  { id: 'compare', label: '후보 비교', n: 2 },
  { id: 'risk', label: '리스크·선택', n: 3 },
  { id: 'report', label: '보고서 초안', n: 4 },
  { id: 'verify', label: '검증', n: 5 },
  { id: 'workflow', label: '부록 · Agent 워크플로우', sep: true },
]

// 사용법 투어. 자동으로 시작하지 않고, 사용자가 이전/다음으로 넘긴다.
const sampleVessel = () => {
  const a = result.value.candidates[0]
  return (a.placements.find((p) => p.dem.cents > 0) ?? a.placements[0]).vid
}
const TOUR = [
  { section: '홈', tab: 'home', target: '.hero-main', title: '한 줄로 상황 파악하기',
    body: '도착 순서대로 대면 체선료가 얼마인지, 가장 싼 후보로 바꾸면 얼마인지가 맨 위에 나와요. 막대는 후보별 총 예상 체선료예요.',
    try: '막대를 누르면 그 후보의 비교 화면으로 가요.' },
  { section: '홈', tab: 'home', target: '.hero-side', title: '먼저 확인할 것',
    body: '기상 경보와 추천 후보에 남은 리스크가 여기 모여 있어요. 담당자가 후보를 골랐는지도 맨 아래에서 봐요.' },
  { section: '공통', tab: 'home', target: '#scen', title: '상황 바꿔 보기',
    body: '데모 상황 3개 중 하나를 골라요. 바꾸면 모든 화면이 다시 계산되고, 오른쪽 입력 버전 번호가 올라가요.' },
  { section: '1 시나리오 입력', tab: 'input', target: '.inputs', title: '선박과 계약 조건 넣기',
    body: '선박마다 도착 예정 시각, 허용 시간, 하루 체선료, 기상 조항을 고칠 수 있어요. 값을 바꾸는 즉시 후보가 다시 계산돼요.',
    try: 'GOLDEN STAR 도착 시각을 몇 시간 늦춰 보세요.' },
  { section: '1 시나리오 입력', tab: 'input', target: '.env', title: '기상·조석 조건',
    body: '기상 악화 예보를 끄거나 시간을 바꿀 수 있어요. 만조와 일출·일몰은 대형선이 접안할 수 있는 시간을 정해요.' },
  { section: '2 후보 비교', tab: 'compare', target: '.cards', title: '후보 한눈에 비교하기',
    body: '맨 왼쪽은 도착순 기준안이에요(비교용, 현행 실적 아님). 나머지는 체선료가 낮은 후보예요. 총액, 기준안 대비 절감액, 바뀐 선박 수, 리스크 수를 나란히 봐요.',
    try: '카드를 누르면 아래 표가 그 후보로 바뀌어요.' },
  { section: '2 후보 비교', tab: 'compare', target: '.tl-row.on', title: '부두별 타임라인 읽기',
    body: '막대 하나가 선박 한 척의 접안부터 작업 종료까지예요. 주황 막대는 체선료가 생기는 선박, 빗금은 기상 악화, 회색 띠는 야간, 점선은 도착 후 기다린 시간이에요.' },
  { section: '2 후보 비교', tab: 'compare', target: '.drawer', title: '왜 이 금액인지 보기',
    body: '막대나 표에서 선박을 누르면 산출 근거가 열려요. 정박시간을 언제부터 셌는지, 기상 공제를 얼마나 했는지, 어떤 계약 규칙을 썼는지, 접안이 왜 그 시각으로 밀렸는지 나와요.',
    do: () => openVessel(result.value.candidates[0].id, sampleVessel()) },
  { section: '3 리스크·선택', tab: 'risk', target: '.risks', title: '남은 리스크 확인하기',
    body: '후보마다 날씨 급변, 설비, 탱크, 긴급 출하, 현장 안전을 해당 / 해당 없음 / 판단 불가로 보여 줘요. 대안과 주의할 점도 붙어 있어요.',
    try: '「해당」 항목을 읽고 「확인함」을 눌러 보세요.' },
  { section: '3 리스크·선택', tab: 'risk', target: '.decide', title: '후보 고르기',
    body: '사유를 적고 「이 후보로 선택」을 눌러요. 확인 안 한 리스크가 있으면 한 번 더 묻고, 선택·취소는 이력으로 남아요. Agent는 계획을 확정하지 않아요.' },
  { section: '4 보고서 초안', tab: 'report', target: '.cols > .panel:first-child', title: '메일·보고서 초안 받기',
    body: '고른 후보로 메일과 보고서 초안이 만들어져요. 복사하거나 내려받아 쓰면 돼요. 초안의 금액은 계산 결과와 자동으로 맞춰 봐요.' },
  { section: '5 검증', tab: 'verify', target: '.answer-set', title: '계산이 맞는지 확인하기',
    body: '손으로 계산한 정답과 자동 계산이 몇 건 맞는지, 시나리오별로 기준안보다 얼마나 줄였는지와 제약 위반 수를 보여 줘요.' },
  { section: '끝', tab: 'home', target: '.help-btn', title: '언제든 다시 보기',
    body: '오른쪽 위 「사용법」 버튼으로 이 안내를 다시 볼 수 있어요. 이제 직접 눌러 보세요.' },
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
  <header class="top">
    <div class="brand">
      <span class="logo">D-MIN</span>
      <span class="sub">울산 CLX 접안 순서 · 체선료 비교</span>
    </div>
    <div class="scen">
      <label class="muted small" for="scen">시나리오</label>
      <select id="scen" v-model="scenarioId" class="input">
        <option value="S1">S1 · 기상 악화 예보일 선박 집중</option>
        <option value="S2">S2 · 평시 (기상 이상 없음)</option>
        <option value="S3">S3 · 대형선 지연 + 조석 제약</option>
      </select>
      <span class="chip">입력 v{{ version }}</span>
    </div>
    <div class="flags">
      <span class="chip unknown">가상 데이터</span>
      <span class="chip accent">의사결정 보조용 · 최종 선택은 담당자</span>
      <button class="btn help-btn" @click="startTour">사용법</button>
    </div>
  </header>

  <nav class="tabs">
    <template v-for="t in tabs" :key="t.id">
      <span v-if="t.sep" class="tab-sep" />
      <button :class="['tab', { on: tab === t.id }]" @click="tab = t.id">
        <span v-if="t.n" class="idx">{{ t.n }}</span>{{ t.label }}
      </button>
    </template>
    <div class="spacer" />
    <div v-if="current" class="status-pill">
      <span class="chip" :class="current.version === version ? 'none' : 'hit'">{{ current.status }}</span>
      <span class="small">{{ current.label }} · {{ money(current.total) }}</span>
      <span v-if="current.version !== version" class="small warn-text">입력이 바뀌어 다시 확인 필요</span>
    </div>
  </nav>

  <main class="main">
    <div v-if="result.error && !['input', 'verify', 'home'].includes(tab)" class="panel error-box">
      <h3>후보를 만들 수 없어요</h3>
      <p>{{ result.error }}</p>
    </div>
    <div v-else-if="result.error && tab === 'home'" class="panel error-box">
      <h3>후보를 만들 수 없어요</h3>
      <p>{{ result.error }} 「시나리오 입력」에서 값을 고쳐 주세요.</p>
    </div>
    <HomeView v-else-if="tab === 'home'" :result="result" :scen="plain" :current="current" :version="version"
      @go="tab = $event" @focus="focusId = $event" @tour="startTour" />
    <WorkflowView v-else-if="tab === 'workflow'" :result="result" :scen="plain" :current="current" :version="version"
      @go="tab = $event" />
    <ScenarioInput v-else-if="tab === 'input'" :scen="scen" :result="result" @run="tab = 'compare'" />
    <CompareView v-else-if="tab === 'compare'" :result="result" :scen="plain" :focus-id="focusId"
      @focus="focusId = $event" @open="openVessel" @next="tab = 'risk'" />
    <RiskView v-else-if="tab === 'risk'" :result="result" :scen="plain" :focus-id="focusId" :checks="checks"
      :version="version" :current="current" :decisions="decisions"
      @focus="focusId = $event" @decide="decide" @next="tab = 'report'" @open="openVessel" />
    <ReportView v-else-if="tab === 'report'" :result="result" :scen="plain" :focus-id="focusId" :current="current" :version="version" />
    <VerifyView v-else-if="tab === 'verify'" />
  </main>

  <VesselDrawer v-if="drawer && drawerSim" :sim="drawerSim" :vid="drawer.vid" :scen="plain" :fcfs="result.fcfs"
    @close="drawer = null" />
  <Tour v-if="tourIdx !== null" :steps="TOUR" :index="tourIdx" @next="tourNext" @prev="tourPrev" @close="endTour" />
</template>

<style scoped>
.top {
  display: flex; align-items: center; gap: 24px; padding: 12px 28px;
  background: var(--panel); border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: baseline; gap: 10px; }
.logo { font-weight: 800; letter-spacing: 0.02em; color: var(--accent); font-size: 17px; }
.sub { color: var(--muted); font-weight: 550; }
.scen { display: flex; align-items: center; gap: 8px; }
.flags { margin-left: auto; display: flex; gap: 6px; }
.tabs {
  display: flex; align-items: center; gap: 2px; padding: 0 28px;
  background: var(--panel); border-bottom: 1px solid var(--line);
}
.tab {
  border: none; background: none; padding: 12px 14px 11px; color: var(--muted); font-weight: 600;
  border-bottom: 2px solid transparent; display: flex; gap: 8px; align-items: center;
}
.tab:hover { color: var(--text); }
.tab.on { color: var(--accent); border-bottom-color: var(--accent); }
.idx {
  display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 50%;
  font-size: 11px; background: #eef0f3; color: var(--muted);
}
.tab.on .idx { background: var(--accent); color: #fff; }
.tab-sep { width: 1px; height: 18px; background: var(--line-strong); margin: 0 8px; }
.status-pill { display: flex; align-items: center; gap: 8px; }
.warn-text { color: var(--warn); font-weight: 600; }
.main { padding: 20px 28px 48px; max-width: 1480px; }
.error-box { padding: 18px; border-color: var(--bad); }
.error-box h3 { color: var(--bad); margin-bottom: 4px; }
</style>
