<script setup>
import { computed } from 'vue'
import { compatibleBerths } from '../lib/engine.js'
import ViewHead from './ViewHead.vue'
import { WEATHER_CLAUSE } from '../lib/scenarios.js'
import { at, fmt, fmtDur, fromInput, toInput, money } from '../lib/time.js'

const props = defineProps({ scen: Object, result: Object })
const emit = defineEmits(['run'])

const berthName = (id) => props.scen.berths.find((b) => b.id === id)?.name.replace(' 부두', '') ?? id
const setTime = (obj, field, e) => {
  const t = fromInput(e.target.value)
  if (t !== null) obj[field] = t
}
const weatherOn = computed({
  get: () => !!props.scen.env.weather,
  set: (on) => {
    props.scen.env.weather = on ? { start: at(14, 18), end: at(15, 6), label: '강풍 주의보 (최대 풍속 17m/s)', source: '기상청 단기예보 (가상)' } : null
  },
})

const errors = computed(() => {
  const out = []
  for (const v of props.scen.vessels) {
    if (!(v.contract.laytimeH > 0)) out.push(`${v.name}: 허용 시간은 0보다 커야 합니다`)
    if (!(v.contract.rateUsd > 0)) out.push(`${v.name}: 하루 체선료는 0보다 커야 합니다`)
    if (compatibleBerths(v, props.scen).length === 0) out.push(`${v.name}: 제품·제원에 맞는 부두가 없습니다`)
  }
  const w = props.scen.env.weather
  if (w && w.end <= w.start) out.push('기상 악화 종료 시각이 시작 시각보다 빠릅니다')
  return out
})
</script>

