// 선석 작업현황판 — 부산항 정보조회서비스 '본선작업현황'의 문법(선석별 열 · 진행률 배지 · 선박 그림 · 왼쪽 진한 머리칸)을
// 액체부두에 맞춰 그린다: 크레인 · 컨테이너 대신 제티 · 로딩암 · 탱커, 진행률 배지는 체선이 예상되면 빨강.
import { DB, berthLabel } from '../core/data.js';
import { esc, usd } from '../core/fmt.js';
import { fmtDT, nowMs, H } from '../core/time.js';

export const BOARD_GROUPS = [
  ['대형부두 · 부이 · 가스', ['#3', '#6', '#7', '#8', 'BUOY2', 'BUOY3', 'GAS1', 'GAS2']],
  ['1부두 · 2부두', ['#1-1', '#1-2', '#2-1', '#2-2', '#2-4', '#2-5', '#2-6', '#2-7']],
  ['4부두 · 5부두', ['#4-1', '#4-2', '#4-3', '#5-1', '#5-2', '#5-3', '#5-4', '#5-5']],
];

const fmtFull = (ms) => {
  const s = fmtDT(ms); // MM/DD HH:mm
  return `${new Date(ms).getUTCFullYear()}/${s.replace(' ', ' ')}`;
};

/** 제티에 댄 탱커 (옆모습, 140×100 안에 다 들어가게 그린다) */
export function tankerSVG({ empty = false, gas = false, buoy = false, cls = 'PP' } = {}) {
  const hull = { CR: '#3b2b27', PP: '#26364f', PC: '#3d3354', LB: '#21413c', SP: '#34383e' }[cls] ?? '#26364f';
  const sea = '<rect width="140" height="100" fill="#3a8edb"/><rect y="62" width="140" height="38" fill="#2f80cc"/>' +
    '<path d="M0 82 q7 -3 14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0" fill="none" stroke="#7cc0f2" stroke-width="1" opacity=".7"/>' +
    '<path d="M-7 92 q7 -3 14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0" fill="none" stroke="#7cc0f2" stroke-width="1" opacity=".45"/>';
  const quay = buoy
    ? '<rect width="140" height="16" fill="#d3d8de"/><circle cx="128" cy="40" r="5" fill="#f2c94c" stroke="#7a6100"/>'
    : '<rect width="140" height="16" fill="#c4cad2"/><rect y="15" width="140" height="2" fill="#8e96a1"/>' +
      '<rect x="56" y="5" width="30" height="10" fill="#8b929c"/><rect x="59" y="17" width="2.5" height="12" fill="#77808b"/><rect x="80" y="17" width="2.5" height="12" fill="#77808b"/>' +
      '<path d="M66 5 V0 M76 5 V0" stroke="#5f6670" stroke-width="1.6"/>';
  if (empty) {
    return `<svg viewBox="0 0 140 100" preserveAspectRatio="xMidYMid slice">${sea}${quay}
      <text x="70" y="66" text-anchor="middle" font-size="13" font-weight="700" fill="#dcecff" font-family="Noto Sans KR, sans-serif">공석</text></svg>`;
  }
  const arm = buoy ? '<path d="M123 42 Q112 46 102 44" fill="none" stroke="#222" stroke-width="1.4"/>' : '<path d="M71 17 V29 L77 37" fill="none" stroke="#e5ad00" stroke-width="2.2" stroke-linecap="round"/>';
  const deck = gas
    ? '<path d="M38 44 a9 7 0 0 1 18 0z M60 44 a9 7 0 0 1 18 0z M82 44 a9 7 0 0 1 18 0z" fill="#eef1f4" stroke="#98a2ad" stroke-width=".8"/>'
    : '<rect x="36" y="42" width="84" height="2.2" fill="#d6b24a"/><rect x="75" y="36" width="2.2" height="7" fill="#d6b24a"/><rect x="80" y="36" width="2.2" height="7" fill="#d6b24a"/>';
  return `<svg viewBox="0 0 140 100" preserveAspectRatio="xMidYMid slice">${sea}${quay}
    <path d="M8 44 H122 Q133 46 136 54 Q133 63 122 66 H17 Q10 62 8 54 Z" fill="${hull}"/>
    <path d="M10 60 H134 Q131 65 122 66 H17 Q12 64 10 60 Z" fill="#b8392d"/>
    ${deck}
    <rect x="12" y="27" width="20" height="17" fill="#f4f5f7"/><rect x="14" y="31" width="16" height="2.4" fill="#2e4a6e"/><rect x="14" y="36" width="16" height="2.4" fill="#2e4a6e"/>
    <rect x="16" y="19" width="7" height="8" fill="#d6202f"/><rect x="16" y="19" width="7" height="2.2" fill="#222"/>
    <path d="M118 44 L129 39 L132 44 Z" fill="${hull}"/>
    ${arm}</svg>`;
}

