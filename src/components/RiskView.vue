<script setup>
import { computed, ref, watch } from 'vue'
import { risks, sensitivity } from '../lib/engine.js'
import { money } from '../lib/time.js'
import ViewHead from './ViewHead.vue'

const props = defineProps({
  result: Object, scen: Object, focusId: String, checks: Object,
  version: Number, current: Object, decisions: Array, role: Object,
})
const emit = defineEmits(['focus', 'decide', 'next', 'open', 'go'])

const all = computed(() => [props.result.fcfs, ...props.result.candidates])
const cand = computed(() => all.value.find((s) => s.id === props.focusId) ?? props.result.candidates[0])
const items = computed(() => risks(cand.value, props.scen))
const sens = computed(() => sensitivity(cand.value, all.value, props.scen).slice(0, 6))
const key = (rk) => `${props.version}:${cand.value.id}:${rk}`
const needsCheck = computed(() => items.value.filter((r) => r.state !== '해당 없음'))
const unchecked = computed(() => needsCheck.value.filter((r) => !props.checks[key(r.key)]))

const reason = ref('')
const confirming = ref(false)
watch(() => props.focusId, () => { confirming.value = false })

const selectedHere = computed(() => props.current && props.current.candId === cand.value.id && props.current.version === props.version)
const statusClass = computed(() => ({ '승인 대기': 'hit', '승인 완료': 'none', '현업 반영 완료': 'none', 반려: 'bad' })[props.current?.status])
const base = () => ({ candId: cand.value.id, label: cand.value.label, total: cand.value.total })

function choose(force) {
  if (unchecked.value.length && !force) { confirming.value = true; return }
  emit('decide', {
    action: '선택', candId: cand.value.id, label: cand.value.label, total: cand.value.total,
    reason: reason.value.trim() || '(사유 미입력)', uncheckedRisks: unchecked.value.map((r) => r.label),
  })
  confirming.value = false
  reason.value = ''
}
const stateClass = (s) => ({ 해당: 'hit', '해당 없음': 'none', '판단 불가': 'unknown' })[s]
</script>

