<script setup>
// 시연용 로그인. 실제 인증이 아니라 화면에 적힌 시연 계정과 맞는지만 본다. 로그인한 계정이 곧 역할이다.
import { onMounted, ref } from 'vue'
import { LockKeyhole } from 'lucide-vue-next'
import { PASSWORD, ROLES } from '../lib/workspace.js'

const emit = defineEmits(['login'])
const pick = ref('scheduler')
const id = ref(ROLES.scheduler.loginId)
const pw = ref('')
const err = ref('')
const pwEl = ref(null)
onMounted(() => pwEl.value?.focus())

function choose(r) { pick.value = r.id; id.value = r.loginId; err.value = ''; pwEl.value?.focus() }
function submit() {
  const r = Object.values(ROLES).find((x) => x.loginId === id.value.trim())
  if (r && pw.value === PASSWORD) emit('login', r.id)
  else err.value = '아이디 또는 비밀번호가 맞지 않습니다.'
}
</script>

<template>
  <div class="login-page">
    <form class="login" aria-labelledby="login-title" @submit.prevent="submit">
      <div class="brand"><b>D-</b><span>MIN</span><small>체선료 비교</small></div>
      <div class="mh"><b id="login-title"><LockKeyhole :size="15" />로그인</b></div>
      <div class="mb">
        <p class="small muted lead">계정에 따라 보이는 메뉴가 다릅니다.</p>
        <table class="grid accts">
          <thead><tr><th>계정</th><th>역할</th><th>하는 일</th><th>아이디</th></tr></thead>
          <tbody>
            <tr v-for="r in ROLES" :key="r.id" class="clickable" :class="{ on: pick === r.id }" @click="choose(r)">
              <td class="c"><input type="radio" name="acct" :checked="pick === r.id" :aria-label="r.name" @change="choose(r)" /> {{ r.name }}</td>
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
        <button type="submit" class="btn primary">로그인</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; background: var(--bg); padding: 40px 20px; }
.login { width: 560px; background: #fff; border: 1px solid var(--line-strong); }
.brand { display: flex; align-items: baseline; padding: 22px 18px 14px; }
.brand b { font-size: 23px; font-weight: 800; color: var(--accent); letter-spacing: -0.6px; }
.brand span { font-size: 23px; color: #23a3a8; font-weight: 500; letter-spacing: -0.6px; }
.brand small { margin-left: 8px; font-size: 12.5px; color: #777; }
.mh { display: flex; align-items: center; background: #2c3746; color: #fff; padding: 12px 18px; font-size: 15px; }
.mh b { display: inline-flex; align-items: center; gap: 7px; }
.mb { padding: 16px 18px 6px; }
.lead { margin: 0 0 10px; }
.c { text-align: center; white-space: nowrap; }
.accts { margin-bottom: 12px; }
.accts td { height: 32px; font-size: 12px; }
.accts tr.on td { background: var(--accent-weak); }
.accts input { margin: 0 4px 0 0; vertical-align: -2px; }
.kv th { width: 84px; vertical-align: middle; }
.kv .input { width: 100%; }
.bad { color: var(--bad); margin: 8px 0 0; }
.hint { margin: 10px 0 8px; padding: 8px 10px; background: var(--sunken); color: #555; }
.mf { display: flex; justify-content: flex-end; padding: 12px 18px; border-top: 1px solid var(--line); }
.mf .btn { min-width: 96px; }
</style>
