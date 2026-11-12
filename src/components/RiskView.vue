<script setup>
import { computed, ref, watch } from 'vue'
import { risks, sensitivity } from '../lib/engine.js'
import { money } from '../lib/time.js'

const props = defineProps({
  result: Object, scen: Object, focusId: String, checks: Object,
  version: Number, current: Object, decisions: Array,
})
const emit = defineEmits(['focus', 'decide', 'next', 'open'])

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
  <div class="layout">
    <div class="stack">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>남은 리스크</h2>
            <p class="muted small">계산에 넣지 못한 변수예요. 「해당」과 「판단 불가」는 확인 표시를 해야 깨끗하게 선택할 수 있어요.</p>
          </div>
          <div class="seg">
            <button v-for="s in all" :key="s.id" :class="{ on: s.id === cand.id }" @click="emit('focus', s.id)">
              {{ s.id === 'FCFS' ? '기준안' : s.label }}
            </button>
          </div>
        </div>
        <div class="panel-body risks">
          <article v-for="r in items" :key="r.key" :class="['risk', stateClass(r.state)]">
            <div class="risk-head">
              <span class="chip" :class="stateClass(r.state)">{{ r.state }}</span>
              <h3>{{ r.label }}</h3>
              <label v-if="r.state !== '해당 없음'" class="check small">
                <input v-model="checks[key(r.key)]" type="checkbox" /> 확인함
              </label>
            </div>
            <p>{{ r.evidence }}</p>
            <dl v-if="r.alternative !== '-' || r.caution !== '-'" class="ac small">
              <template v-if="r.alternative !== '-'"><dt>대안</dt><dd>{{ r.alternative }}</dd></template>
              <template v-if="r.caution !== '-'"><dt>주의</dt><dd>{{ r.caution }}</dd></template>
            </dl>
          </article>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>입력이 바뀌면</h2>
            <p class="muted small">같은 순서·부두 배정을 유지한 채 도착 시각이나 기상 예보가 바뀌었을 때예요. 영향이 큰 순서로 6개만 보여요.</p>
          </div>
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
              <span class="chip none">{{ current.status }}</span>
              <span class="small muted">이 후보가 선택돼 있어요.</span>
            </div>
            <div class="row">
              <button class="btn" @click="emit('decide', { action: '취소', candId: cand.id, label: cand.label, total: cand.total, reason: '담당자 취소' })">선택 취소</button>
              <button v-if="current.status === '선택됨'" class="btn" @click="emit('decide', { action: '현업 반영 완료', candId: cand.id, label: cand.label, total: cand.total, reason: '현업 시스템에 반영함' })">현업 반영 완료 표시</button>
            </div>
            <button class="btn primary" @click="emit('next')">보고서 초안 만들기 →</button>
          </template>
          <template v-else>
            <div class="field">
              <label for="reason">선택 사유 (보고서에 들어가요)</label>
              <textarea id="reason" v-model="reason" class="input" rows="3" placeholder="예: 기상 해제 직후 대형선 우선 접안, 체선료 절감 폭이 가장 큼" />
            </div>
            <div v-if="confirming" class="confirm">
              <p class="small"><b>확인 안 한 리스크 {{ unchecked.length }}건</b>({{ unchecked.map((r) => r.label).join(', ') }})이 있어요. 그대로 선택하면 이력에 함께 남아요.</p>
              <div class="row">
                <button class="btn" @click="confirming = false">돌아가기</button>
                <button class="btn warn" @click="choose(true)">그래도 선택</button>
              </div>
            </div>
            <button v-else class="btn primary" @click="choose(false)">이 후보로 선택</button>
          </template>
          <p class="faint small">Agent는 계획을 확정하지 않아요. 선택·취소·반영 완료는 담당자 기록으로만 남아요.</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h3>선택 이력</h3><span class="faint small">추가만 가능</span></div>
        <div class="panel-body">
          <p v-if="!decisions.length" class="muted small">아직 기록이 없어요.</p>
          <ol class="log">
            <li v-for="(d, i) in [...decisions].reverse()" :key="i" class="small">
              <div class="row"><b>{{ d.action }}</b><span>{{ d.label }}</span><span class="spacer" /><span class="faint">입력 v{{ d.version }}</span></div>
              <div class="muted">{{ d.at }} · {{ d.reason }}</div>
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
.seg { display: inline-flex; border: 1px solid var(--line-strong); border-radius: 6px; overflow: hidden; flex: none; }
.seg button { border: none; background: var(--panel); padding: 6px 12px; font-weight: 600; color: var(--muted); border-right: 1px solid var(--line); }
.seg button:last-child { border-right: none; }
.seg button.on { background: var(--accent); color: #fff; }
.risks { display: flex; flex-direction: column; gap: 10px; }
.risk { border: 1px solid var(--line); border-left-width: 3px; border-radius: 6px; padding: 10px 14px; display: flex; flex-direction: column; gap: 6px; }
.risk.hit { border-left-color: var(--warn); }
.risk.unknown { border-left-color: var(--unknown); }
.risk.none { border-left-color: var(--ok); }
.risk-head { display: flex; align-items: center; gap: 10px; }
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
textarea.input { resize: vertical; }
</style>
