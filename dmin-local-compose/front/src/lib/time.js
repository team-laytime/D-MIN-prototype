// 시각은 2026-11-14 00:00 KST를 0으로 둔 분 단위 정수로 다룬다.
export const at = (day, h, m = 0) => (day - 14) * 1440 + h * 60 + m

const pad = (n) => String(n).padStart(2, '0')

export function fmt(min) {
  const day = 14 + Math.floor(min / 1440)
  const r = ((min % 1440) + 1440) % 1440
  return `11/${day} ${pad(Math.floor(r / 60))}:${pad(r % 60)}`
}

export function fmtDur(min) {
  const sign = min < 0 ? '-' : ''
  const a = Math.abs(min)
  const h = Math.floor(a / 60)
  const m = Math.round((a % 60) * 10) / 10
  if (h === 0) return `${sign}${m}분`
  return m ? `${sign}${h}시간 ${m}분` : `${sign}${h}시간`
}

export function toInput(min) {
  const day = 14 + Math.floor(min / 1440)
  const r = ((min % 1440) + 1440) % 1440
  return `2026-11-${pad(day)}T${pad(Math.floor(r / 60))}:${pad(r % 60)}`
}

export function fromInput(s) {
  const m = /^2026-11-(\d{2})T(\d{2}):(\d{2})$/.exec(s)
  if (!m) return null
  return at(Number(m[1]), Number(m[2]), Number(m[3]))
}

// 금액은 USD 센트 정수. 화면에서 다시 반올림하지 않는다.
export function money(cents) {
  const sign = cents < 0 ? '-' : ''
  const a = Math.abs(cents)
  const dollars = Math.floor(a / 100).toLocaleString('en-US')
  return `${sign}$${dollars}.${pad(a % 100)}`
}

export function moneyShort(cents) {
  const sign = cents < 0 ? '-' : ''
  const a = Math.abs(cents) / 100
  if (a >= 1000) return `${sign}$${(a / 1000).toFixed(1)}k`
  return `${sign}$${Math.round(a)}`
}
