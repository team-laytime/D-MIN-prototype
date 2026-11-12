<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { risks, validate } from '../lib/engine.js'
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
      input: '선박 도착 일시와 계약, 부두 제원, 현재 접안 중인 선박', process: '스케줄러가 화면이나 파일로 대기 선박과 부두 상황을 넣어요.',
      output: `선박 ${s.vessels.length}척, 부두 ${s.berths.length}곳, 계약 ${s.vessels.length}건` },
    { lane: 'engine', title: '입력 검증', out: '검사 · 데이터 고정', tab: 'input',
      input: '시나리오, 공공데이터(기상·조석·일출몰)', process: '필수값·시각·참조를 검사하고, 기상·조석 값의 출처와 버전을 이번 실행에 고정해요. 같은 입력이면 언제 다시 돌려도 같은 결과가 나와요.',
      output: `기상: ${s.env.weather ? s.env.weather.label : '이상 없음'} · 만조 ${s.env.highTides.length}회 · 일출몰 ${s.env.days.length}일치` },
    { lane: 'engine', title: '규칙 준비', out: `계약 ${s.vessels.length}건 → 규칙`, tab: 'verify',
      input: '선박별 계약 조항', process: '계약마다 다른 정박시간 개시 시점과 기상 공제 조항을 규칙 ID로 바꿔요. 규칙은 코드에 박지 않고 계약에서 읽어요.',
      output: ruleSummary.value },
    { lane: 'engine', title: '도착순 기준안', out: money(r.fcfs.total), tab: 'compare',
      input: '도착 순서, 부두별 가능 시각', process: '도착 순서대로 가장 빨리 댈 수 있는 부두에 붙여 비교 기준을 만들어요. 현행 실적이 아니라 비교용이에요.',
      output: `총 예상 체선료 ${money(r.fcfs.total)}` },
    { lane: 'solver', title: '순서 탐색', out: `${r.explored.toLocaleString()}안 탐색`, tab: 'compare',
      input: '규칙 엔진이 만든 선박별 가능 부두·작업 시간·비용표', process: '접안 순서와 부두 배정을 바꿔 가며 체선료가 낮은 배치를 찾아요. 솔버는 배치만 제안하고 금액은 확정하지 않아요.',
      output: `서로 다른 배치 ${r.distinct}개`, proto: '프로토타입은 브라우저에서 6척의 모든 조합을 직접 돌려요. 실제로는 Python 솔버(OR-Tools 검토)가 맡아요.' },
    { lane: 'engine', title: '재검증·확정', out: `후보 ${r.candidates.length}개 · 위반 ${violations.value}`, tab: 'compare',
      input: '솔버가 낸 배치', process: '규칙 엔진이 모든 제약을 처음부터 다시 검사하고, 선박별 체선료를 센트 단위로 한 번만 확정해요. 통과한 안만 화면에 나가요.',
      output: r.candidates.map((c) => `${c.label} ${money(c.total)}`).join(' · ') },
    { lane: 'engine', title: '리스크 점검', out: `해당 ${count(bestRisks.value, (x) => x.state === '해당')} · 불가 ${count(bestRisks.value, (x) => x.state === '판단 불가')}`, tab: 'risk',
      input: '후보 배치, 기상·설비·탱크·출하 계획', process: '후보마다 날씨 급변·설비·탱크·긴급 출하·현장 안전을 해당 / 해당 없음 / 판단 불가로 판정하고, 도착 ±6시간·기상 변화에 순위가 바뀌는지 다시 계산해요.',
      output: `${best.value.label}: ${bestRisks.value.map((x) => `${x.label} ${x.state}`).join(', ')}` },
    { lane: 'writer', title: '초안 작성', out: '메일·보고서 초안', tab: 'report',
      input: '확정된 금액·시각, 리스크 판정', process: 'LLM은 문장 틀만 써요. 금액과 시각은 규칙 엔진 결과를 그대로 끼워 넣고 다시 대조해요. 어긋나면 템플릿 문장으로 바꿔요.',
      output: '메일·보고서 초안 (담당자 검토용)', proto: '프로토타입은 LLM을 부르지 않고 템플릿 문장으로 만들어요.' },
    { lane: 'human', title: '후보 선택', out: chosen.value ? `${chosen.value.label} ${chosen.value.status}` : '담당자 대기', tab: 'risk', waiting: !chosen.value,
      input: '후보 비교, 리스크, 초안', process: '담당자가 리스크를 확인하고 후보를 골라요. Agent는 확정하지 않고, 선택·취소·반영 완료는 이력으로만 남아요.',
      output: chosen.value ? `${chosen.value.label} 선택됨` : '아직 선택 전' },
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