<template>
  <ViewHead title="리스크·선택" crumb="BERTH PLANNING > 리스크·선택" :step="selectedHere ? 4 : 3" desc="계산에 반영하지 못한 변수 확인 후 담당자가 후보를 선택합니다."
    :kpis="[
      { label: '보는 안', value: cand.id === 'FCFS' ? '기준안' : cand.label },
      { label: '확인할 리스크', value: `${needsCheck.length}건` },
      { label: '확인 완료', value: `${needsCheck.length - unchecked.length}건`, good: unchecked.length === 0 },
      { label: '선택 상태', value: selectedHere ? current.status : '선택 전' },
    ]" />
  <div class="layout">
    <div class="stack">
      <section class="panel">
        <div class="panel-head">
          <h2>남은 리스크</h2>
          <div class="seg">
            <button v-for="s in all" :key="s.id" :class="{ on: s.id === cand.id }" @click="emit('focus', s.id)">
              {{ s.id === 'FCFS' ? '기준안' : s.label }}
            </button>
          </div>
        </div>
        <div class="panel-body risks">
          <article v-for="r in items" :key="r.key" class="risk">
            <div class="risk-name">
              <h3>{{ r.label }}</h3>
              <span class="chip" :class="stateClass(r.state)">{{ r.state }}</span>
            </div>
            <div class="risk-body">
              <p>{{ r.evidence }}</p>
              <dl v-if="r.alternative !== '-' || r.caution !== '-'" class="ac small">
                <template v-if="r.alternative !== '-'"><dt>대안</dt><dd>{{ r.alternative }}</dd></template>
                <template v-if="r.caution !== '-'"><dt>주의</dt><dd>{{ r.caution }}</dd></template>
              </dl>
            </div>
            <label v-if="r.state !== '해당 없음'" class="check small">
              <input v-model="checks[key(r.key)]" type="checkbox" /> 확인
            </label>
            <span v-else />
          </article>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>입력 변동 시 영향</h2>
          <span class="small muted">순서·부두 배정 고정 · 영향 큰 순 6건</span>
        </div>
        <div class="panel-body">
          <table class="grid">
            <thead><tr><th>바뀐 입력</th><th class="r">총 체선료 변화</th><th>후보 순위</th></tr></thead>
            <tbody>
              <tr v-for="s in sens" :key="s.label">
                <td>{{ s.label }}</td>
                <td class="r num" :class="{ 'warn-text': s.delta > 0, 'good-text': s.delta < 0 }">
                  {{ s.delta === null ? '배치 불가' : s.delta === 0 ? '변화 없음' : (s.delta > 0 ? '+' : '') + money(s.delta) }}
                </td>
                <td>
                  <span v-if="s.rankAfter !== s.rankBefore" class="chip hit">{{ s.rankBefore }}위 → {{ s.rankAfter }}위<template v-if="s.delta === 0"> (다른 후보가 더 낮아짐)</template></span>
                  <span v-else class="muted small">{{ s.rankBefore }}위 유지</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <aside class="side">
      <section class="panel decide">
        <div class="panel-head"><h2>담당자 선택</h2></div>
        <div class="panel-body stack">
          <div class="sum">
            <span class="strong">{{ cand.label }}</span>
            <span class="num big">{{ money(cand.total) }}</span>
            <span class="small muted num">기준안 대비 {{ money(cand.total - result.fcfs.total) }}</span>
          </div>
          <p class="small" :class="unchecked.length ? 'warn-text' : 'muted'">
            확인할 리스크 {{ needsCheck.length }}건 중 {{ needsCheck.length - unchecked.length }}건 확인
          </p>

          <template v-if="selectedHere">
            <div class="selected">
              <span class="chip" :class="statusClass">{{ current.status }}</span>
              <span class="small muted">{{ current.reqId }} · 요청 {{ current.who }}</span>
            </div>
            <p v-if="current.status === '승인 대기'" class="small muted">승인권자 결재 전입니다. 승인되어야 접안 계획 버전이 바뀝니다.</p>
            <p v-if="current.rejection" class="small bad-text">반려 · {{ current.rejection.who }} · [{{ current.rejection.reasonType }}] {{ current.rejection.reason }}</p>
            <p v-if="current.approval" class="small good-text">
              승인 · {{ current.approval.who }} · 접안 계획 v{{ current.planNo }} 적용<template v-if="current.approval.requestedId !== current.approval.candId"> (요청 {{ current.approval.requestedLabel }} → {{ current.approval.label }})</template>
            </p>
            <div v-if="!role.approve" class="row">
              <button v-if="current.status === '승인 대기'" class="btn" @click="emit('decide', { action: '요청 취소', ...base(), reason: '담당자 요청 취소' })">요청 취소</button>
              <button v-if="current.status === '반려'" class="btn" @click="emit('decide', { action: '요청 취소', ...base(), reason: '반려 후 다시 선택' })">다시 선택</button>
              <button v-if="current.status === '승인 완료'" class="btn" @click="emit('decide', { action: '현업 반영 완료', ...base(), reason: '현업 시스템에 반영함' })">현업 반영 완료 표시</button>
            </div>
            <button v-else-if="current.status === '승인 대기'" class="btn primary" @click="emit('go', 'approvals')">승인 관리에서 결재</button>
            <button class="btn" :class="{ primary: !role.approve }" @click="emit('next')">보고서 초안</button>
          </template>
          <template v-else-if="role.approve">
            <p class="small muted">후보 선택과 승인 요청은 스케줄러 계정이 합니다. 승인권자는 관리자메뉴 › 승인 관리에서 결재합니다.</p>
            <button class="btn primary" @click="emit('go', 'approvals')">승인 관리</button>
          </template>
          <template v-else>
            <div class="field">
              <label for="reason">선택 사유 · 보고서에 포함</label>
              <textarea id="reason" v-model="reason" class="input" rows="3" placeholder="예: 기상 해제 직후 대형선 우선 접안, 체선료 절감 폭이 가장 큼" />
            </div>
            <div v-if="confirming" class="confirm">
              <p class="small"><b>미확인 리스크 {{ unchecked.length }}건</b> ({{ unchecked.map((r) => r.label).join(', ') }}). 요청 시 기록에 함께 남습니다.</p>
              <div class="row">
                <button class="btn" @click="confirming = false">돌아가기</button>
                <button class="btn warn" @click="choose(true)">그래도 요청</button>
              </div>
            </div>
            <button v-else class="btn primary" @click="choose(false)">선택 · 승인 요청</button>
          </template>
          <p class="faint small">Agent는 계획을 확정하지 않습니다. 담당자가 선택해 승인을 요청하고, 승인권자가 승인해야 접안 계획 버전이 바뀝니다.</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h3>처리 이력</h3><span class="faint small">추가만 가능</span></div>
        <div class="panel-body">
          <p v-if="!decisions.length" class="muted small">기록 없음</p>
          <ol class="log">
            <li v-for="(d, i) in [...decisions].reverse()" :key="i" class="small">
              <div class="row"><b>{{ d.action }}</b><span>{{ d.label }}</span><span class="spacer" /><span class="faint">{{ d.reqId }} · 입력 v{{ d.version }}</span></div>
              <div class="muted">{{ d.at }} · {{ d.who }} · {{ d.reasonType ? `[${d.reasonType}] ` : '' }}{{ d.reason }}</div>
              <div v-if="d.uncheckedRisks?.length" class="warn-text">미확인 리스크: {{ d.uncheckedRisks.join(', ') }}</div>
            </li>
          </ol>
        </div>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: 1fr 360px; gap: 16px; align-items: start; }
.side { display: flex; flex-direction: column; gap: 16px; position: sticky; top: 16px; }
.risks { display: flex; flex-direction: column; padding: 0; border-top: 1px solid var(--line); }
.risk { display: grid; grid-template-columns: 140px 1fr 64px; gap: 16px; padding: 12px 16px; border-bottom: 1px solid var(--line); align-items: start; }
.risk:last-child { border-bottom: none; }
.risk-name { display: flex; flex-direction: column; gap: 4px; }
.risk-body { display: flex; flex-direction: column; gap: 6px; }
.check { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; font-weight: 600; cursor: pointer; }
.ac { display: grid; grid-template-columns: 36px 1fr; gap: 4px 8px; margin: 0; }
.ac dt { color: var(--muted); font-weight: 650; }
.ac dd { margin: 0; }
.sum { display: flex; flex-direction: column; gap: 2px; }
.big { font-size: 24px; font-weight: 750; letter-spacing: -0.02em; }
.selected { display: flex; align-items: center; gap: 8px; }
.confirm { background: var(--warn-weak); border-radius: 6px; padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }
.log { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.log li { border-bottom: 1px solid var(--line); padding-bottom: 8px; }
.log li:last-child { border-bottom: none; }
.log .row { gap: 6px; }
.warn-text { color: var(--warn); font-weight: 600; }
.good-text { color: var(--ok); font-weight: 600; }
.bad-text { color: var(--bad); font-weight: 600; }
textarea.input { resize: vertical; }
</style>
