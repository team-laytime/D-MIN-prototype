<script setup>
// 승인권자 로그인(시연용). 실제 인증이 아니라 화면에 적힌 시연 계정과 맞는지만 본다.
import { onMounted, ref } from 'vue'
import { LockKeyhole, X } from 'lucide-vue-next'

const props = defineProps({ account: Object })
const emit = defineEmits(['login', 'close'])
const id = ref('')
const pw = ref('')
const err = ref('')
const idEl = ref(null)
onMounted(() => idEl.value?.focus())

function submit() {
  if (id.value.trim() === props.account.loginId && pw.value === props.account.password) emit('login')
  else err.value = '아이디 또는 비밀번호가 맞지 않습니다.'
}
</script>

<template>
  <div class="modal-back" @click.self="emit('close')" @keydown.esc="emit('close')">
    <form class="modal" role="dialog" aria-modal="true" aria-labelledby="login-title" @submit.prevent="submit">
      <div class="mh"><b id="login-title"><LockKeyhole :size="15" />승인권자 로그인</b><button type="button" class="mx" aria-label="닫기" @click="emit('close')"><X :size="16" /></button></div>
      <div class="mb">
        <p class="small muted lead">관리자메뉴(승인 관리 · 승인 이력)는 승인권자 계정만 사용할 수 있습니다.</p>
        <table class="kv">
          <tbody>
            <tr><th><label for="login-id">아이디</label></th><td><input id="login-id" ref="idEl" v-model="id" class="input" autocomplete="username" @input="err = ''" /></td></tr>
            <tr><th><label for="login-pw">비밀번호</label></th><td><input id="login-pw" v-model="pw" class="input" type="password" autocomplete="current-password" @input="err = ''" /></td></tr>
          </tbody>
        </table>
        <p v-if="err" class="bad small" role="alert">{{ err }}</p>
        <p class="hint small">시연 계정 · 아이디 <b>{{ account.loginId }}</b> / 비밀번호 <b>{{ account.password }}</b> ({{ account.name }}, {{ account.title }})</p>
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
.modal { width: 420px; max-width: calc(100vw - 40px); background: #fff; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3); }
.mh { display: flex; align-items: center; justify-content: space-between; background: #2c3746; color: #fff; padding: 14px 18px; font-size: 15px; }
.mh b { display: inline-flex; align-items: center; gap: 7px; }
.mx { border: 0; background: none; color: #fff; display: grid; place-items: center; }
.mb { padding: 16px 18px 6px; }
.lead { margin: 0 0 10px; }
.kv th { width: 84px; vertical-align: middle; }
.kv .input { width: 100%; }
.bad { color: var(--bad); margin: 8px 0 0; }
.hint { margin: 10px 0 8px; padding: 8px 10px; background: var(--sunken); color: #555; }
.mf { display: flex; justify-content: flex-end; gap: 6px; padding: 12px 18px; border-top: 1px solid var(--line); }
</style>