// 재생: 단계가 하나씩 켜진다.
const head = ref(steps.value.length)
const selected = ref(4)
let timer = null
function play() {
  clearInterval(timer)
  head.value = 0
  selected.value = 0
  timer = setInterval(() => {
    head.value++
    if (head.value < steps.value.length) selected.value = head.value
    if (head.value >= steps.value.length) clearInterval(timer)
  }, 700)
}
onMounted(play)
onBeforeUnmount(() => clearInterval(timer))
const stateOf = (n) => (n.i < head.value ? (n.waiting && head.value >= steps.value.length ? 'waiting' : 'done') : n.i === head.value ? 'running' : 'pending')
const sel = computed(() => steps.value[selected.value])
const playing = computed(() => head.value < steps.value.length)
</script>

<template>
  <div class="stack">
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Agent 워크플로우</h2>
          <p class="muted small">지금 시나리오({{ scen.name }})가 어떤 순서로 계산됐는지 보여 줘요. 단계를 누르면 그 단계의 입력과 결과가 나와요.</p>
        </div>
        <button class="btn" :disabled="playing" @click="play">{{ playing ? '재생 중…' : '▶ 처음부터 다시 재생' }}</button>
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
          <g v-for="n in nodes" :key="n.i" :class="['node', n.lane, stateOf(n), { sel: n.i === selected }]" @click="selected = n.i">
            <rect :x="n.x" :y="n.y" :width="NODE_W" :height="NODE_H" rx="8" />
            <text :x="n.x + 12" :y="n.y + 23" class="node-title">{{ n.i + 1 }}. {{ n.title }}</text>
            <text :x="n.x + 12" :y="n.y + 43" class="node-out">{{ stateOf(n) === 'pending' ? '대기' : stateOf(n) === 'running' ? '실행 중…' : n.out }}</text>
          </g>
        </svg>
      </div>
    </section>

    <div class="detail-grid">
      <section class="panel detail">
        <div class="panel-head">
          <div>
            <p class="small muted">{{ selected + 1 }}단계 · {{ LANES.find((l) => l.id === sel.lane).label }}</p>
            <h2>{{ sel.title }}</h2>
          </div>
          <button class="btn ghost" @click="emit('go', sel.tab)">화면에서 보기 →</button>
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
        <div class="panel-head"><h3>역할을 나눈 이유</h3></div>
        <div class="panel-body">
          <ul>
            <li><span class="sw engine" /><b>금액·시각·제약은 규칙 엔진만</b> 계산해요. 같은 입력이면 늘 같은 숫자가 나와요.</li>
            <li><span class="sw solver" /><b>솔버는 배치만 제안</b>해요. 규칙 엔진 재검증을 통과해야 화면에 나가요.</li>
            <li><span class="sw writer" /><b>LLM은 문장만</b> 써요. 숫자를 바꾸거나 판정하지 않아요.</li>
            <li><span class="sw human" /><b>확정은 사람만</b> 해요. Agent에는 계획을 확정하는 도구가 없어요.</li>
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
.node.running rect { fill: #fff; stroke: var(--c); stroke-width: 2.5; animation: pulse 0.7s ease-in-out infinite alternate; }
.node.waiting rect { fill: #fff; stroke: var(--c); stroke-width: 2; stroke-dasharray: 5 4; }
.node.sel rect { stroke-width: 3; }
.node-title { font-size: 13.5px; font-weight: 700; fill: var(--text); }
.node.pending .node-title { fill: var(--faint); }
.node-out { font-size: 12px; fill: var(--muted); font-variant-numeric: tabular-nums; }
.node.done .node-out { fill: var(--c); font-weight: 650; }
@keyframes pulse { from { stroke-opacity: 1; } to { stroke-opacity: 0.35; } }
@media (prefers-reduced-motion: reduce) { .node.running rect { animation: none; } }
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
