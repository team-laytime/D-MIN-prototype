// 실시간 AIS 모드: demo 서버(/api/ais/vessels)가 울산항만공사 공공 API를 대신 불러 준 값을 받는다.
// 서버가 없으면(GitHub Pages 등) 실패하고, 화면은 실시간 버튼을 숨긴다.
export const LIVE_BOX = [35.4, 129.36, 35.51, 129.48] // 남, 서, 북, 동 (지도 범위)

export async function fetchLive({ maxAgeMin = 30, box = LIVE_BOX } = {}) {
  const r = await fetch(`./api/ais/vessels?max_age_min=${maxAgeMin}&bbox=${box.join(',')}`, { signal: AbortSignal.timeout(20000) })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  const d = await r.json()
  if (!Array.isArray(d.vessels)) throw new Error('unexpected response')
  return d
}

// 한 척의 입항·투묘·접안·이안·출항 기록(울산항만공사 운항정보). 호출부호 + 입항연도로 찾고, 위치 API가 준 항차로 거른다.
export async function fetchVoyage({ callSign, callYear, voyage }) {
  const q = new URLSearchParams({ callsgn: callSign, year: callYear, ...(voyage ? { voyage } : {}) })
  const r = await fetch(`./api/ais/voyage?${q}`, { signal: AbortSignal.timeout(20000) })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

// 울산 입항 신고(해양수산부 선박입출항신고). 입항일시가 지금보다 늦으면 대리점이 신고한 입항 예정 = ETA에 해당한다.
export async function fetchArrivals({ callsgn, hoursAhead = 48, hoursBack = 0 } = {}) {
  const q = new URLSearchParams(callsgn ? { callsgn } : { hours_ahead: hoursAhead, hours_back: hoursBack })
  const r = await fetch(`./api/entry/arrivals?${q}`, { signal: AbortSignal.timeout(60000) })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

// MMSI 앞 3자리(MID)로 본 국적. 자주 보이는 것만 둔다.
const MID = { 440: 'KR', 441: 'KR', 431: 'JP', 432: 'JP', 412: 'CN', 413: 'CN', 414: 'CN', 351: 'PA', 352: 'PA', 353: 'PA', 354: 'PA', 355: 'PA', 356: 'PA', 357: 'PA', 370: 'PA', 371: 'PA', 372: 'PA', 373: 'PA', 538: 'MH', 563: 'SG', 564: 'SG', 565: 'SG', 566: 'SG', 636: 'LR', 637: 'LR', 477: 'HK', 416: 'TW', 273: 'RU', 548: 'PH', 574: 'VN', 525: 'ID', 533: 'MY', 419: 'IN', 255: 'PT', 256: 'MT', 248: 'MT', 249: 'MT', 215: 'MT', 209: 'CY', 210: 'CY', 212: 'CY', 311: 'BS' }
export const flagOf = (mmsi) => (mmsi ? MID[Number(String(mmsi).slice(0, 3))] ?? `MID ${String(mmsi).slice(0, 3)}` : '-')

// 항행 상태 색: 계류 초록, 정박 노랑, 항해 하늘색, 그 밖에 회색. 입항 예정·정박지 대기(빨강)와 겹치지 않게 시나리오 선박과 색을 달리한다.
export function liveColor(s) {
  if (!s) return '#9aa0a8'
  if (s.includes('계류')) return '#2ea043'
  if (s.includes('앵커')) return '#d4a017'
  if (s.includes('항해(동력)')) return '#2b7de0'
  return '#8a63d2'
}
