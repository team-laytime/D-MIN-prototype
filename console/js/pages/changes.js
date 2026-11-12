// ETB Change Log — 계획 버전이 바뀔 때 선박별 선석 · ETB · 체선료 변경
import { DB, berthLabel, diffPlans } from '../core/data.js';
import { esc, usd } from '../core/fmt.js';
import { fmtDT, fmtDiff } from '../core/time.js';
import { versions } from '../core/api.js';
import { openEvidence, openVessel } from '../ui/vessel.js';
import { pageTitle, secTitle } from '../ui/shell.js';

export function render(el) {
  const vs = versions();
  const pairs = [];
  for (let i = vs.length - 1; i >= 1; i--) pairs.push([vs[i - 1], vs[i]]);
  el.innerHTML = `
  ${pageTitle('ETB Change Log', 'Berth Planning > Ship Berthing > ETB Change Log')}
  ${pairs.length ? '' : `<div class="empty">변경 내역이 없습니다. 현재 v1 ${esc(vs[0].label)} 적용 중입니다.<br>관리자메뉴 &gt; 승인 관리에서 안을 승인하면 변경 내역이 생깁니다.</div>`}
  ${pairs.map(([a, b]) => {
    const ch = diffPlans(DB.sets[a.set], DB.sets[b.set]);
    const sum = ch.reduce((s, c) => s + c.delta, 0);
    return `${secTitle(`v${a.no} → v${b.no} · ${esc(b.label)}`, `${fmtDT(b.applied_at)} ${esc(b.applied_by)} 승인${b.report_id ? ` · ${esc(b.report_id)}` : ''}`, `<span class="count">변경 선박:<b>${ch.length}</b></span><span style="margin-left:10px">체선료 ${usd(sum, { sign: true })}</span>`)}
      <div class="tbl-wrap" style="max-height:560px"><table class="tbl">
        <thead><tr><th>선박명</th><th>변경 구분</th><th>변경 전 선석</th><th>변경 후 선석</th><th>변경 전 ETB</th><th>변경 후 ETB</th><th>ETB 차이</th><th>변경 전 체선료</th><th>변경 후 체선료</th><th>차이(USD)</th></tr></thead>
        <tbody>${ch.map((c) => {
          const v = DB.vesselById[c.id];
          return `<tr class="click" data-v="${c.id}" data-set="${b.set}"><td class="l vn">${esc(v.name)}</td><td>${c.berthChanged ? '<b>선석</b>' : ''}${c.berthChanged && c.timeChanged ? ' · ' : ''}${c.timeChanged ? '시각' : ''}</td>
            <td>${esc(berthLabel(c.from.berth))}</td><td class="b ${c.berthChanged ? 't-steel' : ''}">${esc(berthLabel(c.to.berth))}</td>
            <td class="num">${fmtDT(c.from.etb)}</td><td class="num etb">${fmtDT(c.to.etb)}</td><td class="num">${c.timeChanged ? fmtDiff(c.to.etb - c.from.etb) : '-'}</td>
            <td class="r num">${usd(c.from.dem).replace('$', '')}</td><td class="r num">${usd(c.to.dem).replace('$', '')}</td>
            <td class="r"><span class="lnk b ${c.delta < 0 ? 't-ok' : c.delta > 0 ? 't-bad' : ''}" data-ev="${c.id}" data-set="${b.set}">${usd(c.delta, { sign: true }).replace('$', '')}</span></td></tr>`;
        }).join('')}</tbody></table></div>`;
  }).join('')}`;
  el.querySelectorAll('tr[data-v]').forEach((tr) => tr.addEventListener('click', (e) => {
    if (e.target.closest('[data-ev]')) return;
    openVessel(tr.dataset.v, { setKey: tr.dataset.set });
  }));
  el.querySelectorAll('[data-ev]').forEach((a) => a.addEventListener('click', (e) => (e.stopPropagation(), openEvidence(a.dataset.ev, a.dataset.set))));
}
