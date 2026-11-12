// 프로토타입용 규칙 평가기. 실제 구현에서는 Spring 계산 모듈이 맡는다(docs/architecture.md 4.2).
import { WEATHER_CLAUSE } from './scenarios.js'

export const STEP_MIN = 10

export const RULES = {
  ETA: { label: '도착 전에는 접안할 수 없음' },
  'BERTH-FREE': { label: '앞 선박 작업 종료 + 부두 전환 2시간' },
  'WX-BERTH': { label: '기상 악화 예보 구간에는 접안 금지' },
  'DAY-BERTH': { label: 'DWT 6만 톤 이상은 일출 ~ 일몰 1시간 전에만 접안' },
  'TIDE-BERTH': { label: '1번 부두에 흘수 11.5m 이상은 만조 ±2시간에만 접안' },
  'LT-START-NOR': { label: 'NOR 후 정해진 시간이 지나거나 접안한 때 중 빠른 시각부터 정박시간 계산' },
  'LT-START-IMM': { label: 'NOR 제출 즉시 정박시간 계산' },
  'LT-END-WORK': { label: '작업 종료(호스 분리) 시각에 정박시간 종료' },
  'WX-DED-FULL': { label: '정박시간 중 기상 악화로 기다린 시간은 전부 빼 줌' },
  'WX-DED-HALF': { label: '정박시간 중 기상 악화로 기다린 시간의 50%만 빼 줌' },
  'WX-DED-NONE': { label: '기상 악화로 기다린 시간도 정박시간에 넣음' },
  'DEM-PRORATA': { label: '초과 시간 × 하루 체선료 ÷ 24시간, 선박별로 센트 단위 한 번 반올림(HALF_UP)' },
}

const overlap = (a0, a1, b0, b1) => Math.max(0, Math.min(a1, b1) - Math.max(a0, b0))

export function compatibleBerths(v, scen) {
  return scen.berths
    .filter((b) => b.products.includes(v.product) && v.dwt <= b.maxDwt && v.draft <= b.maxDraft)
    .map((b) => b.id)
}

function blockingRule(v, b, t, env) {
  const w = env.weather
  if (w && t >= w.start && t < w.end) return 'WX-BERTH'
  if (v.dwt >= env.daylightDwt && !env.days.some((d) => t >= d.sunrise && t <= d.sunset - 60)) return 'DAY-BERTH'
  if (b.tideLimited && v.draft >= env.tideDraft && !env.highTides.some((h) => Math.abs(t - h) <= env.tideWindowMin)) return 'TIDE-BERTH'
  return null
}

// from 이후 가장 이른 접안 가능 시각. 접안을 막은 규칙과 구간을 근거로 남긴다.
function earliestEtb(v, b, from, env) {
  let t = Math.ceil(from / STEP_MIN) * STEP_MIN
  const blockers = []
  for (let i = 0; i < 1000; i++) {
    const r = blockingRule(v, b, t, env)
    if (!r) return { etb: t, blockers }
    const last = blockers[blockers.length - 1]
    if (last && last.rule === r && last.to === t) last.to = t + STEP_MIN
    else blockers.push({ rule: r, from: t, to: t + STEP_MIN })
    t += STEP_MIN
  }
  return { etb: null, blockers }
}

export function demurrage(v, etb, etu, env) {
  const c = v.contract
  const clause = WEATHER_CLAUSE[c.weather]
  const turnMin = c.norTurnH * 60
  const ltStart = turnMin > 0 ? Math.min(v.eta + turnMin, etb) : v.eta
  const usedMin = etu - ltStart
  const w = env.weather
  const wxOverlap = w ? overlap(ltStart, etb, w.start, w.end) : 0
  const wxDeduct = wxOverlap * clause.ratio
  const countedMin = usedMin - wxDeduct
  const allowMin = c.laytimeH * 60
  const excessMin = Math.max(0, countedMin - allowMin)
  const rateCents = c.rateUsd * 100
  // 0.5분 단위까지 정수로 다루고, 센트 반올림은 마지막에 한 번만 한다.
  const num = Math.round(excessMin * 2) * rateCents
  const den = 2880
  const cents = Math.floor((2 * num + den) / (2 * den))
  return {
    ltStart, ltStartRule: turnMin > 0 ? 'LT-START-NOR' : 'LT-START-IMM', turnMin,
    etb, etu, usedMin, wxOverlap, wxDeduct, clause, countedMin, allowMin, excessMin, rateCents, cents,
    rules: [turnMin > 0 ? 'LT-START-NOR' : 'LT-START-IMM', 'LT-END-WORK', clause.rule, 'DEM-PRORATA'],
  }
}

