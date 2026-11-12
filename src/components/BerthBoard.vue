<script setup>
// 선석 작업현황판 — 부산항 정보조회서비스 '본선작업현황' 문법(선석별 열 · 진행률 배지 · 선박 그림 · 왼쪽 진한 머리칸).
// 팀 console 프로토타입(console/js/ui/board.js)을 우리 3개 부두와 지도 시각에 맞춰 옮겼다. 배지가 빨강이면 체선 예상.
import { computed } from 'vue'
import { tankerSVG } from '../lib/tanker.js'
import { fmt, money } from '../lib/time.js'

const props = defineProps({ sim: Object, scen: Object, t: Number })
const emit = defineEmits(['pick'])

const full = (m) => `2026/${fmt(m)}`
const vById = computed(() => Object.fromEntries(props.scen.vessels.map((v) => [v.id, v])))

const cols = computed(() =>
  [...props.scen.berths].sort((a, b) => a.name.localeCompare(b.name)).map((b) => {
    const ps = props.sim.placements.filter((p) => p.bid === b.id).sort((x, y) => x.etb - y.etb)
    const cur = ps.find((p) => p.etb <= props.t && props.t < p.etu) ?? null
    const upcoming = ps.filter((p) => p.etb > props.t)
    const legacy = !cur && b.occupiedUntil !== null && props.t < b.occupiedUntil
    const show = cur ?? upcoming[0] ?? null
    const v = show ? vById.value[show.vid] : null
    let badge = { cls: 'idle', text: show ? '예정' : '-' }
    if (cur) {
      const pct = Math.round(Math.min(1, Math.max(0, (props.t - cur.etb) / (cur.etu - cur.etb))) * 100)
      badge = { cls: cur.dem.cents > 0 ? 'bad' : 'ok', text: `${pct}%`, title: cur.dem.cents > 0 ? '체선 예상' : '작업 진행률' }
    } else if (legacy) badge = { cls: 'busy', text: '작업' }
    const nextLine = cur ? upcoming[0] : upcoming[1]
    return {
      b, cur, show, v, badge, legacy,
      pic: tankerSVG({ empty: !cur && !legacy }),
      code: cur ? `${v.callSign}-${v.voyage.slice(5)}` : legacy ? '기존 접안선' : show ? `다음 ${fmt(show.etb)}` : '배정 없음',
      next: nextLine ? { at: fmt(nextLine.etb).slice(0, 5), name: vById.value[nextLine.vid].name } : null,
    }
  }),
)
</script>

<template>
  <div class="board" :style="{ gridTemplateColumns: `110px repeat(${cols.length}, minmax(0, 1fr))` }">
    <div class="hcol">
      <div class="h3">선석</div><div>선박명</div><div>입항일시</div><div>접안일시</div><div>이안예정</div><div>화물</div><div>체선료(예상)</div><div>다음 접안</div>
    </div>
    <div v-for="c in cols" :key="c.b.id" :class="['bcol', { click: c.show }]" :title="c.v ? `${c.v.name} · ${c.b.name}` : c.b.name"
      @click="c.show && emit('pick', c.show.vid)">
      <div class="bh"><span class="nm">{{ c.b.name }}</span><span :class="['pct', c.badge.cls]" :title="c.badge.title">{{ c.badge.text }}</span></div>
      <div class="pic" v-html="c.pic" />
      <div class="code" :class="{ dim: !c.cur }">{{ c.code }}</div>
      <div><span class="vname">{{ c.legacy ? c.b.occupiedBy : c.v ? c.v.name : '-' }}</span></div>
      <div class="num">{{ c.show ? full(c.v.eta) : '-' }}</div>
      <div class="num" :class="{ etb: !c.cur && c.show }">{{ c.show ? full(c.show.etb) : '-' }}</div>
      <div class="num">{{ c.legacy ? full(c.b.occupiedUntil) : c.show ? full(c.show.etu) : '-' }}</div>
      <div class="split"><template v-if="c.v"><span>{{ c.v.product }}</span><span class="num">{{ c.v.ton.toLocaleString() }}t</span></template><span v-else>-</span></div>
      <div class="num" :class="{ bad: c.show && c.show.dem.cents > 0 }">{{ c.show ? money(c.show.dem.cents) : '-' }}</div>
      <div class="nx">{{ c.next ? '' : '-' }}<template v-if="c.next"><span class="muted">{{ c.next.at }}</span> {{ c.next.name }}</template></div>
    </div>
  </div>
</template>

<style scoped>
.board { display: grid; border: 1px solid var(--line-strong); background: #fff; font-size: 12.5px; }
.hcol, .bcol { display: grid; grid-template-rows: 42px 84px 26px repeat(7, 34px); }
.hcol { background: #3d4a5c; color: #fff; }
.hcol .h3 { grid-row: span 3; font-size: 14px; }
.hcol div { display: flex; align-items: center; padding: 0 18px; border-bottom: 1px solid rgba(255, 255, 255, 0.14); }
.bcol { border-left: 1px solid var(--line-strong); min-width: 0; }
.bcol > div { border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: center; text-align: center; padding: 0 6px; min-width: 0; }
.bcol.click { cursor: pointer; }
.bcol.click:hover > div:not(.pic):not(.code) { background: #fafbfc; }
.bh { justify-content: space-between !important; padding: 0 !important; font-weight: 700; font-size: 15px; color: #333; }
.bh .nm { padding-left: 14px; white-space: nowrap; }
.pct { align-self: stretch; display: grid; place-items: center; padding: 0 10px; color: #fff; font-size: 17px; font-weight: 800; min-width: 66px; }
.pct.ok { background: #2e9e3e; }
.pct.bad { background: var(--bad); }
.pct.busy { background: #3d4a5c; font-size: 13px; }
.pct.idle { background: #b7bbc1; font-size: 13px; }
/* 열이 넓어도 그림은 원래 비율(140×100)로 가운데 두고, 양옆은 같은 안벽·바다 색으로 잇는다. */
.pic { padding: 0 !important; display: flex !important; justify-content: center; background: linear-gradient(#c4cad2 0 13.4px, #8e96a1 13.4px 14.6px, #3a8edb 14.6px 52px, #2f80cc 52px); }
.pic :deep(svg) { display: block; height: 100%; width: auto; aspect-ratio: 140 / 100; }
.code { background: var(--accent); color: #fff; letter-spacing: 0.3px; }
.code.dim { background: #7b8796; }
.vname { font-weight: 700; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
.etb { color: var(--accent); font-weight: 700; }
.split { padding: 0 !important; }
.split span { flex: 1; align-self: stretch; display: grid; place-items: center; }
.split span + span { border-left: 1px solid var(--line); }
.bad { color: var(--bad); font-weight: 700; }
.nx { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block !important; line-height: 34px; font-size: 12px; }
</style>
