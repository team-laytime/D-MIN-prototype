<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { BadgeCheck, ChevronLeft, ChevronRight, CircleAlert, ClipboardList, Columns3, Database, Factory, FileText, Inbox, Moon, Pause, Play, Receipt, ScrollText, ShieldAlert, Ship, SkipBack, Workflow } from 'lucide-vue-next'
import ViewHead from './ViewHead.vue'
import LiveVesselCard from './LiveVesselCard.vue'
import { fetchArrivals, fetchLive, liveColor } from '../lib/liveAis.js'
import BerthBoard from './BerthBoard.vue'
import { risks, stateAt } from '../lib/engine.js'
import { MAP_CONTEXT } from '../lib/scenarios.js'
import { NAV, anchorageFor, positionOf } from '../lib/vesselState.js'
import { at, fmt, fmtDur, money } from '../lib/time.js'
import { canUse, groupOf, ws } from '../lib/workspace.js'

const props = defineProps({ result: Object, scen: Object, current: Object, version: Number })
const emit = defineEmits(['go', 'focus', 'open'])

const plans = computed(() => [props.result.fcfs, ...props.result.candidates])
const planId = ref(props.result.candidates[0]?.id ?? 'FCFS')
watch(plans, (ps) => { if (!ps.some((s) => s.id === planId.value)) planId.value = ps[1]?.id ?? 'FCFS' })
const plan = computed(() => plans.value.find((s) => s.id === planId.value))
const fcfs = computed(() => props.result.fcfs)
function choose(id) { planId.value = id; emit('focus', id) }

// 시간 막대: 11/14 00:00부터 모든 안의 작업이 끝날 때까지
const START = at(14, 0)
const END = computed(() => Math.ceil(Math.max(...plans.value.flatMap((s) => s.placements.map((p) => p.etu))) / 60) * 60 + 60)
const t = ref(at(14, 20))
const playing = ref(false)
let timer = null
function stop() { clearInterval(timer); playing.value = false }
function togglePlay() {
  if (playing.value) return stop()
  if (t.value >= END.value) t.value = START
  playing.value = true
  timer = setInterval(() => {
    t.value = Math.min(END.value, t.value + 30)
    if (t.value >= END.value) stop()
  }, 350)
}
const step = (d) => { stop(); t.value = Math.max(START, Math.min(END.value, t.value + d)) }
onBeforeUnmount(stop)

const states = computed(() => stateAt(plan.value, props.scen, t.value).sort((a, b) => a.v.eta - b.v.eta))
const accrued = computed(() => Object.fromEntries(plans.value.map((s) => [s.id, stateAt(s, props.scen, t.value).reduce((n, x) => n + x.cents, 0)])))
// 아직 항해 중인 배는 지도 범위(울산항 앞바다) 밖이라 점으로 그릴 수 없다. ETA와 남은 시간을 지도 위 목록으로 보여 준다.
const comingList = computed(() => states.value.filter((x) => x.phase === 'coming').map((x) => ({ id: x.v.id, name: x.v.name, eta: x.v.eta, left: x.v.eta - t.value, nm: Math.round(((x.v.eta - t.value) / 60) * NAV.coming.sog), prev: x.v.prevPort.split(',')[0] })))
const w = computed(() => props.scen.env.weather)
const weatherNow = computed(() => w.value && t.value >= w.value.start && t.value < w.value.end)
const isNight = computed(() => !props.scen.env.days.some((d) => t.value >= d.sunrise && t.value < d.sunset))
const openRisks = computed(() => risks(plan.value, props.scen).filter((r) => r.state !== '해당 없음'))

