<script setup>
// 관리자메뉴(기준 정보 관리자): 기준 정보 · 사용자·권한 · 처리 이력.
// 기준 정보(부두 제원 · 운영 기준값) 변경은 관리자만 한다(HN-096). 고친 값은 계산 입력에 바로 들어가고 기록이 남는다.
import { computed, ref } from 'vue'
import { Check } from 'lucide-vue-next'
import { RULES } from '../lib/engine.js'
import { NAV, PERMS, ROLES, addLog, ws } from '../lib/workspace.js'
import ViewHead from './ViewHead.vue'

const props = defineProps({ section: String, scen: Object })
const TITLES = { master: '기준 정보', users: '사용자·권한', log: '처리 이력' }

function setBerth(b, field, raw, label) {
  const value = field === 'products' ? raw.split(',').map((s) => s.trim()).filter(Boolean) : field === 'tideLimited' ? raw : Number(raw)
  const before = Array.isArray(b[field]) ? b[field].join(', ') : String(b[field])
  b[field] = value
  addLog('기준 정보 변경', `${b.name} · ${label}`, `${before} → ${Array.isArray(value) ? value.join(', ') : value}`)
}
const ENV = [
  { key: 'switchingMin', label: '부두 전환 시간(분)', step: 10 },
  { key: 'daylightDwt', label: '주간 접안 대상 DWT 이상', step: 1000 },
  { key: 'tideDraft', label: '만조 접안 대상 흘수(m) 이상', step: 0.1 },
  { key: 'tideWindowMin', label: '만조 전후 허용(분)', step: 10 },
]
function setEnv(e, raw) {
  const before = props.scen.env[e.key]
  props.scen.env[e.key] = Number(raw)
  addLog('기준 정보 변경', `운영 기준 · ${e.label}`, `${before} → ${raw}`)
}

const menusOf = (id) => NAV.filter((g) => g.roles.includes(id)).map((g) => g.gnb).join(' · ')
const who = ref('')
const log = computed(() => [...ws.log].reverse().filter((l) => !who.value || l.roleTitle === who.value))
</script>

