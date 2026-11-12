<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-vue-next'
import { risks, validate } from '../lib/engine.js'
import ViewHead from './ViewHead.vue'
import { money } from '../lib/time.js'

const props = defineProps({ result: Object, scen: Object, current: Object, version: Number })
const emit = defineEmits(['go'])

const LANES = [
  { id: 'human', label: '담당자', sub: '사람' },
  { id: 'engine', label: '규칙 엔진', sub: 'Spring · 결정적 계산' },
  { id: 'solver', label: '솔버 Agent', sub: 'Python · 배치 제안' },
  { id: 'writer', label: '문장 Agent', sub: 'Python · LLM' },
]

const chosen = computed(() => (props.current && props.current.version === props.version ? props.current : null))
const best = computed(() => props.result.candidates[0])
const bestRisks = computed(() => risks(best.value, props.scen))
const count = (arr, f) => arr.filter(f).length
const ruleSummary = computed(() => {
  const c = {}
  for (const v of props.scen.vessels) {
    const ids = [v.contract.norTurnH ? 'LT-START-NOR' : 'LT-START-IMM', { FULL: 'WX-DED-FULL', HALF: 'WX-DED-HALF', NONE: 'WX-DED-NONE' }[v.contract.weather]]
    for (const id of ids) c[id] = (c[id] ?? 0) + 1
  }
  return Object.entries(c).map(([k, n]) => `${k} ${n}건`).join(' · ')
})
const violations = computed(() => [props.result.fcfs, ...props.result.candidates].reduce((n, s) => n + validate(s, props.scen).length, 0))

const steps = computed(() => {
  const s = props.scen
  const r = props.result
  return [
    { lane: 'human', title: '상황 입력', out: `${s.vessels.length}척 · ${s.berths.length}부두`, tab: 'input',
      input: '선박 도착 일시와 계약, 부두 제원, 현재 접안 중인 선박', process: '스케줄러가 화면 또는 파일로 대기 선박과 부두 상황을 입력합니다.',
      output: `선박 ${s.vessels.length}척, 부두 ${s.berths.length}곳, 계약 ${s.vessels.length}건` },
    { lane: 'engine', title: '입력 검증', out: '검사 · 데이터 고정', tab: 'input',
      input: '시나리오, 공공데이터(기상·조석·일출몰)', process: '필수값·시각·참조를 검사하고 기상·조석 값의 출처와 버전을 실행 단위로 고정합니다. 같은 입력은 언제 재실행해도 같은 결과를 냅니다.',
      output: `기상: ${s.env.weather ? s.env.weather.label : '이상 없음'} · 만조 ${s.env.highTides.length}회 · 일출몰 ${s.env.days.length}일치` },
    { lane: 'engine', title: '규칙 준비', out: `계약 ${s.vessels.length}건 → 규칙`, tab: 'verify',
      input: '선박별 계약 조항', process: '계약마다 다른 정박시간 개시 시점과 기상 공제 조항을 규칙 ID로 변환합니다. 규칙은 코드가 아니라 계약에서 읽습니다.',
      output: ruleSummary.value },
    { lane: 'engine', title: '도착순 기준안', out: money(r.fcfs.total), tab: 'compare',
      input: '도착 순서, 부두별 가능 시각', process: '도착 순서대로 가장 빨리 접안 가능한 부두에 배정해 비교 기준을 만듭니다. 현행 실적이 아닌 비교용입니다.',
      output: `총 예상 체선료 ${money(r.fcfs.total)}` },
    { lane: 'solver', title: '순서 탐색', out: `${r.explored.toLocaleString()}안 탐색`, tab: 'compare',
      input: '규칙 엔진이 만든 선박별 가능 부두·작업 시간·비용표', process: '접안 순서와 부두 배정을 바꿔 가며 체선료가 낮은 배치를 찾습니다. 솔버는 배치만 제안하고 금액은 확정하지 않습니다.',
      output: `서로 다른 배치 ${r.distinct}개`, proto: '프로토타입은 브라우저에서 6척의 전체 조합을 직접 계산합니다. 실제 구현은 Python 솔버(OR-Tools 검토)가 담당합니다.' },
    { lane: 'engine', title: '재검증·확정', out: `후보 ${r.candidates.length}개 · 위반 ${violations.value}`, tab: 'compare',
      input: '솔버가 낸 배치', process: '규칙 엔진이 모든 제약을 처음부터 재검사하고 선박별 체선료를 센트 단위로 한 번만 확정합니다. 통과한 안만 화면에 표시합니다.',
      output: r.candidates.map((c) => `${c.label} ${money(c.total)}`).join(' · ') },
    { lane: 'engine', title: '리스크 점검', out: `해당 ${count(bestRisks.value, (x) => x.state === '해당')} · 불가 ${count(bestRisks.value, (x) => x.state === '판단 불가')}`, tab: 'risk',
      input: '후보 배치, 기상·설비·탱크·출하 계획', process: '후보마다 날씨 급변·설비·탱크·긴급 출하·현장 안전을 해당 / 해당 없음 / 판단 불가로 판정하고, 도착 ±6시간·기상 변화 시 순위 변동을 재계산합니다.',
      output: `${best.value.label}: ${bestRisks.value.map((x) => `${x.label} ${x.state}`).join(', ')}` },
    { lane: 'writer', title: '초안 작성', out: '메일·보고서 초안', tab: 'report',
      input: '확정된 금액·시각, 리스크 판정', process: 'LLM은 문장 틀만 작성합니다. 금액과 시각은 규칙 엔진 결과를 그대로 넣고 재대조하며, 불일치 시 템플릿 문장으로 대체합니다.',
      output: '메일·보고서 초안 (담당자 검토용)', proto: '프로토타입은 LLM을 호출하지 않고 템플릿 문장으로 생성합니다.' },
    { lane: 'human', title: '후보 선택', out: chosen.value ? `${chosen.value.label} ${chosen.value.status}` : '담당자 대기', tab: 'risk', waiting: !chosen.value,
      input: '후보 비교, 리스크, 초안', process: '담당자가 리스크를 확인하고 후보를 선택합니다. Agent는 확정하지 않으며 선택·취소·반영 완료는 이력으로만 기록됩니다.',
      output: chosen.value ? `${chosen.value.label} 선택됨` : '선택 전' },
  ]
})

