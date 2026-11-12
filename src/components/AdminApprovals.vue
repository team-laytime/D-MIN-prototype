<script setup>
// 관리자메뉴 > 승인 관리. 목록(승인 대기 · 처리 완료)과 승인 처리(보고서 + 결재 처리 표) 두 화면.
// console(BerthDesk) approvals.js 모양을 따른다. 승인해야 접안 계획 버전이 올라가고, Agent는 결재하지 않는다.
import { computed, reactive, ref, watch } from 'vue'
import { marked } from 'marked'
import { CircleAlert, CircleCheck, X } from 'lucide-vue-next'
import { risks } from '../lib/engine.js'
import { buildReport, reportPeriod } from '../lib/report.js'
import { fmt, money } from '../lib/time.js'
import ViewHead from './ViewHead.vue'

const props = defineProps({ requests: Array, result: Object, scen: Object, version: Number, role: Object, planVersions: Array })
const emit = defineEmits(['decide', 'open', 'go'])

const REASONS = ['금액', '현장 사정', '안전', '화주 · 선주 관계', '기타']
const all = computed(() => [props.result.fcfs, ...props.result.candidates])
const fcfs = computed(() => props.result.fcfs)
const vById = computed(() => Object.fromEntries(props.scen.vessels.map((x) => [x.id, x])))
const bn = (id) => props.scen.berths.find((b) => b.id === id)?.name ?? '-'
const title = (r) => `${reportPeriod(all.value.find((s) => s.id === r.candId) ?? props.result.candidates[0])} 접안 계획 검토`

const pend = computed(() => props.requests.filter((r) => r.status === '승인 대기').reverse())
const done = computed(() => props.requests.filter((r) => r.status === '승인 완료' || r.status === '반려').reverse())
const others = computed(() => props.requests.filter((r) => r.status === '요청 취소' || r.status === '재요청으로 대체').reverse())
const nextPlanNo = computed(() => props.planVersions.length + 1)
const planMove = computed(() => `${props.planVersions.length ? `v${props.planVersions.length}` : '없음'} → v${nextPlanNo.value}`)

// 승인 처리 화면 상태
const openId = ref(null)
const req = computed(() => props.requests.find((r) => r.id === openId.value) ?? null)
const isOpen = computed(() => req.value?.status === '승인 대기')
const A = reactive({ pick: null, tab: 'doc', type: '금액', opinion: '', checks: {}, err: '' })
watch(openId, () => Object.assign(A, { pick: req.value?.candId ?? null, tab: 'doc', type: '금액', opinion: '', checks: {}, err: '' }))
const pick = computed(() => {
  const id = isOpen.value ? A.pick : req.value?.decision?.candId ?? req.value?.candId
  return all.value.find((s) => s.id === id) ?? props.result.candidates[0]
})
const stale = computed(() => req.value && req.value.version !== props.version)
const items = computed(() => {
  const out = risks(pick.value, props.scen).filter((r) => r.state !== '해당 없음').map((r) => ({ key: r.label, text: `${r.state} · ${r.evidence}` }))
  if (stale.value) out.unshift({ key: '입력 변경', text: `요청 뒤 입력이 바뀜 (v${req.value.version} → v${props.version}). 금액은 현재 입력으로 다시 계산한 값` })
  return out
})
const checked = (k) => (isOpen.value ? !!A.checks[k] : (req.value?.decision?.risksChecked ?? []).includes(k))
const reportHtml = computed(() => marked.parse(buildReport({ result: props.result, scen: props.scen, cand: pick.value, reason: req.value?.reason })))
const diffRows = computed(() => {
  const base = Object.fromEntries(fcfs.value.placements.map((p) => [p.vid, p]))
  return [...pick.value.placements].sort((a, b) => a.etb - b.etb).map((p) => {
    const b = base[p.vid]
    return { vid: p.vid, name: vById.value[p.vid].name, b, p, moved: b.bid !== p.bid || b.etb !== p.etb }
  })
})