// 지도 옆 알림 패널(console 대시보드 모양)과 바로가기 타일
const notes = computed(() => {
  const out = []
  if (w.value) out.push({ tag: '기상', red: weatherNow.value, text: `${w.value.label} · ${fmt(w.value.start)}~${fmt(w.value.end).slice(6)} 접안 금지`, at: weatherNow.value ? '발효 중' : '예보' })
  for (const s of states.value.filter((x) => x.ticking)) out.push({ tag: '체선', red: true, text: `${s.v.name} 체선 발생 · 누적 ${money(s.cents)}`, at: fmt(t.value).slice(6), vid: s.v.id })
  for (const r of openRisks.value) out.push({ tag: '리스크', text: `${r.label} ${r.state} · ${label(plan.value)}`, at: '확인 필요', go: 'risk' })
  out.push(props.current && props.current.version === props.version
    ? { tag: '확정', text: `${props.current.label} ${props.current.status}`, at: '스케줄러', go: 'ops' }
    : { tag: '확정', text: '접안 계획 확정 전', at: '대기', go: 'risk' })
  return out
})
// 바로가기는 로그인한 계정이 쓸 수 있는 화면만 보여 준다.
const ALL_TILES = [
  { id: 'input', label: '시나리오\n입력', icon: ClipboardList },
  { id: 'compare', label: '후보\n비교', icon: Columns3 },
  { id: 'risk', label: '리스크·\n확정', icon: ShieldAlert },
  { id: 'requests', label: '요청\n처리', icon: Inbox },
  { id: 'ops', label: '확정\n접안 일정', icon: Ship },
  { id: 'prod', label: '탱크·\n긴급 출하', icon: Factory },
  { id: 'contract', label: '계약 조건·\nLaytime', icon: ScrollText },
  { id: 'settle', label: '체선료\n정산', icon: Receipt },
  { id: 'report', label: '접안계획\n보고서', icon: FileText },
  { id: 'verify', label: '계산\n검증', icon: BadgeCheck },
  { id: 'master', label: '기준\n정보', icon: Database },
  { id: 'workflow', label: 'Agent\n워크플로우', icon: Workflow },
]
const TILES = computed(() => ALL_TILES.filter((t) => canUse(ws.roleId, groupOf(t.id))).slice(0, 6))
function onNote(n) {
  if (n.vid) openCard(n.vid)
  else if (n.go) emit('go', n.go)
}
const berthOf = (bid) => props.scen.berths.find((b) => b.id === bid)
const weekday = (min) => ['일', '월', '화', '수', '목', '금', '토'][(6 + Math.floor(min / 1440)) % 7]
const label = (s) => (s.id === 'FCFS' ? '도착순 기준안' : s.label)
const best = computed(() => props.result.candidates[0])
const kpis = computed(() => [
  { label: '대기 선박', value: `${props.scen.vessels.length}척`, sub: `부두 ${props.scen.berths.length}곳` },
  { label: '도착순 기준안', value: money(fcfs.value.total), sub: '비교용 · 현행 실적 아님' },
  { label: `${best.value.label} (최저)`, value: money(best.value.total), sub: `기준안 대비 ${(((best.value.total - fcfs.value.total) / fcfs.value.total) * 100).toFixed(1)}%`, good: true },
  { label: '확인할 리스크', value: `${risks(best.value, props.scen).filter((r) => r.state !== '해당 없음').length}건`, sub: best.value.label, bad: true },
  { label: '계획 확정', value: props.current && props.current.version === props.version ? `${props.current.label} ${props.current.status}` : '확정 전' },
])

// 지도 표식 색은 PortWise 문법(빨강 입항·대기, 초록 계류, 회색 출항). 체선 발생은 빨간 점선 고리로 겹쳐 표시한다.
const PHASE = {
  coming: { text: '입항 예정', color: NAV.coming.color, row: 'plan' },
  waiting: { text: '정박지 대기', color: NAV.waiting.color, row: 'plan' },
  berthed: { text: '작업 중', color: NAV.berthed.color, row: 'berth' },
  left: { text: '출항', color: NAV.left.color, row: 'dep' },
}
const color = (s) => PHASE[s.phase].color
function stateText(s) {
  if (s.phase === 'coming') return `${fmt(s.v.eta)} 도착 예정`
  if (s.phase === 'waiting') return `${anchorageFor(s.v).label} ${fmtDur(t.value - s.v.eta)} · ${berthOf(s.p.bid).name} ${fmt(s.p.etb).slice(6)} 접안 예정`
  if (s.phase === 'berthed') return `${berthOf(s.p.bid).name} · 진행 ${Math.round(s.progress * 100)}%`
  return `${fmt(s.p.etu)} 작업 종료`
}

// 시간 막대 바탕: 야간과 기상 악화 구간을 따로 그려 겹쳐도 둘 다 보이게 한다.
const pct = (m) => ((m - START) / (END.value - START)) * 100
const bands = computed(() => {
  const clip = (a, b) => ({ left: Math.max(0, pct(a)), width: Math.min(100, pct(b)) - Math.max(0, pct(a)) })
  const d = props.scen.env.days
  const out = []
  for (let i = 0; i < d.length - 1; i++) out.push({ k: `n${i}`, cls: 'night', ...clip(d[i].sunset, d[i + 1].sunrise) })
  if (w.value) out.push({ k: 'wx', cls: 'wx', ...clip(w.value.start, w.value.end) })
  return out.filter((b) => b.width > 0)
})
const dayTicks = computed(() => {
  const out = []
  for (let m = START; m <= END.value; m += 1440) out.push({ m, label: fmt(m).slice(0, 5) })
  return out
})

