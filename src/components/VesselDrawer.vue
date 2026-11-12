<script setup>
// 선박 카드 — 울산항만공사 PortWise 선박 카드 구성(위치·신고 두 칸, 기준 시각, 제원 그림, 정보 표,
// 출발지 → 목적지, Status · Speed · Course, 아래 버튼)을 팀 console 프로토타입(console/js/ui/vessel.js)대로 옮겼다.
// 아래 버튼은 '체선료 산출 근거'로 바뀌고, 근거 화면에서 다시 선박 정보로 돌아올 수 있다.
import { computed, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, Star, X } from 'lucide-vue-next'
import { RULES, compatibleBerths, stateAt } from '../lib/engine.js'
import { NAV, anchorageFor, positionOf } from '../lib/vesselState.js'
import { fmt, fmtDur, money } from '../lib/time.js'
import { PERMS, ws } from '../lib/workspace.js'

const props = defineProps({
  sim: Object, vid: String, scen: Object, fcfs: Object,
  at: { type: Number, default: null }, // 지도에서 열면 그 시각, 다른 화면에서는 계획 기준
  mode: { type: String, default: 'card' },
})
// 계약 단가는 권한 표의 '계약 단가 · 체선료 금액 조회' 역할만 본다(HN-095). 나머지는 '비공개'.
const rateOk = computed(() => PERMS.find((p) => p.act.startsWith('계약 단가')).roles.includes(ws.roleId))
const rate = (cents) => (rateOk.value ? money(cents) : '비공개')
const emit = defineEmits(['close'])

const view = ref(props.mode)
watch(() => [props.vid, props.mode], () => { view.value = props.mode })

const v = computed(() => props.scen.vessels.find((x) => x.id === props.vid))
const p = computed(() => props.sim.placements.find((x) => x.vid === props.vid))
const base = computed(() => props.fcfs.placements.find((x) => x.vid === props.vid))
const d = computed(() => p.value.dem)
const berth = computed(() => props.scen.berths.find((b) => b.id === p.value.bid))
const berthName = (id) => props.scen.berths.find((b) => b.id === id)?.name ?? id
const hours = (min) => fmtDur(min)
const yy = (min) => `26-${fmt(min).replace('/', '-')}`

// 지도 시각 기준 상태. 지도 밖에서 열면 계획(ETB 직후) 기준으로 보여 준다.
const live = computed(() => props.at !== null)
const t = computed(() => props.at ?? p.value.etb)
const state = computed(() => {
  const all = stateAt(props.sim, props.scen, t.value).sort((a, b) => a.v.eta - b.v.eta)
  const me = all.find((s) => s.v.id === props.vid)
  const sameAnch = all.filter((s) => s.phase === 'waiting' && anchorageFor(s.v).id === anchorageFor(me.v).id)
  return { ...me, spot: Math.max(0, sameAnch.findIndex((s) => s.v.id === props.vid)) }
})
const nav = computed(() => NAV[state.value.phase])
const pos = computed(() => positionOf(state.value, props.scen, state.value.spot))
const where = computed(() => {
  const s = state.value
  if (s.phase === 'coming') return '입항 전 (항해)'
  if (s.phase === 'waiting') return `${anchorageFor(s.v).label} 대기`
  if (s.phase === 'berthed') return `${berth.value.name} 계류`
  return '출항'
})
const use = computed(() => {
  const s = state.value
  if (s.phase === 'berthed') return `${berth.value.name} 사용 중 (${fmt(p.value.etb)} ~)`
  if (s.phase === 'left') return `${berth.value.name} 사용 끝 (${fmt(p.value.etu)} 작업 종료)`
  return '-'
})

const steps = computed(() => {
  const x = d.value
  const c = v.value.contract
  return [
    { rule: 'ETA', k: '도착 (NOR)', f: `NOR 제출 ${fmt(v.value.eta)}`, val: fmt(v.value.eta) },
    { rule: p.value.binding, k: '접안 (ETB)', f: p.value.blockers.length ? `${p.value.blockers.map((b) => RULES[b.rule].label).join(' · ')} → ${fmt(x.etb)} 접안` : `제약 없음 → ${fmt(x.etb)} 접안`, val: fmt(x.etb) },
    { rule: x.ltStartRule, k: '정박개시', f: x.turnMin > 0 ? `min(NOR + ${c.norTurnH}시간, 접안)` : 'NOR 제출 즉시', val: fmt(x.ltStart) },
    { rule: 'LT-END-WORK', k: '정박종료', f: '작업 종료(호스 분리)', val: fmt(x.etu) },
    { rule: x.clause.rule, k: '기상 공제', f: x.wxOverlap ? `대기 중 기상 악화 ${hours(x.wxOverlap)} × ${x.clause.ratio * 100}%` : '정박시간 중 기상 대기 없음', val: x.wxDeduct ? `− ${hours(x.wxDeduct)}` : '0' },
    { rule: '-', k: '산입 시간', f: `사용 ${hours(x.usedMin)} − 공제`, val: hours(x.countedMin) },
    { rule: '-', k: '체선 시간', f: `산입 − 허용 ${hours(x.allowMin)} (0 미만은 0)`, val: hours(x.excessMin) },
    { rule: 'DEM-PRORATA', k: '체선료', f: `${hours(x.excessMin)} ÷ 24시간 × ${rate(x.rateCents)}/일`, val: money(x.cents), strong: true },
  ]
})