function stateOf(berthId, set, now) {
  const ps = set.plans.filter((p) => p.berth === berthId).sort((a, b) => a.etb - b.etb);
  const cur = ps.find((p) => p.etb <= now && now < p.etu) ?? null;
  const upcoming = ps.filter((p) => p.etb > now);
  return { cur, next: upcoming[0] ?? null, after: upcoming[1] ?? null };
}

/**
 * @param container 그릴 곳
 * @param set 화면 표시용 계획(작업 중 배 + 적용 계획)
 * @param berthIds 열로 보일 선석
 */
export function renderBoard(container, { set, berthIds, onSelect, now = nowMs() }) {
  const rows = '42px 84px 26px repeat(7, 34px)';
  const head = `<div class="hcol" style="grid-template-rows:${rows}">
    <div style="grid-row:span 3;font-size:14px">선석</div><div>선박명</div><div>입항일시</div><div>접안일시</div><div>이안예정</div><div>화물</div><div>체선료(예상)</div><div>다음 접안</div></div>`;
  const cols = berthIds.map((bid) => {
    const b = DB.berthById[bid];
    const { cur, next, after } = stateOf(bid, set, now);
    const show = cur ?? next;
    const v = show ? DB.vesselById[show.id] : null;
    let badge = '<span class="pct idle">예정</span>';
    if (cur) {
      const span = Math.max(1, cur.we - cur.ws);
      const pct = Math.round(Math.min(1, Math.max(0, (now - cur.ws) / span)) * 100);
      badge = `<span class="pct ${cur.dem > 0 ? 'bad' : 'ok'}" title="${cur.dem > 0 ? '체선 예상' : '작업 진행률'}">${pct}%</span>`;
    } else if (!show) {
      badge = '<span class="pct idle">-</span>';
    }
    const pic = tankerSVG({ empty: !cur, gas: bid.startsWith('GAS') || v?.product === 'LPG', buoy: bid.startsWith('BUOY'), cls: v?.class });
    const code = cur ? `${esc(v.call_sign)}-${esc(v.port_mis.voyage.slice(5))}` : show ? `다음 ${fmtDT(show.etb)}` : '배정 없음';
    const nextLine = cur ? next : after;
    const nv = nextLine ? DB.vesselById[nextLine.id] : null;
    return `<div class="bcol ${show ? 'click' : ''}" ${show ? `data-v="${show.id}"` : ''} style="grid-template-rows:${rows}" title="${v ? esc(`${v.name} · ${b.label}`) : esc(b.label)}">
      <div class="bh"><span class="nm">${esc(b.label)}</span>${badge}</div>
      <div class="pic">${pic}</div>
      <div class="code" style="${cur ? '' : 'background:#7b8796'}">${code}</div>
      <div><span class="vname">${v ? esc(v.name) : '-'}</span></div>
      <div class="num">${show ? fmtFull(show.eta) : '-'}</div>
      <div class="num ${cur ? '' : 't-steel b'}">${show ? fmtFull(show.etb) : '-'}</div>
      <div class="num">${show ? fmtFull(show.etu) : '-'}</div>
      <div class="split">${v ? `<span>${esc(v.product)}</span><span class="num">${Number(v.qty_bbl).toLocaleString()}</span>` : '<span>-</span>'}</div>
      <div class="num ${show && show.dem > 0 ? 't-bad b' : ''}">${show ? usd(show.dem) : '-'}</div>
      <div class="nx" title="${nv ? esc(`${nv.name} · ETB ${fmtDT(nextLine.etb)}`) : ''}">${nv ? `<span class="muted">${fmtDT(nextLine.etb).slice(0, 5)}</span> ${esc(nv.name)}` : '-'}</div>
    </div>`;
  }).join('');
  container.innerHTML = `<div class="board" style="grid-template-columns:110px repeat(${berthIds.length}, minmax(0,1fr))">${head}${cols}</div>`;
  if (onSelect) container.querySelectorAll('.bcol[data-v]').forEach((c) => c.addEventListener('click', () => onSelect(c.dataset.v)));
}

/** 진행 중인 배 수 · 빈 선석 수 */
export function boardCounts(set, now = nowMs()) {
  let busy = 0;
  for (const b of DB.berths) if (stateOf(b.id, set, now).cur) busy++;
  return { busy, idle: DB.berths.length - busy };
}
export { berthLabel, H };