// ── 실시간 AIS 모드 ──
// 서버(/api/ais/vessels)가 있을 때만 버튼이 나온다. 켜면 가상 시나리오 선박 대신 울산항의 실제 선박을 그린다.
const liveOn = ref(false)
const liveAvail = ref(false)
const live = ref(null) // { vessels, fetchedAt, stale, error, total }
const liveErr = ref('')
const liveSel = ref(null)
let liveTimer = null
async function pullLive() {
  try {
    live.value = await fetchLive()
    liveErr.value = live.value.error ?? ''
    liveAvail.value = true
  } catch (e) {
    liveErr.value = String(e.message ?? e)
    if (!live.value) liveAvail.value = false
  }
}
// 입항 예정(대리점 신고): 앞으로 24시간 안. 5분마다 새로 받는다(서버도 5분 캐시).
const planned = ref([])
const plannedErr = ref('')
async function pullPlanned() {
  try { planned.value = (await fetchArrivals({ hoursAhead: 24 })).arrivals.filter((a) => a.planned); plannedErr.value = '' } catch (e) { plannedErr.value = String(e.message ?? e) }
}
let plannedTimer = null
const hhmm = (iso) => `${iso.slice(5, 10).replace('-', '/')} ${iso.slice(11, 16)}`
function pickPlanned(a) {
  const x = live.value?.vessels.find((v) => v.callSign === a.callSign)
  if (x) { liveSel.value = x.mmsi; draw() }
}
async function toggleLive() {
  liveOn.value = !liveOn.value
  clearInterval(liveTimer)
  clearInterval(plannedTimer)
  if (liveOn.value) { await pullLive(); liveTimer = setInterval(pullLive, 30000); pullPlanned(); plannedTimer = setInterval(pullPlanned, 300000) }
  draw()
}
onBeforeUnmount(() => { clearInterval(liveTimer); clearInterval(plannedTimer) })
const liveSelected = computed(() => live.value?.vessels.find((x) => x.mmsi === liveSel.value) ?? null)

// ── 지도 ──
const mapEl = ref(null)
const selected = ref(null)
let map = null
let dyn = null

// PortWise처럼 위에서 본 배 모양. ring = 체선 발생 중
const shipSvg = (fill, cog, sel, ring) =>
  `<svg width="22" height="22" viewBox="-11 -11 22 22">${ring ? '<circle r="10" fill="none" stroke="#e02424" stroke-width="2" stroke-dasharray="3 2"/>' : ''}<g transform="rotate(${cog})"><path d="M0 -8 L4 -3 L4 7 L-4 7 L-4 -3 Z" fill="${fill}" stroke="${sel ? '#111' : '#fff'}" stroke-width="${sel ? 1.8 : 1}" stroke-linejoin="round"/><rect x="-2.6" y="2" width="5.2" height="3" fill="#fff" opacity=".85"/></g></svg>`

function shipMarker(pos, fill, cog, name, extra, sel, ring, onClick, tip) {
  const icon = L.divIcon({
    className: 'vmk-wrap',
    html: `<div class="vmk">${shipSvg(fill, cog, sel, ring)}<span class="lbl${sel ? ' sel' : ''}">${name}${extra ? ` <em>${extra}</em>` : ''}</span></div>`,
    iconSize: [22, 22], iconAnchor: [11, 11],
  })
  const m = L.marker(pos, { icon, zIndexOffset: sel ? 1000 : 0 })
  if (onClick) m.on('click', onClick)
  if (tip) m.bindTooltip(tip, { direction: 'right', offset: [14, 0], className: 'map-tip' })
  return m
}
function openCard(vid) {
  selected.value = vid
  emit('open', plan.value.id, vid, { at: t.value })
}

