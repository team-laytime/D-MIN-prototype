<script setup>
import { computed } from 'vue'
import { ANSWER_SET } from '../lib/answerSet.js'
import { demurrage, runSearch, validate } from '../lib/engine.js'
import { SCENARIOS } from '../lib/scenarios.js'
import { fmt, fmtDur, money } from '../lib/time.js'

const calc = computed(() =>
  ANSWER_SET.map((t) => {
    const vessel = { eta: t.eta, contract: { laytimeH: t.laytimeH, rateUsd: t.rateUsd, norTurnH: t.turnH, weather: t.weather } }
    const d = demurrage(vessel, t.etb, t.etu, { weather: t.wx })
    return { ...t, got: d.cents, ok: d.cents === t.expectedCents, excess: d.excessMin }
  }),
)
const okCount = computed(() => calc.value.filter((r) => r.ok).length)

const scen = computed(() =>
  Object.entries(SCENARIOS).map(([id, make]) => {
    const s = make()
    const t0 = performance.now()
    const r = runSearch(s)
    const ms = Math.round(performance.now() - t0)
    const best = r.candidates[0]
    const violations = [r.fcfs, ...r.candidates].reduce((n, x) => n + validate(x, s).length, 0)
    return { id, name: s.name, vessels: s.vessels.length, berths: s.berths.length, fcfs: r.fcfs.total, best: best.total, saving: r.fcfs.total - best.total, violations, ms, explored: r.explored }
  }),
)
const clause = { FULL: '전부 공제', HALF: '50% 공제', NONE: '공제 없음' }
</script>

<template>
  <div class="stack">
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>체선료 계산 정답 세트</h2>
          <p class="muted small">팀원이 손으로 계산한 값(Decimal, HALF_UP)과 자동 계산을 센트 단위로 비교해요.</p>
        </div>
        <div class="score">
          <span class="num big" :class="okCount === calc.length ? 'ok' : 'bad'">{{ okCount }} / {{ calc.length }}</span>
          <span class="muted small">일치 {{ Math.round((okCount / calc.length) * 100) }}%</span>
        </div>
      </div>
      <div class="panel-body">
        <table class="grid">
          <thead>
            <tr><th>ID</th><th>사례</th><th>NOR</th><th>접안</th><th>작업 종료</th><th>허용</th><th>기상 조항</th><th class="r">초과</th><th class="r">손계산</th><th class="r">자동 계산</th><th>결과</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in calc" :key="r.id">
              <td class="num faint">{{ r.id }}</td>
              <td>{{ r.note }}</td>
              <td class="num">{{ fmt(r.eta) }}<span v-if="r.turnH" class="faint"> +{{ r.turnH }}h</span></td>
              <td class="num">{{ fmt(r.etb) }}</td>
              <td class="num">{{ fmt(r.etu) }}</td>
              <td class="num">{{ r.laytimeH }}h</td>
              <td>{{ clause[r.weather] }}</td>
              <td class="num r">{{ fmtDur(r.excess) }}</td>
              <td class="num r">{{ money(r.expectedCents) }}</td>
              <td class="num r">{{ money(r.got) }}</td>
              <td><span class="chip" :class="r.ok ? 'none' : 'bad'">{{ r.ok ? '일치' : '불일치' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>시나리오별 제안 효과</h2>
          <p class="muted small">도착 순서대로 접안한 기준안과 체선료가 가장 낮은 후보를 같은 규칙으로 비교해요. 제약 위반은 탐색과 따로 짠 검사기로 다시 셌어요.</p>
        </div>
      </div>
      <div class="panel-body">
        <table class="grid">
          <thead>
            <tr><th>시나리오</th><th class="r">규모</th><th class="r">기준안</th><th class="r">최선 후보</th><th class="r">절감액</th><th class="r">절감률</th><th class="r">제약 위반</th><th class="r">탐색</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in scen" :key="s.id">
              <td><span class="faint num">{{ s.id }}</span> {{ s.name }}</td>
              <td class="num r">{{ s.berths }}부두 · {{ s.vessels }}척</td>
              <td class="num r">{{ money(s.fcfs) }}</td>
              <td class="num r">{{ money(s.best) }}</td>
              <td class="num r ok">{{ money(s.saving) }}</td>
              <td class="num r">{{ ((s.saving / s.fcfs) * 100).toFixed(1) }}%</td>
              <td class="num r"><span class="chip" :class="s.violations ? 'bad' : 'none'">{{ s.violations }}건</span></td>
              <td class="num r faint">{{ s.explored.toLocaleString() }}안 · {{ s.ms }}ms</td>
            </tr>
          </tbody>
        </table>
        <p class="faint small note">6척은 모든 순서·부두 조합을 돌렸어요. 실제 규모(8~16척)에서는 솔버로 후보를 추리고 같은 검사기로 재검증해야 해요.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.score { display: flex; flex-direction: column; align-items: flex-end; }
.big { font-size: 24px; font-weight: 750; }
.ok { color: var(--ok); font-weight: 650; }
.bad { color: var(--bad); }
.note { margin-top: 10px; }
</style>
