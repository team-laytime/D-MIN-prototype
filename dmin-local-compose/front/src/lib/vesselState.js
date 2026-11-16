// 지도와 선박 카드가 같은 규칙으로 선박 위치·항행 상태를 정하도록 한 곳에 둔다.
import { MAP_CONTEXT } from './scenarios.js'

// DWT 3만 톤 이하는 E2, 그보다 큰 선박은 E3 정박지에서 기다린다.
export const anchorageFor = (v) => MAP_CONTEXT.anchorages.find((a) => v.dwt <= a.maxDwt)

// PortWise 문법: 빨강 = 입항 예정·정박지 대기, 초록 = 부두 계류, 회색 = 출항.
export const NAV = {
  coming: { status: '항해(동력)', label: '입항 예정', color: '#e5484d', sog: 11.5, cog: 315 },
  waiting: { status: '정박', label: '정박지 대기', color: '#e5484d', sog: 0.1, cog: 300 },
  berthed: { status: '계류', label: '부두 계류', color: '#2ea043', sog: 0.0, cog: 20 },
  left: { status: '항해(출항)', label: '출항', color: '#9aa0a8', sog: 12.0, cog: 135 },
}

// 위치가 정해지지 않은 상태(입항 전·출항 후)는 항로 입구 근처 점으로 보여 준다.
const SEA_IN = [35.392, 129.47]
const SEA_OUT = [35.395, 129.462]

export function positionOf(state, scen, spotIndex = 0) {
  if (state.phase === 'berthed') return scen.berths.find((b) => b.id === state.p.bid).moor
  if (state.phase === 'waiting') {
    const a = anchorageFor(state.v)
    return a.spots[spotIndex % a.spots.length]
  }
  return state.phase === 'coming' ? SEA_IN : SEA_OUT
}