// SVG 배치
const W = 1360
const LABEL_W = 150
const LANE_H = 92
const NODE_W = 124
const NODE_H = 58
const colW = (W - LABEL_W - 16) / 9
const H = LANE_H * LANES.length
const laneIdx = (id) => LANES.findIndex((l) => l.id === id)
const nodes = computed(() =>
  steps.value.map((s, i) => ({
    ...s, i,
    x: LABEL_W + i * colW + (colW - NODE_W) / 2,
    y: laneIdx(s.lane) * LANE_H + (LANE_H - NODE_H) / 2,
  })),
)
const edges = computed(() =>
  nodes.value.slice(1).map((b, k) => {
    const a = nodes.value[k]
    const x1 = a.x + NODE_W
    const y1 = a.y + NODE_H / 2
    const x2 = b.x
    const y2 = b.y + NODE_H / 2
    const mx = (x1 + x2) / 2
    return { i: b.i, d: y1 === y2 ? `M${x1},${y1} H${x2 - 4}` : `M${x1},${y1} H${mx} V${y2} H${x2 - 4}` }
  }),
)

// 재생은 사용자가 직접 넘긴다. head = 지금까지 보여 준 단계 수.
const head = ref(0)
const selected = ref(-1)
const auto = ref(false)
let timer = null
const total = computed(() => steps.value.length)
function go(n) {
  head.value = Math.max(0, Math.min(total.value, n))
  selected.value = head.value - 1
}
const next = () => go(head.value + 1)
const prev = () => go(head.value - 1)
function stopAuto() {
  clearInterval(timer)
  auto.value = false
}
function toggleAuto() {
  if (auto.value) return stopAuto()
  if (head.value >= total.value) go(0)
  auto.value = true
  next()
  timer = setInterval(() => {
    next()
    if (head.value >= total.value) stopAuto()
  }, 1600)
}
function pick(i) {
  stopAuto()
  if (i >= head.value) head.value = i + 1
  selected.value = i
}
function onKey(e) {
  if (e.key === 'ArrowRight') { stopAuto(); next() }
  if (e.key === 'ArrowLeft') { stopAuto(); prev() }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => { stopAuto(); window.removeEventListener('keydown', onKey) })
