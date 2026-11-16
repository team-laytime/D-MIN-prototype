import { at } from './time.js'

// 팀원이 손으로 계산한 정답 세트를 흉내 낸 것. expectedCents는 엔진과 별도로 Decimal + HALF_UP으로 구했다.
const WX = { start: at(14, 18), end: at(15, 6) }

export const ANSWER_SET = [
  { id: 'T01', note: '정박시간 개시 전에 접안', eta: at(14, 2), turnH: 6, etb: at(14, 6), etu: at(15, 2), laytimeH: 26, rateUsd: 28000, weather: 'FULL', wx: WX, expectedCents: 0 },
  { id: 'T02', note: '기상 대기, 공제 없음 계약', eta: at(14, 8), turnH: 6, etb: at(15, 14, 20), etu: at(16, 15, 40), laytimeH: 32, rateUsd: 35000, weather: 'NONE', wx: WX, expectedCents: 2576389 },
  { id: 'T03', note: '기상 대기, 전부 공제 계약', eta: at(14, 8), turnH: 6, etb: at(15, 14, 20), etu: at(16, 15, 40), laytimeH: 32, rateUsd: 35000, weather: 'FULL', wx: WX, expectedCents: 826389 },
  { id: 'T04', note: '기상 대기, 50% 공제 계약', eta: at(14, 8), turnH: 6, etb: at(15, 14, 20), etu: at(16, 15, 40), laytimeH: 32, rateUsd: 35000, weather: 'HALF', wx: WX, expectedCents: 1701389 },
  { id: 'T05', note: 'NOR 즉시 개시 계약', eta: at(14, 10), turnH: 0, etb: at(15, 8), etu: at(15, 18), laytimeH: 14, rateUsd: 12000, weather: 'FULL', wx: WX, expectedCents: 300000 },
  { id: 'T06', note: '50% 공제로 0.5분 단위 발생', eta: at(14, 5, 30), turnH: 6, etb: at(15, 6, 10), etu: at(15, 22, 10), laytimeH: 22, rateUsd: 22000, weather: 'HALF', wx: { start: at(14, 18), end: at(15, 6, 7) }, expectedCents: 605764 },
  { id: 'T07', note: '반 센트 경계(HALF_UP)', eta: at(14, 8), turnH: 6, etb: at(14, 8), etu: at(15, 8, 36), laytimeH: 24, rateUsd: 10001, weather: 'NONE', wx: WX, expectedCents: 25003 },
  { id: 'T08', note: '허용 시간 안에 종료', eta: at(14, 2), turnH: 6, etb: at(14, 11), etu: at(15, 9), laytimeH: 26, rateUsd: 28000, weather: 'FULL', wx: WX, expectedCents: 0 },
  { id: 'T09', note: '작업 중 기상 악화는 공제 대상 아님', eta: at(14, 8), turnH: 6, etb: at(14, 13, 30), etu: at(15, 14, 50), laytimeH: 24, rateUsd: 35000, weather: 'FULL', wx: WX, expectedCents: 194444 },
  { id: 'T10', note: '기상 일부 겹침 + 장기 대기', eta: at(14, 20), turnH: 6, etb: at(16, 17, 40), etu: at(17, 9, 33), laytimeH: 22, rateUsd: 18000, weather: 'HALF', wx: WX, expectedCents: 2366250 },
]
