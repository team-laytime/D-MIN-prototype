// 글자 · 금액 표시 (NFR-07: 금액은 USD 센트 정수로 계산하고 표시할 때만 반올림)

export const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

export const cents = (usd) => Math.round((usd ?? 0) * 100);

/** $216,986 (기본) · $216,985.68 (cents: true) */
export function usd(v, { cents: withCents = false, sign = false } = {}) {
  if (v == null) return '-';
  const c = Math.round(v * 100);
  const neg = c < 0;
  const abs = Math.abs(c);
  const body = withCents
    ? `${Math.floor(abs / 100).toLocaleString('en-US')}.${String(abs % 100).padStart(2, '0')}`
    : Math.round(abs / 100).toLocaleString('en-US');
  const s = sign ? (neg ? '−' : c > 0 ? '+' : '±') : neg ? '−' : '';
  return `${s}$${body}`;
}

export const pct = (a, b, digits = 1) => (b ? `${((a / b) * 100).toFixed(digits)}%` : '-');
export const n0 = (v) => (v == null ? '-' : Math.round(v).toLocaleString('ko-KR'));
export const n1 = (v) => (v == null ? '-' : (+v).toFixed(1));

/** 짧은 해시(실행 · 입력 지문 표시) */
export function shortHash(s) {
  let h = 2166136261;
  for (const ch of String(s)) {
    h ^= ch.charCodeAt(0);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}

/** 결정적 의사 난수 (같은 선박이면 같은 값) */
export function seeded(key) {
  let h = 2166136261;
  for (const ch of String(key)) {
    h ^= ch.charCodeAt(0);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h ^= h << 13;
    h ^= h >>> 17;
    h ^= h << 5;
    return ((h >>> 0) % 100000) / 100000;
  };
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/** 아이콘 (선 그림) */
export const ICON = {
  search: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="9" r="6"/><path d="M13.5 13.5 18 18" stroke-linecap="round"/></svg>',
  expand: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 8V3h5M17 8V3h-5M3 12v5h5M17 12v5h-5"/></svg>',
  cal: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="4" width="14" height="13" rx="1"/><path d="M3 8h14M7 2v4M13 2v4"/></svg>',
  mail: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="4.5" width="15" height="11" rx="1"/><path d="m3 5 7 6 7-6"/></svg>',
  down: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10 3v10m-4-4 4 4 4-4M4 16h12"/></svg>',
  play: '<svg viewBox="0 0 20 20" fill="currentColor"><path d="M6 4v12l10-6z"/></svg>',
  warn: '<svg viewBox="0 0 20 20" fill="none" stroke="#b45f06" stroke-width="1.7"><path d="M10 3 2 17h16z"/><path d="M10 8v4M10 14.5v.5" stroke-linecap="round"/></svg>',
  info: '<svg viewBox="0 0 20 20" fill="none" stroke="#1f5fbf" stroke-width="1.7"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.5V7" stroke-linecap="round"/></svg>',
  ok: '<svg viewBox="0 0 20 20" fill="none" stroke="#17803d" stroke-width="2"><circle cx="10" cy="10" r="7.5"/><path d="m6.5 10.2 2.4 2.3 4.6-4.8" stroke-linecap="round"/></svg>',
  stop: '<svg viewBox="0 0 20 20" fill="none" stroke="#b81d25" stroke-width="1.8"><circle cx="10" cy="10" r="7.5"/><path d="M6 6l8 8" stroke-linecap="round"/></svg>',
  doc: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 2.5h7l3 3V17.5H5z"/><path d="M12 2.5v3h3M7.5 9.5h5M7.5 12.5h5"/></svg>',
  print: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 7V3h10v4M5 14H3V8h14v6h-2M5 11h10v6H5z"/></svg>',
  map: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2.5 5 7 3l6 2 4.5-2v12L13 17l-6-2-4.5 2zM7 3v12M13 5v12"/></svg>',
};