const stateOf = (n) => (n.i < head.value ? (n.waiting && head.value >= total.value ? 'waiting' : 'done') : 'pending')
const sel = computed(() => (selected.value >= 0 ? steps.value[selected.value] : null))
</script>

<template>
  <div class="stack">
    <ViewHead title="Agent 워크플로우" crumb="APPENDIX > Agent 워크플로우" :desc="`현재 시나리오(${scen.name})의 계산 순서와 단계별 담당 주체. 단계를 직접 넘겨 확인합니다.`" />
    <section class="panel">
      <div class="panel-head">
        <h2>단계 흐름</h2>
        <div class="row">
          <button class="btn" :disabled="head === 0" @click="stopAuto(); go(0)">처음으로</button>
          <button class="btn" :disabled="head === 0" @click="stopAuto(); prev()"><ChevronLeft :size="14" />이전</button>
          <span class="counter num">{{ head }} / {{ total }}</span>
          <button class="btn primary" :disabled="head >= total" @click="stopAuto(); next()">다음 단계<ChevronRight :size="14" /></button>
          <button class="btn" @click="toggleAuto"><Pause v-if="auto" :size="14" /><Play v-else :size="14" />{{ auto ? '멈춤' : '자동 재생' }}</button>
          <button class="btn" :disabled="head >= total" @click="stopAuto(); go(total)">전체 보기</button>
        </div>
      </div>
      <div class="panel-body">
        <svg :viewBox="`0 0 ${W} ${H}`" class="flow" role="img" aria-label="Agent 워크플로우">
          <defs>
            <marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" class="arrow-head" />
            </marker>
            <marker id="arr-on" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" class="arrow-head on" />
            </marker>
          </defs>
          <g v-for="(l, i) in LANES" :key="l.id" :class="['lane', l.id]">
            <rect :x="0" :y="i * LANE_H" :width="W" :height="LANE_H" class="lane-bg" />
            <rect :x="0" :y="i * LANE_H + 10" width="4" :height="LANE_H - 20" rx="2" class="lane-bar" />
            <text x="16" :y="i * LANE_H + LANE_H / 2 - 4" class="lane-label">{{ l.label }}</text>
            <text x="16" :y="i * LANE_H + LANE_H / 2 + 14" class="lane-sub">{{ l.sub }}</text>
          </g>
          <path v-for="e in edges" :key="e.i" :d="e.d" :class="['edge', { on: e.i < head }]" :marker-end="e.i < head ? 'url(#arr-on)' : 'url(#arr)'" />
          <g v-for="n in nodes" :key="n.i" :class="['node', n.lane, stateOf(n), { sel: n.i === selected }]" @click="pick(n.i)">
            <rect :x="n.x" :y="n.y" :width="NODE_W" :height="NODE_H" rx="8" />
            <text :x="n.x + 12" :y="n.y + 23" class="node-title">{{ n.i + 1 }}. {{ n.title }}</text>
            <text :x="n.x + 12" :y="n.y + 43" class="node-out">{{ stateOf(n) === 'pending' ? '아직' : n.out }}</text>
          </g>
        </svg>
      </div>
    </section>

    <div class="detail-grid">
      <section v-if="!sel" class="panel detail">
        <div class="panel-head"><h2>단계 상세</h2></div>
        <div class="panel-body">
          <p>「다음 단계」 또는 → 키로 한 단계씩 진행합니다. 단계별 입력·처리·이번 시나리오 결과가 이 칸에 표시됩니다.</p>
          <p class="muted small hint">그림의 상자를 직접 선택해도 됩니다. 가로줄은 해당 단계를 맡는 주체입니다.</p>
        </div>
      </section>
      <section v-else class="panel detail">
        <div class="panel-head">
          <h2>{{ selected + 1 }}단계 · {{ sel.title }}</h2>
          <span class="muted">{{ LANES.find((l) => l.id === sel.lane).label }}</span>
          <button class="btn" @click="emit('go', sel.tab)">해당 화면</button>
        </div>
        <div class="panel-body">
          <dl class="io">
            <dt>입력</dt><dd>{{ sel.input }}</dd>
            <dt>하는 일</dt><dd>{{ sel.process }}</dd>
            <dt>이번 결과</dt><dd class="strong">{{ sel.output }}</dd>
          </dl>
          <p v-if="sel.proto" class="proto small">{{ sel.proto }}</p>
        </div>
      </section>

      <section class="panel rules">
        <div class="panel-head"><h2>역할 분리 원칙</h2></div>
        <div class="panel-body">
          <ul>
            <li><span class="sw engine" /><span><b>금액·시각·제약은 규칙 엔진만</b> 계산합니다. 같은 입력이면 항상 같은 숫자입니다.</span></li>
            <li><span class="sw solver" /><span><b>솔버는 배치만 제안</b>합니다. 규칙 엔진 재검증을 통과한 안만 표시합니다.</span></li>
            <li><span class="sw writer" /><span><b>LLM은 문장만</b> 작성합니다. 숫자를 바꾸거나 판정하지 않습니다.</span></li>
            <li><span class="sw human" /><span><b>확정은 담당자만</b> 합니다. Agent에는 계획 확정 도구가 없습니다.</span></li>
          </ul>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.flow { width: 100%; height: auto; display: block; font-family: inherit; }