const modal = ref(false)
function validate(what) {
  A.err = A.opinion.trim() ? '' : `결재 의견(${what})을 적어 주십시오.`
  return !A.err
}
function askApprove() { if (validate('선택 이유')) modal.value = true }
function approve() {
  const keys = items.value.map((i) => i.key)
  emit('decide', {
    action: '승인', reqId: req.value.id, candId: pick.value.id, label: pick.value.label, total: pick.value.total,
    requestedId: req.value.candId, requestedLabel: req.value.label,
    reason: A.opinion.trim(), reasonType: A.type,
    risksChecked: keys.filter((k) => A.checks[k]), uncheckedRisks: keys.filter((k) => !A.checks[k]),
  })
  modal.value = false
}
function reject() {
  if (!validate('반려 사유')) return
  emit('decide', { action: '반려', reqId: req.value.id, candId: req.value.candId, label: req.value.label, total: req.value.total, reason: A.opinion.trim(), reasonType: A.type })
}
const nowText = () => new Date().toLocaleString('ko-KR', { hour12: false })
</script>

<template>
  <!-- 목록 -->
  <div v-if="!req" class="stack">
    <ViewHead title="승인 관리" crumb="관리자메뉴 > 승인 관리" desc="접안계획 보고서를 검토하고 적용할 안을 승인합니다. 승인하면 접안 계획 버전이 올라갑니다."
      :kpis="[
        { label: '승인 대기', value: `${pend.length}건`, bad: pend.length > 0 },
        { label: '처리 완료', value: `${done.length}건` },
        { label: '적용 중 계획', value: planVersions.length ? `v${planVersions.length} · ${planVersions.at(-1).label}` : '없음' },
      ]" />

    <section class="panel">
      <div class="panel-head">
        <h2>승인 대기</h2>
        <span class="muted">스케줄러가 선택해 올린 보고서입니다.</span>
        <span class="count">전체 조회 건수 <b>{{ pend.length }}</b></span>
      </div>
      <table class="grid">
        <thead><tr><th>No</th><th>문서번호</th><th>제목</th><th>요청자</th><th>요청일시</th><th>요청 안</th><th>예상 체선료(USD)</th><th>기준안 대비</th><th>입력 기준</th><th>재확인</th><th>처리</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in pend" :key="r.id" class="clickable" @click="openId = r.id">
            <td class="c">{{ pend.length - i }}</td>
            <td class="c strong">{{ r.id }}</td>
            <td>{{ title(r) }}</td>
            <td class="c">{{ r.who }}</td>
            <td class="c num">{{ r.at }}</td>
            <td class="c">{{ r.label }}</td>
            <td class="r num strong">{{ money(r.total) }}</td>
            <td class="r num good">{{ money(r.total - fcfs.total) }}</td>
            <td class="c">v{{ r.version }}</td>
            <td class="c"><span v-if="r.version !== version" class="bad strong">필요 (입력 변경)</span><span v-else class="faint">-</span></td>
            <td class="c"><button class="btn primary sm" @click.stop="openId = r.id">검토</button></td>
          </tr>
          <tr v-if="!pend.length"><td colspan="11" class="empty">승인 대기 중인 보고서가 없습니다. 스케줄러가 「리스크·선택」에서 후보를 선택하면 여기에 올라옵니다.</td></tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>처리 완료</h2>
        <button class="btn ghost" @click="emit('go', 'history')">승인 이력</button>
      </div>
      <table class="grid">
        <thead><tr><th>문서번호</th><th>결정</th><th>선택 안</th><th>요청 안과 같음</th><th>사유 구분</th><th>결재 의견</th><th>결재자</th><th>결재일시</th></tr></thead>
        <tbody>
          <tr v-for="r in done" :key="r.id" class="clickable" @click="openId = r.id">
            <td class="c strong">{{ r.id }}</td>
            <td class="c"><span :class="r.status === '승인 완료' ? 'good strong' : 'bad strong'">{{ r.status === '승인 완료' ? '승인' : '반려' }}</span></td>
            <td class="c">{{ r.status === '승인 완료' ? r.decision.label : '-' }}</td>
            <td class="c">{{ r.status !== '승인 완료' ? '-' : r.decision.candId === r.candId ? '예' : '아니오' }}</td>
            <td class="c">{{ r.decision.reasonType }}</td>
            <td>{{ r.decision.reason }}</td>
            <td class="c">{{ r.decision.who }}</td>
            <td class="c num">{{ r.decision.at }}</td>
          </tr>
          <tr v-if="!done.length"><td colspan="8" class="empty">처리한 보고서가 없습니다.</td></tr>
        </tbody>
      </table>
      <p v-if="others.length" class="faint small note-line">취소·대체된 요청 {{ others.length }}건은 승인 이력에 남습니다.</p>
    </section>
  </div>

  <!-- 승인 처리 -->
  <div v-else class="stack">
    <ViewHead title="승인 처리" :crumb="`관리자메뉴 > 승인 관리 > ${req.id}`" />
    <div class="bar">
      <span>{{ req.id }} · {{ req.who }} · {{ req.at }} 요청 · 상태 <b :class="{ bad: req.status === '반려', good: req.status === '승인 완료' }">{{ req.status }}</b></span>
      <button class="btn" @click="openId = null">목록</button>
    </div>
    <div v-if="req.status === '승인 완료'" class="notice done">
      <CircleCheck class="ico" :size="18" />
      <span><b>{{ req.decision.label }} 승인 완료</b> · 접안 계획 v{{ req.decision.planNo }} 적용 · {{ req.decision.who }} · {{ req.decision.at }} · [{{ req.decision.reasonType }}] {{ req.decision.reason }}</span>
    </div>
    <div v-else-if="req.status === '반려'" class="notice danger">
      <CircleAlert class="ico" :size="18" />
      <span><b>반려</b> · {{ req.decision.who }} · {{ req.decision.at }} · [{{ req.decision.reasonType }}] {{ req.decision.reason }}</span>
    </div>
    <div v-else-if="stale" class="notice">
      <CircleAlert class="ico" :size="18" />
      <span><b>요청 뒤 입력이 바뀌었습니다</b> (v{{ req.version }} → v{{ version }}). 아래 금액은 현재 입력으로 다시 계산한 값입니다.</span>
    </div>

    <div class="side-doc">
      <section class="panel">
        <div class="seg tabs">
          <button :class="{ on: A.tab === 'doc' }" @click="A.tab = 'doc'">보고서</button>
          <button :class="{ on: A.tab === 'diff' }" @click="A.tab = 'diff'">변경 미리보기 (기준안 → {{ pick.label }})</button>
        </div>
        <div class="panel-body">
          <article v-if="A.tab === 'doc'" class="md-doc doc-box" v-html="reportHtml" />
          <template v-else>
            <p class="small muted diff-note">바뀐 선박 {{ diffRows.filter((r) => r.moved).length }}척 · 행을 누르면 선박 카드</p>
            <table class="grid">
              <thead><tr><th>선박</th><th>기준안 부두 · 접안</th><th>{{ pick.label }} 부두 · 접안</th><th>체선료(USD) 기준안 → {{ pick.label }}</th><th>변경</th></tr></thead>
              <tbody>
                <tr v-for="r in diffRows" :key="r.vid" class="clickable" :class="{ moved: r.moved }" @click="emit('open', pick.id, r.vid)">
                  <td class="strong">{{ r.name }}</td>
                  <td class="c num">{{ bn(r.b.bid) }} · {{ fmt(r.b.etb) }}</td>
                  <td class="c num">{{ bn(r.p.bid) }} · {{ fmt(r.p.etb) }}</td>
                  <td class="r num">{{ money(r.b.dem.cents) }} → <b>{{ money(r.p.dem.cents) }}</b></td>
                  <td class="c">{{ r.moved ? (r.b.bid !== r.p.bid ? '부두·시각' : '시각') : '-' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </section>

      <aside class="sticky">
        <div class="panel-head"><h2>결재 처리</h2></div>
        <table class="kv">
          <tbody>
            <tr><th>선택 안</th><td>
              <label v-for="s in all" :key="s.id" class="opt">
                <input type="radio" name="pick" :value="s.id" :checked="pick.id === s.id" :disabled="!isOpen" @change="A.pick = s.id" />
                <b>{{ s.label }}</b> {{ money(s.total) }}<span v-if="s.id === req.candId" class="req-mark">(요청)</span>
              </label>
            </td></tr>
            <tr><th>예상 체선료</th><td>
              <b class="num">{{ money(pick.total) }}</b> <span class="good num">(기준안 대비 {{ money(pick.total - fcfs.total) }})</span>
              <p v-if="isOpen && pick.id !== req.candId" class="warn small">요청 안과 다른 안입니다. 결재 의견이 기록됩니다.</p>
            </td></tr>
            <tr><th>확인 사항</th><td>
              <label v-for="it in items" :key="it.key" class="opt chk">
                <input type="checkbox" :checked="checked(it.key)" :disabled="!isOpen" @change="A.checks[it.key] = $event.target.checked" />
                <span><b>{{ it.key }}</b> <span class="muted small">{{ it.text }}</span></span>
              </label>
              <span v-if="!items.length" class="muted">확인할 항목 없음</span>
            </td></tr>
            <tr><th>사유 구분</th><td>
              <select v-if="isOpen" v-model="A.type" class="input sm"><option v-for="x in REASONS" :key="x">{{ x }}</option></select>
              <span v-else>{{ req.decision?.reasonType ?? '-' }}</span>
            </td></tr>
            <tr><th>결재 의견 <span class="bad">*</span></th><td>
              <textarea v-if="isOpen" v-model="A.opinion" class="input" rows="4" placeholder="선택 이유 또는 반려 사유" @input="A.err = ''" />
              <span v-else>{{ req.decision?.reason ?? '-' }}</span>
              <p v-if="A.err" class="bad small">{{ A.err }}</p>
            </td></tr>
            <tr><th>결재자</th><td>
              {{ isOpen ? role.name : req.decision?.who }} <span class="muted">(로그인 계정)</span>
              <p class="muted small">{{ isOpen ? `승인 시 접안 계획 ${planMove} · 입력 v${version} 기준으로 기록` : `요청 입력 v${req.version}` }}</p>
            </td></tr>
          </tbody>
        </table>
        <div v-if="isOpen" class="acts">
          <button class="btn lg" @click="reject">반려</button>
          <button class="btn primary lg" @click="askApprove">승인</button>
        </div>

        <div class="panel-head prog-head"><h2>진행</h2></div>
        <table class="grid prog">
          <thead><tr><th>단계</th><th>처리자</th><th>일시</th></tr></thead>
          <tbody>
            <tr><td class="c">선택 · 승인 요청</td><td class="c">{{ req.who }}</td><td class="c num">{{ req.at }}</td></tr>
            <tr><td class="c">{{ req.decision ? (req.status === '승인 완료' ? '승인' : '반려') : '결재' }}</td>
              <td class="c">{{ req.decision?.who ?? '대기' }}</td><td class="c num">{{ req.decision?.at ?? '-' }}</td></tr>
          </tbody>
        </table>
      </aside>
    </div>

    <div v-if="modal" class="modal-back" @click.self="modal = false">
      <div class="modal" role="dialog" aria-modal="true" :aria-label="`${pick.label} 승인`">
        <div class="mh"><b>{{ pick.label }} 승인</b><button class="mx" aria-label="닫기" @click="modal = false"><X :size="16" /></button></div>
        <div class="mb">
          <table class="kv">
            <tbody>
              <tr><th>문서</th><td>{{ req.id }} · {{ title(req) }}</td></tr>
              <tr><th>선택 안</th><td><b>{{ pick.label }}</b><span v-if="pick.id !== req.candId" class="warn"> (요청 안 {{ req.label }}과 다름)</span></td></tr>
              <tr><th>예상 체선료</th><td><b>{{ money(pick.total) }}</b> · 기준안 대비 {{ money(pick.total - fcfs.total) }}</td></tr>
              <tr><th>바뀌는 선박</th><td>{{ diffRows.filter((r) => r.moved).length }}척 (기준안 대비)</td></tr>
              <tr><th>확인 사항</th><td>
                {{ items.filter((i) => A.checks[i.key]).map((i) => i.key).join(', ') || '-' }}
                <p v-if="items.some((i) => !A.checks[i.key])" class="warn small">미확인: {{ items.filter((i) => !A.checks[i.key]).map((i) => i.key).join(', ') }} (기록에 남음)</p>
              </td></tr>
              <tr><th>결재 의견</th><td>[{{ A.type }}] {{ A.opinion }}</td></tr>
              <tr><th>적용</th><td>접안 계획 {{ planMove }}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="mf">
          <span class="muted small">결재자 {{ role.name }} · {{ nowText() }}</span>
          <button class="btn" @click="modal = false">취소</button>
          <button class="btn primary" @click="approve">승인</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.r { text-align: right; }
.good { color: var(--ok); }
.bad { color: var(--bad); }
.warn { color: var(--warn); font-weight: 600; margin: 4px 0 0; }
.count { margin-left: auto; color: #333; font-size: 12.5px; }
.count b { color: var(--bad); font-size: 15px; margin-left: 4px; }
.empty { text-align: center; color: var(--muted); height: 56px; }
.note-line { margin: 8px 0 0; }
.btn.sm { height: 24px; padding: 0 10px; font-size: 12px; }
.btn.lg { height: 38px; min-width: 96px; font-size: 13.5px; font-weight: 700; justify-content: center; }

.bar { display: flex; align-items: center; justify-content: space-between; margin-top: -14px; font-size: 12.5px; color: #444; }
.side-doc { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 20px; align-items: start; }
.tabs { margin-bottom: 0; }
.doc-box { background: #fff; border: 1px solid var(--line-strong); border-top: 2px solid #5b6575; padding: 18px 22px; max-height: 760px; }
.diff-note { margin: 0 0 6px; }
tr.moved td { background: #fff6c4; }
.sticky { position: sticky; top: 16px; display: flex; flex-direction: column; }
.opt { display: flex; align-items: baseline; gap: 6px; margin: 3px 0; cursor: pointer; }
.opt.chk { align-items: flex-start; margin: 5px 0; }
.opt.chk input { margin-top: 3px; }
.opt input { margin: 0; }
.req-mark { color: var(--accent); font-weight: 700; }
.kv textarea.input { width: 100%; height: auto; padding: 6px 8px; resize: vertical; }
.acts { display: flex; justify-content: center; gap: 8px; margin-top: 14px; }
.prog-head { margin-top: 22px; }
.prog td { height: 34px; }

.modal-back { position: fixed; inset: 0; z-index: 2100; background: rgba(20, 26, 36, 0.45); display: grid; place-items: center; }
.modal { width: 560px; max-width: calc(100vw - 40px); background: #fff; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3); }
.mh { display: flex; align-items: center; justify-content: space-between; background: #2c3746; color: #fff; padding: 14px 18px; font-size: 15px; }
.mx { border: 0; background: none; color: #fff; display: grid; place-items: center; }
.mb { padding: 16px 18px; }
.mf { display: flex; align-items: center; justify-content: flex-end; gap: 6px; padding: 12px 18px; border-top: 1px solid var(--line); }
.mf > span { margin-right: auto; }
</style>
