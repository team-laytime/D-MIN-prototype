<script setup>
// 실시간 선박 카드 — 울산항만공사 '항내 선박위치정보'(공공데이터포털)가 주는 값만 보여 준다.
// 이 API에는 목적지 · ETA · 길이 · 폭 · DWT가 없다. 없는 값은 없다고 적고, 어디서 받을지 안내한다.
import { computed, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { fetchArrivals, fetchVoyage, flagOf } from '../lib/liveAis.js'

const props = defineProps({ vessel: Object, fetchedAt: String })
const emit = defineEmits(['close'])
const v = computed(() => props.vessel)
const kst = (iso) => (iso ? iso.slice(0, 19).replace('T', ' ') : '-')
const age = computed(() => (v.value.ageMin == null ? '-' : v.value.ageMin < 1 ? '1분 미만 전' : `${Math.round(v.value.ageMin)}분 전`))
// 이번 항차의 입항·투묘·접안·이안·출항 기록. 호출부호·입항연도가 없는 선박은 조회할 수 없다.
const voy = ref({ state: 'idle', events: [], err: '' })
watch(() => v.value.mmsi, async () => {
  const x = v.value
  if (!x.callSign || !x.callYear) { voy.value = { state: 'none', events: [], err: '' }; return }
  voy.value = { state: 'load', events: [], err: '' }
  try {
    const d = await fetchVoyage(x)
    voy.value = { state: 'ok', events: d.events, err: '', voyages: d.voyages }
  } catch (e) { voy.value = { state: 'err', events: [], err: String(e.message ?? e) } }
}, { immediate: true })
// 입항 신고(ETA): 호출부호로 찾고, 위치 API의 항차와 같은 입항횟수가 있으면 그것, 없으면 가장 늦은 입항 신고.
const eta = ref({ state: 'idle', a: null, err: '' })
watch(() => v.value.mmsi, async () => {
  const x = v.value
  if (!x.callSign) { eta.value = { state: 'none', a: null, err: '' }; return }
  eta.value = { state: 'load', a: null, err: '' }
  try {
    const d = await fetchArrivals({ callsgn: x.callSign })
    const list = d.arrivals.filter((r) => !x.callYear || r.year === x.callYear)
    // 같은 호출부호에 입항 신고가 여러 건(지난 입항 + 다음 입항)이면, 위치 API와 입항횟수가 같은 건 → 없으면 지금 시각에 가장 가까운 건.
    const near = (r) => Math.abs(new Date(r.eta) - Date.now())
    const a = list.find((r) => r.count === x.voyage) ?? [...list].sort((p, q) => near(p) - near(q))[0] ?? null
    eta.value = { state: a ? 'ok' : 'empty', a, err: '' }
  } catch (e) { eta.value = { state: 'err', a: null, err: String(e.message ?? e) } }
}, { immediate: true })
const dest = computed(() => eta.value.a?.nextPort ?? eta.value.a?.destPort ?? null)
const hm = (iso) => (iso ? `${iso.slice(5, 10).replace('-', '/')} ${iso.slice(11, 16)}` : '-')
const val = (x, unit = '') => (x == null ? '-' : `${x}${unit}`)
</script>

<template>
  <div class="scrim" @click.self="emit('close')">
    <aside class="drawer" role="dialog" :aria-label="`${v.name} 실시간 선박 정보`">
      <header class="dh">
        <h2>{{ v.name || v.mmsi }} <span class="live">LIVE</span></h2>
        <button class="x" aria-label="닫기" @click="emit('close')"><X :size="16" /></button>
      </header>
      <div class="db">
        <table class="kv">
          <tbody>
            <tr><th>항행 상태</th><td><b>{{ val(v.navStatus) }}</b></td></tr>
            <tr><th>위치</th><td class="num">{{ v.lat.toFixed(5) }}, {{ v.lng.toFixed(5) }}</td></tr>
            <tr><th>속력 · 침로</th><td class="num">{{ val(v.sog, ' kn') }} · COG {{ val(v.cog, '°') }} · 선수 {{ val(v.heading, '°') }} · 선회율 {{ val(v.rot) }}</td></tr>
            <tr><th>흘수</th><td class="num">{{ val(v.draft, ' m') }}</td></tr>
            <tr><th>마지막 수신</th><td class="num">{{ kst(v.updatedAt) }} <span class="muted">({{ age }})</span></td></tr>
          </tbody>
        </table>

        <div class="sec">식별 <small>AIS 동적·정적 정보</small></div>
        <table class="kv">
          <tbody>
            <tr><th>선명</th><td>{{ v.name || '-' }}</td></tr>
            <tr><th>국적(MID)</th><td>{{ flagOf(v.mmsi) }}</td></tr>
            <tr><th>MMSI</th><td class="num">{{ val(v.mmsi) }}</td></tr>
            <tr><th>IMO · 호출부호</th><td class="num">{{ val(v.imo) }} · {{ val(v.callSign) }}</td></tr>
            <tr><th>입항연도 · 항차</th><td class="num">{{ val(v.callYear) }} · {{ val(v.voyage) }} <span class="muted">(PORT-MIS와 잇는 열쇠: 호출부호 + 입항연도 + 항차)</span></td></tr>
          </tbody>
        </table>

        <div class="sec">이번 항차 입출항 기록 <small>울산항만공사 운항정보 · 이미 일어난 일</small></div>
        <p v-if="voy.state === 'none'" class="muted small">호출부호 또는 입항연도가 없어 조회할 수 없습니다.</p>
        <p v-else-if="voy.state === 'load'" class="muted small">불러오는 중…</p>
        <p v-else-if="voy.state === 'err'" class="none small">운항정보를 받지 못했습니다 ({{ voy.err }})</p>
        <p v-else-if="!voy.events.length" class="muted small">이 항차({{ v.callYear }}-{{ v.voyage }}) 기록이 아직 없습니다.</p>
        <table v-else class="kv ev">
          <tbody>
            <tr v-for="(e, i) in voy.events" :key="i"><th>{{ hm(e.eventAt) }}</th><td><b>{{ e.event }}</b> <span class="muted">{{ e.facility ?? '' }}</span></td></tr>
          </tbody>
        </table>

        <div class="sec">입항 예정 · ETA <small>해양수산부 선박입출항신고 · 대리점 신고</small></div>
        <p v-if="eta.state === 'none'" class="muted small">호출부호가 없어 조회할 수 없습니다.</p>
        <p v-else-if="eta.state === 'load'" class="muted small">불러오는 중…</p>
        <p v-else-if="eta.state === 'err'" class="none small">입항 신고를 받지 못했습니다 ({{ eta.err }})</p>
        <p v-else-if="eta.state === 'empty'" class="muted small">최근 3일~앞으로 10일 사이의 울산 입항 신고가 없습니다.</p>
        <table v-else class="kv">
          <tbody>
            <tr><th>입항 일시</th><td class="num"><b>{{ hm(eta.a.eta) }}</b> <span :class="eta.a.planned ? 'plan' : 'muted'">{{ eta.a.planned ? '입항 예정(ETA)' : '신고된 입항' }}</span> <span class="muted">· {{ eta.a.filing }} 신고</span></td></tr>
            <tr><th>예정 계선시설</th><td>{{ eta.a.facility ?? '-' }} <span class="muted">· 도선 {{ eta.a.pilot ?? '-' }} · 예선 {{ eta.a.tug ?? '-' }}</span></td></tr>
            <tr><th>항로</th><td>{{ eta.a.prevPort ?? '-' }} → 울산<template v-if="dest"> → {{ dest }}</template> <span class="muted">(전출항지 → 차항지·목적지)</span></td></tr>
            <tr><th>선종 · 톤수</th><td class="num">{{ eta.a.type ?? '-' }} · 총톤수 {{ eta.a.grt?.toLocaleString() ?? '-' }}<template v-if="eta.a.intlGrt"> · 국제총톤수 {{ eta.a.intlGrt.toLocaleString() }}</template></td></tr>
            <tr><th>입항 목적 · 화물</th><td>{{ eta.a.purpose ?? '-' }}<template v-if="eta.a.loadTon || eta.a.unloadTon"> · 적하 {{ eta.a.loadTon ?? 0 }}t · 양하 {{ eta.a.unloadTon ?? 0 }}t</template></td></tr>
            <tr><th>선원 · 신고업체</th><td>{{ eta.a.crew ?? '-' }}명 · {{ eta.a.agent ?? '-' }}</td></tr>
          </tbody>
        </table>

        <div class="sec">AIS에서 아직 못 받는 값</div>
        <table class="kv">
          <tbody>
            <tr><th>AIS ETA · 목적지</th><td class="none">없음 <span class="muted">— 울산항만공사 위치 API가 공개하지 않습니다. 위 입항 신고가 대신합니다.</span></td></tr>
            <tr><th>길이 · 폭 · DWT</th><td class="none">없음 <span class="muted">— 총톤수만 신고에 있습니다. 나머지는 AIS 정적 정보, 선박 원부, 대리점 자료에서 받습니다.</span></td></tr>
          </tbody>
        </table>
      </div>
      <div class="df">출처: 울산항만공사 항내 선박위치정보 · 항만 내 선박 운항정보, 해양수산부 선박입출항신고(공공데이터포털). 서버가 {{ kst(fetchedAt) }}에 받은 값입니다. 가상 시나리오 선박과는 다른 배입니다.</div>
    </aside>
  </div>
</template>

<style scoped>
.scrim { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.12); display: flex; justify-content: flex-end; z-index: 2000; }
.drawer { width: 440px; height: 100%; background: #fff; box-shadow: -4px 0 18px rgba(0, 0, 0, 0.16); display: flex; flex-direction: column; }
.dh { display: flex; align-items: center; gap: 8px; padding: 14px 16px; border-bottom: 2px solid #3d4a5c; }
.dh h2 { margin: 0; font-size: 17px; color: var(--accent); font-weight: 800; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.live { font-size: 10px; color: #fff; background: #2b7de0; padding: 1px 6px; border-radius: 2px; vertical-align: middle; margin-left: 6px; }
.x { width: 30px; height: 30px; border-radius: 50%; border: 1px solid #b9bdc3; background: #fff; color: #555; display: grid; place-items: center; flex: none; }
.db { flex: 1; overflow-y: auto; padding: 12px 16px 20px; }
.df { border-top: 1px solid var(--line); padding: 10px 16px; font-size: 11.5px; color: #888; line-height: 1.5; }
.sec { font-size: 13px; font-weight: 700; color: #222; margin: 16px 0 6px; display: flex; justify-content: space-between; align-items: baseline; }
.sec small { font-weight: 400; color: #999; font-size: 11px; }
.ev th { width: 96px; font-variant-numeric: tabular-nums; }
.plan { color: var(--bad); font-weight: 700; }
.none { color: #b0361f; font-weight: 600; }
.none .muted { font-weight: 400; }
</style>