.lane-bg { fill: transparent; }
.lane:nth-child(odd) .lane-bg { fill: #fafbfc; }
.lane-label { font-size: 15px; font-weight: 700; fill: var(--text); }
.lane-sub { font-size: 12px; fill: var(--muted); }
.lane-bar { fill: var(--c); }
.lane.human, .node.human { --c: #0b5872; --cw: #e2eff4; }
.lane.engine, .node.engine { --c: #1d6b45; --cw: #e4f2ea; }
.lane.solver, .node.solver { --c: #5a4fa0; --cw: #eeecf8; }
.lane.writer, .node.writer { --c: #9a5200; --cw: #fff1dc; }
.edge { fill: none; stroke: var(--line-strong); stroke-width: 1.5; stroke-dasharray: 4 4; transition: stroke 0.3s; }
.edge.on { stroke: #5b6676; stroke-dasharray: none; }
.arrow-head { fill: var(--line-strong); }
.arrow-head.on { fill: #5b6676; }
.node { cursor: pointer; }
.node rect { fill: #fff; stroke: var(--line-strong); stroke-width: 1.5; transition: fill 0.3s, stroke 0.3s; }
.node.done rect { fill: var(--cw); stroke: var(--c); }
.node.waiting rect { fill: #fff; stroke: var(--c); stroke-width: 2; stroke-dasharray: 5 4; }
.node.sel rect { stroke-width: 3; }
.node-title { font-size: 13.5px; font-weight: 700; fill: var(--text); }
.node.pending .node-title { fill: var(--faint); }
.node-out { font-size: 12px; fill: var(--muted); font-variant-numeric: tabular-nums; }
.node.done .node-out { fill: var(--c); font-weight: 650; }
.controls { display: flex; align-items: center; gap: 6px; flex: none; }
.counter { min-width: 48px; text-align: center; font-weight: 650; color: var(--muted); }
.hint { margin-top: 8px; }
.detail-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 16px; align-items: start; }
.io { display: grid; grid-template-columns: 72px 1fr; gap: 10px 14px; margin: 0; }
.io dt { color: var(--muted); font-weight: 600; }
.io dd { margin: 0; }
.proto { margin-top: 12px; padding: 8px 12px; background: var(--unknown-weak); color: var(--unknown); border-radius: 6px; }
.rules ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }
.rules li { display: flex; gap: 10px; align-items: baseline; }
.sw { flex: none; width: 10px; height: 10px; border-radius: 3px; background: var(--c); }
.sw.human { --c: #0b5872; }
.sw.engine { --c: #1d6b45; }
.sw.solver { --c: #5a4fa0; }
.sw.writer { --c: #9a5200; }
</style>
