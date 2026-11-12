<script setup>
import { computed } from 'vue'
import { fmt, moneyShort } from '../lib/time.js'

const props = defineProps({
  sim: Object,
  scen: Object,
  range: Object,
  changed: { type: Array, default: () => [] },
  compact: Boolean,
  axis: { type: Boolean, default: true },
  activeVid: String,
})
const emit = defineEmits(['pick'])

const span = computed(() => props.range.end - props.range.start)
const pct = (t) => `${((Math.min(Math.max(t, props.range.start), props.range.end) - props.range.start) / span.value) * 100}%`
const width = (a, b) => `${((Math.min(b, props.range.end) - Math.max(a, props.range.start)) / span.value) * 100}%`

const vessel = computed(() => Object.fromEntries(props.scen.vessels.map((v) => [v.id, v])))

const ticks = computed(() => {
  const out = []
  for (let t = Math.ceil(props.range.start / 360) * 360; t <= props.range.end; t += 360) {
    const h = ((t % 1440) + 1440) % 1440 / 60
    out.push({ t, day: h === 0, label: h === 0 ? fmt(t).slice(0, 5) : `${String(h).padStart(2, '0')}시` })
  }
  return out
})

const nights = computed(() => {
  const d = props.scen.env.days
  const out = []
  for (let i = 0; i < d.length - 1; i++) out.push({ start: d[i].sunset, end: d[i + 1].sunrise })
  return out.filter((n) => n.end > props.range.start && n.start < props.range.end)
})

const rows = computed(() =>
  props.scen.berths.map((b) => ({
    berth: b,
    bars: props.sim.placements.filter((p) => p.bid === b.id),
  })),
)
</script>

<template>
  <div :class="['tl', { compact }]">
    <div v-if="axis" class="axis">
      <div class="label-col" />
      <div class="track">
        <span v-for="k in ticks" :key="k.t" :class="['tick', { day: k.day }]" :style="{ left: pct(k.t) }">{{ k.label }}</span>
      </div>
    </div>
    <div v-for="r in rows" :key="r.berth.id" class="lane">
      <div class="label-col">
        <span class="strong">{{ r.berth.name }}</span>
        <span v-if="!compact" class="faint small">{{ (r.berth.maxDwt / 1000).toFixed(0) }}k DWT</span>
      </div>
      <div class="track">
        <div v-for="n in nights" :key="n.start" class="band night" :style="{ left: pct(n.start), width: width(n.start, n.end) }" />
        <div v-if="scen.env.weather" class="band weather" :style="{ left: pct(scen.env.weather.start), width: width(scen.env.weather.start, scen.env.weather.end) }" />
        <div v-if="r.berth.facility.maintenance" class="band maint"
          :style="{ left: pct(r.berth.facility.maintenance.start), width: width(r.berth.facility.maintenance.start, r.berth.facility.maintenance.end) }"
          :title="r.berth.facility.maintenance.label" />
        <template v-if="r.berth.tideLimited">
          <span v-for="h in scen.env.highTides" :key="h" class="tide" :style="{ left: pct(h) }" :title="`만조 ${fmt(h)}`" />
        </template>
        <div v-if="r.berth.occupiedUntil" class="bar occupied" :style="{ left: pct(range.start), width: width(range.start, r.berth.occupiedUntil) }">
          <span class="bar-name">{{ r.berth.occupiedBy }}</span>
        </div>
        <template v-for="p in r.bars" :key="p.vid">
          <div v-if="p.etb > vessel[p.vid].eta" class="wait" :style="{ left: pct(vessel[p.vid].eta), width: width(vessel[p.vid].eta, p.etb) }"
            :title="`${vessel[p.vid].name} 대기 ${fmt(vessel[p.vid].eta)} → ${fmt(p.etb)}`" />
          <button
            :class="['bar', { dem: p.dem.cents > 0, changed: changed.includes(p.vid), active: activeVid === p.vid }]"
            :style="{ left: pct(p.etb), width: width(p.etb, p.etu) }"
            :title="`${vessel[p.vid].name} ${fmt(p.etb)} ~ ${fmt(p.etu)}`"
            @click="emit('pick', p.vid)">
            <span class="bar-name">{{ vessel[p.vid].name }}</span>
            <span v-if="p.dem.cents > 0" class="bar-dem num">{{ moneyShort(p.dem.cents) }}</span>
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tl { --lane: 40px; --label: 92px; user-select: none; }
.tl.compact { --lane: 30px; --label: 64px; }
.axis, .lane { display: flex; }
.label-col { width: var(--label); flex: none; display: flex; flex-direction: column; justify-content: center; padding-right: 8px; line-height: 1.2; }
.compact .label-col { font-size: 12px; }
.track { position: relative; flex: 1; }
.axis .track { height: 20px; border-bottom: 1px solid var(--line); }
.tick { position: absolute; bottom: 3px; transform: translateX(-50%); font-size: 11px; color: var(--faint); white-space: nowrap; }
.tick.day { color: var(--text); font-weight: 650; }
.tick::after { content: ''; position: absolute; left: 50%; top: 100%; height: 4px; border-left: 1px solid var(--line-strong); }
.lane .track { height: var(--lane); border-bottom: 1px solid var(--line); }
.band { position: absolute; top: 0; bottom: 0; }
.band.night { background: var(--night); }
.band.weather { background: repeating-linear-gradient(135deg, rgba(179, 38, 30, 0.10) 0 6px, rgba(179, 38, 30, 0.03) 6px 12px); border-left: 1px dashed rgba(179, 38, 30, 0.5); border-right: 1px dashed rgba(179, 38, 30, 0.5); }
.band.maint { background: repeating-linear-gradient(45deg, rgba(90, 79, 160, 0.16) 0 4px, transparent 4px 8px); }
.tide { position: absolute; top: 0; width: 0; height: 0; transform: translateX(-5px); border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #2f7fb0; }
.wait { position: absolute; bottom: 4px; height: 0; border-top: 2px dotted var(--faint); }
.bar {
  position: absolute; top: 5px; bottom: 9px; border-radius: 4px; border: 1px solid #8fb7c7;
  background: var(--accent-weak); color: var(--accent); padding: 0 6px; overflow: hidden;
  display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 650; text-align: left; white-space: nowrap;
}
.compact .bar { top: 4px; bottom: 7px; font-size: 11px; }
.bar:hover { filter: brightness(0.97); }
.bar.dem { background: var(--warn-weak); border-color: #e2b26f; color: var(--warn); }
.bar.changed { border-width: 2px; border-style: solid; }
.bar.active { outline: 2px solid var(--text); outline-offset: 1px; }
.bar.occupied { background: #e9ebef; border-color: #d0d4da; color: var(--muted); cursor: default; }
.bar-name { overflow: hidden; text-overflow: ellipsis; }
.bar-dem { font-weight: 700; }
</style>
