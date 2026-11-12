<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { ChevronLeft, ChevronRight, CircleAlert, Moon, Pause, Play, SkipBack } from 'lucide-vue-next'
import ViewHead from './ViewHead.vue'
import { risks, stateAt } from '../lib/engine.js'
import { MAP_CONTEXT } from '../lib/scenarios.js'
import { at, fmt, fmtDur, money } from '../lib/time.js'

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
const w = computed(() => props.scen.env.weather)
const weatherNow = computed(() => w.value && t.value >= w.value.start && t.value < w.value.end)
const isNight = computed(() => !props.scen.env.days.some((d) => t.value >= d.sunrise && t.value < d.sunset))
const openRisks = computed(() => risks(plan.value, props.scen).filter((r) => r.state !== '해당 없음'))
const berthOf = (bid) => props.scen.berths.find((b) => b.id === bid)
const anchorageFor = (v) => MAP_CONTEXT.anchorages.find((a) => v.dwt <= a.maxDwt)
const weekday = (min) => ['일', '월', '화', '수', '목', '금', '토'][(6 + Math.floor(min / 1440)) % 7]
const label = (s) => (s.id === 'FCFS' ? '도착순 기준안' : s.label)
const best = computed(() => props.result.candidates[0])
const kpis = computed(() => [
  { label: '대기 선박', value: `${props.scen.vessels.length}척`, sub: `부두 ${props.scen.berths.length}곳` },
  { label: '도착순 기준안', value: money(fcfs.value.total), sub: '비교용 · 현행 실적 아님' },
  { label: `${best.value.label} (최저)`, value: money(best.value.total), sub: `기준안 대비 ${(((best.value.total - fcfs.value.total) / fcfs.value.total) * 100).toFixed(1)}%`, good: true },
  { label: '확인할 리스크', value: `${risks(best.value, props.scen).filter((r) => r.state !== '해당 없음').length}건`, sub: best.value.label, bad: true },
  { label: '담당자 선택', value: props.current && props.current.version === props.version ? `${props.current.label} ${props.current.status}` : '선택 전' },
])

const PHASE = {
  coming: { text: '입항 예정', color: '#999999' },
  waiting: { text: '정박지 대기', color: '#e2a12a' },
  berthed: { text: '작업 중', color: '#1f4e9c' },
  left: { text: '출항', color: '#999999' },
}
const color = (s) => (s.ticking ? '#e02424' : PHASE[s.phase].color)
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

// ── 지도 ──
const mapEl = ref(null)
const selected = ref(null)
let map = null
let dyn = null

const shipSvg = (c, deg, sel) =>
  `<svg width="14" height="28" viewBox="-2 -2 18 32" style="transform:rotate(${deg}deg)"><path d="M7 0 L14 8 L14 28 L0 28 L0 8 Z" fill="${c}" stroke="${sel ? '#101828' : '#fff'}" stroke-width="${sel ? 2.4 : 1.4}"/></svg>`

function shipMarker(pos, c, deg, name, extra, sel, onClick) {
  const icon = L.divIcon({
    className: 'ship-mk',
    html: `${shipSvg(c, deg, sel)}<span class="ship-lbl${sel ? ' sel' : ''}">${name}${extra ? ` <em>${extra}</em>` : ''}</span>`,
    iconSize: [14, 28], iconAnchor: [7, 14],
  })
  const m = L.marker(pos, { icon, zIndexOffset: sel ? 1000 : 0 })
  if (onClick) m.on('click', onClick)
  return m
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
    const html = `<div class="sk-mk${busy ? ' busy' : ''}">${b.code}</div>`
    L.marker(b.pos, { icon: L.divIcon({ className: 'sk-wrap', html, iconSize: [0, 0] }), zIndexOffset: 500 })
      .bindTooltip(`<b>${b.name}</b> · ${b.maxDwt.toLocaleString()} DWT · 흘수 ${b.maxDraft}m<br>${b.products.join(', ')}<br><br><b>${label(plan.value)} 접안 순서</b><br>${queue.map((p) => `${fmt(p.etb)}  ${props.scen.vessels.find((v) => v.id === p.vid).name}`).join('<br>')}`, { direction: 'left', offset: [-16, 0], className: 'map-tip' })
      .addTo(dyn)
    if (legacy) shipMarker(b.moor, '#999999', 20, b.occupiedBy, '', false).addTo(dyn)
  }
  for (const s of states.value) {
    if (s.phase === 'coming' || s.phase === 'left') continue
    let pos
    let deg = 20
    if (s.phase === 'berthed') pos = berthOf(s.p.bid).moor
    else {
      const a = anchorageFor(s.v)
      const i = (anchorUse[a.id] = (anchorUse[a.id] ?? -1) + 1)
      pos = a.spots[i % a.spots.length]
      deg = 300
    }
    const sel = selected.value === s.v.id
    const extra = s.ticking ? money(s.cents).replace(/\.\d+$/, '') : ''
    shipMarker(pos, color(s), deg, s.v.name, extra, sel, () => { selected.value = s.v.id }).addTo(dyn)
  }
}

