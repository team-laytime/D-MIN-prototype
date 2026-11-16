<script setup>
// 스케줄러 요청 처리: 작업 지시자·생산 부서가 보낸 변경·우선순위 요청을 받아 반영 또는 반려한다.
// 반영은 기록만 남긴다. 실제 일정 변경은 스케줄러가 시나리오 입력에서 고치고 다시 확정한다.
import { computed, reactive } from 'vue'
import { answerRequest, ws } from '../lib/workspace.js'
import ViewHead from './ViewHead.vue'

const emit = defineEmits(['go'])
const list = computed(() => [...ws.requests].reverse())
const open = computed(() => ws.requests.filter((r) => r.status === '접수').length)
const reply = reactive({})
const err = reactive({})
function answer(r, status) {
  const text = (reply[r.id] ?? '').trim()
  if (!text) { err[r.id] = '회신 내용을 적어 주십시오.'; return }
  answerRequest(r.id, status, text)
  err[r.id] = ''
}
</script>

<template>
  <div class="stack">
    <ViewHead title="요청 처리" crumb="BERTH PLANNING > 요청 처리" desc="작업 지시자·생산 부서가 보낸 요청에 회신합니다. 반영한 요청은 시나리오 입력에서 고친 뒤 다시 확정합니다."
      :kpis="[
        { label: '처리 대기', value: `${open}건`, bad: open > 0 },
        { label: '반영', value: `${ws.requests.filter((r) => r.status === '반영').length}건` },
        { label: '반려', value: `${ws.requests.filter((r) => r.status === '반려').length}건` },
      ]" />
    <section class="panel">
      <div class="panel-head">
        <h2>받은 요청</h2>
        <span class="count">전체 조회 건수 <b>{{ list.length }}</b></span>
      </div>
      <table class="grid">
        <thead><tr><th>요청번호</th><th>유형</th><th>보낸 곳</th><th>선박</th><th>내용</th><th>접수일시</th><th>상태</th><th>회신</th></tr></thead>
        <tbody>
          <tr v-for="r in list" :key="r.id" :class="{ wait: r.status === '접수' }">
            <td class="c strong">{{ r.id }}</td>
            <td class="c">{{ r.type }}</td>
            <td class="c">{{ r.roleTitle }}<br><span class="faint small">{{ r.who }}</span></td>
            <td class="c strong">{{ r.vname }}</td>
            <td>{{ r.text }}</td>
            <td class="c num small">{{ r.at }}</td>
            <td class="c"><span class="strong" :class="{ warnc: r.status === '접수', good: r.status === '반영', bad: r.status === '반려' }">{{ r.status }}</span></td>
            <td class="answer">
              <template v-if="r.status === '접수'">
                <input v-model="reply[r.id]" class="input sm" placeholder="회신 내용" @input="err[r.id] = ''" />
                <div class="row">
                  <button class="btn primary sm" @click="answer(r, '반영')">반영</button>
                  <button class="btn sm" @click="answer(r, '반려')">반려</button>
                </div>
                <p v-if="err[r.id]" class="bad small">{{ err[r.id] }}</p>
              </template>
              <span v-else class="small">{{ r.reply }}<br><span class="faint">{{ r.repliedBy }} · {{ r.repliedAt }}</span></span>
            </td>
          </tr>
          <tr v-if="!list.length"><td colspan="8" class="empty">받은 요청이 없습니다. 작업 지시자(현장 변경)·생산 부서(우선순위) 계정에서 요청을 보내면 여기에 쌓입니다.</td></tr>
        </tbody>
      </table>
      <p class="small muted after"><button class="btn ghost" @click="emit('go', 'input')">시나리오 입력</button>에서 반영할 값을 고친 뒤 「리스크·확정」에서 다시 확정합니다.</p>
    </section>
  </div>
</template>

<style scoped>
.c { text-align: center; white-space: nowrap; }
.good { color: var(--ok); }
.bad { color: var(--bad); }
.warnc { color: var(--warn); }
.count { margin-left: auto; color: #333; font-size: 12.5px; }
.count b { color: var(--bad); font-size: 15px; margin-left: 4px; }
.empty { text-align: center; color: var(--muted); height: 56px; }
tr.wait td { background: #fff6c4; }
.answer { width: 240px; }
.answer .input { width: 100%; margin-bottom: 4px; }
.btn.sm { height: 24px; padding: 0 10px; font-size: 12px; }
.after { margin: 8px 0 0; }
</style>
