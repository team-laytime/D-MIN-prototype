<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import { Copy, Download } from 'lucide-vue-next'
import { risks } from '../lib/engine.js'
import { fmt, money } from '../lib/time.js'
import ViewHead from './ViewHead.vue'

const props = defineProps({ result: Object, scen: Object, focusId: String, current: Object, version: Number })

const all = computed(() => [props.result.fcfs, ...props.result.candidates])
const chosen = computed(() => (props.current && props.current.version === props.version ? props.current : null))
const cand = computed(() => all.value.find((s) => s.id === (chosen.value?.candId ?? props.focusId)) ?? props.result.candidates[0])
const fcfs = computed(() => props.result.fcfs)
const v = computed(() => Object.fromEntries(props.scen.vessels.map((x) => [x.id, x])))
const bn = (id) => props.scen.berths.find((b) => b.id === id).name
const rs = computed(() => risks(cand.value, props.scen))
const saving = computed(() => fcfs.value.total - cand.value.total)
const savingPct = computed(() => (fcfs.value.total ? ((saving.value / fcfs.value.total) * 100).toFixed(1) : '0.0'))
const period = computed(() => {
  const ps = cand.value.placements
  return `${fmt(Math.min(...ps.map((p) => p.etb))).slice(0, 5)} ~ ${fmt(Math.max(...ps.map((p) => p.etu))).slice(0, 5)}`
})
const hits = computed(() => rs.value.filter((r) => r.state !== '해당 없음'))
const sorted = computed(() => [...cand.value.placements].sort((a, b) => a.etb - b.etb))
const statusWord = computed(() => (chosen.value ? '선택' : '검토 중인'))

const mail = computed(() => {
  const lines = [
    `제목: [울산 CLX] ${period.value} 접안 계획안 검토 요청 (${cand.value.label}, 예상 체선료 ${money(cand.value.total)})`,
    '',
    '안녕하세요.',
    `${period.value} 울산 터미널 접안 계획으로 ${cand.value.label}을 ${chosen.value ? '선택했습니다' : '검토 중입니다'}.`,
    '',
    `- 총 예상 체선료: ${money(cand.value.total)} (도착순 기준안 ${money(fcfs.value.total)} 대비 ${money(saving.value)}, ${savingPct.value}% 감소)`,
    `- 기준안과 달라진 선박: ${cand.value.changed.map((id) => v.value[id].name).join(', ') || '없음'}`,
    `- 확인이 필요한 리스크: ${hits.value.map((r) => `${r.label}(${r.state})`).join(', ') || '없음'}`,
  ]
  if (chosen.value) lines.push(`- 선택 사유: ${chosen.value.reason}`)
  lines.push('', '선박별 일정과 산출 근거는 첨부 보고서를 참고해 주십시오.', '', '※ 가상 데이터 기반 의사결정 보조 자료이며, 담당자 검토용 초안입니다.')
  return lines.join('\n')
})

// 초안에 들어간 금액이 모두 계산 결과에서 나온 값인지 대조한다.
const allowed = computed(() => {
  const s = new Set()
  for (const sim of all.value) {
    s.add(money(sim.total))
    s.add(money(sim.total - fcfs.value.total))
    for (const p of sim.placements) s.add(money(p.dem.cents))
  }
  s.add(money(saving.value))
  s.add(money(-saving.value))
  return s
})
const check = computed(() => {
  const found = [...(mail.value + reportText.value).matchAll(/-?\$[\d,]+\.\d{2}/g)].map((m) => m[0])
  const bad = found.filter((x) => !allowed.value.has(x))
  return { count: found.length, bad }
})

const reportText = computed(() => {
  const L = []
  L.push(`# 울산 CLX 접안 계획 검토 보고 (${period.value})`, '', '담당자 검토용 초안 · 가상 데이터 · 의사결정 보조용', '')
  L.push('## 1. 결론', `${cand.value.label}을 ${statusWord.value} 안으로 제출합니다. 총 예상 체선료는 ${money(cand.value.total)}이며, 도착순 기준안 ${money(fcfs.value.total)} 대비 ${money(saving.value)}(${savingPct.value}%) 적습니다.`, '')
  L.push('## 2. 후보 비교', '| 안 | 총 예상 체선료 | 기준안 대비 | 변경 선박 |', '| --- | ---: | ---: | ---: |')
  for (const s of all.value) L.push(`| ${s.label} | ${money(s.total)} | ${s.id === 'FCFS' ? '-' : money(s.total - fcfs.value.total)} | ${s.changed.length}척 |`)
  L.push('', `## 3. ${cand.value.label} 선박별 일정`, '| 선박 | 부두 | 도착 | 접안 | 작업 종료 | 예상 체선료 |', '| --- | --- | --- | --- | --- | ---: |')
  for (const p of sorted.value) L.push(`| ${v.value[p.vid].name} | ${bn(p.bid)} | ${fmt(v.value[p.vid].eta)} | ${fmt(p.etb)} | ${fmt(p.etu)} | ${money(p.dem.cents)} |`)
  L.push('', '## 4. 남은 리스크')
  for (const r of rs.value) L.push(`- ${r.label} · ${r.state}: ${r.evidence}${r.alternative !== '-' ? ` 대안: ${r.alternative}` : ''}`)
  if (chosen.value) L.push('', '## 5. 선택 사유', chosen.value.reason)
  L.push('', '## 계산 기준', '- 체선료 = 초과 시간 ÷ 24시간 × 하루 체선료, 선박별 센트 단위 한 번 반올림(HALF_UP)', '- 정박시간 개시·기상 공제는 선박별 계약 조항을 따름', '- 기준안은 비교용 도착순 배치이며 현행 실적이 아님')
  return L.join('\n')
})

