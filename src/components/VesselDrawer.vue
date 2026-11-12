<script setup>
import { computed } from 'vue'
import { RULES } from '../lib/engine.js'
import { fmt, fmtDur, money } from '../lib/time.js'

const props = defineProps({ sim: Object, vid: String, scen: Object, fcfs: Object })
const emit = defineEmits(['close'])

const v = computed(() => props.scen.vessels.find((x) => x.id === props.vid))
const p = computed(() => props.sim.placements.find((x) => x.vid === props.vid))
const base = computed(() => props.fcfs.placements.find((x) => x.vid === props.vid))
const d = computed(() => p.value.dem)
const berth = computed(() => props.scen.berths.find((b) => b.id === p.value.bid))
const hours = (min) => fmtDur(min)

const steps = computed(() => {
  const x = d.value
  const c = v.value.contract
  return [
    {
      k: '정박시간 개시',
      f: x.turnMin > 0 ? `min(NOR ${fmt(v.value.eta)} + ${c.norTurnH}시간, 접안 ${fmt(x.etb)})` : `NOR ${fmt(v.value.eta)} 즉시`,
      val: fmt(x.ltStart), rule: x.ltStartRule,
    },
    { k: '정박시간 종료', f: '작업 종료(호스 분리)', val: fmt(x.etu), rule: 'LT-END-WORK' },
    { k: '사용 시간', f: `${fmt(x.etu)} − ${fmt(x.ltStart)}`, val: hours(x.usedMin) },
    {
      k: '기상 공제',
      f: x.wxOverlap ? `대기 중 기상 악화 ${hours(x.wxOverlap)} × ${x.clause.ratio * 100}%` : '정박시간 중 기상 악화로 기다린 시간 없음',
      val: x.wxDeduct ? `− ${hours(x.wxDeduct)}` : '0', rule: x.clause.rule,
    },
    { k: '산입 시간', f: '사용 시간 − 기상 공제', val: hours(x.countedMin) },
    { k: '허용 시간(Laytime)', f: `계약 ${c.id}`, val: hours(x.allowMin) },
    { k: '초과 시간', f: 'max(0, 산입 − 허용)', val: hours(x.excessMin), strong: true },
    {
      k: '예상 체선료',
      f: `${hours(x.excessMin)} ÷ 24시간 × ${money(x.rateCents)}/일`,
      val: money(x.cents), rule: 'DEM-PRORATA', strong: true,
    },
  ]
})
</script>

