<script setup>
// 생산 관련 부서: 탱크 여유와 긴급 출하(납기)를 직접 관리하고, 필요하면 스케줄러에게 우선순위를 요청한다.
// 여기서 고친 값은 계산 입력이라, 스케줄러 화면의 '탱크'·'긴급 출하' 리스크가 바로 다시 판정된다.
import { computed, ref } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import { risks } from '../lib/engine.js'
import { fmt, fromInput, toInput } from '../lib/time.js'
import { activePlan, addLog } from '../lib/workspace.js'
import RequestPanel from './RequestPanel.vue'
import ViewHead from './ViewHead.vue'

const props = defineProps({ scen: Object, plain: Object, result: Object })
const vname = (id) => props.plain.vessels.find((v) => v.id === id)?.name ?? id
const vessels = computed(() => props.plain.vessels.map((v) => ({ vid: v.id, name: v.name })))

// 판정 기준 안: 확정 계획이 있으면 그 안, 없으면 후보 A
const basis = computed(() => {
  if (props.result.error) return null
  const p = activePlan()
  return [props.result.fcfs, ...props.result.candidates].find((s) => s.id === p?.candId) ?? props.result.candidates[0]
})
const judged = computed(() => (basis.value ? risks(basis.value, props.plain).filter((r) => r.key === 'tank' || r.key === 'urgent') : []))
const stateClass = (s) => ({ 해당: 'warnc', '해당 없음': 'good', '판단 불가': 'unknown' })[s]

function setTank(t, field, value) {
  const before = field === 'readyAt' ? fmt(t.readyAt) : t.ullageTon.toLocaleString()
  t[field] = value
  addLog('탱크 여유 수정', t.product, `${field === 'readyAt' ? '확보 시각' : '여유'} ${before} → ${field === 'readyAt' ? fmt(value) : value.toLocaleString()}`)
}
function setUrgent(u, field, value) {
  const before = field === 'deadline' ? fmt(u.deadline) : vname(u.vid)
  u[field] = value
  addLog('긴급 출하 수정', vname(u.vid), `${field === 'deadline' ? '납기' : '선박'} ${before} → ${field === 'deadline' ? fmt(value) : vname(value)}`)
}
const newVid = ref('')
function addUrgent() {
  const vid = newVid.value || props.plain.vessels.find((v) => !props.scen.urgent.some((u) => u.vid === v.id))?.id
  if (!vid) return
  const v = props.plain.vessels.find((x) => x.id === vid)
  props.scen.urgent.push({ vid, deadline: v.eta + 48 * 60, note: '생산 부서 긴급 출하 지시' })
  addLog('긴급 출하 추가', v.name, `납기 ${fmt(v.eta + 48 * 60)}`)
}
function removeUrgent(i) {
  const u = props.scen.urgent[i]
  props.scen.urgent.splice(i, 1)
  addLog('긴급 출하 삭제', vname(u.vid), '')
}
</script>

<template>
  <div class="stack">
    <ViewHead title="탱크·긴급 출하" crumb="PRODUCTION > 탱크·긴급 출하" desc="탱크 여유와 출하 납기를 관리합니다. 고친 값은 스케줄러의 계산 입력에 바로 들어갑니다."
      :kpis="[
        { label: '판정 기준 안', value: basis ? basis.label : '-' },
        ...judged.map((r) => ({ label: r.label, value: r.state, bad: r.state === '해당' })),
        { label: '긴급 출하', value: `${scen.urgent.length}건` },
      ]" />

    <section class="panel">
      <div class="panel-head"><h2>판정 결과</h2><span class="muted">{{ basis ? `${basis.label} 기준` : '' }}</span></div>
      <table class="grid">
        <thead><tr><th>항목</th><th>판정</th><th>근거</th><th>대안</th></tr></thead>
        <tbody>
          <tr v-for="r in judged" :key="r.key">
            <td class="c strong">{{ r.label }}</td>
            <td class="c strong" :class="stateClass(r.state)">{{ r.state }}</td>
            <td>{{ r.evidence }}</td>
            <td>{{ r.alternative }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>탱크 여유</h2><span class="muted">수입 선박 하역 시점에 받을 수 있는 양</span></div>
      <table class="grid">
        <thead><tr><th>제품</th><th>현재 여유(톤)</th><th>추가 여유 확보 시각</th><th>비고</th></tr></thead>
        <tbody>
          <tr v-for="t in scen.tanks" :key="t.product">
            <td class="c strong">{{ t.product }}</td>
            <td class="c"><input class="input sm num w-num" type="number" step="1000" :value="t.ullageTon" :aria-label="`${t.product} 여유`" @change="setTank(t, 'ullageTon', Number($event.target.value))" /></td>
            <td class="c"><input class="input sm" type="datetime-local" :value="toInput(t.readyAt)" :aria-label="`${t.product} 확보 시각`" @change="fromInput($event.target.value) !== null && setTank(t, 'readyAt', fromInput($event.target.value))" /></td>
            <td>{{ t.note }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>긴급 출하</h2><span class="muted">납기 안에 작업이 끝나야 하는 선박</span>
        <div class="row">
          <select v-model="newVid" class="input sm" aria-label="추가할 선박">
            <option value="">선박 선택</option>
            <option v-for="v in plain.vessels.filter((x) => !scen.urgent.some((u) => u.vid === x.id))" :key="v.id" :value="v.id">{{ v.name }}</option>
          </select>
          <button class="btn" @click="addUrgent"><Plus :size="14" />추가</button>
        </div>
      </div>
      <table class="grid">
        <thead><tr><th>선박</th><th>출하 납기</th><th>내용</th><th>삭제</th></tr></thead>
        <tbody>
          <tr v-for="(u, i) in scen.urgent" :key="u.vid">
            <td class="c strong">{{ vname(u.vid) }}</td>
            <td class="c"><input class="input sm" type="datetime-local" :value="toInput(u.deadline)" :aria-label="`${vname(u.vid)} 납기`" @change="fromInput($event.target.value) !== null && setUrgent(u, 'deadline', fromInput($event.target.value))" /></td>
            <td>{{ u.note }}</td>
            <td class="c"><button class="btn sm" :aria-label="`${vname(u.vid)} 삭제`" @click="removeUrgent(i)"><Trash2 :size="13" /></button></td>
          </tr>
          <tr v-if="!scen.urgent.length"><td colspan="4" class="empty">긴급 출하가 없습니다.</td></tr>
        </tbody>
      </table>
    </section>

    <RequestPanel type="우선순위 요청" :vessels="vessels" :kinds="['먼저 접안', '하역 시점 조정', '출하 납기 협의', '기타']"
      placeholder="예: 나프타 재고 부족, GOLDEN STAR 하역을 11/15 오전으로 당겨 주십시오" />
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.good { color: var(--ok); }
.warnc { color: var(--warn); }
.unknown { color: var(--unknown); }
.w-num { width: 110px; text-align: right; }
.btn.sm { height: 24px; padding: 0 8px; }
.empty { text-align: center; color: var(--muted); height: 48px; }
</style>
