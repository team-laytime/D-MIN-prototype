<script setup>
// 일정 이용자: 확정된 계획만 본다(HN-094). 체선료 단가·금액은 보이지 않는다(HN-095).
// 확정 당시 스냅숏을 보므로, 스케줄러가 입력을 고쳐도 다시 확정하기 전까지 이 일정은 바뀌지 않는다.
import { computed } from 'vue'
import { CircleAlert } from 'lucide-vue-next'
import { fmt } from '../lib/time.js'
import { activePlan } from '../lib/workspace.js'
import ViewHead from './ViewHead.vue'

const plan = computed(() => activePlan())
const hourOf = (min) => Math.floor((((min % 1440) + 1440) % 1440) / 60)
const night = (p) => hourOf(p.etb) >= 20 || hourOf(p.etb) < 6
const flags = (p) => [night(p) && '야간 접안', p.dwt >= 60000 && '6만 DWT 이상'].filter(Boolean)
</script>

<template>
  <div class="stack">
    <ViewHead title="확정 접안 일정" crumb="SCHEDULE > 확정 접안 일정" desc="스케줄러가 확정한 일정입니다. 검토 중인 후보와 체선료 금액은 이 화면에 나오지 않습니다."
      :kpis="plan ? [
        { label: '적용 계획', value: `v${plan.no} · ${plan.label}` },
        { label: '확정', value: `${plan.who} · ${plan.at}` },
        { label: '선박', value: `${plan.placements.length}척` },
        { label: '야간 접안', value: `${plan.placements.filter(night).length}건`, bad: plan.placements.some(night) },
      ] : []" />

    <div v-if="!plan" class="notice">
      <CircleAlert class="ico" :size="18" />
      <span><b>확정된 계획이 없습니다.</b> 스케줄러가 계획을 확정하면 이 화면에 일정이 나옵니다.</span>
    </div>

    <section v-else class="panel">
      <div class="panel-head">
        <h2>접안 순서</h2>
        <span class="muted">접안 시각 순</span>
      </div>
      <table class="grid">
        <thead><tr><th>순서</th><th>선박</th><th>화물</th><th>부두</th><th>도착</th><th>접안</th><th>작업 종료</th><th>주의</th></tr></thead>
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
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.flag { display: inline-block; margin: 0 2px; padding: 0 5px; font-size: 11px; font-weight: 700; color: var(--bad); border: 1px solid #f2b8b8; }
</style>