onMounted(() => {
  map = L.map(mapEl.value, { zoomControl: false, attributionControl: true, minZoom: 11, maxZoom: 16, zoomSnap: 0.5 })
  L.control.zoom({ position: 'bottomright' }).addTo(map)
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 16, attribution: 'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors',
  }).addTo(map)
  // SK 부두부터 E3 정박지까지 한 화면에 담는다.
  map.fitBounds([[35.402, 129.372], [35.505, 129.474]], { paddingTopLeft: [16, 16], paddingBottomRight: [16, 80] })
  for (const f of MAP_CONTEXT.facilities) {
    L.marker(f.pos, { icon: L.divIcon({ className: 'sk-wrap', html: `<div class="sk-mk ctx">${f.code}</div>`, iconSize: [0, 0] }) })
      .bindTooltip('계산 대상 아님', { className: 'map-tip' }).addTo(map)
  }
  for (const a of MAP_CONTEXT.anchorages) {
    L.circle(a.center, { radius: 900, color: '#667085', weight: 1, fillColor: '#667085', fillOpacity: 0.04, dashArray: '3 4' }).addTo(map)
    L.marker([a.center[0] + 0.0102, a.center[1]], { icon: L.divIcon({ className: 'anch-lbl', html: `<span>${a.label}</span>`, iconSize: [0, 0] }) }).addTo(map)
  }
  dyn = L.layerGroup().addTo(map)
  draw()
})
onBeforeUnmount(() => { map?.remove(); map = null })
watch([states, selected, () => props.scen], draw)

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
        <h2>선박 위치</h2>
        <span class="muted">{{ label(plan) }} · 기준 {{ fmt(t) }}</span>
        <div class="legend small">
          <span><i :style="{ background: PHASE.berthed.color }" />작업 중</span>
          <span><i :style="{ background: PHASE.waiting.color }" />정박지 대기</span>
          <span><i style="background:#e02424" />체선 발생</span>
          <span><i class="sk" />SK 부두</span>
        </div>
      </div>
      <div class="panel-body map-box">
        <div ref="mapEl" class="map" />
        <div v-if="isNight" class="night-tag small"><Moon :size="13" />야간 · 6만 DWT 이상 접안 불가</div>
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
          <div class="keys small">
            <span><i class="wx-key" />기상 악화</span>
            <span><i class="night-key" />야간</span>
          </div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>선박 현황</h2>
        <span class="muted">{{ label(plan) }} · {{ fmt(t) }} 기준 · 행 선택 시 지도 이동</span>
      </div>
      <div class="panel-body">
        <table class="grid vessel-list">
          <thead>
            <tr><th>선박명</th><th>화물</th><th>상태</th><th>위치·예정</th><th>도착(NOR)</th><th>접안(ETB)</th><th>작업 종료</th><th>누적 체선료(USD)</th><th>산출 근거</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in states" :key="s.v.id" :class="['clickable', { on: selected === s.v.id, faded: s.phase === 'coming' || s.phase === 'left' }]" @click="pick(s.v.id)">
              <td class="strong">{{ s.v.name }}</td>
              <td class="c">{{ s.v.product }} {{ s.v.dir }}</td>
              <td class="c"><span class="phase" :style="{ color: s.ticking ? 'var(--bad)' : PHASE[s.phase].text === '작업 중' ? 'var(--blue)' : s.phase === 'waiting' ? 'var(--warn)' : 'var(--muted)' }">{{ s.ticking ? '체선 발생' : PHASE[s.phase].text }}</span></td>
              <td class="small">{{ stateText(s) }}</td>
              <td class="c num">{{ fmt(s.v.eta) }}</td>
              <td class="c num">{{ fmt(s.p.etb) }}</td>
              <td class="c num">{{ fmt(s.p.etu) }}</td>
              <td class="r num" :class="{ bad: s.ticking, strong: s.cents > 0 }">{{ s.cents > 0 ? money(s.cents) : '0' }}</td>
              <td class="c"><button class="btn ghost" @click.stop="emit('open', plan.id, s.v.id)">보기</button></td>
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
.vessel-list tr.faded td { color: var(--faint); }
.vessel-list tr.faded td.strong { color: var(--muted); }
.phase { font-weight: 700; font-size: 12.5px; }

