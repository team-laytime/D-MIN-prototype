<script setup>
// 계약 담당 부서: 선박별 계약 조건을 보고, 확정 계획의 Laytime 산정 결과를 선박별로 확인하거나 이의를 남긴다.
// 이의는 기록만 남긴다. NOR·Laytime 분쟁·변경 승인 권한은 아직 확인 전([V])이다.
import { computed, reactive } from 'vue'
import { CircleAlert } from 'lucide-vue-next'
import { WEATHER_CLAUSE } from '../lib/scenarios.js'
import { fmt, fmtDur, money } from '../lib/time.js'
import { activePlan, addLog, nowText, role, ws } from '../lib/workspace.js'
import ViewHead from './ViewHead.vue'

const props = defineProps({ scen: Object })
const plan = computed(() => activePlan())
const key = (p) => `${plan.value.no}:${p.vid}`
const note = reactive({})
const err = reactive({})
const reviewed = computed(() => (plan.value ? plan.value.placements.filter((p) => ws.reviews[key(p)]).length : 0))
const disputes = computed(() => (plan.value ? plan.value.placements.filter((p) => ws.reviews[key(p)]?.state === '이의').length : 0))

function review(p, state) {
  const text = (note[p.vid] ?? '').trim()
  if (state === '이의' && !text) { err[p.vid] = '이의 사유를 적어 주십시오.'; return }
  ws.reviews[key(p)] = { state, note: text, who: role().name, at: nowText() }
  addLog(`Laytime ${state}`, `${p.name} · 접안 계획 v${plan.value.no}`, text || `예상 체선료 ${money(p.dem.cents)}`)
  err[p.vid] = ''
}
</script>

<template>
  <div class="stack">
    <ViewHead title="계약 조건·Laytime" crumb="CONTRACT > 계약 조건·Laytime" desc="선박별 계약 조건과, 확정 계획의 정박시간(Laytime) 산정 결과를 확인합니다."
      :kpis="[
        { label: '계약', value: `${scen.vessels.length}건` },
        { label: '적용 계획', value: plan ? `v${plan.no} · ${plan.label}` : '확정 전' },
        { label: 'Laytime 확인', value: plan ? `${reviewed} / ${plan.placements.length}` : '-', good: plan && reviewed === plan.placements.length },
        { label: '이의', value: `${disputes}건`, bad: disputes > 0 },
      ]" />

    <section class="panel">
      <div class="panel-head"><h2>계약 조건</h2><span class="muted">계산에 쓰는 값입니다(가상 계약).</span></div>
      <table class="grid">
        <thead><tr><th>계약번호</th><th>선박</th><th>화물</th><th>허용 정박시간</th><th>하루 체선료(USD)</th><th>정박 개시</th><th>기상 공제</th></tr></thead>
        <tbody>
          <tr v-for="v in scen.vessels" :key="v.id">
            <td class="c strong">{{ v.contract.id }}</td>
            <td class="c">{{ v.name }}</td>
            <td class="c">{{ v.product }} {{ v.dir }}</td>
            <td class="c">{{ v.contract.laytimeH }}시간</td>
            <td class="r num">{{ money(v.contract.rateUsd * 100) }}</td>
            <td class="c">{{ v.contract.norTurnH ? `NOR 후 ${v.contract.norTurnH}시간 또는 접안 중 빠른 때` : 'NOR 제출 즉시' }}</td>
            <td class="c">{{ WEATHER_CLAUSE[v.contract.weather].label }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="!plan" class="notice">
      <CircleAlert class="ico" :size="18" />
      <span><b>확정된 계획이 없습니다.</b> 스케줄러가 계획을 확정하면 선박별 Laytime 산정표가 나옵니다.</span>
    </div>
    <section v-else class="panel">
      <div class="panel-head"><h2>Laytime 산정표</h2><span class="muted">접안 계획 v{{ plan.no }} · {{ plan.label }} · 확정 {{ plan.at }}</span></div>
      <table class="grid lt">
        <thead><tr><th>선박</th><th>NOR</th><th>정박 개시</th><th>정박 종료</th><th>사용</th><th>기상 공제</th><th>허용</th><th>초과</th><th>예상 체선료</th><th>판정</th></tr></thead>
        <tbody>
          <tr v-for="p in plan.placements" :key="p.vid" :class="{ dis: ws.reviews[key(p)]?.state === '이의' }">
            <td class="c strong">{{ p.name }}</td>
            <td class="c num">{{ fmt(p.eta) }}</td>
            <td class="c num">{{ fmt(p.dem.ltStart) }}</td>
            <td class="c num">{{ fmt(p.etu) }}</td>
            <td class="c">{{ fmtDur(p.dem.usedMin) }}</td>
            <td class="c">{{ p.dem.wxDeduct ? `− ${fmtDur(p.dem.wxDeduct)}` : '0' }}</td>
            <td class="c">{{ fmtDur(p.dem.allowMin) }}</td>
            <td class="c" :class="{ bad: p.dem.excessMin > 0 }">{{ fmtDur(p.dem.excessMin) }}</td>
            <td class="r num strong">{{ money(p.dem.cents) }}</td>
            <td class="judge">
              <template v-if="ws.reviews[key(p)]">
                <b :class="ws.reviews[key(p)].state === '이의' ? 'bad' : 'good'">{{ ws.reviews[key(p)].state }}</b>
                <span class="small muted"> {{ ws.reviews[key(p)].note }}</span>
                <div class="faint small">{{ ws.reviews[key(p)].who }} · {{ ws.reviews[key(p)].at }}</div>
              </template>
              <template v-else>
                <input v-model="note[p.vid]" class="input sm" placeholder="메모 · 이의 사유" @input="err[p.vid] = ''" />
                <div class="row">
                  <button class="btn primary sm" @click="review(p, '확인')">확인</button>
                  <button class="btn sm" @click="review(p, '이의')">이의</button>
                </div>
                <p v-if="err[p.vid]" class="bad small">{{ err[p.vid] }}</p>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="small muted after">체선료 = 초과 시간 ÷ 24시간 × 하루 체선료, 선박별 센트 단위 한 번 반올림(HALF_UP). 이의는 기록으로 남고, 분쟁·변경 승인 절차는 확인 전입니다.</p>
    </section>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.r { text-align: right; }
.good { color: var(--ok); }
.bad { color: var(--bad); }
.judge { width: 220px; }
.judge .input { width: 100%; margin-bottom: 4px; }
.btn.sm { height: 24px; padding: 0 10px; font-size: 12px; }
tr.dis td { background: var(--bad-weak); }
.judge b + span { margin-left: 6px; }
.after { margin: 8px 0 0; }
</style>
