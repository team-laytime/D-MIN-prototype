// 선석배정 그래프 — 부산항 정보조회서비스 '선석배정 현황(G)' 모양
// 날짜를 가로로, 선석을 세로로 두고, 상자 왼쪽 위에 접안 시(時), 오른쪽 위에 이안 시를 적는다.
// 색: 작업중 = 분홍, 확정(FIX) = 노랑, 계획 = 회색, 규칙 위반 = 연빨강. 점선 = 접안 전 대기(빨강 = 24시간 이상), 빗금 점선 상자 = 바뀌기 전 자리
import { DB, berthLabel } from '../core/data.js';
import { esc, usd } from '../core/fmt.js';
import { fmtDT, H, D, nowMs } from '../core/time.js';

const WD = ['일', '월', '화', '수', '목', '금', '토'];
const LAB = 72;
const ROW = 46;
const pad = (n) => String(n).padStart(2, '0');

export function dayFloor(ms) {
  return Math.floor(ms / D) * D;
}

export function renderGantt(container, opt) {
  const { set, from, to, ghost = null, onSelect, showAll = false, maxHeight = 640, highlight = null } = opt;
  const days = Math.round((to - from) / D);
  const width = Math.max(700, container.clientWidth || 1000) - 2;
  const dayW = Math.max(188, Math.floor((width - LAB) / days));
  const hp = dayW / 24;
  const tw = dayW * days;
  const X = (ms) => ((ms - from) / H) * hp;
  const now = nowMs();

  const used = new Set(set.plans.filter((p) => p.etu > from && p.etb < to).map((p) => p.berth));
  if (ghost) ghost.plans.forEach((p) => used.add(p.berth));
  const rows = DB.berths.filter((b) => showAll || used.has(b.id));
  const rowIdx = Object.fromEntries(rows.map((b, i) => [b.id, i]));

  let head = `<div class="c0" style="width:${LAB}px">선석</div>`;
  for (let d = from; d < to; d += D) {
    const dt = new Date(d);
    head += `<div style="width:${dayW}px">${dt.getUTCFullYear()}.${pad(dt.getUTCMonth() + 1)}.${pad(dt.getUTCDate())} (${WD[dt.getUTCDay()]})</div>`;
  }

  let back = '';
  for (let d = from; d < to; d += D) back += `<div class="gday" style="left:${LAB + X(d)}px"></div>`;
  const today = dayFloor(now);
  if (today >= from && today < to) back += `<div class="gtoday" style="left:${LAB + X(today)}px;width:${dayW}px"></div>`;
  if (now > from && now < to) back += `<div class="gnow" style="left:${LAB + X(now)}px" title="현재 ${fmtDT(now)}"></div>`;

  let body = '';
  rows.forEach((b, i) => {
    body += `<div class="grow" style="top:${24 + i * ROW}px;height:${ROW}px"><div class="glab" style="width:${LAB}px">${esc(b.label)}</div></div>`;
  });

  const vById = DB.vesselById;
  if (ghost) {
    for (const g of ghost.plans) {
      const p = set.byId[g.id];
      if (!p || (p.berth === g.berth && p.etb === g.etb) || g.etu <= from || g.etb >= to) continue;
      const i = rowIdx[g.berth];
      if (i == null) continue;
      const l = Math.max(0, X(g.etb));
      const w = Math.max(14, Math.min(tw, X(g.etu)) - l);
      body += `<div class="ghost" style="left:${LAB + l}px;width:${w}px;top:${24 + i * ROW + 4}px;height:${ROW - 8}px">${esc(vById[g.id].name)}</div>`;
    }
  }

  for (const p of set.plans) {
    if (p.etu <= from || p.etb >= to) continue;
    const i = rowIdx[p.berth];
    if (i == null) continue;
    const v = vById[p.id];
    const top = 24 + i * ROW;
    const l = Math.max(0, X(p.etb));
    const w = Math.max(16, Math.min(tw, X(p.etu)) - l);
    if (p.eta < p.etb && p.etb > from) {
      const wl = Math.max(0, X(p.eta));
      if (l - wl > 3) body += `<div class="wait ${p.wait >= 24 ? 'long' : ''}" style="left:${LAB + wl}px;width:${l - wl}px;top:${top + ROW - 7}px" title="접안 전 대기 ${p.wait}h"></div>`;
    }
    const working = p.etb <= now && now < p.etu;
    const cls = set.violById?.[p.id] ? 'viol' : working ? 'work' : v.fix || p.inport ? 'fix' : 'plan';
    const dimmed = highlight && highlight.size && !highlight.has(p.id) && opt.dimOthers;
    const tip = `${v.name} (${v.product} ${Number(v.qty_bbl).toLocaleString()} BBL)\n${berthLabel(p.berth)} · ETB ${fmtDT(p.etb)} → ETU ${fmtDT(p.etu)}\n대기 ${Math.max(0, p.wait)}h · 체선료 ${usd(p.dem, { cents: true })}${set.violById?.[p.id] ? `\n위반: ${set.violById[p.id].join(' / ')}` : ''}`;
    const short = v.name.length > 16 ? `${v.name.slice(0, 15)}…` : v.name;
    body += `<div class="box ${cls} ${dimmed ? 'dim' : ''}" data-id="${p.id}" style="left:${LAB + l}px;width:${w}px;top:${top + 4}px;height:${ROW - 8}px" title="${esc(tip)}">
      ${w >= 44 ? `<span class="h1">${pad(new Date(p.etb).getUTCHours())}</span><span class="h2">${pad(new Date(p.etu).getUTCHours())}</span>` : ''}
      ${w >= 26 ? `<span class="nm">${esc(short)}</span>` : ''}
      ${w >= 56 ? `<span class="tg">${esc(v.product)}</span>` : ''}${p.dem > 0 && w >= 26 ? '<span class="dm">체선</span>' : highlight?.has(p.id) && w >= 26 ? '<span class="dm" style="color:#c77700">ETA</span>' : ''}
    </div>`;
  }

  const h = 24 + rows.length * ROW;
  container.innerHTML = `<div class="berthg" style="max-height:${maxHeight}px"><div class="gin" style="width:${LAB + tw}px;height:${h}px">
      <div class="ghd" style="width:${LAB + tw}px">${head}</div>${back}${body}</div></div>
    <div class="glegend">
      <span><i style="background:#f9c8f6;border-color:#b77bb3"></i>작업중</span><span><i style="background:#fde7b0;border-color:#c9a24a"></i>확정 · 작업 고정</span>
      <span><i style="background:#e4e5e7"></i>계획</span><span><i style="background:#ffd5d5;border-color:#d33"></i>규칙 위반</span>
      ${ghost ? '<span><i style="border-style:dashed;background:#fff"></i>바뀌기 전 자리</span>' : ''}
      <span>상자 위 숫자 = 접안 · 이안 시(時)</span><span>점선 = 접안 전 대기 (빨강 24h 이상)</span><span style="color:#c00;font-weight:700">체선</span><span>= 예상 체선료 발생</span>
    </div>`;
  if (onSelect) container.querySelectorAll('.box').forEach((el) => el.addEventListener('click', () => onSelect(el.dataset.id)));
  const sc = container.querySelector('.berthg');
  if (now > from && now < to && sc.scrollWidth > sc.clientWidth) sc.scrollLeft = Math.max(0, X(now) - 160);
}
