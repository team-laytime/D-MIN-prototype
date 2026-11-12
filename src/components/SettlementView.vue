<script setup>
// 체선료 지불 담당: 확정 계획의 예상 체선료와 선주 청구액을 비교하고 지급을 승인한다.
// 청구액은 사람이 입력한다(가상). 금액은 USD 센트 정수로 저장하고 다시 반올림하지 않는다.
import { computed, reactive } from 'vue'
import { CircleAlert } from 'lucide-vue-next'
import { money } from '../lib/time.js'
import { activePlan, addLog, nowText, role, ws } from '../lib/workspace.js'
import ViewHead from './ViewHead.vue'

const plan = computed(() => activePlan())
const key = (p) => `${plan.value.no}:${p.vid}`
const input = reactive({})
const err = reactive({})
const toCents = (s) => {
  const m = /^\s*\$?([\d,]+)(?:\.(\d{1,2}))?\s*$/.exec(s ?? '')
  return m ? Number(m[1].replace(/,/g, '')) * 100 + Number((m[2] ?? '').padEnd(2, '0') || 0) : null
}
const rows = computed(() => (plan.value ? plan.value.placements.map((p) => ({ p, c: ws.claims[key(p)] })) : []))
const expected = computed(() => rows.value.reduce((s, r) => s + r.p.dem.cents, 0))
const claimed = computed(() => rows.value.reduce((s, r) => s + (r.c?.cents ?? 0), 0))
const approved = computed(() => rows.value.filter((r) => r.c?.state === '지급 승인').length)
const dispute = (p) => ws.reviews[key(p)]?.state === '이의'

function register(p) {
  const cents = toCents(input[p.vid])
  if (cents === null) { err[p.vid] = '청구액을 숫자로 적어 주십시오. 예: 6,120.00'; return }
  ws.claims[key(p)] = { cents, state: '청구 접수', who: role().name, at: nowText() }
  addLog('청구 접수', `${p.name} · 접안 계획 v${plan.value.no}`, `청구 ${money(cents)} · 예상 ${money(p.dem.cents)}`)
  err[p.vid] = ''
}
function approve(p) {
  const c = ws.claims[key(p)]
  c.state = '지급 승인'
  c.approvedAt = nowText()
  addLog('지급 승인', `${p.name} · 접안 계획 v${plan.value.no}`, `${money(c.cents)}`)
}
</script>

<template>
  <div class="stack">
    <ViewHead title="체선료 정산" crumb="SETTLEMENT > 체선료 정산" desc="확정 계획의 예상 체선료와 선주 청구액을 비교하고 지급을 승인합니다."
      :kpis="plan ? [
        { label: '적용 계획', value: `v${plan.no} · ${plan.label}` },
        { label: '예상 체선료', value: money(expected) },
        { label: '청구 합계', value: money(claimed) },
        { label: '지급 승인', value: `${approved} / ${rows.length}`, good: approved === rows.length },
      ] : []" />

    <div v-if="!plan" class="notice">
      <CircleAlert class="ico" :size="18" />
      <span><b>확정된 계획이 없습니다.</b> 스케줄러가 계획을 확정하면 선박별 예상 체선료가 나옵니다.</span>
    </div>
    <section v-else class="panel">
      <div class="panel-head"><h2>선박별 정산</h2><span class="muted">접안 계획 v{{ plan.no }} · 확정 {{ plan.at }}</span></div>
      <table class="grid">
        <thead><tr><th>선박</th><th>계약번호</th><th>예상 체선료(USD)</th><th>청구액(USD)</th><th>차이</th><th>계약 담당</th><th>상태</th><th>처리</th></tr></thead>
        <tbody>
          <tr v-for="{ p, c } in rows" :key="p.vid">
            <td class="c strong">{{ p.name }}</td>
            <td class="c">{{ p.contract.id }}</td>
            <td class="r num">{{ money(p.dem.cents) }}</td>
            <td class="r num">
              <template v-if="c">{{ money(c.cents) }}</template>
              <template v-else>
                <input v-model="input[p.vid]" class="input sm num w-amt" placeholder="0.00" :aria-label="`${p.name} 청구액`" @input="err[p.vid] = ''" />
                <p v-if="err[p.vid]" class="bad small">{{ err[p.vid] }}</p>
              </template>
            </td>
            <td class="r num" :class="{ bad: c && c.cents > p.dem.cents, good: c && c.cents <= p.dem.cents }">{{ c ? money(c.cents - p.dem.cents) : '-' }}</td>
            <td class="c"><span v-if="dispute(p)" class="bad strong">이의</span><span v-else-if="ws.reviews[key(p)]" class="good">확인</span><span v-else class="faint">미확인</span></td>
            <td class="c strong" :class="{ good: c?.state === '지급 승인' }">{{ c?.state ?? '청구 전' }}</td>
            <td class="c">
              <button v-if="!c" class="btn sm" @click="register(p)">청구 접수</button>
              <button v-else-if="c.state === '청구 접수'" class="btn primary sm" :disabled="dispute(p)" :title="dispute(p) ? '계약 담당 이의가 있어 지급을 보류합니다' : ''" @click="approve(p)">지급 승인</button>
              <span v-else class="faint small">{{ c.approvedAt }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="small muted after">계약 담당이 Laytime에 이의를 남긴 선박은 지급 승인을 막습니다. 청구액이 예상보다 크면 차이를 빨강으로 표시합니다.</p>
    </section>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.r { text-align: right; white-space: nowrap; }
.good { color: var(--ok); }
.bad { color: var(--bad); }
.w-amt { width: 120px; text-align: right; }
.btn.sm { height: 24px; padding: 0 10px; font-size: 12px; }
.after { margin: 8px 0 0; }
</style>