function draw() {
  if (!map) return
  dyn.clearLayers()
  const anchorUse = {}
  for (const b of props.scen.berths) {
    const occ = states.value.find((s) => s.phase === 'berthed' && s.p.bid === b.id)
    const legacy = b.occupiedUntil !== null && t.value < b.occupiedUntil
    const busy = !!occ || legacy
    const queue = plan.value.placements.filter((p) => p.bid === b.id).sort((x, y) => x.etb - y.etb)
    const html = `<span class="bmk${busy ? ' busy' : ''}">${b.code}</span>`
    L.marker(b.pos, { icon: L.divIcon({ className: 'sk-wrap', html, iconSize: [0, 0] }), zIndexOffset: 500 })
      .bindTooltip(`<b>${b.name}</b> · ${b.maxDwt.toLocaleString()} DWT · 흘수 ${b.maxDraft}m<br>${b.products.join(', ')}<br><br><b>${label(plan.value)} 접안 순서</b><br>${queue.map((p) => `${fmt(p.etb)}  ${props.scen.vessels.find((v) => v.id === p.vid).name}`).join('<br>')}`, { direction: 'left', offset: [-16, 0], className: 'map-tip' })
      .addTo(dyn)
    if (legacy) shipMarker(b.moor, NAV.berthed.color, NAV.berthed.cog, b.occupiedBy, '', false, false).addTo(dyn)
  }
  if (liveOn.value && live.value) {
    for (const x of live.value.vessels) {
      const cog = x.heading && x.heading < 360 ? x.heading : x.cog ?? 0
      const sel = liveSel.value === x.mmsi
      const tip = `<b>${x.name || x.mmsi}</b> · ${x.navStatus ?? '상태 없음'}<br>${x.sog ?? '-'} kn · ${Math.round(x.ageMin ?? 0)}분 전<br><span style="color:#888">눌러서 실시간 정보 보기</span>`
      shipMarker([x.lat, x.lng], liveColor(x.navStatus), cog, x.name || '', '', sel, false, () => { liveSel.value = x.mmsi; draw() }, tip).addTo(dyn)
    }
    return
  }
  for (const s of states.value) {
    if (s.phase === 'coming' || s.phase === 'left') continue
    let spot = 0
    if (s.phase === 'waiting') {
      const a = anchorageFor(s.v)
      spot = anchorUse[a.id] = (anchorUse[a.id] ?? -1) + 1
    }
    const pos = positionOf(s, props.scen, spot)
    const sel = selected.value === s.v.id
    const extra = s.ticking ? money(s.cents).replace(/\.\d+$/, '') : ''
    const tip = `<b>${s.v.name}</b> · ${s.v.type}<br>${s.v.flag} · DWT ${s.v.dwt.toLocaleString()} · ${s.v.product} ${s.v.dir}<br>도착(ETA) ${fmt(s.v.eta)} · 접안(ETB) ${fmt(s.p.etb)}<br><span style="color:#888">눌러서 전체 제원 보기</span>`
    shipMarker(pos, color(s), NAV[s.phase].cog, s.v.name, extra, sel, s.ticking, () => openCard(s.v.id), tip).addTo(dyn)
  }
}

onMounted(() => {
  map = L.map(mapEl.value, { zoomControl: false, attributionControl: true, minZoom: 11, maxZoom: 18, zoomSnap: 0.5 })
  L.control.zoom({ position: 'bottomright' }).addTo(map)
  // Esri 회색 타일은 울산 일대가 13단계까지만 있어서 그 이상 확대하면 "Map data not yet available"이 뜬다.
  // console(BerthDesk)과 같은 OSM 타일로 바꾸고, 표식이 묻히지 않게 채도만 낮춘다(.base-tiles).
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, className: 'base-tiles', attribution: '© OpenStreetMap contributors',
  }).addTo(map)
  // SK 부두부터 E3 정박지까지 한 화면에 담는다.
  map.fitBounds([[35.402, 129.372], [35.505, 129.474]], { paddingTopLeft: [16, 16], paddingBottomRight: [16, 80] })
  for (const f of MAP_CONTEXT.facilities) {
    L.marker(f.pos, { icon: L.divIcon({ className: 'sk-wrap', html: `<span class="bmk ctx">${f.code}</span>`, iconSize: [0, 0] }) })
      .bindTooltip('계산 대상 아님', { className: 'map-tip' }).addTo(map)
  }
  for (const a of MAP_CONTEXT.anchorages) {
    L.circle(a.center, { radius: 900, color: '#b8942a', weight: 1, dashArray: '4 4', fillColor: '#f4e3a1', fillOpacity: 0.15, interactive: false }).addTo(map)
    L.marker([a.center[0] + 0.0102, a.center[1]], { icon: L.divIcon({ className: 'anch-lbl', html: `<span>${a.label}</span>`, iconSize: [0, 0] }), interactive: false }).addTo(map)
  }
  dyn = L.layerGroup().addTo(map)
  // 실시간 모드는 배가 170척 넘게 겹쳐서, 14단계 이상 확대했을 때만 이름을 보여 준다(이름은 마우스를 올리면 툴팁으로도 보인다).
  const lblZoom = () => mapEl.value?.classList.toggle('hide-lbl', liveOn.value && map.getZoom() < 14)
  map.on('zoomend', lblZoom)
  watch(liveOn, lblZoom)
  draw()
  pullLive() // 서버가 없으면 조용히 실패하고 버튼은 숨겨진다
})
onBeforeUnmount(() => { map?.remove(); map = null })
watch([states, selected, () => props.scen, live], draw)

function pick(vid) {
  selected.value = vid
  const s = states.value.find((x) => x.v.id === vid)
  if (!map || !s || s.phase === 'coming' || s.phase === 'left') return
  if (s.phase === 'berthed') map.flyTo(berthOf(s.p.bid).moor, 15, { duration: 0.6 })
  else map.flyTo(anchorageFor(s.v).center, 14, { duration: 0.6 })
}
</script>

