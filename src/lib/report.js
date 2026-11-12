// 접안계획 보고서 초안(마크다운). 보고서 화면과 관리자 승인 처리 화면이 같은 문서를 본다.
import { risks } from './engine.js'
import { fmt, money } from './time.js'

export function reportPeriod(cand) {
  const ps = cand.placements
  return `${fmt(Math.min(...ps.map((p) => p.etb))).slice(0, 5)} ~ ${fmt(Math.max(...ps.map((p) => p.etu))).slice(0, 5)}`
}

/** reason이 있으면 '선택한 안', 없으면 '검토 중인 안'으로 쓴다. */
export function buildReport({ result, scen, cand, reason = null }) {
  const fcfs = result.fcfs
  const all = [fcfs, ...result.candidates]
  const v = Object.fromEntries(scen.vessels.map((x) => [x.id, x]))
  const bn = (id) => scen.berths.find((b) => b.id === id).name
  const saving = fcfs.total - cand.total
  const savingPct = fcfs.total ? ((saving / fcfs.total) * 100).toFixed(1) : '0.0'
  const L = []
  L.push(`# 울산 CLX 접안 계획 검토 보고 (${reportPeriod(cand)})`, '', '담당자 검토용 초안 · 가상 데이터 · 의사결정 보조용', '')
  L.push('## 1. 결론', `${cand.label}을 ${reason ? '선택' : '검토 중인'} 안으로 제출합니다. 총 예상 체선료는 ${money(cand.total)}이며, 도착순 기준안 ${money(fcfs.total)} 대비 ${money(saving)}(${savingPct}%) 적습니다.`, '')
  L.push('## 2. 후보 비교', '| 안 | 총 예상 체선료 | 기준안 대비 | 변경 선박 |', '| --- | ---: | ---: | ---: |')
  for (const s of all) L.push(`| ${s.label} | ${money(s.total)} | ${s.id === 'FCFS' ? '-' : money(s.total - fcfs.total)} | ${s.changed.length}척 |`)
  L.push('', `## 3. ${cand.label} 선박별 일정`, '| 선박 | 부두 | 도착 | 접안 | 작업 종료 | 예상 체선료 |', '| --- | --- | --- | --- | --- | ---: |')
  for (const p of [...cand.placements].sort((a, b) => a.etb - b.etb)) {
    L.push(`| ${v[p.vid].name} | ${bn(p.bid)} | ${fmt(v[p.vid].eta)} | ${fmt(p.etb)} | ${fmt(p.etu)} | ${money(p.dem.cents)} |`)
  }
  L.push('', '## 4. 남은 리스크')
  for (const r of risks(cand, scen)) L.push(`- ${r.label} · ${r.state}: ${r.evidence}${r.alternative !== '-' ? ` 대안: ${r.alternative}` : ''}`)
  if (reason) L.push('', '## 5. 선택 사유', reason)
  L.push('', '## 계산 기준', '- 체선료 = 초과 시간 ÷ 24시간 × 하루 체선료, 선박별 센트 단위 한 번 반올림(HALF_UP)', '- 정박시간 개시·기상 공제는 선박별 계약 조항을 따름', '- 기준안은 비교용 도착순 배치이며 현행 실적이 아님')
  return L.join('\n')
}
