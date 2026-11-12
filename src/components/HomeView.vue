<script setup>
import { computed } from 'vue'
import { risks } from '../lib/engine.js'
import { fmt, fmtDur, money } from '../lib/time.js'

const props = defineProps({ result: Object, scen: Object, current: Object, version: Number })
const emit = defineEmits(['go', 'focus', 'tour'])

const fcfs = computed(() => props.result.fcfs)
const best = computed(() => props.result.candidates[0])
const chosen = computed(() => (props.current && props.current.version === props.version ? props.current : null))
const plan = computed(() => [fcfs.value, ...props.result.candidates].find((s) => s.id === chosen.value?.candId) ?? best.value)
const saving = computed(() => fcfs.value.total - best.value.total)
const savingPct = computed(() => ((saving.value / fcfs.value.total) * 100).toFixed(1))
const options = computed(() => {
  const all = [fcfs.value, ...props.result.candidates]
  const max = Math.max(...all.map((s) => s.total))
  return all.map((s) => ({ sim: s, w: max ? (s.total / max) * 100 : 0 }))
})
const vmap = computed(() => Object.fromEntries(props.scen.vessels.map((v) => [v.id, v])))
const planRisks = computed(() => risks(plan.value, props.scen))
const openRisks = computed(() => planRisks.value.filter((r) => r.state !== '해당 없음'))

const berths = computed(() =>
  props.scen.berths.map((b) => ({
    b,
    queue: plan.value.placements.filter((p) => p.bid === b.id).sort((x, y) => x.etb - y.etb),
  })),
)
const arrivals = computed(() =>
  [...props.scen.vessels]
    .sort((a, b) => a.eta - b.eta)
    .map((v) => {
      const p = plan.value.placements.find((x) => x.vid === v.id)
      const tags = []
      if (v.dwt >= props.scen.env.daylightDwt) tags.push('주간 접안만')
      if (v.draft >= props.scen.env.tideDraft && p && props.scen.berths.find((b) => b.id === p.bid).tideLimited) tags.push('만조 접안')
      if (props.scen.urgent.some((u) => u.vid === v.id)) tags.push('긴급 출하')
      return { v, p, tags }
    }),
)
const firstEta = computed(() => Math.min(...props.scen.vessels.map((v) => v.eta)))
const lastEta = computed(() => Math.max(...props.scen.vessels.map((v) => v.eta)))
const berthName = (id) => props.scen.berths.find((b) => b.id === id).name
const demCount = (s) => s.placements.filter((p) => p.dem.cents > 0).length
const longest = computed(() => best.value.placements.reduce((a, b) => (b.waitMin > a.waitMin ? b : a)))
</script>

