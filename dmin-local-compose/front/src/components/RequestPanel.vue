<script setup>
// 다른 부서 → 스케줄러 요청 보내기 + 내가 보낸 요청 목록. 작업 지시자(현장 변경)·생산 부서(우선순위)가 같이 쓴다.
import { computed, ref } from 'vue'
import { addRequest, ws } from '../lib/workspace.js'

const props = defineProps({ type: String, vessels: Array, kinds: Array, placeholder: String })
const vid = ref(props.vessels[0]?.vid ?? '')
const kind = ref(props.kinds[0])
const text = ref('')
const err = ref('')
const sent = ref('')
const mine = computed(() => ws.requests.filter((r) => r.from === ws.roleId).reverse())

function send() {
  if (!text.value.trim()) { err.value = '요청 내용을 적어 주십시오.'; return }
  const v = props.vessels.find((x) => x.vid === vid.value)
  const r = addRequest({ type: props.type, vid: v.vid, vname: v.name, text: `[${kind.value}] ${text.value.trim()}` })
  sent.value = `${r.id}를 스케줄러에게 보냈습니다.`
  text.value = ''
  err.value = ''
}
</script>

<template>
  <section class="panel">
    <div class="panel-head"><h2>{{ type }}</h2><span class="muted">스케줄러가 회신합니다. 일정 변경은 스케줄러가 다시 확정해야 적용됩니다.</span></div>
    <table class="kv">
      <tbody>
        <tr><th>선박</th><td><select v-model="vid" class="input sm"><option v-for="v in vessels" :key="v.vid" :value="v.vid">{{ v.name }}</option></select></td></tr>
        <tr><th>구분</th><td><select v-model="kind" class="input sm"><option v-for="k in kinds" :key="k">{{ k }}</option></select></td></tr>
        <tr><th>내용 <span class="bad">*</span></th><td>
          <textarea v-model="text" class="input" rows="2" :placeholder="placeholder" @input="err = ''; sent = ''" />
          <p v-if="err" class="bad small">{{ err }}</p>
          <p v-if="sent" class="good small">{{ sent }}</p>
        </td></tr>
      </tbody>
    </table>
    <div class="acts"><button class="btn primary" @click="send">요청 보내기</button></div>

    <table class="grid mine">
      <thead><tr><th>요청번호</th><th>선박</th><th>내용</th><th>보낸 일시</th><th>상태</th><th>스케줄러 회신</th></tr></thead>
      <tbody>
        <tr v-for="r in mine" :key="r.id">
          <td class="c strong">{{ r.id }}</td>
          <td class="c">{{ r.vname }}</td>
          <td>{{ r.text }}</td>
          <td class="c num small">{{ r.at }}</td>
          <td class="c strong" :class="{ warnc: r.status === '접수', good: r.status === '반영', bad: r.status === '반려' }">{{ r.status }}</td>
          <td>{{ r.reply || '-' }}</td>
        </tr>
        <tr v-if="!mine.length"><td colspan="6" class="empty">보낸 요청이 없습니다.</td></tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.good { color: var(--ok); }
.bad { color: var(--bad); }
.warnc { color: var(--warn); }
.kv textarea.input { width: 100%; height: auto; padding: 6px 8px; resize: vertical; }
.kv p { margin: 4px 0 0; }
.acts { display: flex; justify-content: flex-end; margin: 8px 0 14px; }
.empty { text-align: center; color: var(--muted); height: 48px; }
</style>