.legend { display: flex; gap: 14px; color: var(--muted); }
.legend span { display: inline-flex; align-items: center; gap: 5px; }
.legend i { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.legend i.sk { width: 14px; height: 9px; border-radius: 0; background: var(--navy); }

.map-box { position: relative; padding: 0; height: 560px; }
.map { position: absolute; inset: 0; background: #e8ecef; }
.night-tag { position: absolute; z-index: 900; top: 10px; right: 10px; display: inline-flex; align-items: center; gap: 6px; background: #fff; border: 1px solid var(--line-strong); padding: 4px 10px; color: #444; }

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
.keys { display: flex; gap: 12px; color: var(--muted); margin-right: 40px; white-space: nowrap; }
.keys span { display: inline-flex; align-items: center; gap: 5px; }
.wx-key, .night-key { display: inline-block; width: 12px; height: 8px; background: var(--bad); }
.night-key { background: #c9ccd1; }
:deep(.leaflet-bottom) { bottom: 66px; }
:deep(.leaflet-control-zoom) { border: 1px solid #cfd2d6 !important; border-radius: 2px !important; }
:deep(.leaflet-control-zoom a) { color: #333; border-radius: 0 !important; }
:deep(.map-tip) { font: inherit; font-size: 12px; line-height: 1.5; border-radius: 2px; border-color: var(--line-strong); }

:deep(.sk-wrap) { background: none; border: 0; }
:deep(.sk-mk) {
  position: absolute; transform: translate(-50%, -50%); background: #fff; color: var(--navy); border: 1.5px solid var(--navy);
  font-size: 11px; font-weight: 700; padding: 0 5px; line-height: 17px; white-space: nowrap;
}
:deep(.sk-mk.busy) { background: var(--navy); color: #fff; }
:deep(.sk-mk.ctx) { border-color: #c9ccd1; color: #999; font-weight: 500; }
:deep(.ship-mk) { background: none; border: 0; }
:deep(.ship-mk svg) { overflow: visible; display: block; filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.35)); }
:deep(.ship-lbl) {
  position: absolute; left: 16px; top: 5px; white-space: nowrap; background: rgba(255, 255, 255, 0.95); padding: 0 4px;
  font-size: 11px; font-weight: 700; color: var(--text); border: 1px solid var(--line-strong);
}
:deep(.ship-lbl em) { font-style: normal; color: var(--bad); margin-left: 2px; }
:deep(.ship-lbl.sel) { border-color: var(--accent); color: var(--accent); }
:deep(.anch-lbl) { background: none; border: 0; }
:deep(.anch-lbl span) { position: absolute; transform: translate(-50%, -50%); color: #555; font-size: 11.5px; font-weight: 700; white-space: nowrap; text-shadow: 0 0 3px #fff, 0 0 3px #fff; }
</style>