<template>
  <div class="stack">
    <section class="hero panel">
      <div class="hero-main">
        <p class="eyebrow">{{ scen.name }} · {{ fmt(firstEta).slice(0, 5) }} 도착 선박 {{ scen.vessels.length }}척</p>
        <h1>
          도착순으로 대면 예상 체선료 <span class="num">{{ money(fcfs.total) }}</span>,<br />
          {{ best.label }}로 바꾸면 <span class="num accent">{{ money(best.total) }}</span>이에요.
        </h1>
        <p class="hero-sub">
          <b class="good num">{{ money(saving) }} ({{ savingPct }}%)</b> 줄어들어요. 대신 확인할 리스크가
          <b>{{ openRisks.length }}건</b> 있어요.
        </p>
        <div class="bars">
          <button v-for="o in options" :key="o.sim.id" class="bar-row" @click="emit('focus', o.sim.id); emit('go', 'compare')">
            <span class="bar-label">{{ o.sim.id === 'FCFS' ? '도착순 기준안' : o.sim.label }}</span>
            <span class="bar-track"><span :class="['bar-fill', o.sim.id === 'FCFS' ? 'base' : o.sim.id === best.id ? 'best' : 'alt']" :style="{ width: o.w + '%' }" /></span>
            <span class="bar-val num">{{ money(o.sim.total) }}</span>
          </button>
        </div>
        <div class="row cta">
          <button class="btn primary" @click="emit('go', 'compare')">후보 비교하기 →</button>
          <button class="btn" @click="emit('tour')">처음이라면: 사용법 둘러보기</button>
        </div>
        <div class="stats">
          <div class="stat">
            <span class="small muted">체선이 생기는 선박</span>
            <span class="stat-v num">{{ demCount(best) }}척 <span class="small muted">기준안 {{ demCount(fcfs) }}척</span></span>
            <span class="small faint">척수는 늘어도 큰 금액이 사라져 총액이 줄어요</span>
          </div>
          <div class="stat">
            <span class="small muted">가장 오래 기다리는 선박</span>
            <span class="stat-v num">{{ fmtDur(longest.waitMin) }}</span>
            <span class="small faint">{{ vmap[longest.vid].name }} · {{ berthName(longest.bid) }}</span>
          </div>
          <div class="stat">
            <span class="small muted">확인한 조합</span>
            <span class="stat-v num">{{ result.explored.toLocaleString() }}안</span>
            <span class="small faint">제약을 지키는 배치 {{ result.distinct }}개 중 상위 {{ result.candidates.length }}개</span>
          </div>
        </div>
      </div>

      <aside class="hero-side">
        <h3>지금 확인할 것</h3>
        <div v-if="scen.env.weather" class="alert weather">
          <span class="alert-icon">!</span>
          <div>
            <b>{{ scen.env.weather.label }}</b>
            <p class="small">{{ fmt(scen.env.weather.start) }} ~ {{ fmt(scen.env.weather.end) }} · 이 시간에는 접안할 수 없어요</p>
          </div>
        </div>
        <div v-for="r in openRisks" :key="r.key" :class="['alert', r.state === '판단 불가' ? 'unknown' : 'hit']">
          <span class="chip" :class="r.state === '판단 불가' ? 'unknown' : 'hit'">{{ r.state }}</span>
          <div>
            <b>{{ r.label }}</b>
            <p class="small">{{ r.evidence }}</p>
          </div>
        </div>
        <div class="decision">
          <template v-if="chosen">
            <span class="chip none">{{ chosen.status }}</span>
            <span class="small">{{ chosen.label }} · {{ money(chosen.total) }}</span>
          </template>
          <template v-else>
            <span class="chip">선택 전</span>
            <span class="small muted">담당자가 아직 후보를 고르지 않았어요.</span>
            <button class="btn ghost small" @click="emit('go', 'risk')">고르러 가기</button>
          </template>
        </div>
      </aside>
    </section>

    <div class="grid2">
      <section class="panel">
        <div class="panel-head">
          <h2>부두 현황</h2>
          <span class="faint small">{{ plan.label }} 기준 접안 순서</span>
        </div>
        <div class="panel-body berths">
          <div v-for="x in berths" :key="x.b.id" class="berth">
            <div class="berth-head">
              <span class="strong">{{ x.b.name }}</span>
              <span class="faint small">{{ (x.b.maxDwt / 1000).toFixed(0) }}k DWT · {{ x.b.products.join('·') }}</span>
            </div>
            <div v-if="x.b.occupiedBy" class="slot now">
              <span class="dot busy" /><span class="strong">{{ x.b.occupiedBy }}</span>
              <span class="small muted">작업 중 · {{ fmt(x.b.occupiedUntil) }} 종료</span>
            </div>
            <div v-else class="slot now"><span class="dot free" /><span class="small muted">지금 비어 있음</span></div>
            <ol class="queue">
              <li v-for="p in x.queue" :key="p.vid">
                <span class="num small muted">{{ fmt(p.etb) }}</span>
                <span>{{ vmap[p.vid].name }}</span>
                <span v-if="p.dem.cents > 0" class="chip hit">{{ money(p.dem.cents) }}</span>
              </li>
              <li v-if="!x.queue.length" class="small faint">배정된 선박 없음</li>
            </ol>
            <p v-if="x.b.facility.maintenance" class="small maint">{{ x.b.facility.maintenance.label }} {{ fmt(x.b.facility.maintenance.start) }}~{{ fmt(x.b.facility.maintenance.end).slice(6) }}</p>
            <p v-else-if="!x.b.facility.known" class="small unknown-text">설비 점검 일정 미입력</p>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>도착 예정 선박</h2>
          <span class="faint small">{{ fmt(firstEta) }} ~ {{ fmt(lastEta) }}</span>
        </div>
        <div class="panel-body">
          <table class="grid">
            <thead><tr><th>도착</th><th>선박</th><th>화물</th><th>{{ plan.label }} 배정</th><th class="r">대기</th><th>주의</th></tr></thead>
            <tbody>
              <tr v-for="a in arrivals" :key="a.v.id">
                <td class="num">{{ fmt(a.v.eta) }}</td>
                <td class="strong">{{ a.v.name }}</td>
                <td>{{ a.v.product }} {{ a.v.dir }}</td>
                <td>{{ berthName(a.p.bid) }} <span class="faint num small">{{ fmt(a.p.etb).slice(6) }}</span></td>
                <td class="num r" :class="{ 'warn-text': a.p.waitMin >= 12 * 60 }">{{ fmtDur(a.p.waitMin) }}</td>
                <td><span v-for="t in a.tags" :key="t" class="chip tag">{{ t }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.hero { display: grid; grid-template-columns: 1.6fr 1fr; overflow: hidden; }
.hero-main { padding: 24px 28px; display: flex; flex-direction: column; gap: 12px; }
.eyebrow { color: var(--muted); font-weight: 600; font-size: 13px; }
.hero h1 { font-size: 26px; line-height: 1.4; letter-spacing: -0.02em; font-weight: 700; }
.accent { color: var(--accent); }
.good { color: var(--ok); }
.hero-sub { font-size: 15px; color: var(--muted); }
.hero-sub b { color: var(--text); }
.hero-sub b.good { color: var(--ok); }
.bars { display: flex; flex-direction: column; gap: 6px; margin-top: 6px; }
.bar-row { display: grid; grid-template-columns: 110px 1fr 120px; gap: 12px; align-items: center; border: none; background: none; padding: 3px 0; text-align: left; }
.bar-row:hover .bar-track { background: #e9edf1; }
.bar-label { font-weight: 600; font-size: 13px; }
.bar-track { height: 18px; background: #f0f2f5; border-radius: 4px; overflow: hidden; }
.bar-fill { display: block; height: 100%; border-radius: 4px; }
.bar-fill.base { background: #aab2bd; }
.bar-fill.best { background: var(--accent); }
.bar-fill.alt { background: #8fb7c7; }
.bar-val { text-align: right; font-weight: 650; }
.cta { margin-top: 8px; }
.stats { margin-top: auto; padding-top: 16px; border-top: 1px solid var(--line); display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.stat { display: flex; flex-direction: column; gap: 2px; }
.stat-v { font-size: 20px; font-weight: 700; letter-spacing: -0.01em; }
.hero-side { background: #fafbfc; border-left: 1px solid var(--line); padding: 20px 22px; display: flex; flex-direction: column; gap: 10px; }
.alert { display: flex; gap: 10px; align-items: flex-start; padding: 9px 10px; border-radius: 6px; background: var(--panel); border: 1px solid var(--line); }
.alert p { color: var(--muted); margin-top: 2px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.alert.weather { background: var(--bad-weak); border-color: #f2c4bf; }
.alert-icon { flex: none; width: 20px; height: 20px; border-radius: 50%; background: var(--bad); color: #fff; display: grid; place-items: center; font-weight: 800; font-size: 12px; }
.alert .chip { flex: none; }
.decision { margin-top: auto; display: flex; align-items: center; gap: 8px; padding-top: 10px; border-top: 1px solid var(--line); }
.grid2 { display: grid; grid-template-columns: 1fr 1.2fr; gap: 16px; align-items: start; }
.berths { display: flex; flex-direction: column; gap: 10px; }
.berth { border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; }
.berth-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.slot { display: flex; align-items: center; gap: 8px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.busy { background: var(--warn); }
.dot.free { background: var(--ok); }
.queue { margin: 0; padding-left: 16px; display: flex; flex-direction: column; gap: 3px; }
.queue li { display: flex; gap: 8px; align-items: center; }
.maint { color: var(--unknown); }
.unknown-text { color: var(--unknown); }
.warn-text { color: var(--warn); font-weight: 650; }
.chip.tag { margin-right: 4px; }
</style>
