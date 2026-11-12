<script setup>
// 입출항 작업 지시자: 확정된 계획만 본다(HN-094). 체선료 단가·금액은 보이지 않는다(HN-095).
// 확정 당시 스냅숏을 보므로, 스케줄러가 입력을 고쳐도 다시 확정하기 전까지 이 일정은 바뀌지 않는다.
import { computed } from 'vue'
import { CircleAlert } from 'lucide-vue-next'
import { fmt } from '../lib/time.js'
import { activePlan, addLog, ws } from '../lib/workspace.js'
import RequestPanel from './RequestPanel.vue'
import ViewHead from './ViewHead.vue'

const plan = computed(() => activePlan())
const PREP = ['도선', '예선', '줄잡이', '로딩암']
const hourOf = (min) => Math.floor((((min % 1440) + 1440) % 1440) / 60)
const night = (p) => hourOf(p.etb) >= 20 || hourOf(p.etb) < 6
const flags = (p) => [night(p) && '야간 접안', p.dwt >= 60000 && '6만 DWT 이상'].filter(Boolean)
const key = (p, item) => `${plan.value.no}:${p.vid}:${item}`
const done = computed(() => (plan.value ? plan.value.placements.reduce((n, p) => n + PREP.filter((i) => ws.prep[key(p, i)]).length, 0) : 0))
const total = computed(() => (plan.value ? plan.value.placements.length * PREP.length : 0))
function toggle(p, item, on) {
  ws.prep[key(p, item)] = on
  addLog(on ? '준비 완료' : '준비 해제', `${p.name} · ${item}`, `접안 계획 v${plan.value.no}`)
}
const vessels = computed(() => plan.value?.placements.map((p) => ({ vid: p.vid, name: p.name })) ?? [])
</script>

<template>
  <div class="stack">
    <ViewHead title="확정 접안 일정" crumb="OPERATIONS > 확정 접안 일정" desc="스케줄러가 확정한 일정입니다. 검토 중인 후보와 체선료 금액은 이 화면에 나오지 않습니다."
      :kpis="plan ? [
        { label: '적용 계획', value: `v${plan.no} · ${plan.label}` },
        { label: '확정', value: `${plan.who} · ${plan.at}` },
        { label: '야간 접안', value: `${plan.placements.filter(night).length}건`, bad: plan.placements.some(night) },
        { label: '작업 준비', value: `${done} / ${total}`, good: done === total },
      ] : []" />

    <div v-if="!plan" class="notice">
      <CircleAlert class="ico" :size="18" />
      <span><b>확정된 계획이 없습니다.</b> 스케줄러가 「리스크·확정」에서 확정하면 이 화면에 일정이 나옵니다.</span>
    </div>

    <template v-else>
      <section class="panel">
        <div class="panel-head">
          <h2>접안 순서</h2>
          <span class="muted">접안 시각 순 · 준비가 끝나면 체크합니다.</span>
          <span v-if="plan.fieldDone" class="ok-tag small">현업 반영 완료</span>
        </div>
        <table class="grid">
          <thead><tr><th>순서</th><th>선박</th><th>화물</th><th>부두</th><th>도착</th><th>접안</th><th>작업 종료</th><th>주의</th><th v-for="i in PREP" :key="i">{{ i }}</th></tr></thead>
          <tbody>
            <tr v-for="(p, n) in plan.placements" :key="p.vid">
              <td class="c">{{ n + 1 }}</td>
              <td class="strong">{{ p.name }}</td>
              <td class="c">{{ p.product }} {{ p.dir }} · {{ p.ton.toLocaleString() }}t</td>
              <td class="c">{{ p.berth }}</td>
              <td class="c num">{{ fmt(p.eta) }}</td>
              <td class="c num strong">{{ fmt(p.etb) }}</td>
              <td class="c num">{{ fmt(p.etu) }}</td>
              <td class="c"><span v-for="f in flags(p)" :key="f" class="flag">{{ f }}</span><span v-if="!flags(p).length" class="faint">-</span></td>
              <td v-for="i in PREP" :key="i" class="c"><input type="checkbox" :checked="!!ws.prep[key(p, i)]" :aria-label="`${p.name} ${i}`" @change="toggle(p, i, $event.target.checked)" /></td>
            </tr>
          </tbody>
        </table>
      </section>

      <RequestPanel type="현장 변경 요청" :vessels="vessels" :kinds="['접안 시각 조정', '부두 변경', '작업 중단 · 지연', '기타']"
        placeholder="예: 야간 줄잡이 인력 부족, 접안을 06:00 이후로 조정 요청" />
    </template>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.flag { display: inline-block; margin: 0 2px; padding: 0 5px; font-size: 11px; font-weight: 700; color: var(--bad); border: 1px solid #f2b8b8; }
.ok-tag { margin-left: auto; color: var(--ok); font-weight: 700; }
</style>