// 시간 흐름 막대: 점선 대기 · 파랑 작업 · 초록 허용 정박시간 · 빨강 체선
const flow = computed(() => {
  const x = d.value
  const allowEnd = x.ltStart + x.allowMin + x.wxDeduct
  const t0 = Math.min(v.value.eta, x.ltStart) - 120
  const t1 = Math.max(x.etu, allowEnd) + 120
  const X = (m) => `${(2 + ((m - t0) / (t1 - t0)) * 96).toFixed(2)}%`
  const W = (a, b) => `${Math.max(0.4, ((b - a) / (t1 - t0)) * 96).toFixed(2)}%`
  return { X, W, allowEnd: Math.min(allowEnd, x.etu), demFrom: allowEnd, x }
})
</script>

<template>
  <div class="scrim" @click.self="emit('close')">
    <aside :class="['drawer', { wide: view === 'evidence' }]" role="dialog" :aria-label="`${v.name} 선박 정보`">
      <header class="dh">
        <Star class="star" :size="16" />
        <h2>{{ v.name }}<template v-if="view === 'evidence'"> — 체선료 산출 근거</template></h2>
        <button class="x" aria-label="닫기" @click="emit('close')"><X :size="16" /></button>
      </header>

      <div v-if="view === 'card'" class="db">
        <div class="vc-two">
          <div>{{ live ? '현재 위치' : '계획 위치' }}<b>위치 : {{ where }}</b>ETA : {{ yy(v.eta) }}</div>
          <div>접안 계획 · {{ sim.label }}<b>{{ berth.name }} 접안</b>ETB : {{ yy(p.etb) }}</div>
        </div>
        <div class="vc-upd">{{ live ? '기준 시각' : '계획 기준' }} : 2026-{{ fmt(t).replace('/', '-') }}{{ live ? '' : ' (접안 시점)' }}</div>
        <div class="vc-ship">
          <span class="d" style="left:14px;top:12px">톤수 {{ v.grt.toLocaleString() }}t</span><span class="d" style="right:14px;top:12px">흘수 {{ v.draft }}m</span>
          <span class="d" style="left:14px;top:36px">길이 {{ v.loa }}m</span><span class="d" style="right:14px;top:36px">폭 {{ v.beam }}m</span>
          <svg viewBox="0 0 400 70" height="70" preserveAspectRatio="none" aria-hidden="true">
            <rect y="44" width="400" height="26" fill="#5b8fd1" />
            <path d="M70 30 H318 Q338 33 346 44 Q338 56 318 58 H86 Q72 52 70 44 Z" :fill="nav.color" />
            <path d="M74 44 H344 Q338 56 318 58 H86 Q76 53 74 44 Z" fill="#000" opacity=".22" />
            <rect x="84" y="14" width="36" height="16" fill="#f2f3f5" /><rect x="88" y="18" width="28" height="3" fill="#30486c" /><rect x="92" y="6" width="10" height="8" fill="#d6202f" />
            <rect x="130" y="27" width="170" height="3" fill="#d9c27a" />
          </svg>
        </div>
        <div class="vc-act">
          <span v-if="state.ticking" class="bad b">체선 발생 중 · 누적 {{ money(state.cents) }}</span>
          <span v-else-if="d.cents > 0" class="warn">예상 체선 {{ hours(d.excessMin) }} · {{ money(d.cents) }}</span>
          <span v-else class="muted">허용 정박시간 안에 작업 종료 예정</span>
          <button class="btn sm" @click="view = 'evidence'">체선료 산출 근거</button>
        </div>
        <table class="kv">
          <tbody>
            <tr><th>국적</th><td>{{ v.flag }}</td></tr>
            <tr><th>선박명</th><td>{{ v.name }} <span class="muted">(가상 선명)</span></td></tr>
            <tr><th>MMSI</th><td class="num">{{ v.mmsi }}</td></tr>
            <tr><th>IMO · 호출부호</th><td class="num">{{ v.imo }} · {{ v.callSign }}</td></tr>
            <tr><th>선박 타입</th><td>{{ v.type }}</td></tr>
            <tr><th>선박 위치</th><td class="num">{{ pos[0].toFixed(5) }}, {{ pos[1].toFixed(5) }}</td></tr>
            <tr><th>DWT · 흘수</th><td class="num">{{ v.dwt.toLocaleString() }} t · {{ v.draft }} m</td></tr>
            <tr><th>화물</th><td>{{ v.dir }} · {{ v.product }} · {{ v.ton.toLocaleString() }} t</td></tr>
            <tr><th>계약</th><td>{{ v.contract.id }} · 허용 {{ v.contract.laytimeH }}h · 일 {{ rate(v.contract.rateUsd * 100) }}</td></tr>
            <tr><th>시설 신청</th><td>{{ compatibleBerths(v, scen).map(berthName).join(', ') }} <span class="muted">(접안 가능 · 항차 {{ v.voyage }})</span></td></tr>
            <tr><th>시설 사용</th><td>{{ use }}</td></tr>
            <tr>
              <th>접안 계획</th>
              <td>{{ berth.name }} · ETB {{ fmt(p.etb) }} → ETU {{ fmt(p.etu) }}<br>
                <span class="muted">{{ sim.label }}{{ p.waitMin > 0 ? ` · 접안 전 대기 ${hours(p.waitMin)}` : '' }}</span></td>
            </tr>
            <tr>
              <th>예상 체선료</th>
              <td><b :class="d.cents > 0 ? 'bad' : 'ok'">{{ money(d.cents) }}</b>
                <span class="muted">(체선 {{ hours(d.excessMin) }} · 일 {{ rate(v.contract.rateUsd * 100) }})</span>
                <template v-if="sim.id !== 'FCFS'"><br><span class="muted">도착순 기준안 {{ money(base.dem.cents) }}</span></template></td>
            </tr>
          </tbody>
        </table>
        <div class="vc-route">
          <div>출발지<b>{{ v.prevPort }}</b></div>
          <ArrowRight class="arr" :size="22" />
          <div class="rt">목적지<b>ULSAN, KOREA</b></div>
        </div>
        <div class="vc-three">
          <div>Status<b>{{ live ? nav.status : '-' }}</b></div>
          <div>Speed<b>{{ live ? `${nav.sog.toFixed(1)}kn` : '-' }}</b></div>
          <div>Course<b>{{ live ? `${nav.cog}°` : '-' }}</b></div>
        </div>
        <button class="vc-btn" @click="view = 'evidence'">체선료 산출 근거 보기</button>
      </div>

      <div v-else class="db">
        <button class="btn sm back" @click="view = 'card'"><ArrowLeft :size="13" />선박 정보</button>
        <table class="kv">
          <tbody>
            <tr><th>계획</th><td>{{ sim.label }}</td></tr>
            <tr><th>부두 · 접안</th><td>{{ berth.name }} · ETB {{ fmt(p.etb) }} → ETU {{ fmt(p.etu) }}</td></tr>
            <tr><th>정박 시간</th><td>{{ fmt(d.ltStart) }} ~ {{ fmt(d.etu) }} (허용 {{ v.contract.laytimeH }}h)</td></tr>
            <tr><th>체선</th><td><b :class="d.cents > 0 ? 'bad' : 'ok'">{{ hours(d.excessMin) }} · {{ money(d.cents) }}</b></td></tr>
          </tbody>
        </table>

        <div class="vc-sec">시간 흐름 <small>점선 대기 · 파랑 작업 · 초록 허용 정박시간 · 빨강 체선</small></div>
        <div class="tl">
          <div class="ax" />
          <div v-if="v.eta < d.etb" class="sg wait" :style="{ left: flow.X(v.eta), width: flow.W(v.eta, d.etb) }" />
          <div class="sg work" :style="{ left: flow.X(d.etb), width: flow.W(d.etb, d.etu) }" />
          <div class="sg lay" :style="{ left: flow.X(d.ltStart), width: flow.W(d.ltStart, flow.allowEnd) }" />
          <div v-if="d.excessMin > 0" class="sg dem" :style="{ left: flow.X(flow.demFrom), width: flow.W(flow.demFrom, d.etu) }" />
          <span class="tk" :style="{ left: flow.X(v.eta) }">ETA {{ fmt(v.eta).slice(6) }}</span>
          <span class="tk" :style="{ left: flow.X(d.etu) }">작업 종료 {{ fmt(d.etu).slice(6) }}</span>
          <span class="tk b" :style="{ left: flow.X(d.ltStart) }">정박개시</span>
        </div>

        <div class="vc-sec">산출 순서 <small>규칙 ID = 규칙 표 번호</small></div>
        <table class="calc">
          <thead><tr><th style="width:34px">No</th><th style="width:96px">규칙</th><th style="width:84px">항목</th><th>내용</th><th style="width:96px">값</th></tr></thead>
          <tbody>
            <tr v-for="(s, i) in steps" :key="s.k" :class="{ em: s.strong }">
              <td class="c">{{ i + 1 }}</td>
              <td class="rid">{{ s.rule }}</td>
              <td class="it">{{ s.k }}</td>
              <td>{{ s.f }}</td>
              <td class="r num">{{ s.val }}</td>
            </tr>
          </tbody>
        </table>
        <div class="formula">
          체선료 = 체선 시간 {{ hours(d.excessMin) }} × 일 체선료 {{ rate(d.rateCents) }} ÷ 24<br>
          <span class="res" :class="d.cents > 0 ? 'bad' : 'ok'">= {{ money(d.cents) }}</span>
          <span class="muted"> (선박별 센트 단위 한 번 반올림 · HALF_UP)</span>
        </div>

        <div class="vc-sec">접안 시각 결정</div>
        <ul class="why">
          <li>
            도착(NOR) <b class="num">{{ fmt(v.eta) }}</b>
            <template v-if="p.ready !== null"> · {{ berth.name }} 앞 선박 <b>{{ p.prev }}</b> 작업 종료 + 전환 2시간 = <b class="num">{{ fmt(p.ready) }}</b></template>
            → 둘 중 늦은 <b class="num">{{ fmt(p.from) }}</b>부터 접안 가능 여부 판정
          </li>
          <li v-for="b in p.blockers" :key="b.from">
            <span class="num">{{ fmt(b.from) }} ~ {{ fmt(b.to) }}</span> 접안 불가 · {{ RULES[b.rule].label }} <span class="rule">{{ b.rule }}</span>
          </li>
          <li v-if="!p.blockers.length">추가 제약 없음 · 즉시 접안</li>
        </ul>

        <table class="kv">
          <tbody>
            <tr><th>Laytime</th><td>{{ v.contract.laytimeH }}h <span class="muted">(계약 {{ v.contract.id }})</span></td></tr>
            <tr><th>정박시간 개시</th><td>{{ v.contract.norTurnH ? `NOR 후 ${v.contract.norTurnH}시간 또는 접안 중 빠른 때` : 'NOR 즉시' }}</td></tr>
            <tr><th>기상 조항</th><td>{{ d.clause.label }}</td></tr>
            <tr><th>작업 시간</th><td>{{ v.ton.toLocaleString() }}톤 ÷ {{ v.pump.toLocaleString() }}톤/시간 + 부대작업 2시간 = {{ hours(v.workMin) }}</td></tr>
            <tr><th>계산 기준</th><td>규칙 엔진 · LLM 사용 안 함</td></tr>
          </tbody>
        </table>
      </div>

      <footer class="df">출처: 시나리오 입력 · 계약 정보 · 규칙 엔진 계산 — 선박명·제원·계약값은 가상입니다.</footer>
    </aside>
  </div>