// order: 접안 우선순위, assign: 선박→부두. assign이 없으면 도착순 기준안처럼 가장 빨리 댈 수 있는 부두를 고른다.
export function simulate(order, assign, scen, compat) {
  const free = {}
  const prev = {}
  for (const b of scen.berths) {
    free[b.id] = b.occupiedUntil ?? null
    prev[b.id] = b.occupiedBy
  }
  const byId = Object.fromEntries(scen.vessels.map((v) => [v.id, v]))
  const berthById = Object.fromEntries(scen.berths.map((b) => [b.id, b]))
  const placements = []
  for (const vid of order) {
    const v = byId[vid]
    const options = assign ? [assign[vid]] : compat[vid]
    let best = null
    for (const bid of options) {
      const ready = free[bid] === null ? null : free[bid] + scen.env.switchingMin
      const from = ready === null ? v.eta : Math.max(v.eta, ready)
      const r = earliestEtb(v, berthById[bid], from, scen.env)
      if (r.etb === null) continue
      const cand = { vid, bid, etb: r.etb, etu: r.etb + v.workMin, ready, from, blockers: r.blockers, prev: prev[bid] }
      if (!best || cand.etb < best.etb || (cand.etb === best.etb && cand.etu < best.etu)) best = cand
    }
    if (!best) return null
    best.binding = best.ready !== null && best.ready > v.eta ? 'BERTH-FREE' : 'ETA'
    best.dem = demurrage(v, best.etb, best.etu, scen.env)
    best.waitMin = best.etb - v.eta
    placements.push(best)
    free[best.bid] = best.etu
    prev[best.bid] = byId[vid].name
  }
  return {
    order: [...order],
    assign: Object.fromEntries(placements.map((p) => [p.vid, p.bid])),
    placements,
    total: placements.reduce((s, p) => s + p.dem.cents, 0),
  }
}

function permutations(arr) {
  const out = []
  const a = [...arr]
  const c = new Array(a.length).fill(0)
  out.push([...a])
  let i = 0
  while (i < a.length) {
    if (c[i] < i) {
      const j = i % 2 ? c[i] : 0
      ;[a[j], a[i]] = [a[i], a[j]]
      out.push([...a])
      c[i]++
      i = 0
    } else {
      c[i] = 0
      i++
    }
  }
  return out
}

function combos(ids, compat) {
  let acc = [{}]
  for (const id of ids) {
    const next = []
    for (const partial of acc) for (const b of compat[id]) next.push({ ...partial, [id]: b })
    acc = next
  }
  return acc
}

const signature = (sim) =>
  sim.placements
    .slice()
    .sort((a, b) => a.bid.localeCompare(b.bid) || a.etb - b.etb)
    .map((p) => `${p.bid}:${p.vid}@${p.etb}`)
    .join('|')

export function fcfsOrder(scen) {
  return [...scen.vessels].sort((a, b) => a.eta - b.eta || a.id.localeCompare(b.id)).map((v) => v.id)
}

export function compatMap(scen) {
  return Object.fromEntries(scen.vessels.map((v) => [v.id, compatibleBerths(v, scen)]))
}

