<script setup>
// 포털식 페이지 머리: 제목 + 오른쪽 브레드크럼, 계획 흐름 단계, 요약 표.
defineProps({
  title: String,
  crumb: String,
  desc: String,
  step: { type: Number, default: 0 },
  kpis: { type: Array, default: () => [] },
})
const STEPS = ['입력 확인', '후보 비교', '리스크 확인', '계획 확정', '보고서 작성']
</script>

<template>
  <div class="view-head">
    <div class="view-title">
      <h1>{{ title }}</h1>
      <span v-if="crumb" class="crumb">{{ crumb }}</span>
    </div>
    <ol v-if="step" class="steps" aria-label="계획 단계">
      <li v-for="(s, i) in STEPS" :key="s" :class="{ on: i + 1 === step }" :aria-current="i + 1 === step ? 'step' : null">{{ i + 1 }}. {{ s }}</li>
    </ol>
    <p v-if="desc" class="desc">{{ desc }}</p>
    <table v-if="kpis.length" class="grid summary">
      <thead><tr><th v-for="k in kpis" :key="k.label">{{ k.label }}</th></tr></thead>
      <tbody>
        <tr>
          <td v-for="k in kpis" :key="k.label" :class="{ good: k.good, bad: k.bad }">{{ k.value }}<small v-if="k.sub">{{ k.sub }}</small></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
