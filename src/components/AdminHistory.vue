<script setup>
// 관리자메뉴 > 승인 이력. 승인으로 적용된 접안 계획 버전과, 요청·취소·승인·반려·반영 처리 기록. 기록은 고치거나 지우지 않는다.
import { computed } from 'vue'
import { money } from '../lib/time.js'
import ViewHead from './ViewHead.vue'

const props = defineProps({ planVersions: Array, decisions: Array, requests: Array })
const versions = computed(() => [...props.planVersions].reverse())
const log = computed(() => [...props.decisions].reverse())
</script>

<template>
  <div class="stack">
    <ViewHead title="승인 이력" crumb="관리자메뉴 > 승인 이력" desc="승인으로 적용된 접안 계획 버전과 처리 기록입니다. 기록은 고치거나 지우지 않습니다."
      :kpis="[
        { label: '적용 중 계획', value: versions.length ? `v${versions[0].planNo} · ${versions[0].label}` : '없음' },
        { label: '승인 요청', value: `${requests.length}건` },
        { label: '처리 기록', value: `${log.length}건` },
      ]" />

    <section class="panel">
      <div class="panel-head"><h2>계획 버전</h2><span class="muted">맨 위가 적용 중인 계획입니다.</span></div>
      <table class="grid">
        <thead><tr><th>버전</th><th>계획</th><th>예상 체선료(USD)</th><th>적용일시</th><th>적용자</th><th>보고서</th><th>입력 기준</th><th>사유</th></tr></thead>
        <tbody>
          <tr v-for="(v, i) in versions" :key="v.planNo" :class="{ live: i === 0 }">
            <td class="c strong">v{{ v.planNo }}<span v-if="i === 0"> (적용 중)</span></td>
            <td class="c">{{ v.label }}<span v-if="v.requestedId !== v.candId" class="warn"> · 요청 {{ v.requestedLabel }}에서 변경</span></td>
            <td class="r num">{{ money(v.total) }}</td>
            <td class="c num">{{ v.at }}</td>
            <td class="c">{{ v.who }}</td>
            <td class="c">{{ v.reqId }}</td>
            <td class="c">v{{ v.version }}</td>
            <td>[{{ v.reasonType }}] {{ v.reason }}<span v-if="v.uncheckedRisks?.length" class="warn"> · 미확인 {{ v.uncheckedRisks.join(', ') }}</span></td>
          </tr>
          <tr v-if="!versions.length"><td colspan="8" class="empty">승인된 계획이 없습니다. 승인 관리에서 승인하면 v1이 생깁니다.</td></tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>처리 기록</h2>
        <span class="muted">선택 · 요청 취소 · 승인 · 반려 · 현업 반영을 시간 순으로 남깁니다.</span>
        <span class="count">전체 조회 건수 <b>{{ log.length }}</b></span>
      </div>
      <table class="grid">
        <thead><tr><th>일시</th><th>처리자</th><th>역할</th><th>처리</th><th>대상</th><th>내용</th></tr></thead>
        <tbody>
          <tr v-for="(d, i) in log" :key="i">
            <td class="c num">{{ d.at }}</td>
            <td class="c">{{ d.who }}</td>
            <td class="c">{{ d.roleTitle }}</td>
            <td class="c strong" :class="{ bad: d.action === '반려', good: d.action === '승인' }">{{ d.action === '선택' ? '선택 · 승인 요청' : d.action }}</td>
            <td class="c">{{ d.reqId }} · {{ d.label }}</td>
            <td>{{ d.reasonType ? `[${d.reasonType}] ` : '' }}{{ d.reason }}<span v-if="d.planNo"> · 접안 계획 v{{ d.planNo }} 적용</span></td>
          </tr>
          <tr v-if="!log.length"><td colspan="6" class="empty">기록이 없습니다.</td></tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.r { text-align: right; }
.good { color: var(--ok); }
.bad { color: var(--bad); }
.warn { color: var(--warn); font-weight: 600; }
.count { margin-left: auto; color: #333; font-size: 12.5px; }
.count b { color: var(--bad); font-size: 15px; margin-left: 4px; }
.empty { text-align: center; color: var(--muted); height: 56px; }
tr.live td { background: #fff6c4; }
</style>
