<script setup>
import { computed } from 'vue'
import Timeline from './Timeline.vue'
import { risks, validate } from '../lib/engine.js'
import { at, fmt, fmtDur, money } from '../lib/time.js'

const props = defineProps({ result: Object, scen: Object, focusId: String })
const emit = defineEmits(['focus', 'open', 'next'])

const all = computed(() => [props.result.fcfs, ...props.result.candidates])
const range = computed(() => {
  const end = Math.max(...all.value.flatMap((s) => s.placements.map((p) => p.etu)))
  return { start: at(14, 0), end: Math.ceil((end + 60) / 360) * 360 }
})
const cards = computed(() =>
  all.value.map((s) => {
    const r = risks(s, props.scen)
    return {
      sim: s,
      delta: s.total - props.result.fcfs.total,
      hit: r.filter((x) => x.state === '해당').length,
      unknown: r.filter((x) => x.state === '판단 불가').length,
      violations: validate(s, props.scen).length,
    }
  }),
)
const focus = computed(() => all.value.find((s) => s.id === props.focusId) ?? props.result.candidates[0])
const vessel = computed(() => Object.fromEntries(props.scen.vessels.map((v) => [v.id, v])))
const berthName = (id) => props.scen.berths.find((b) => b.id === id).name
const fcfsBy = computed(() => Object.fromEntries(props.result.fcfs.placements.map((p) => [p.vid, p])))
const rows = computed(() => [...focus.value.placements].sort((a, b) => vessel.value[a.vid].eta - vessel.value[b.vid].eta))
const pctOf = (d) => (props.result.fcfs.total ? Math.round((d / props.result.fcfs.total) * 1000) / 10 : 0)
</script>

