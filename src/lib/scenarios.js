import { at } from './time.js'

// 전부 가상 데이터다. 조석·일출몰 값은 11월 울산 근처 수준으로 맞춘 예시일 뿐이다.
// 부두 이름·위치·제원은 SK 울산 액체부두 공개 자료 수준(팀 portwise 프로토타입과 같은 값)에 맞췄다.
const berths = () => [
  {
    id: 'B1', name: 'SK 6부두', code: 'SK6', maxDwt: 70000, maxDraft: 14.5,
    products: ['나프타', '경유', '휘발유', '벙커C'], tideLimited: true,
    occupiedBy: 'SEA DRAGON', occupiedUntil: at(14, 9),
    facility: { known: true, maintenance: null },
    pos: [35.4855, 129.3907], moor: [35.4851, 129.3926],
  },
  {
    id: 'B2', name: 'SK 3부두', code: 'SK3', maxDwt: 50000, maxDraft: 11.5,
    products: ['휘발유', '경유', '항공유', '등유'], tideLimited: false,
    occupiedBy: 'KOMODO', occupiedUntil: at(14, 4),
    facility: { known: true, maintenance: { start: at(15, 10), end: at(15, 14), label: '로딩암 2번 정기 점검' } },
    pos: [35.4946, 129.3829], moor: [35.4941, 129.3848],
  },
  {
    id: 'B3', name: 'SK 5부두', code: 'SK5', maxDwt: 15000, maxDraft: 9.0,
    products: ['등유', '경유', '휘발유'], tideLimited: false,
    occupiedBy: null, occupiedUntil: null,
    facility: { known: false, maintenance: null },
    pos: [35.4892, 129.3863], moor: [35.4888, 129.3882],
  },
]

// 지도 배경용: 이번 계산에 쓰지 않는 다른 SK 시설과 묘박지(정박지) 대기 위치.
export const MAP_CONTEXT = {
  facilities: [
    { code: 'SK1', pos: [35.5027, 129.3632] }, { code: 'SK2', pos: [35.4986, 129.3658] },
    { code: 'SK4', pos: [35.4927, 129.3842] }, { code: 'SK7', pos: [35.4824, 129.3907] },
    { code: 'SK8', pos: [35.4791, 129.3906] }, { code: '2부이', pos: [35.4483, 129.4236] },
    { code: '3부이', pos: [35.44, 129.43] },
  ],
  // DWT 3만 톤 이하는 E2, 그보다 큰 선박은 E3 정박지에서 기다린다.
  anchorages: [
    { id: 'E2', label: 'E2 정박지', maxDwt: 30000, center: [35.4225, 129.4441],
      spots: [[35.42403, 129.42868], [35.42313, 129.44412], [35.42403, 129.45956], [35.41863, 129.4364]] },
    { id: 'E3', label: 'E3 정박지', maxDwt: Infinity, center: [35.4098, 129.4535],
      spots: [[35.41051, 129.43971], [35.41142, 129.45515], [35.41412, 129.47059], [35.4033, 129.44853]] },
  ],
}

// workMin = 물량 / 펌프율 + 부대작업 120분(호스 연결·검척·서류)
const work = (ton, rate) => Math.round((ton / rate) * 60) + 120