export function runSearch(scen, maxCandidates = 3) {
  const compat = compatMap(scen)
  const noBerth = scen.vessels.filter((v) => compat[v.id].length === 0)
  if (noBerth.length) return { error: `접안 가능한 부두가 없는 선박: ${noBerth.map((v) => v.name).join(', ')}` }

  const fcfs = simulate(fcfsOrder(scen), null, scen, compat)
  if (!fcfs) return { error: '도착순 기준안도 만들 수 없어요. 입력을 확인해 주세요.' }
  const fcfsEtb = Object.fromEntries(fcfs.placements.map((p) => [p.vid, p]))

  const seen = new Map()
  let explored = 0
  const ids = scen.vessels.map((v) => v.id)
  const assigns = combos(ids, compat)
  for (const order of permutations(ids)) {
    for (const assign of assigns) {
      explored++
      const sim = simulate(order, assign, scen, compat)
      if (!sim) continue
      const sig = signature(sim)
      if (!seen.has(sig)) seen.set(sig, sim)
    }
  }
  const changed = (sim) =>
    sim.placements.filter((p) => p.bid !== fcfsEtb[p.vid].bid || p.etb !== fcfsEtb[p.vid].etb).map((p) => p.vid)

  const fcfsSig = signature(fcfs)
  const ranked = [...seen.entries()]
    .filter(([sig]) => sig !== fcfsSig)
    .map(([sig, sim]) => ({ ...sim, sig, changed: changed(sim) }))
    .filter((s) => s.total < fcfs.total || s.total === fcfs.total)
    .sort((a, b) => a.total - b.total || a.changed.length - b.changed.length || a.sig.localeCompare(b.sig))

  // 부두별 순서가 같은 안은 하나만 남기고, 이미 고른 안보다 모든 선박이 같거나 늦게 끝나는 안(지배되는 안)은 뺀다.
  const seq = (s) => s.placements.slice().sort((a, b) => a.bid.localeCompare(b.bid) || a.etb - b.etb).map((p) => `${p.bid}${p.vid}`).join('')
  const etuOf = (s) => Object.fromEntries(s.placements.map((p) => [p.vid, p.etu]))
  const dominated = (s, p) => {
    const a = etuOf(s)
    const b = etuOf(p)
    return Object.keys(a).every((k) => a[k] >= b[k])
  }
  const picked = []
  const seqSeen = new Set([seq(fcfs)])
  for (const s of ranked) {
    if (seqSeen.has(seq(s))) continue
    if (picked.some((p) => dominated(s, p))) continue
    seqSeen.add(seq(s))
    picked.push(s)
    if (picked.length === maxCandidates) break
  }
  return {
    fcfs: { ...fcfs, sig: fcfsSig, changed: [], id: 'FCFS', label: '기준안 (도착순)' },
    candidates: picked.map((s, i) => ({ ...s, id: 'ABC'[i], label: `후보 ${'ABC'[i]}` })),
    explored,
    distinct: seen.size,
  }
}

// 후보 배치를 규칙과 하나씩 대조한다. 탐색 코드와 따로 짜서 서로 검증한다.
export function validate(sim, scen) {
  const v = Object.fromEntries(scen.vessels.map((x) => [x.id, x]))
  const b = Object.fromEntries(scen.berths.map((x) => [x.id, x]))
  const out = []
  for (const p of sim.placements) {
    const vs = v[p.vid]
    const bs = b[p.bid]
    if (!bs.products.includes(vs.product)) out.push(`${vs.name}: ${bs.name} 접안 불가 제품`)
    if (vs.dwt > bs.maxDwt || vs.draft > bs.maxDraft) out.push(`${vs.name}: ${bs.name} 제원 초과`)
    if (p.etb < vs.eta) out.push(`${vs.name}: 도착 전 접안`)
    if (blockingRule(vs, bs, p.etb, scen.env)) out.push(`${vs.name}: ${RULES[blockingRule(vs, bs, p.etb, scen.env)].label}`)
    if (bs.occupiedUntil !== null && p.etb < bs.occupiedUntil + scen.env.switchingMin) out.push(`${vs.name}: 기존 접안선과 겹침`)
  }
  for (const bid of Object.keys(b)) {
    const list = sim.placements.filter((p) => p.bid === bid).sort((x, y) => x.etb - y.etb)
    for (let i = 1; i < list.length; i++) {
      if (list[i].etb < list[i - 1].etu + scen.env.switchingMin) out.push(`${b[bid].name}: ${v[list[i - 1].vid].name}와 ${v[list[i].vid].name} 전환 시간 부족`)
    }
  }
  return out
}