<template>
  <div class="stack">
    <ViewHead title="운영 현황" crumb="DASHBOARD > 운영 현황" :kpis="kpis" />

    <div v-if="w" :class="['notice', { danger: weatherNow }]">
      <CircleAlert class="ico" :size="18" />
      <span><b>{{ w.label }}</b> — {{ fmt(w.start) }} ~ {{ fmt(w.end) }} 전 부두 접안 금지{{ weatherNow ? ' · 현재 발효 중' : '' }} · {{ w.source }}</span>
      <button class="act" @click="emit('go', 'compare')">후보 비교</button>
    </div>

    <section class="panel">
      <div class="panel-head">
        <h2>안별 예상 체선료</h2>
        <span class="muted">행 선택 시 지도와 선박 현황이 해당 안으로 전환</span>
        <button class="btn primary" @click="emit('go', 'compare')">후보 비교</button>
      </div>
      <div class="panel-body">
        <table class="grid plan-table">
          <thead>
            <tr><th>선택</th><th>구분</th><th>총 예상 체선료(USD)</th><th>기준안 대비</th><th>변경 선박</th><th>{{ fmt(t) }} 누적</th><th>리스크</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in plans" :key="s.id" :class="['clickable', { on: s.id === planId }]" @click="choose(s.id)">
              <td class="c"><input type="radio" name="plan" :checked="s.id === planId" :aria-label="label(s)" @change="choose(s.id)" /></td>
              <td class="c strong">{{ label(s) }}</td>
              <td class="r num strong">{{ money(s.total) }}</td>
              <td class="r num" :class="{ good: s.total < fcfs.total }">{{ s.id === 'FCFS' ? '-' : `${money(s.total - fcfs.total)} (${(((s.total - fcfs.total) / fcfs.total) * 100).toFixed(1)}%)` }}</td>
              <td class="c num">{{ s.changed.length }}</td>
              <td class="r num" :class="{ bad: accrued[s.id] > 0 }">{{ money(accrued[s.id]) }}</td>
              <td class="c"><span class="chip hit">해당 {{ risks(s, scen).filter((r) => r.state === '해당').length }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>선석 작업현황</h2>
        <span class="muted">{{ label(plan) }} · {{ fmt(t) }} 기준 · 선석을 누르면 선박 카드</span>
        <span class="side-note small">진행률 배지: 초록 = 정상, 빨강 = 체선 예상</span>
      </div>
      <BerthBoard :sim="plan" :scen="scen" :t="t" @pick="openCard" />
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>선박 위치 · 알림</h2>
        <span class="muted">{{ label(plan) }} · 기준 {{ fmt(t) }} · 배를 누르면 선박 카드</span>
      </div>
      <div class="row-map">
        <div class="map-box">
          <div ref="mapEl" class="map" />
          <button v-if="liveAvail" :class="['live-btn', { on: liveOn }]" @click="toggleLive">
            <i class="dot" />{{ liveOn ? `실시간 AIS 켜짐 · ${live?.count ?? 0}척` : '실시간 AIS 보기' }}
          </button>
          <div v-if="liveOn && live" class="live-info small">
            울산항만공사 항내 선박위치 · {{ (live.fetchedAt || '').slice(11, 19) }} 수신 · 30분 안 갱신 {{ live.count }} / 전체 {{ live.total }}척
            <b v-if="live.stale" class="bad"> · 공공 API 오류, 이전 값 표시</b>
          </div>
          <div v-if="liveOn" class="coming-box live-plan">
            <h4>입항 예정 <small>대리점 신고 · 24시간 안 {{ planned.length }}척</small></h4>
            <p v-if="plannedErr" class="small bad" style="margin:6px 10px">신고 조회 실패: {{ plannedErr }}</p>
            <button v-for="a in planned.slice(0, 12)" :key="a.callSign + a.count" @click="pickPlanned(a)">
              <span class="nm">{{ a.name }}</span>
              <span class="eta num">ETA {{ hhmm(a.eta) }}</span>
              <span class="rest">{{ a.facility ?? '-' }} · {{ a.prevPort ?? '-' }}발 · {{ a.grt ? a.grt.toLocaleString() + ' GT' : '' }} · {{ a.filing }}</span>
            </button>
          </div>
          <div v-if="liveOn" class="live-legend">
            <span><i style="background:#2b7de0" />항해</span><span><i style="background:#d4a017" />정박(앵커)</span><span><i style="background:#2ea043" />계류</span><span><i style="background:#8a63d2" />기타</span>
          </div>
          <div v-if="comingList.length && !liveOn" class="coming-box">
            <h4>입항 예정 <small>항해 중 · 눌러서 제원 보기</small></h4>
            <button v-for="c in comingList" :key="c.id" @click="openCard(c.id)">
              <span class="nm">{{ c.name }}</span>
              <span class="eta num">ETA {{ fmt(c.eta) }}</span>
              <span class="rest">{{ c.left > 0 ? `${fmtDur(c.left)} 후 · 약 ${c.nm}nm` : '도착 시각 경과' }} · {{ c.prev }}발</span>
            </button>
          </div>
          <div v-if="isNight" class="night-tag small"><Moon :size="13" />야간 · 6만 DWT 이상 접안 불가</div>
          <div class="map-legend">
            <span><span v-html="shipSvg(NAV.waiting.color, 0, false, false)" />입항 예정 · 정박지 대기</span>
            <span><span v-html="shipSvg(NAV.berthed.color, 0, false, false)" />부두 계류</span>
            <span><span v-html="shipSvg(NAV.waiting.color, 0, false, true)" />체선 발생</span>
            <span><span class="bmk-key">SK6</span>SK 부두</span>
          </div>
          <div class="time-dock">
            <div class="ctrls">
              <button class="icon-btn" title="처음으로" aria-label="처음으로" @click="stop(); t = START"><SkipBack :size="14" /></button>
              <button class="icon-btn" title="1시간 전" aria-label="1시간 전" @click="step(-60)"><ChevronLeft :size="14" /></button>
              <button class="icon-btn play" :title="playing ? '멈춤' : '재생'" :aria-label="playing ? '멈춤' : '재생'" @click="togglePlay">
                <Pause v-if="playing" :size="14" /><Play v-else :size="14" />
              </button>
              <button class="icon-btn" title="1시간 후" aria-label="1시간 후" @click="step(60)"><ChevronRight :size="14" /></button>
            </div>
            <div class="clock">
              <span class="hm num">{{ fmt(t).slice(6) }}</span>
              <span class="date num">{{ fmt(t).slice(0, 5) }} ({{ weekday(t) }})</span>
            </div>
            <div class="slider">
              <div class="track">
                <span v-for="b in bands" :key="b.k" :class="['band', b.cls]" :style="{ left: b.left + '%', width: b.width + '%' }" />
              </div>
              <input v-model.number="t" type="range" :min="START" :max="END" step="10" aria-label="시각" @input="stop" />
              <div class="ticks">
                <span v-for="d in dayTicks" :key="d.m" :style="{ left: pct(d.m) + '%' }">{{ d.label }}</span>
              </div>
            </div>
          </div>
        </div>
        <aside class="note-panel">
          <div class="note">
            <h3>알림 <small>{{ fmt(t) }}</small></h3>
            <ul>
              <li v-for="(n, i) in notes" :key="i" @click="onNote(n)">
                <span class="tx"><span :class="['tg', { r: n.red }]">{{ n.tag }}</span>{{ n.text }}</span>
                <span class="dt">{{ n.at }}</span>
              </li>
            </ul>
          </div>
          <div class="tiles">
            <button v-for="tl in TILES" :key="tl.id" @click="emit('go', tl.id)">
              <component :is="tl.icon" :size="22" :stroke-width="1.6" />
              <span>{{ tl.label }}</span>
            </button>
          </div>
        </aside>
      </div>
    </section>

    <LiveVesselCard v-if="liveSelected" :vessel="liveSelected" :fetched-at="live?.fetchedAt" @close="liveSel = null; draw()" />

    <section class="panel">
      <div class="panel-head">
        <h2>선박 현황</h2>
        <span class="muted">{{ label(plan) }} · {{ fmt(t) }} 기준 · 행 선택 시 지도 이동</span>
        <div class="row-legend small">
          <span><i class="dep" />출항</span><span><i class="berth" />작업중</span><span><i class="plan" />계획</span>
          <span class="count">전체 조회 건수 <b>{{ states.length }}</b></span>
        </div>
      </div>
      <div class="panel-body">
        <table class="grid vessel-list">
          <thead>
            <tr><th>선박명</th><th>화물</th><th>상태</th><th>위치·예정</th><th>도착(NOR)</th><th>접안(ETB)</th><th>작업 종료</th><th>누적 체선료(USD)</th><th>산출 근거</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in states" :key="s.v.id" :class="['clickable', PHASE[s.phase].row, { sel: selected === s.v.id }]" @click="pick(s.v.id)">
              <td class="strong">{{ s.v.name }}</td>
              <td class="c">{{ s.v.product }} {{ s.v.dir }}</td>
              <td class="c"><span class="phase" :class="{ bad: s.ticking }">{{ s.ticking ? '체선 발생' : PHASE[s.phase].text }}</span></td>
              <td class="small">{{ stateText(s) }}</td>
              <td class="c num">{{ fmt(s.v.eta) }}</td>
              <td class="c num">{{ fmt(s.p.etb) }}</td>
              <td class="c num">{{ fmt(s.p.etu) }}</td>
              <td class="r num" :class="{ bad: s.ticking, strong: s.cents > 0 }">{{ s.cents > 0 ? money(s.cents) : '0' }}</td>
              <td class="c"><button class="btn ghost" @click.stop="openCard(s.v.id)">선박 카드</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.c { text-align: center; }
.good { color: var(--ok); }
.bad { color: var(--bad); }
.plan-table input[type='radio'] { margin: 0; }
.phase { font-weight: 700; font-size: 12.5px; }
.side-note { margin-left: auto; color: var(--muted); }

/* 상태 행 색 (출항 회색 · 작업중 노랑 · 계획 하늘) */
.vessel-list tr.dep td { background: #ececec; color: #666; }
.vessel-list tr.berth td { background: #fff6c4; }
.vessel-list tr.plan td { background: #e1f5f7; }
.vessel-list tr.sel td { box-shadow: inset 0 0 0 9999px rgba(14, 107, 114, 0.1); }
.row-legend { margin-left: auto; display: flex; align-items: center; gap: 14px; color: #444; }
.row-legend span { display: inline-flex; align-items: center; }
.row-legend i { display: inline-block; width: 30px; height: 13px; margin-right: 6px; border: 1px solid rgba(0, 0, 0, 0.08); }
.row-legend i.dep { background: #ececec; } .row-legend i.berth { background: #fff6c4; } .row-legend i.plan { background: #e1f5f7; }
.count { color: #333; }
.count b { color: var(--bad); font-size: 15px; margin-left: 4px; }

/* 지도 + 알림 패널 */
.row-map { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr); border: 1px solid var(--line-strong); border-top: 2px solid var(--rule); background: #fff; }
.map-box { position: relative; height: 580px; border-right: 1px solid var(--line-strong); }
.map { position: absolute; inset: 0; background: #cfe3f1; }
.live-btn { position: absolute; z-index: 901; top: 10px; left: 50%; transform: translateX(-50%); display: inline-flex; align-items: center; gap: 7px; height: 30px; padding: 0 14px; background: #fff; border: 1px solid var(--line-strong); font-size: 12.5px; font-weight: 700; color: #333; }
.live-btn .dot { width: 9px; height: 9px; border-radius: 50%; background: #aaa; }
.live-btn.on { background: #2b7de0; border-color: #2b7de0; color: #fff; }
.live-btn.on .dot { background: #7dffa0; box-shadow: 0 0 0 3px rgba(125, 255, 160, 0.35); }
.live-info { position: absolute; z-index: 900; top: 46px; left: 272px; background: rgba(255, 255, 255, 0.95); border: 1px solid var(--line-strong); padding: 3px 10px; color: #444; white-space: nowrap; }
.live-plan { top: 10px; left: 10px; }
.live-legend { position: absolute; z-index: 900; left: auto; right: 10px; top: 46px; background: rgba(255, 255, 255, 0.95); border: 1px solid var(--line-strong); padding: 4px 10px; font-size: 11.5px; display: flex; flex-direction: column; gap: 3px; }
.live-legend i { display: inline-block; width: 10px; height: 10px; margin-right: 6px; border-radius: 2px; }
.coming-box { position: absolute; z-index: 900; top: 10px; left: 10px; width: 250px; max-height: 300px; overflow: auto; background: rgba(255, 255, 255, 0.96); border: 1px solid var(--line-strong); }
.coming-box h4 { margin: 0; padding: 6px 10px; font-size: 12.5px; background: #eef0f3; border-bottom: 1px solid var(--line-strong); display: flex; justify-content: space-between; align-items: baseline; }
.coming-box h4 small { font-weight: 400; color: #888; font-size: 10.5px; }
.coming-box button { display: grid; grid-template-columns: 1fr auto; gap: 1px 8px; width: 100%; text-align: left; padding: 5px 10px; border: 0; border-bottom: 1px solid #eceef1; background: none; font-size: 12px; }
.coming-box button:hover { background: #e1f5f7; }
.coming-box .nm { font-weight: 700; }
.coming-box .eta { color: var(--bad); font-weight: 700; }
.coming-box .rest { grid-column: 1 / -1; font-size: 11px; color: #777; }
.night-tag { position: absolute; z-index: 900; top: 10px; right: 10px; display: inline-flex; align-items: center; gap: 6px; background: #fff; border: 1px solid var(--line-strong); padding: 4px 10px; color: #444; }
.map-legend { position: absolute; z-index: 900; left: 50%; transform: translateX(-50%); bottom: 76px; background: rgba(255, 255, 255, 0.95); border: 1px solid #c9ccd1; border-radius: 4px; padding: 4px 12px; font-size: 11.5px; color: #333; display: flex; gap: 14px; white-space: nowrap; }
.map-legend > span { display: inline-flex; align-items: center; gap: 4px; }
.map-legend :deep(svg) { display: block; }
.bmk-key { background: #fff; border: 1px solid #666; font-size: 10px; font-weight: 700; padding: 0 3px; line-height: 13px; }
.note-panel { display: flex; flex-direction: column; background: #2c3746; }
.note { flex: 1; color: #fff; padding: 20px 22px; overflow: auto; }
.note h3 { margin: 0 0 12px; font-size: 16px; display: flex; justify-content: space-between; align-items: center; }
.note h3 small { font-size: 11.5px; color: #aab3c0; font-weight: 400; }
.note ul { list-style: none; margin: 0; padding: 0; }
.note li { display: flex; justify-content: space-between; gap: 10px; padding: 7px 0; font-size: 12.5px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); cursor: pointer; }
.note li:last-child { border-bottom: 0; }
.note li:hover .tx { text-decoration: underline; }
.note .tg { display: inline-block; font-size: 10.5px; padding: 0 5px; margin-right: 6px; border: 1px solid #7f8b9b; color: #d7dde5; }
.note .tg.r { border-color: #ff8a8a; color: #ffb3b3; }
.note .dt { color: #aab3c0; font-size: 11.5px; white-space: nowrap; }
.tiles { display: grid; grid-template-columns: repeat(3, 1fr); background: #3a4657; }
.tiles button { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; color: #fff; font-size: 12px; text-align: center; padding: 12px 6px; border: 0; border-right: 1px solid rgba(255, 255, 255, 0.12); border-top: 1px solid rgba(255, 255, 255, 0.12); background: none; min-height: 84px; line-height: 1.35; white-space: pre-line; }
.tiles button:hover { background: var(--accent); }

.time-dock {
  position: absolute; z-index: 900; left: 10px; right: 10px; bottom: 10px; height: 56px;
  background: #fff; border: 1px solid var(--line-strong);
  display: flex; align-items: center; gap: 14px; padding: 0 14px;
}
.ctrls { display: flex; gap: 2px; }
.icon-btn { width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid #cfd2d6; background: #fff; border-radius: 2px; color: #333; }
.icon-btn:hover { background: var(--sunken); }
.icon-btn.play { background: var(--navy); border-color: var(--navy); color: #fff; }
.clock { display: flex; flex-direction: column; line-height: 1.15; min-width: 80px; }
.clock .hm { font-size: 19px; font-weight: 700; }
.clock .date { font-size: 11.5px; color: var(--muted); }
.slider { flex: 1; position: relative; padding-bottom: 16px; }
.track { position: absolute; left: 0; right: 0; top: 4px; height: 8px; background: #e6e7ea; overflow: hidden; pointer-events: none; }
.band { position: absolute; top: 0; bottom: 0; }
.band.night { background: #c9ccd1; }
.band.wx { background: var(--bad); opacity: 0.85; }
.slider input { position: relative; width: 100%; -webkit-appearance: none; appearance: none; height: 16px; margin: 0; background: transparent; }
.slider input::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 18px; border-radius: 2px; background: #fff; border: 2px solid var(--navy); cursor: grab; }
.slider input::-moz-range-thumb { width: 12px; height: 16px; border-radius: 2px; background: #fff; border: 2px solid var(--navy); cursor: grab; }
.ticks { position: absolute; left: 0; right: 0; bottom: -2px; height: 14px; }
.ticks span { position: absolute; transform: translateX(-50%); font-size: 11px; color: var(--faint); white-space: nowrap; }
:deep(.vmk-wrap) { background: none; border: 0; }
:deep(.vmk svg) { display: block; overflow: visible; }
:deep(.vmk .lbl) { position: absolute; left: 20px; top: 3px; white-space: nowrap; font-size: 10.5px; font-weight: 700; color: #1e2a3a; text-shadow: 0 0 2px #fff, 0 0 2px #fff, 0 0 3px #fff; pointer-events: none; }
:deep(.vmk .lbl em) { font-style: normal; color: var(--bad); }
:deep(.hide-lbl .vmk .lbl:not(.sel)) { display: none; }
:deep(.vmk .lbl.sel) { color: var(--accent); }
:deep(.base-tiles) { filter: saturate(0.55) brightness(1.03); }
:deep(.leaflet-bottom) { bottom: 66px; }
:deep(.leaflet-control-zoom) { border: 1px solid #cfd2d6 !important; border-radius: 2px !important; }
:deep(.leaflet-control-zoom a) { color: #333; border-radius: 0 !important; }
:deep(.map-tip) { font: inherit; font-size: 12px; line-height: 1.5; border-radius: 2px; border-color: var(--line-strong); }

:deep(.sk-wrap) { background: none; border: 0; }
:deep(.bmk) { position: absolute; transform: translate(-50%, -50%); background: #fff; border: 1px solid #666; font-size: 10px; font-weight: 700; padding: 0 3px; line-height: 13px; color: #333; white-space: nowrap; }
:deep(.bmk.busy) { border-color: #2c3746; background: #2c3746; color: #fff; }
:deep(.bmk.ctx) { border-color: #b3b6bb; color: #999; font-weight: 500; }
:deep(.anch-lbl) { background: none; border: 0; }
:deep(.anch-lbl span) { position: absolute; transform: translate(-50%, -50%); color: #7a5d00; font-size: 10.5px; white-space: nowrap; text-shadow: 0 0 3px #fff; }
</style>