<template>
  <div class="stack">
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>접안 순서 후보 비교</h2>
          <p class="muted small">
            {{ result.explored.toLocaleString() }}개 순서·부두 조합을 같은 규칙으로 돌려 서로 다른 배치 {{ result.distinct }}개를 얻었고,
            그중 총 예상 체선료가 낮은 후보 {{ result.candidates.length }}개를 남겼어요. 모두 제약 검증을 다시 통과한 안이에요.
          </p>
        </div>
        <div class="row">
          <span class="chip unknown">결과 신뢰: 가정값 포함</span>
          <span class="chip">최선 탐색 결과 (최적 증명 아님)</span>
        </div>
      </div>
      <div class="panel-body cards">
        <button v-for="c in cards" :key="c.sim.id" :class="['card', { on: c.sim.id === focus.id, base: c.sim.id === 'FCFS' }]"
          @click="emit('focus', c.sim.id)">
          <div class="card-top">
            <span class="strong">{{ c.sim.label }}</span>
            <span v-if="c.sim.id === 'A'" class="chip accent">체선료 최저</span>
            <span v-if="c.sim.id === 'FCFS'" class="faint small">비교용 · 현행 실적 아님</span>
          </div>
          <div class="total num">{{ money(c.sim.total) }}</div>
          <div class="delta num" :class="{ good: c.delta < 0 }">
            <template v-if="c.sim.id === 'FCFS'">기준</template>
            <template v-else>{{ money(c.delta) }} ({{ pctOf(c.delta) }}%)</template>
          </div>
          <div class="card-meta">
            <span class="small muted">변경 선박 {{ c.sim.changed.length }}척</span>
            <span class="small" :class="c.violations ? 'bad-text' : 'muted'">제약 위반 {{ c.violations }}</span>
          </div>
          <div class="card-risk">
            <span class="chip" :class="c.hit ? 'hit' : 'none'">리스크 해당 {{ c.hit }}</span>
            <span v-if="c.unknown" class="chip unknown">판단 불가 {{ c.unknown }}</span>
          </div>
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>부두별 타임라인</h2>
        <div class="legend small muted">
          <span><i class="lg bar" />작업</span>
          <span><i class="lg bar dem" />체선 발생</span>
          <span><i class="lg bar changed" />기준안과 달라진 선박</span>
          <span><i class="lg wait" />도착 후 대기</span>
          <span><i class="lg night" />야간</span>
          <span><i class="lg weather" />{{ scen.env.weather ? scen.env.weather.label : '기상 악화 없음' }}</span>
          <span><i class="lg maint" />설비 점검</span>
          <span><i class="lg tide" />만조(1번 부두)</span>
        </div>
      </div>
      <div class="panel-body tls">
        <div v-for="s in all" :key="s.id" :class="['tl-row', { on: s.id === focus.id }]">
          <button class="tl-head" @click="emit('focus', s.id)">
            <span class="strong">{{ s.label }}</span>
            <span class="num small">{{ money(s.total) }}</span>
          </button>
          <Timeline :sim="s" :scen="scen" :range="range" :changed="s.changed" :axis="s.id === 'FCFS'" compact @pick="(vid) => emit('open', s.id, vid)" />
        </div>
        <p class="faint small">막대를 누르면 그 선박의 체선료 산출 근거가 열려요.</p>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>{{ focus.label }} 선박별 결과</h2>
        <button class="btn primary" @click="emit('next')">리스크 확인하고 고르기 →</button>
      </div>
      <div class="panel-body">
        <table class="grid">
          <thead>
            <tr>
              <th>선박</th><th>제품</th><th>부두</th><th>도착(NOR)</th><th>접안(ETB)</th><th class="r">대기</th>
              <th>작업 종료</th><th class="r">예상 체선료</th><th class="r">기준안 대비</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in rows" :key="p.vid" class="clickable" @click="emit('open', focus.id, p.vid)">
              <td class="strong">{{ vessel[p.vid].name }}<span v-if="focus.changed.includes(p.vid)" class="chip accent tiny">변경</span></td>
              <td>{{ vessel[p.vid].product }} {{ vessel[p.vid].dir }}</td>
              <td>{{ berthName(p.bid) }}</td>
              <td class="num">{{ fmt(vessel[p.vid].eta) }}</td>
              <td class="num">{{ fmt(p.etb) }}</td>
              <td class="num r">{{ fmtDur(p.waitMin) }}</td>
              <td class="num">{{ fmt(p.etu) }}</td>
              <td class="num r" :class="{ 'warn-text': p.dem.cents > 0 }">{{ money(p.dem.cents) }}</td>
              <td class="num r" :class="{ 'good-text': p.dem.cents < fcfsBy[p.vid].dem.cents, 'warn-text': p.dem.cents > fcfsBy[p.vid].dem.cents }">
                {{ p.dem.cents === fcfsBy[p.vid].dem.cents ? '-' : (p.dem.cents > fcfsBy[p.vid].dem.cents ? '+' : '') + money(p.dem.cents - fcfsBy[p.vid].dem.cents) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.card {
  text-align: left; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;
}
.card:hover { border-color: var(--line-strong); }
.card.on { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.card.base { background: #fafbfc; }
.card-top { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.total { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; margin-top: 2px; }
.delta { font-size: 13px; color: var(--muted); font-weight: 600; }
.delta.good { color: var(--ok); }
.card-meta { display: flex; gap: 12px; margin-top: 4px; }
.card-risk { display: flex; gap: 6px; margin-top: 2px; }
.bad-text { color: var(--bad); font-weight: 650; }
.warn-text { color: var(--warn); font-weight: 650; }
.good-text { color: var(--ok); font-weight: 650; }
.tiny { margin-left: 6px; font-size: 11px; padding: 0 6px; }

.tls { display: flex; flex-direction: column; gap: 6px; }
.tl-row { display: grid; grid-template-columns: 120px 1fr; gap: 8px; padding: 6px 8px; border-radius: 6px; border: 1px solid transparent; }
.tl-row.on { background: #f7fafb; border-color: var(--accent-weak); }
.tl-head { border: none; background: none; text-align: left; display: flex; flex-direction: column; justify-content: center; gap: 2px; padding: 0; }

.legend { display: flex; flex-wrap: wrap; gap: 12px; justify-content: flex-end; }
.legend span { display: inline-flex; align-items: center; gap: 5px; }
.lg { display: inline-block; width: 16px; height: 10px; border-radius: 2px; }
.lg.bar { background: var(--accent-weak); border: 1px solid #8fb7c7; }
.lg.bar.dem { background: var(--warn-weak); border-color: #e2b26f; }
.lg.bar.changed { border-width: 2px; }
.lg.wait { height: 0; border-top: 2px dotted var(--faint); border-radius: 0; }
.lg.night { background: rgba(30, 41, 59, 0.12); }
.lg.weather { background: repeating-linear-gradient(135deg, rgba(179, 38, 30, 0.25) 0 3px, rgba(179, 38, 30, 0.06) 3px 6px); }
.lg.maint { background: repeating-linear-gradient(45deg, rgba(90, 79, 160, 0.3) 0 2px, transparent 2px 4px); }
.lg.tide { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #2f7fb0; border-radius: 0; }
</style>
