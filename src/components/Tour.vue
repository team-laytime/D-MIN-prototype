<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({ steps: Array, index: Number })
const emit = defineEmits(['next', 'prev', 'close'])

const step = computed(() => props.steps[props.index])
const rect = ref(null)
// 다음 대상을 찾는 동안에는 카드를 숨겨, 가운데에 잠깐 떴다가 옮겨 가는 깜빡임을 막는다.
const ready = ref(false)
const vw = ref(window.innerWidth)
const vh = ref(window.innerHeight)
const PAD = 6
const CARD_W = 360

function measure() {
  vw.value = window.innerWidth
  vh.value = window.innerHeight
  const el = step.value.target && document.querySelector(step.value.target)
  rect.value = el ? el.getBoundingClientRect() : null
}

// 단계가 바뀌면 화면 전환(탭·패널)이 그려진 뒤 대상을 찾아 가운데로 스크롤한다.
// 이전 강조 위치는 그대로 두고 새 위치로 옮겨 가게 한다.
async function locate() {
  ready.value = false
  await nextTick()
  await new Promise((r) => setTimeout(r, 120))
  const el = step.value.target && document.querySelector(step.value.target)
  if (el) el.scrollIntoView({ block: el.getBoundingClientRect().height > vh.value * 0.7 ? 'start' : 'center' })
  await new Promise((r) => requestAnimationFrame(r))
  measure()
  ready.value = true
}
watch(() => props.index, locate)

// Enter는 포커스된 버튼이 직접 처리하므로 여기서 받지 않는다(두 단계씩 넘어가는 문제).
function onKey(e) {
  if (e.target.closest?.('input, textarea, select')) return
  if (e.key === 'ArrowRight') emit('next')
  else if (e.key === 'ArrowLeft') emit('prev')
  else if (e.key === 'Escape') emit('close')
}
onMounted(() => {
  locate()
  window.addEventListener('resize', measure)
  window.addEventListener('scroll', measure, true)
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', measure)
  window.removeEventListener('scroll', measure, true)
  window.removeEventListener('keydown', onKey)
})

const spot = computed(() => {
  const r = rect.value
  if (!r) return null
  const top = Math.max(r.top - PAD, 4)
  const bottom = Math.min(r.bottom + PAD, vh.value - 4)
  return { left: r.left - PAD, top, width: r.width + PAD * 2, height: Math.max(bottom - top, 0) }
})

// 카드 자리: 큰 대상은 옆 → 그 외는 아래 → 위 → 오른쪽 아래 구석 순으로 찾는다.
const CARD_H = 300
const cardStyle = computed(() => {
  const s = spot.value
  if (!s) return { left: `${(vw.value - CARD_W) / 2}px`, top: `${vh.value / 2 - CARD_H / 2}px` }
  const midTop = `${Math.min(Math.max(s.top + s.height / 2 - CARD_H / 2, 16), vh.value - CARD_H - 16)}px`
  if (s.height > vh.value * 0.5) {
    if (vw.value - (s.left + s.width) > CARD_W + 32) return { left: `${s.left + s.width + 16}px`, top: midTop }
    if (s.left > CARD_W + 32) return { left: `${s.left - CARD_W - 16}px`, top: midTop }
    return { left: '24px', bottom: '24px' }
  }
  const left = Math.min(Math.max(s.left, 16), vw.value - CARD_W - 16)
  if (s.top + s.height + CARD_H + 12 < vh.value) return { left: `${left}px`, top: `${s.top + s.height + 12}px` }
  if (s.top > CARD_H + 12) return { left: `${left}px`, top: `${s.top - 12}px`, transform: 'translateY(-100%)' }
  return { right: '24px', bottom: '24px' }
})
const last = computed(() => props.index === props.steps.length - 1)
</script>

<template>
  <Teleport to="body">
    <div class="tour" role="dialog" aria-modal="true" :aria-label="step.title">
      <div v-if="spot" class="spot" :style="{ left: spot.left + 'px', top: spot.top + 'px', width: spot.width + 'px', height: spot.height + 'px' }" />
      <div v-else class="dim" />
      <div :class="['card', { hidden: !ready }]" :style="cardStyle">
        <div class="progress"><span :style="{ width: ((index + 1) / steps.length) * 100 + '%' }" /></div>
        <p class="count small">{{ step.section }} · {{ index + 1 }} / {{ steps.length }}</p>
        <h3>{{ step.title }}</h3>
        <p class="body">{{ step.body }}</p>
        <p v-if="step.try" class="try small"><b>해 보기</b> {{ step.try }}</p>
        <div class="actions">
          <button class="btn ghost" @click="emit('close')">{{ last ? '닫기' : '그만 보기' }}</button>
          <span class="spacer" />
          <button class="btn" :disabled="index === 0" @click="emit('prev')">이전</button>
          <button class="btn primary" @click="last ? emit('close') : emit('next')">{{ last ? '직접 써 보기' : '다음' }}</button>
        </div>
        <p class="keys faint small">← → 키로 넘기고 Esc로 닫아요</p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.tour { position: fixed; inset: 0; z-index: 50; pointer-events: none; }
.spot {
  position: fixed; border-radius: 10px; box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.52);
  outline: 2px solid #fff; transition: all 0.25s ease;
}
.dim { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.52); }
.card {
  position: fixed; width: 360px; pointer-events: auto; background: var(--panel); border-radius: 10px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.25); padding: 16px 18px 12px; display: flex; flex-direction: column; gap: 8px;
}
.card.hidden { visibility: hidden; }
.progress { height: 3px; background: #eef0f3; border-radius: 2px; overflow: hidden; }
.progress span { display: block; height: 100%; background: var(--accent); transition: width 0.25s; }
.count { color: var(--accent); font-weight: 650; }
.card h3 { font-size: 17px; }
.body { color: var(--text); line-height: 1.6; }
.try { background: var(--accent-weak); color: var(--accent); border-radius: 6px; padding: 7px 10px; }
.try b { margin-right: 6px; }
.actions { display: flex; align-items: center; gap: 6px; margin-top: 4px; }
.keys { text-align: right; }
@media (prefers-reduced-motion: reduce) { .spot, .progress span { transition: none; } }
</style>
