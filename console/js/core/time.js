// 시각 처리 (NFR-07: KST · 분 단위, 표시는 MM/DD HH:mm)
// 모든 시각은 'KST 벽시계를 UTC 자리에 둔 밀리초'로 다룬다. 서버·브라우저 시간대가 달라도 같은 값이 나온다 (N-192).
// 목업 데이터는 계획 시작일(base_date)이 2026-11-09이다. 화면에서는 계획 시작이 늘 '내일 00:00'이 되도록 날짜만 옮긴다.
// ?now=2026-11-12T15:00 을 주소에 붙이면 기준 시각을 고정한다 (시연 · 화면 확인용).

export const MIN = 60e3;
export const H = 3600e3;
export const D = 86400e3;

let shiftMs = 0;
let fixedNow = null;

export function parseRaw(s) {
  const m = /(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(s);
  if (!m) return null;
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] ?? 0), +(m[5] ?? 0));
}

export function initClock(baseDate) {
  const p = new URLSearchParams(location.search).get('now');
  if (p) fixedNow = parseRaw(p);
  const now = nowMs();
  const today0 = Math.floor(now / D) * D;
  shiftMs = today0 + D - parseRaw(baseDate);
  return { planStart: today0 + D, shiftMs };
}

/** 지금 (KST 벽시계) */
export const nowMs = () => fixedNow ?? Date.now() + 9 * H;
export const isFixedNow = () => fixedNow != null;

/** 데이터의 'YYYY-MM-DDTHH:MM' → 화면 시각(날짜를 옮긴 값) */
export const t = (iso) => (iso ? parseRaw(iso) + shiftMs : null);

const pad = (n) => String(n).padStart(2, '0');

export function fmtDT(ms) {
  if (ms == null) return '-';
  const d = new Date(ms);
  return `${pad(d.getUTCMonth() + 1)}/${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}
export function fmtD(ms) {
  const d = new Date(ms);
  return `${pad(d.getUTCMonth() + 1)}/${pad(d.getUTCDate())}`;
}
export function fmtHM(ms) {
  const d = new Date(ms);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}
export function fmtDate(ms) {
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
}
const WD = ['일', '월', '화', '수', '목', '금', '토'];
export function fmtDW(ms) {
  const d = new Date(ms);
  return `${fmtD(ms)}(${WD[d.getUTCDay()]})`;
}
export function hourOf(ms) {
  return new Date(ms).getUTCHours();
}

/** '3분 전' 같은 상대 시각 */
export function fmtAgo(ms) {
  const s = Math.max(0, Math.round((nowMs() - ms) / 1000));
  if (s < 60) return `${s}초 전`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 ${m % 60}분 전`;
  return `${Math.floor(h / 24)}일 전`;
}

/** 시간(h) 표시: 18.28 → '18.3h' */
export function fmtH(h, digits = 1) {
  if (h == null) return '-';
  return `${(+h).toFixed(digits).replace(/\.0+$/, '')}h`;
}
/** 시간 차이(ms) → '+6h 00m' */
export function fmtDiff(ms) {
  const sign = ms < 0 ? '−' : '+';
  const m = Math.round(Math.abs(ms) / MIN);
  return `${sign}${Math.floor(m / 60)}h ${pad(m % 60)}m`;
}

/** 계산 근거 문장 속 'MM/DD HH:mm'을 화면 날짜로 옮긴다 (데이터 연도 2026 기준) */
export function shiftText(s) {
  if (!s) return s;
  return s.replace(/(\d{2})\/(\d{2}) (\d{2}):(\d{2})/g, (_, mo, d, hh, mi) => fmtDT(Date.UTC(2026, +mo - 1, +d, +hh, +mi) + shiftMs));
}
