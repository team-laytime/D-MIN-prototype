<script setup>
// 계정 전환(시연용 로그인). 실제 인증이 아니라 화면에 적힌 시연 계정과 맞는지만 본다.
import { onMounted, ref } from 'vue'
import { LockKeyhole, X } from 'lucide-vue-next'
import { PASSWORD, ROLES } from '../lib/workspace.js'

const props = defineProps({ preset: String, current: String })
const emit = defineEmits(['login', 'close'])
const pick = ref(props.preset ?? props.current)
const id = ref(ROLES[pick.value].loginId)
const pw = ref('')
const err = ref('')
const pwEl = ref(null)
onMounted(() => pwEl.value?.focus())

function choose(r) { pick.value = r.id; id.value = r.loginId; err.value = '' }
function submit() {
  const r = Object.values(ROLES).find((x) => x.loginId === id.value.trim())
  if (r && pw.value === PASSWORD) emit('login', r.id)
  else err.value = '아이디 또는 비밀번호가 맞지 않습니다.'
}
</script>

<template>
  <div class="modal-back" @click.self="emit('close')" @keydown.esc="emit('close')">
    <form class="modal" role="dialog" aria-modal="true" aria-labelledby="login-title" @submit.prevent="submit">
      <div class="mh"><b id="login-title"><LockKeyhole :size="15" />계정 전환</b><button type="button" class="mx" aria-label="닫기" @click="emit('close')"><X :size="16" /></button></div>
      <div class="mb">
        <p class="small muted lead">이해관계자마다 쓰는 메뉴가 다릅니다. 시연 계정을 고르고 비밀번호를 넣습니다.</p>
        <table class="grid accts">
          <thead><tr><th>계정</th><th>역할</th><th>하는 일</th><th>아이디</th></tr></thead>
          <tbody>
            <tr v-for="r in ROLES" :key="r.id" class="clickable" :class="{ on: pick === r.id }" @click="choose(r)">
              <td class="c"><input type="radio" name="acct" :checked="pick === r.id" :aria-label="r.name" @change="choose(r)" /> {{ r.name }}<span v-if="r.id === current" class="now">현재</span></td>
              <td class="c">{{ r.title }}</td>
              <td>{{ r.desc }}</td>
              <td class="c num">{{ r.loginId }}</td>
            </tr>
          </tbody>
        </table>
        <table class="kv">
          <tbody>
            <tr><th><label for="login-id">아이디</label></th><td><input id="login-id" v-model="id" class="input" autocomplete="username" @input="err = ''" /></td></tr>
            <tr><th><label for="login-pw">비밀번호</label></th><td><input id="login-pw" ref="pwEl" v-model="pw" class="input" type="password" autocomplete="current-password" @input="err = ''" /></td></tr>
          </tbody>
        </table>
        <p v-if="err" class="bad small" role="alert">{{ err }}</p>
        <p class="hint small">시연 계정 비밀번호는 모두 <b>{{ PASSWORD }}</b>입니다. 실제 인증이 아닙니다.</p>
      </div>
      <div class="mf">
        <button type="button" class="btn" @click="emit('close')">취소</button>
        <button type="submit" class="btn primary">로그인</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.modal-back { position: fixed; inset: 0; z-index: 2100; background: rgba(20, 26, 36, 0.45); display: grid; place-items: center; }
.modal { width: 640px; max-width: calc(100vw - 40px); background: #fff; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3); }
.mh { display: flex; align-items: center; justify-content: space-between; background: #2c3746; color: #fff; padding: 14px 18px; font-size: 15px; }
.mh b { display: inline-flex; align-items: center; gap: 7px; }
.mx { border: 0; background: none; color: #fff; display: grid; place-items: center; }
.mb { padding: 16px 18px 6px; }
.lead { margin: 0 0 10px; }
.c { text-align: center; white-space: nowrap; }
.accts { margin-bottom: 12px; }
.accts td { height: 32px; font-size: 12px; }
.accts tr.on td { background: var(--accent-weak); }
.accts input { margin: 0 4px 0 0; vertical-align: -2px; }
.now { margin-left: 4px; font-size: 10.5px; color: var(--accent); font-weight: 700; }
.kv th { width: 84px; vertical-align: middle; }
.kv .input { width: 100%; }
.bad { color: var(--bad); margin: 8px 0 0; }
.hint { margin: 10px 0 8px; padding: 8px 10px; background: var(--sunken); color: #555; }
.mf { display: flex; justify-content: flex-end; gap: 6px; padding: 12px 18px; border-top: 1px solid var(--line); }
</style>