<template>
  <div class="scrim" @click.self="emit('close')">
    <aside class="drawer">
      <header class="d-head">
        <div>
          <p class="muted small">{{ sim.label }} · 체선료 산출 근거</p>
          <h2>{{ v.name }}</h2>
          <p class="small muted">{{ v.product }} {{ v.dir }} · {{ v.dwt.toLocaleString() }} DWT · 흘수 {{ v.draft }}m · {{ berth.name }}</p>
        </div>
        <button class="btn ghost" aria-label="닫기" @click="emit('close')">닫기 ✕</button>
      </header>

      <div class="d-body">
        <div class="hero">
          <div>
            <p class="muted small">예상 체선료</p>
            <p class="big num" :class="{ warn: d.cents > 0 }">{{ money(d.cents) }}</p>
          </div>
          <div>
            <p class="muted small">체선 시간</p>
            <p class="mid num">{{ hours(d.excessMin) }}</p>
          </div>
          <div v-if="sim.id !== 'FCFS'">
            <p class="muted small">기준안에서는</p>
            <p class="mid num">{{ money(base.dem.cents) }}</p>
          </div>
        </div>

        <h3>계산 과정</h3>
        <table class="grid steps">
          <tbody>
            <tr v-for="s in steps" :key="s.k" :class="{ em: s.strong }">
              <td class="k">{{ s.k }}</td>
              <td class="f small muted">{{ s.f }}<span v-if="s.rule" class="rule">{{ s.rule }}</span></td>
              <td class="v num">{{ s.val }}</td>
            </tr>
          </tbody>
        </table>

        <h3>접안 시각이 {{ fmt(p.etb) }}로 정해진 이유</h3>
        <ul class="why">
          <li>
            도착(NOR) <b class="num">{{ fmt(v.eta) }}</b>
            <template v-if="p.ready !== null">
              · {{ berth.name }} 앞 선박 <b>{{ p.prev }}</b> 작업 종료 + 전환 2시간 = <b class="num">{{ fmt(p.ready) }}</b>
            </template>
            → 이 중 늦은 <b class="num">{{ fmt(p.from) }}</b>부터 접안 가능 여부를 봐요.
          </li>
          <li v-for="b in p.blockers" :key="b.from">
            <span class="num">{{ fmt(b.from) }} ~ {{ fmt(b.to) }}</span> 접안 불가 · {{ RULES[b.rule].label }}
            <span class="rule">{{ b.rule }}</span>
          </li>
          <li v-if="!p.blockers.length">추가로 막는 제약이 없어 바로 접안해요.</li>
        </ul>

        <h3>계약 정보</h3>
        <dl class="kv small">
          <dt>계약</dt><dd>{{ v.contract.id }}</dd>
          <dt>허용 시간</dt><dd>{{ v.contract.laytimeH }}시간</dd>
          <dt>하루 체선료</dt><dd class="num">{{ money(v.contract.rateUsd * 100) }}</dd>
          <dt>정박시간 개시</dt><dd>{{ v.contract.norTurnH ? `NOR 후 ${v.contract.norTurnH}시간 또는 접안 중 빠른 때` : 'NOR 즉시' }}</dd>
          <dt>기상 조항</dt><dd>{{ d.clause.label }}</dd>
          <dt>작업 시간</dt><dd>{{ v.ton.toLocaleString() }}톤 ÷ {{ v.pump.toLocaleString() }}톤/시간 + 부대작업 2시간 = {{ hours(v.workMin) }}</dd>
        </dl>
        <p class="faint small note">계산 규칙은 계약 정보에서 읽어요. 같은 선박이라도 계약 조항이 다르면 결과가 달라져요.</p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.scrim { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.18); display: flex; justify-content: flex-end; z-index: 20; }
.drawer { width: 560px; height: 100%; background: var(--panel); box-shadow: -8px 0 24px rgba(15, 23, 42, 0.08); display: flex; flex-direction: column; }
.d-head { display: flex; justify-content: space-between; align-items: flex-start; padding: 18px 22px 14px; border-bottom: 1px solid var(--line); }
.d-head h2 { font-size: 20px; margin: 2px 0; }
.d-body { padding: 16px 22px 32px; overflow: auto; display: flex; flex-direction: column; gap: 12px; }
.d-body h3 { margin-top: 10px; }
.hero { display: flex; gap: 32px; padding: 12px 14px; background: #fafbfc; border: 1px solid var(--line); border-radius: var(--radius); }
.big { font-size: 26px; font-weight: 750; letter-spacing: -0.02em; }
.big.warn { color: var(--warn); }
.mid { font-size: 18px; font-weight: 650; margin-top: 4px; }
.steps td { padding: 7px 8px; }
.steps .k { width: 120px; font-weight: 600; white-space: nowrap; }
.steps .v { text-align: right; white-space: nowrap; font-weight: 600; }
.steps tr.em td { background: #fafbfc; }
.steps tr.em .v { color: var(--text); font-weight: 750; }
.rule { display: inline-block; margin-left: 6px; font-size: 10.5px; font-weight: 600; color: var(--accent); background: var(--accent-weak); border-radius: 4px; padding: 0 5px; vertical-align: 1px; }
.why { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; }
.kv { display: grid; grid-template-columns: 100px 1fr; gap: 6px 12px; margin: 0; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; }
.note { margin-top: 4px; }
</style>