<template>
  <div class="stack">
    <ViewHead title="시나리오 입력" crumb="BERTH PLANNING > 시나리오 입력" :step="1" :desc="`${scen.summary}. 수정 즉시 전체 화면을 재계산합니다.`"
      :kpis="[
        { label: '대기 선박', value: `${scen.vessels.length}척` },
        { label: '부두', value: `${scen.berths.length}곳` },
        { label: '기상 악화', value: scen.env.weather ? '예보 있음' : '없음' },
        { label: '입력 오류', value: `${errors.length}건`, good: errors.length === 0 },
      ]" />
    <section class="panel">
      <div class="panel-head">
        <h2>선박·계약 조건</h2>
        <div class="row">
          <span v-if="errors.length" class="chip bad">입력 오류 {{ errors.length }}건</span>
          <span v-else class="chip none">검증 통과</span>
          <button class="btn primary" :disabled="errors.length > 0 || !!result.error" @click="emit('run')">후보 비교</button>
        </div>
      </div>
      <div class="panel-body">
        <ul v-if="errors.length" class="errors small"><li v-for="e in errors" :key="e">{{ e }}</li></ul>
        <table class="grid inputs">
          <thead>
            <tr>
              <th>선박</th><th>화물</th><th class="r">DWT</th><th class="r">흘수</th><th class="r">작업 시간</th>
              <th>도착 예정(NOR)</th><th class="r">허용(h)</th><th class="r">일 체선료($)</th>
              <th class="r">개시(h)</th><th>기상 조항</th><th>가능 부두</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in scen.vessels" :key="v.id">
              <td><span class="strong nowrap">{{ v.name }}</span><div class="faint small">{{ v.contract.id }}</div></td>
              <td class="nowrap">{{ v.product }} {{ v.dir }}<div class="faint small num">{{ v.ton.toLocaleString() }}톤</div></td>
              <td class="num r">{{ v.dwt.toLocaleString() }}</td>
              <td class="num r">{{ v.draft }}m</td>
              <td class="num r nowrap">{{ fmtDur(v.workMin) }}</td>
              <td><input class="input sm num" type="datetime-local" :value="toInput(v.eta)" @change="setTime(v, 'eta', $event)" /></td>
              <td class="r"><input v-model.number="v.contract.laytimeH" class="input sm num w60" type="number" min="1" /></td>
              <td class="r"><input v-model.number="v.contract.rateUsd" class="input sm num w90" type="number" min="1" step="500" /></td>
              <td class="r"><input v-model.number="v.contract.norTurnH" class="input sm num w50" type="number" min="0" /></td>
              <td>
                <select v-model="v.contract.weather" class="input sm">
                  <option v-for="(c, k) in WEATHER_CLAUSE" :key="k" :value="k">{{ c.label }}</option>
                </select>
              </td>
              <td class="nowrap"><span v-for="b in compatibleBerths(v, scen)" :key="b" class="chip berth">{{ berthName(b) }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="two">
      <section class="panel">
        <div class="panel-head"><h2>부두</h2></div>
        <div class="panel-body">
          <table class="grid">
            <thead><tr><th>부두</th><th class="r">최대 DWT</th><th class="r">최대 흘수</th><th>접안 가능 제품</th><th>현재 접안</th><th>설비 점검</th></tr></thead>
            <tbody>
              <tr v-for="b in scen.berths" :key="b.id">
                <td class="strong">{{ b.name }}<div v-if="b.tideLimited" class="faint small">조석 제한</div></td>
                <td class="num r">{{ b.maxDwt.toLocaleString() }}</td>
                <td class="num r">{{ b.maxDraft }}m</td>
                <td>{{ b.products.join(', ') }}</td>
                <td class="small">
                  <template v-if="b.occupiedBy">{{ b.occupiedBy }}<div class="faint num">~ {{ fmt(b.occupiedUntil) }}</div></template>
                  <span v-else class="faint">비어 있음</span>
                </td>
                <td class="small">
                  <template v-if="b.facility.maintenance">{{ b.facility.maintenance.label }}<div class="faint num">{{ fmt(b.facility.maintenance.start) }} ~ {{ fmt(b.facility.maintenance.end).slice(6) }}</div></template>
                  <span v-else-if="!b.facility.known" class="chip unknown">미입력</span>
                  <span v-else class="faint">없음</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h2>기상·조석·일출몰</h2><span class="faint small">공공데이터포털 형식 · 가상 값</span></div>
        <div class="panel-body env">
          <div class="env-row">
            <label class="toggle"><input v-model="weatherOn" type="checkbox" /> 기상 악화 예보</label>
            <template v-if="scen.env.weather">
              <input class="input sm num" type="datetime-local" :value="toInput(scen.env.weather.start)" @change="setTime(scen.env.weather, 'start', $event)" />
              <span class="faint">~</span>
              <input class="input sm num" type="datetime-local" :value="toInput(scen.env.weather.end)" @change="setTime(scen.env.weather, 'end', $event)" />
            </template>
          </div>
          <p v-if="scen.env.weather" class="small muted">{{ scen.env.weather.label }} · {{ scen.env.weather.source }} · 구간 내 전 부두 접안 금지</p>
          <dl class="kv small">
            <dt>만조</dt><dd class="num">{{ scen.env.highTides.slice(0, 6).map(fmt).join(' · ') }}</dd>
            <dt>일출 / 일몰</dt><dd class="num">{{ scen.env.days.slice(1, 4).map((d) => `${fmt(d.sunrise)} / ${fmt(d.sunset).slice(6)}`).join(' · ') }}</dd>
            <dt>접안 규칙</dt>
            <dd>
              부두 전환 {{ scen.env.switchingMin / 60 }}시간 · DWT {{ (scen.env.daylightDwt / 10000).toFixed(0) }}만 톤 이상은 주간(일몰 1시간 전까지)만 접안 ·
              SK 6부두 흘수 {{ scen.env.tideDraft }}m 이상은 만조 ±{{ scen.env.tideWindowMin / 60 }}시간
            </dd>
            <dt>탱크</dt><dd>{{ scen.tanks.map((t) => `${t.product} 여유 ${t.ullageTon.toLocaleString()}톤`).join(', ') }}</dd>
            <dt>긴급 출하</dt><dd>{{ scen.urgent.map((u) => `${scen.vessels.find((v) => v.id === u.vid).name} ${fmt(u.deadline)}까지`).join(', ') }}</dd>
          </dl>
        </div>
      </section>
    </div>

    <p v-if="!result.error" class="faint small">현재 입력 기준: 도착순 {{ money(result.fcfs.total) }} → 최저 후보 {{ money(result.candidates[0]?.total ?? result.fcfs.total) }}</p>
  </div>
</template>

<style scoped>
.inputs td { padding: 6px 10px; }
.nowrap { white-space: nowrap; }
.w50 { width: 50px; text-align: right; }
.w60 { width: 60px; text-align: right; }
.w90 { width: 90px; text-align: right; }
.chip.berth { margin-right: 4px; }
.errors { margin: 0 0 10px; padding: 8px 12px 8px 28px; background: var(--bad-weak); color: var(--bad); border-radius: 6px; }
.two { display: grid; grid-template-columns: 1.15fr 1fr; gap: 16px; align-items: start; }
.env { display: flex; flex-direction: column; gap: 10px; }
.env-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toggle { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; margin-right: 6px; }
.kv { display: grid; grid-template-columns: 76px 1fr; gap: 6px 12px; margin: 0; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; }
</style>