const nightOf = (t, env) => !env.days.some((d) => t >= d.sunrise && t < d.sunset)

export function risks(sim, scen) {
  const v = Object.fromEntries(scen.vessels.map((x) => [x.id, x]))
  const b = Object.fromEntries(scen.berths.map((x) => [x.id, x]))
  const P = sim.placements
  const w = scen.env.weather
  const out = []

  if (!w) {
    out.push({ key: 'weather', label: '날씨 급변', state: '해당 없음', evidence: '계산 기간에 기상 악화 예보가 없어요.', alternative: '-', caution: '예보 갱신 때 다시 계산해 주세요.' })
  } else {
    const near = P.filter((p) => Math.abs(p.etb - w.start) <= 180 || Math.abs(p.etb - w.end) <= 180)
    out.push(near.length
      ? { key: 'weather', label: '날씨 급변', state: '해당',
          evidence: `${near.map((p) => v[p.vid].name).join(', ')}의 접안이 기상 악화 구간 경계 3시간 안에 있어요. 예보가 앞당겨지거나 늘어나면 접안이 밀려요.`,
          alternative: '기상 해제 직후 접안할 선박 순서를 미리 정하고, 도선사·예선 대기를 요청해 두세요.',
          caution: '단기예보 갱신(05·11·17·23시)마다 같은 조건으로 다시 계산해 순위가 바뀌는지 보세요.' }
      : { key: 'weather', label: '날씨 급변', state: '해당 없음', evidence: '기상 악화 구간 경계 3시간 안에 접안하는 선박이 없어요.', alternative: '-', caution: '예보 갱신 때 다시 계산해 주세요.' })
  }

  const maint = P.filter((p) => b[p.bid].facility.maintenance && overlap(p.etb, p.etu, b[p.bid].facility.maintenance.start, b[p.bid].facility.maintenance.end) > 0)
  const unknown = [...new Set(P.filter((p) => !b[p.bid].facility.known).map((p) => b[p.bid].name))]
  if (maint.length) {
    const m = b[maint[0].bid].facility.maintenance
    out.push({ key: 'facility', label: '설비', state: '해당',
      evidence: `${maint.map((p) => v[p.vid].name).join(', ')} 작업이 ${b[maint[0].bid].name} ${m.label}과 겹쳐요.${unknown.length ? ` ${unknown.join(', ')}은 설비 일정이 입력되지 않았어요.` : ''}`,
      alternative: '점검을 작업 종료 뒤로 미루거나, 점검 중에는 남은 로딩암 1기로 작업 시간을 늘려 다시 계산하세요.',
      caution: '이 계산은 점검 중에도 펌프율이 같다고 가정했어요.' })
  } else if (unknown.length) {
    out.push({ key: 'facility', label: '설비', state: '판단 불가', evidence: `${unknown.join(', ')}의 설비 점검 일정이 입력되지 않아 판단할 수 없어요.`, alternative: '설비팀에 해당 기간 점검 일정을 확인해 입력하세요.', caution: '확인 전에는 이 후보를 확정 대상으로 보지 마세요.' })
  } else {
    out.push({ key: 'facility', label: '설비', state: '해당 없음', evidence: '접안 기간과 겹치는 설비 점검이 없어요.', alternative: '-', caution: '-' })
  }

  const tankHits = scen.tanks.flatMap((t) => P.filter((p) => v[p.vid].dir === '수입' && v[p.vid].product === t.product && p.etb < t.readyAt && v[p.vid].ton > t.ullageTon).map((p) => ({ p, t })))
  out.push(tankHits.length
    ? { key: 'tank', label: '탱크', state: '해당',
        evidence: `${v[tankHits[0].p.vid].name} 하역량 ${v[tankHits[0].p.vid].ton.toLocaleString()}톤이 ${tankHits[0].t.product} 탱크 여유 ${tankHits[0].t.ullageTon.toLocaleString()}톤보다 많아요. ${tankHits[0].t.note}.`,
        alternative: '하역 속도를 낮춰 여유 확보 시각에 맞추거나, 하역 개시를 여유 확보 이후로 미룬 후보와 비교하세요.',
        caution: '하역 속도를 바꾸면 작업 종료 시각과 체선료가 달라져요. 다시 계산하세요.' }
    : { key: 'tank', label: '탱크', state: '해당 없음', evidence: '수입 선박 하역 시점의 탱크 여유가 충분해요.', alternative: '-', caution: '-' })

  const late = scen.urgent.map((u) => ({ u, p: P.find((p) => p.vid === u.vid) })).filter(({ u, p }) => p && p.etu > u.deadline)
  out.push(!scen.urgent.length
    ? { key: 'urgent', label: '긴급 출하', state: '판단 불가', evidence: '긴급 출하 계획이 입력되지 않았어요.', alternative: '출하팀에 긴급 출하 여부를 확인하세요.', caution: '-' }
    : late.length
      ? { key: 'urgent', label: '긴급 출하', state: '해당',
          evidence: late.map(({ u, p }) => `${v[u.vid].name}가 ${u.note} 납기보다 ${Math.round((p.etu - u.deadline) / 60)}시간 늦게 끝나요.`).join(' '),
          alternative: '해당 선박을 앞당긴 후보와 체선료 차이를 비교하세요.', caution: '납기 위반 비용은 체선료 합계에 들어 있지 않아요.' }
      : { key: 'urgent', label: '긴급 출하', state: '해당 없음', evidence: `긴급 출하(${scen.urgent.map((u) => v[u.vid].name).join(', ')})가 납기 안에 끝나요.`, alternative: '-', caution: '-' })

  const night = P.filter((p) => nightOf(p.etb, scen.env))
  out.push(night.length
    ? { key: 'safety', label: '현장 안전', state: '해당',
        evidence: `야간 접안 ${night.length}건: ${night.map((p) => v[p.vid].name).join(', ')}.`,
        alternative: '야간 접안을 일출 뒤로 미룬 후보와 체선료 차이를 비교하세요.',
        caution: '야간 도선·계류 인력 배치를 작업 지시 전에 확인하세요.' }
    : { key: 'safety', label: '현장 안전', state: '해당 없음', evidence: '야간 접안이 없어요.', alternative: '-', caution: '-' })

  return out
}