// 보고서는 문서 모양으로 렌더링해 보여 준다. 복사·내려받기는 마크다운 원문 그대로.
// 입력은 이 화면이 계산 결과로 만든 문자열뿐이라 외부 HTML이 섞이지 않는다.
const reportHtml = computed(() => marked.parse(reportText.value))
const reportView = ref('view')
const copied = ref('')
async function copy(which, text) {
  await navigator.clipboard.writeText(text)
  copied.value = which
  setTimeout(() => { copied.value = '' }, 1500)
}
function download() {
  const blob = new Blob([reportText.value], { type: 'text/markdown' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `접안계획_검토보고_${cand.value.id}.md`
  a.click()
}
</script>

<template>
  <div class="stack">
    <ViewHead title="접안계획 보고서" crumb="REPORT > 접안계획 보고서" :step="5" desc="선택한 후보 기준 메일·보고서 초안. 금액은 계산 결과를 그대로 넣고 자동 대조하며, 메일은 발송하지 않습니다."
      :kpis="[
        { label: '기준 후보', value: cand.label },
        { label: '총 예상 체선료', value: money(cand.total).replace(/\.\d+$/, '') },
        { label: '숫자 대조', value: check.bad.length ? '실패' : '통과', good: !check.bad.length },
      ]" />
    <div v-if="!chosen" class="banner">
      <b>담당자 선택 전.</b> {{ cand.label }} 기준 초안입니다. 「리스크·선택」에서 선택하면 선택 사유가 추가됩니다.
    </div>
    <div class="check-line small" :class="check.bad.length ? 'bad' : 'ok'">
      <template v-if="!check.bad.length">숫자 대조 통과 · 초안 금액 {{ check.count }}개 모두 계산 결과와 일치</template>
      <template v-else>숫자 대조 실패: {{ check.bad.join(', ') }}. 사용 금지.</template>
    </div>

    <div class="cols">
      <section class="panel">
        <div class="panel-head">
          <h2>메일 초안</h2>
          <button class="btn" @click="copy('mail', mail)"><Copy :size="16" />{{ copied === 'mail' ? '복사됨' : '복사' }}</button>
        </div>
        <div class="panel-body"><pre class="doc">{{ mail }}</pre></div>
        <p class="faint small foot">발송 기능 없음 · 복사 후 직접 발송</p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>보고서 초안</h2>
          <div class="row">
            <div class="seg" role="tablist" aria-label="보기 방식">
              <button :class="{ on: reportView === 'view' }" @click="reportView = 'view'">문서 보기</button>
              <button :class="{ on: reportView === 'raw' }" @click="reportView = 'raw'">마크다운 원문</button>
            </div>
            <button class="btn" @click="copy('report', reportText)"><Copy :size="16" />{{ copied === 'report' ? '복사됨' : '복사' }}</button>
            <button class="btn" @click="download"><Download :size="16" />내려받기 (.md)</button>
          </div>
        </div>
        <div class="panel-body">
          <article v-if="reportView === 'view'" class="md" v-html="reportHtml" />
          <pre v-else class="doc">{{ reportText }}</pre>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.banner { background: var(--warn-weak); color: #5c3500; border-radius: var(--radius); padding: 10px 14px; }
.check-line { padding: 8px 14px; border-radius: var(--radius); font-weight: 600; }
.check-line.ok { background: var(--ok-weak); color: var(--ok); }
.check-line.bad { background: var(--bad-weak); color: var(--bad); }
.cols { display: grid; grid-template-columns: 1fr 1.25fr; gap: 16px; align-items: start; }
.doc {
  margin: 0; white-space: pre-wrap; word-break: keep-all; font-family: inherit; font-size: 13.5px; line-height: 1.7;
  background: #fafbfc; border: 1px solid var(--line); border-radius: 6px; padding: 14px 16px; max-height: 640px; overflow: auto;
}
.foot { padding: 0 18px 14px; }
/* 마크다운 문서 보기: 포털 표 양식에 맞춘 제목·표·목록 */
.md { max-height: 640px; overflow: auto; padding: 4px 6px 8px; font-size: 13px; line-height: 1.75; color: var(--text); }
.md :deep(h1) { font-size: 19px; font-weight: 800; text-align: center; margin: 6px 0 4px; letter-spacing: -0.4px; }
.md :deep(h1 + p) { text-align: center; color: var(--muted); font-size: 12px; margin-bottom: 14px; }
.md :deep(h2) { font-size: 14.5px; font-weight: 700; margin: 20px 0 8px; padding-bottom: 4px; border-bottom: 1px solid var(--line-strong); }
.md :deep(p) { margin: 0 0 8px; }
.md :deep(table) { width: 100%; border-collapse: collapse; border-top: 2px solid #5b6575; border-bottom: 1px solid var(--line-strong); font-size: 12.5px; margin: 4px 0 8px; }
.md :deep(th) { background: #eef0f3; color: #2b3445; font-weight: 600; padding: 6px 8px; border: 1px solid var(--line); border-top: 0; white-space: nowrap; }
.md :deep(td) { padding: 6px 8px; border: 1px solid var(--line); font-variant-numeric: tabular-nums; }
.md :deep(ul) { margin: 0 0 8px; padding-left: 0; list-style: none; }
.md :deep(li) { position: relative; padding-left: 16px; }
.md :deep(li)::before { content: '○'; position: absolute; left: 0; color: #555; font-size: 11px; top: 2px; }
</style>