</template>

<style scoped>
.scrim { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.12); display: flex; justify-content: flex-end; z-index: 2000; }
.drawer { width: 440px; height: 100%; background: #fff; box-shadow: -4px 0 18px rgba(0, 0, 0, 0.16); display: flex; flex-direction: column; }
.drawer.wide { width: 600px; }
.dh { display: flex; align-items: center; gap: 8px; padding: 14px 16px; border-bottom: 2px solid #3d4a5c; }
.star { color: #b9bdc3; flex: none; }
.dh h2 { margin: 0; font-size: 17px; color: var(--accent); font-weight: 800; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.x { width: 30px; height: 30px; border-radius: 50%; border: 1px solid #b9bdc3; background: #fff; color: #555; display: grid; place-items: center; flex: none; }
.db { flex: 1; overflow-y: auto; padding: 12px 16px 20px; }
.df { border-top: 1px solid var(--line); padding: 10px 16px; font-size: 11.5px; color: #888; line-height: 1.5; }

.vc-two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px; }
.vc-two > div { border: 1px solid #b5d6d8; border-top: 2px solid var(--accent); border-radius: 0 0 6px 6px; padding: 9px 11px; font-size: 12px; color: #555; }
.vc-two b { display: block; color: var(--accent); font-size: 14px; margin: 3px 0; }
.vc-upd { text-align: right; font-size: 12px; font-weight: 700; color: #333; margin: 2px 0 6px; }
.vc-ship { background: #1f2b4f; color: #fff; border-radius: 4px 4px 0 0; position: relative; height: 128px; overflow: hidden; }
.vc-ship .d { position: absolute; font-size: 12.5px; font-weight: 700; }
.vc-ship svg { position: absolute; left: 0; right: 0; bottom: 0; width: 100%; }
.vc-act { display: flex; justify-content: space-between; align-items: center; gap: 8px; border: 1px solid #c9d3df; border-top: 0; padding: 6px 8px; margin-bottom: 10px; font-size: 12px; }
.btn.sm { height: 24px; padding: 0 8px; font-size: 11.5px; }
.vc-route { display: flex; justify-content: space-between; align-items: center; border: 1px solid #b5d6d8; border-radius: 6px; padding: 9px 12px; margin: 10px 0 8px; font-size: 12px; color: #555; }
.vc-route b { display: block; color: #222; font-size: 13px; }
.vc-route .rt { text-align: right; }
.vc-route .arr { color: #23a3a8; }
.vc-three { display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid #b5d6d8; border-radius: 6px; padding: 9px 0; margin-bottom: 12px; text-align: center; font-size: 12px; color: #555; }
.vc-three > div + div { border-left: 1px solid #d3e7e8; }
.vc-three b { display: block; color: #222; font-size: 13.5px; margin-top: 4px; }
.vc-btn { width: 100%; height: 40px; border: 0; border-radius: 4px; background: var(--accent); color: #fff; font-size: 14px; font-weight: 700; }
.vc-btn:hover { background: var(--accent-hover); }
.vc-sec { font-size: 13px; font-weight: 700; color: #222; margin: 16px 0 6px; display: flex; justify-content: space-between; align-items: baseline; }
.vc-sec small { font-weight: 400; color: #999; font-size: 11px; }
.back { margin-bottom: 10px; }

.kv { width: 100%; border-collapse: collapse; background: #fff; border-top: 2px solid #5b6575; font-size: 12.5px; }
.kv th { width: 120px; background: var(--sunken); color: #2b3445; font-weight: 700; text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); border-right: 1px solid var(--line); vertical-align: top; }
.kv td { padding: 9px 12px; border-bottom: 1px solid var(--line); line-height: 1.5; }
.calc { width: 100%; border-collapse: collapse; font-size: 12px; border-top: 2px solid #5b6575; }
.calc th { background: #eef0f3; color: #2b3445; font-weight: 600; padding: 6px; border: 1px solid var(--line); }
.calc td { border: 1px solid var(--line); padding: 6px 7px; vertical-align: top; line-height: 1.5; }
.calc td.c { text-align: center; }
.calc td.r { text-align: right; white-space: nowrap; }
.calc td.rid { text-align: center; font-weight: 700; color: #5b3c99; white-space: nowrap; font-size: 11px; }
.calc td.it { white-space: nowrap; font-weight: 600; }
.calc tr.em td { background: #fafbfc; font-weight: 700; }
.formula { border: 1px solid var(--line-strong); background: #fafbfc; padding: 10px 12px; margin: 10px 0; font-size: 12.5px; line-height: 1.7; }
.formula .res { font-size: 17px; font-weight: 800; }
.tl { position: relative; height: 62px; margin: 6px 0 4px; border: 1px solid var(--line); background: #fff; }
.tl .ax { position: absolute; left: 8px; right: 8px; top: 30px; height: 1px; background: #c9ccd1; }
.tl .sg { position: absolute; height: 10px; top: 25px; }
.tl .sg.wait { height: 0; border-top: 1px dotted #777; top: 30px; }
.tl .sg.work { background: #3a6db3; }
.tl .sg.lay { top: 40px; height: 6px; background: #cde6d3; }
.tl .sg.dem { top: 40px; height: 6px; background: var(--bad); }
.tl .tk { position: absolute; top: 6px; font-size: 10px; color: #555; transform: translateX(-50%); white-space: nowrap; }
.tl .tk.b { top: 47px; }
.why { margin: 0 0 12px; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; }
.rule { display: inline-block; margin-left: 4px; font-size: 10.5px; color: #5b3c99; border: 1px solid #c9b8e8; padding: 0 4px; }
.ok { color: #2e9e3e; }
.bad { color: var(--bad); }
.warn { color: var(--warn); font-weight: 700; }
.b { font-weight: 700; }
</style>