<template>
  <div class="stack">
    <ViewHead :title="TITLES[section]" :crumb="`관리자메뉴 > ${TITLES[section]}`"
      :desc="section === 'master' ? '계산이 읽는 부두 제원과 운영 기준값입니다. 바꾸면 모든 후보가 다시 계산되고 기록이 남습니다.'
        : section === 'users' ? '이해관계자별 시연 계정과 메뉴·권한입니다. [V]는 아직 확인 전인 권한입니다.'
        : '모든 계정의 처리 기록입니다. 기록은 고치거나 지우지 않습니다.'" />

    <template v-if="section === 'master'">
      <section class="panel">
        <div class="panel-head"><h2>부두 제원</h2><span class="muted">값을 바꾸면 바로 다시 계산합니다.</span></div>
        <table class="grid">
          <thead><tr><th>부두</th><th>코드</th><th>최대 DWT</th><th>최대 흘수(m)</th><th>취급 화물(쉼표로 구분)</th><th>만조 접안 제한</th></tr></thead>
          <tbody>
            <tr v-for="b in scen.berths" :key="b.id">
              <td class="c strong">{{ b.name }}</td>
              <td class="c">{{ b.code }}</td>
              <td class="c"><input class="input sm num w-num" type="number" step="1000" :value="b.maxDwt" :aria-label="`${b.name} 최대 DWT`" @change="setBerth(b, 'maxDwt', $event.target.value, '최대 DWT')" /></td>
              <td class="c"><input class="input sm num w-num" type="number" step="0.1" :value="b.maxDraft" :aria-label="`${b.name} 최대 흘수`" @change="setBerth(b, 'maxDraft', $event.target.value, '최대 흘수')" /></td>
              <td><input class="input sm w-full" :value="b.products.join(', ')" :aria-label="`${b.name} 취급 화물`" @change="setBerth(b, 'products', $event.target.value, '취급 화물')" /></td>
              <td class="c"><input type="checkbox" :checked="b.tideLimited" :aria-label="`${b.name} 만조 접안 제한`" @change="setBerth(b, 'tideLimited', $event.target.checked, '만조 접안 제한')" /></td>
            </tr>
          </tbody>
        </table>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>운영 기준값</h2></div>
        <table class="kv env">
          <tbody>
            <tr v-for="e in ENV" :key="e.key">
              <th>{{ e.label }}</th>
              <td><input class="input sm num w-num" type="number" :step="e.step" :value="scen.env[e.key]" :aria-label="e.label" @change="setEnv(e, $event.target.value)" /></td>
            </tr>
          </tbody>
        </table>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>계산 규칙</h2><span class="muted">규칙 엔진이 쓰는 규칙 목록(조회만). 규칙 변경은 코드 배포로 합니다.</span></div>
        <table class="grid">
          <thead><tr><th>규칙 ID</th><th>내용</th></tr></thead>
          <tbody>
            <tr v-for="(r, id) in RULES" :key="id"><td class="c strong rid">{{ id }}</td><td>{{ r.label }}</td></tr>
          </tbody>
        </table>
      </section>
    </template>

    <template v-else-if="section === 'users'">
      <section class="panel">
        <div class="panel-head"><h2>시연 계정</h2><span class="muted">비밀번호는 모두 1234 · 실제 인증 아님</span></div>
        <table class="grid">
          <thead><tr><th>계정</th><th>역할</th><th>아이디</th><th>하는 일</th><th>쓰는 메뉴</th></tr></thead>
          <tbody>
            <tr v-for="r in ROLES" :key="r.id">
              <td class="c strong">{{ r.name }}</td><td class="c">{{ r.title }}</td><td class="c num">{{ r.loginId }}</td>
              <td>{{ r.desc }}</td><td>{{ menusOf(r.id) }}</td>
            </tr>
            <tr class="ext"><td class="c">-</td><td class="c">선주 · 대리점 · 도선</td><td class="c">-</td><td>ETA · NOR · 항만서비스 정보 제공(로그인 사용자 아님, 입력 출처로 표시)</td><td>-</td></tr>
          </tbody>
        </table>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>권한</h2><span class="muted">근거: 팀 요구사항 HN-091 ~ HN-096</span></div>
        <table class="grid perm">
          <thead><tr><th>업무</th><th v-for="r in ROLES" :key="r.id">{{ r.title }}</th><th>근거 · 확인 필요</th></tr></thead>
          <tbody>
            <tr v-for="p in PERMS" :key="p.act">
              <td class="strong">{{ p.act }}</td>
              <td v-for="r in ROLES" :key="r.id" class="c"><Check v-if="p.roles.includes(r.id)" :size="15" class="yes" :aria-label="`${r.title} 가능`" /></td>
              <td class="small">{{ p.src ?? '' }}<span v-if="p.open" class="open"> [V] {{ p.open }}</span></td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>

    <section v-else class="panel">
      <div class="panel-head">
        <h2>처리 기록</h2>
        <select v-model="who" class="input sm" aria-label="역할로 거르기">
          <option value="">전체 역할</option>
          <option v-for="r in ROLES" :key="r.id" :value="r.title">{{ r.title }}</option>
        </select>
        <span class="count">전체 조회 건수 <b>{{ log.length }}</b></span>
      </div>
      <table class="grid">
        <thead><tr><th>일시</th><th>처리자</th><th>역할</th><th>처리</th><th>대상</th><th>내용</th></tr></thead>
        <tbody>
          <tr v-for="(l, i) in log" :key="i">
            <td class="c num small">{{ l.at }}</td>
            <td class="c">{{ l.who }}</td>
            <td class="c">{{ l.roleTitle }}</td>
            <td class="c strong">{{ l.action }}</td>
            <td>{{ l.target }}</td>
            <td>{{ l.detail }}</td>
          </tr>
          <tr v-if="!log.length"><td colspan="6" class="empty">기록이 없습니다.</td></tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.w-num { width: 110px; text-align: right; }
.w-full { width: 100%; }
.env { max-width: 520px; }
.env th { width: 220px; }
.rid { color: #5b3c99; font-size: 12px; }
.perm th { font-size: 11.5px; white-space: normal; }
.yes { color: var(--accent); vertical-align: middle; }
.open { color: var(--warn); font-weight: 600; }
tr.ext td { color: var(--muted); background: #f7f8f9; }
.count { margin-left: auto; color: #333; font-size: 12.5px; }
.count b { color: var(--bad); font-size: 15px; margin-left: 4px; }
.panel-head select { margin-left: 12px; }
.empty { text-align: center; color: var(--muted); height: 48px; }
</style>
