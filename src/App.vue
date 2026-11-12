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
  { id: 'workflow', label: 'Agent 워크플로우', sep: true },
]
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
      @go="tab = $event" @focus="focusId = $event" />
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