// 같은 순서·부두 배정을 유지한 채 도착 시각과 기상 구간이 바뀌면 금액과 순위가 어떻게 되는지 본다.
export function sensitivity(target, all, scen) {
  const compat = compatMap(scen)
  const rankOf = (totals, id) => Object.entries(totals).sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0])).findIndex(([k]) => k === id) + 1
  const baseTotals = Object.fromEntries(all.map((s) => [s.id, s.total]))
  const baseRank = rankOf(baseTotals, target.id)
  const cases = []
  for (const v of scen.vessels) {
    for (const d of [-360, 360]) {
      cases.push({ label: `${v.name} 도착 ${d > 0 ? '6시간 늦음' : '6시간 빠름'}`, patch: (s) => { s.vessels.find((x) => x.id === v.id).eta += d } })
    }
  }
  if (scen.env.weather) {
    cases.push({ label: '기상 악화 6시간 연장', patch: (s) => { s.env.weather.end += 360 } })
    cases.push({ label: '기상 악화 6시간 일찍 시작', patch: (s) => { s.env.weather.start -= 360 } })
  }
  return cases.map((c) => {
    const s2 = JSON.parse(JSON.stringify(scen)) // Vue 반응형 프록시도 복제할 수 있게
    c.patch(s2)
    const totals = {}
    for (const s of all) {
      const r = s.id === 'FCFS' ? simulate(fcfsOrder(s2), null, s2, compat) : simulate(s.order, s.assign, s2, compat)
      totals[s.id] = r ? r.total : Infinity
    }
    const after = totals[target.id]
    return { label: c.label, delta: after === Infinity ? null : after - target.total, rankBefore: baseRank, rankAfter: rankOf(totals, target.id) }
  }).sort((a, b) => (b.rankAfter !== b.rankBefore) - (a.rankAfter !== a.rankBefore) || Math.abs(b.delta ?? 1e15) - Math.abs(a.delta ?? 1e15))
}