const vessels = () => [
  { id: 'V1', name: 'PACIFIC JADE', product: '경유', dir: '수출', dwt: 48000, draft: 11.0, ton: 45000, pump: 2500,
    eta: at(14, 2), contract: { id: 'CA-2611-014', laytimeH: 26, rateUsd: 28000, norTurnH: 6, weather: 'FULL' } },
  { id: 'V2', name: 'OCEAN LILY', product: '휘발유', dir: '수출', dwt: 40000, draft: 10.2, ton: 35000, pump: 2500,
    eta: at(14, 5, 30), contract: { id: 'CA-2611-021', laytimeH: 22, rateUsd: 22000, norTurnH: 6, weather: 'HALF' } },
  { id: 'V3', name: 'GOLDEN STAR', product: '나프타', dir: '수입', dwt: 68000, draft: 13.2, ton: 62000, pump: 3000,
    eta: at(14, 8), contract: { id: 'CA-2610-087', laytimeH: 32, rateUsd: 35000, norTurnH: 6, weather: 'NONE' } },
  { id: 'V4', name: 'HANA MARU', product: '등유', dir: '수출', dwt: 12000, draft: 7.5, ton: 10000, pump: 1250,
    eta: at(14, 10), contract: { id: 'CA-2611-030', laytimeH: 14, rateUsd: 12000, norTurnH: 0, weather: 'FULL' } },
  { id: 'V5', name: 'STELLA', product: '항공유', dir: '수출', dwt: 45000, draft: 11.0, ton: 40000, pump: 2500,
    eta: at(14, 14), contract: { id: 'CA-2611-033', laytimeH: 26, rateUsd: 30000, norTurnH: 6, weather: 'FULL' } },
  { id: 'V6', name: 'BLUE CORAL', product: '벙커C', dir: '수출', dwt: 30000, draft: 9.8, ton: 25000, pump: 1800,
    eta: at(14, 20), contract: { id: 'CA-2611-041', laytimeH: 22, rateUsd: 18000, norTurnH: 6, weather: 'HALF' } },
].map((v) => ({ ...v, workMin: work(v.ton, v.pump) }))

const env = () => ({
  switchingMin: 120,
  daylightDwt: 60000,
  tideDraft: 11.5,
  tideWindowMin: 120,
  days: [
    { day: 13, sunrise: at(13, 7, 8), sunset: at(13, 17, 25) },
    { day: 14, sunrise: at(14, 7, 9), sunset: at(14, 17, 24) },
    { day: 15, sunrise: at(15, 7, 10), sunset: at(15, 17, 23) },
    { day: 16, sunrise: at(16, 7, 11), sunset: at(16, 17, 23) },
    { day: 17, sunrise: at(17, 7, 12), sunset: at(17, 17, 22) },
  ],
  highTides: [at(14, 3, 10), at(14, 15, 28), at(15, 3, 52), at(15, 16, 15), at(16, 4, 33), at(16, 16, 58), at(17, 5, 15), at(17, 17, 40)],
  weather: { start: at(14, 18), end: at(15, 6), label: '강풍 주의보 (최대 풍속 17m/s)', source: '기상청 단기예보 (가상)' },
})

const tanks = () => [
  { product: '나프타', ullageTon: 52000, readyAt: at(15, 6), note: '11/15 06:00 이후 공정 투입으로 여유 7만 톤 이상 확보 예정' },
]

const urgent = () => [
  { vid: 'V5', deadline: at(15, 22), note: '김해·김포 항공유 재고 보충 출하' },
]

function build(id, name, summary, patch) {
  const s = { id, name, summary, berths: berths(), vessels: vessels(), env: env(), tanks: tanks(), urgent: urgent() }
  patch?.(s)
  return s
}

export const SCENARIOS = {
  S1: () => build('S1', '기상 악화 예보일 선박 집중', '11/14 18시부터 12시간 강풍 예보, 6척이 하루 안에 도착'),
  S2: () => build('S2', '평시 (기상 이상 없음)', 'S1과 같은 선박, 기상 악화 예보 없음', (s) => { s.env.weather = null }),
  S3: () => build('S3', '대형선 지연 + 조석 제약', 'GOLDEN STAR가 8시간 늦게 도착, 만조·주간 접안 제약이 겹침', (s) => {
    s.vessels.find((v) => v.id === 'V3').eta = at(14, 16)
  }),
}

export const WEATHER_CLAUSE = {
  FULL: { label: '기상 대기 전부 공제', ratio: 1, rule: 'WX-DED-FULL' },
  HALF: { label: '기상 대기 50% 공제', ratio: 0.5, rule: 'WX-DED-HALF' },
  NONE: { label: '기상 대기 공제 없음', ratio: 0, rule: 'WX-DED-NONE' },
}
