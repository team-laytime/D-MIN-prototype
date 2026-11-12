<script setup>
import { computed, ref } from 'vue'
import { risks } from '../lib/engine.js'
import { fmt, money } from '../lib/time.js'

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
    `${period.value} 울산 터미널 접안 계획으로 ${cand.value.label}을 ${chosen.value ? '선택했어요' : '검토하고 있어요'}.`,
    '',
    `- 총 예상 체선료: ${money(cand.value.total)} (도착순 기준안 ${money(fcfs.value.total)} 대비 ${money(saving.value)}, ${savingPct.value}% 감소)`,
    `- 기준안과 달라진 선박: ${cand.value.changed.map((id) => v.value[id].name).join(', ') || '없음'}`,
    `- 확인이 필요한 리스크: ${hits.value.map((r) => `${r.label}(${r.state})`).join(', ') || '없음'}`,
  ]
  if (chosen.value) lines.push(`- 선택 사유: ${chosen.value.reason}`)
  lines.push('', '선박별 일정과 산출 근거는 첨부 보고서에 있어요.', '', '※ 가상 데이터 기반 의사결정 보조 자료이며, 담당자 검토용 초안입니다.')
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
  L.push('## 1. 결론', `${cand.value.label}을 ${statusWord.value} 안으로 올려요. 총 예상 체선료는 ${money(cand.value.total)}이고, 도착순 기준안 ${money(fcfs.value.total)}보다 ${money(saving.value)}(${savingPct.value}%) 적어요.`, '')
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
    <div v-if="!chosen" class="banner">
      <b>아직 담당자가 고른 후보가 없어요.</b> 지금 보고 있는 {{ cand.label }} 기준으로 초안을 만들었어요. 「리스크·선택」에서 고르면 선택 사유까지 들어가요.
    </div>
    <div class="check-line small" :class="check.bad.length ? 'bad' : 'ok'">
      <template v-if="!check.bad.length">숫자 대조 통과: 초안의 금액 {{ check.count }}개가 모두 계산 결과와 같아요.</template>
      <template v-else>숫자 대조 실패: {{ check.bad.join(', ') }}. 이 초안은 쓰지 마세요.</template>
    </div>

    <div class="cols">
      <section class="panel">
        <div class="panel-head">
          <h2>메일 초안</h2>
          <button class="btn" @click="copy('mail', mail)">{{ copied === 'mail' ? '복사했어요' : '복사' }}</button>
        </div>
        <div class="panel-body"><pre class="doc">{{ mail }}</pre></div>
        <p class="faint small foot">메일은 보내지 않아요. 복사해서 직접 보내 주세요.</p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>보고용 Report 초안</h2>
          <div class="row">
            <button class="btn" @click="copy('report', reportText)">{{ copied === 'report' ? '복사했어요' : '복사' }}</button>
            <button class="btn" @click="download">내려받기 (.md)</button>
          </div>
        </div>
        <div class="panel-body"><pre class="doc">{{ reportText }}</pre></div>
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
</style>
