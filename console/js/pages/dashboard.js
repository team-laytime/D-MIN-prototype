// 운영 현황 — 현황 요약 줄, 선석 작업현황판(부산항 본선작업현황 문법), AIS 지도 + 알림 · 바로가기, 48시간 선석 운영 표
import { DB, berthLabel } from '../core/data.js';
import { esc, usd } from '../core/fmt.js';
import { fmtDT, fmtAgo, fmtDiff, nowMs, H } from '../core/time.js';
import { role } from '../core/store.js';
import { vesselsNow, appliedVersion, appliedSet, displaySet, pendingApprovals, sources, ETA_ALERT_H } from '../core/api.js';
import { createMap, legendHTML } from '../ui/map.js';
import { renderBoard, BOARD_GROUPS } from '../ui/board.js';
import { openVessel, openEvidence } from '../ui/vessel.js';
import { pageTitle, secTitle } from '../ui/shell.js';

const S = { tab: 0 };
const IC = {
  sched: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="5" width="18" height="15"/><path d="M3 10h18M8 3v4M16 3v4M7 14h4M7 17h7"/></svg>',
  opt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3v15M7 8h10M5 14a7 7 0 0 0 14 0"/><circle cx="12" cy="3.5" r="1.5"/></svg>',
  rep: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3h9l3 3v15H6z"/><path d="M9 11h6M9 15h6M9 7h3"/></svg>',
  appr: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 12l4 4 10-10"/><rect x="3" y="3" width="18" height="18"/></svg>',
  ais: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="2"/><path d="M8 8a6 6 0 0 0 0 8M16 8a6 6 0 0 1 0 8M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/></svg>',
  list: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 18h18l-2 3H5zM6 18v-6h12v6M10 12V8h4v4"/></svg>',
  log: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/></svg>',
  hist: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
};

/** 48시간 표 행 상태: 출항(회색) · 작업중(노랑) · 계획(하늘) */
export function rowState(p, now) {
  if (p.etu <= now) return ['dep', '출항'];
  if (p.etb <= now) return ['berth', '작업중'];
  return ['plan', '계획'];
}

export function render(el) {
  const now = nowMs();
  const rows = vesselsNow(now);
  const alerts = rows.filter((r) => r.alert);
  const ver = appliedVersion();
  const set = appliedSet();
  const dset = displaySet(set);
  const pend = pendingApprovals();
  const r = role();
  const anchored = rows.filter((x) => x.ais.nav === 'anchored');
  const maxWait = anchored.length ? Math.max(...anchored.map((x) => (now - x.v.ais.etaMs) / H)) : 0;
  const next48 = set.plans.filter((p) => p.etb >= now && p.etb < now + 48 * H);
  const ops = dset.plans
    .filter((p) => (p.etu > now - 12 * H && p.etb < now + 48 * H))
    .sort((a, b) => a.etb - b.etb);
  const cnt = (k) => rows.filter((x) => x.ais.nav === k).length;
  const pendHref = pend[0] ? (r.can.approve ? `#approval-${pend[0].id}` : `#report-${pend[0].id}`) : '#reports';
  const warnSrc = sources().filter((s) => s.state !== 'ok');

  el.innerHTML = `
  ${pageTitle('운영 현황', 'Dashboard > 운영 현황')}
  ${alerts.length ? `<div class="alert" data-req="N-002"><span class="ic">!</span><div class="grow"><b>ETA 변경 ${alerts.length}척</b> — ${alerts.map((a) => `${esc(a.v.name)} ${fmtDiff(a.etaDiff)}`).join(', ')} · AIS ETA가 계획 입력과 ${ETA_ALERT_H}시간 넘게 다릅니다.</div>${r.can.run ? '<a href="#plan">계획 재계산</a>' : ''}</div>` : ''}

  ${secTitle('현황 요약', '적용 중인 접안 계획과 지금 항만 상황입니다.', `기준 ${fmtDT(now)}`)}
  <table class="sum" data-req="NFR-08,U-091">
    <thead>
      <tr><th colspan="2">적용 계획</th><th colspan="2">예상 체선료 (USD)</th><th colspan="3">선박 현황 (AIS)</th><th colspan="2">48시간 내 접안</th><th rowspan="2">승인 대기</th></tr>
      <tr><th>버전</th><th>적용 일시</th><th>합계</th><th>규칙 위반</th><th>입항 예정</th><th>정박지 대기</th><th>계류</th><th>척수</th><th>체선 예상</th></tr>
    </thead>
    <tbody><tr>
      <td><b>v${ver.no}</b><small>${esc(ver.label)}</small></td>
      <td class="num">${fmtDT(ver.applied_at)}<small>${esc(ver.applied_by)}</small></td>
      <td class="num"><b>${usd(set.total_usd).replace('$', '')}</b><small>샘플 데이터 기준</small></td>
      <td class="${set.violations.length ? 't-bad b' : 't-ok'}">${set.violations.length}건</td>
      <td>${cnt('underway')}</td>
      <td>${anchored.length}<small>최장 ${maxWait.toFixed(1)}h</small></td>
      <td>${cnt('moored')}</td>
      <td>${next48.length}</td>
      <td class="${next48.some((p) => p.dem > 0) ? 't-bad' : ''}">${next48.filter((p) => p.dem > 0).length}척<small>${usd(next48.reduce((s, p) => s + p.dem, 0))}</small></td>
      <td>${pend.length ? `<a class="lnk b" href="${pendHref}">${pend.length}건</a><small>${esc(pend[0].id)}</small>` : '0건'}</td>
    </tr></tbody>
  </table>

  ${secTitle('선석 작업현황', '선석별 작업 진행률과 다음 접안 선박을 한눈에 볼 수 있습니다.', '<span>진행률 배지: 초록 = 정상, 빨강 = 체선 예상</span>')}
  <div class="tabs" id="bTabs">${BOARD_GROUPS.map(([n], i) => `<button data-i="${i}" class="${S.tab === i ? 'on' : ''}">${esc(n)}</button>`).join('')}</div>
  <div id="board"></div>

  ${secTitle('선박 위치 · 알림', 'AIS로 받은 선박 위치와 처리할 일입니다.', `<a class="lnk" href="#vessels-map">AIS 크게 보기 ›</a>`)}
  <div class="row-map">
    <div class="map" id="dMap" style="height:430px">${legendHTML()}</div>
    <div style="display:grid;grid-template-rows:1fr auto">
      <div class="note" data-req="N-002,NFR-11">
        <h3>알림 <small>${fmtDT(now)}</small></h3>
        <ul>
          ${alerts.map((a) => `<li data-v="${a.v.id}"><span class="tx"><span class="tg r">ETA</span>${esc(a.v.name)} ${fmtDiff(a.etaDiff)} · 재계산 필요</span><span class="dt">${fmtDT(a.ais.updatedAt).slice(6)}</span></li>`).join('')}
          ${pend.map((p) => `<li data-href="${r.can.approve ? `#approval-${p.id}` : `#report-${p.id}`}"><span class="tx"><span class="tg">결재</span>${esc(p.id)} 접안계획 승인 요청</span><span class="dt">${fmtDT(p.submitted_at).slice(6)}</span></li>`).join('')}
          ${warnSrc.map((s) => `<li><span class="tx"><span class="tg">연계</span>${esc(s.name)} — ${esc(s.note ?? '확인 필요')}</span><span class="dt">${fmtAgo(s.at)}</span></li>`).join('')}
          ${!alerts.length && !pend.length && !warnSrc.length ? '<li><span class="tx">새 알림이 없습니다</span></li>' : ''}
        </ul>
      </div>
      <div class="tiles">
        <a href="#schedule">${IC.sched}Berthing<br>Schedule</a>
        <a href="#plan">${IC.opt}Berth<br>Optimization</a>
        <a href="#reports">${IC.rep}접안계획<br>보고서</a>
        <a href="${r.can.approve ? '#approvals' : '#reports'}">${IC.appr}승인 관리</a>
        <a href="#vessels-map">${IC.ais}AIS</a>
        <a href="#vessels-list">${IC.list}입항 예정<br>선박</a>
        <a href="#changes">${IC.log}ETB<br>Change Log</a>
        <a href="${r.can.approve ? '#history' : '#reports'}">${IC.hist}승인 이력</a>
      </div>
    </div>
  </div>

  ${secTitle('선석 운영 현황', '최근 12시간 출항부터 48시간 내 접안 예정까지입니다.', `<span class="legend"><span><i class="dep"></i>출항</span><span><i class="berth"></i>작업중</span><span><i class="plan"></i>계획</span></span><span class="count" style="margin-left:14px">전체 조회 건수:<b>${ops.length}</b></span>`)}
  <div class="tbl-wrap" style="max-height:470px"><table class="tbl">
    <thead><tr><th>상태</th><th>선석</th><th>선박명</th><th>화물</th><th>수량(BBL)</th><th>입항일시</th><th>접안(예정)일시</th><th>호스분리</th><th>이안(예정)일시</th><th>정박종료</th><th>대기(h)</th><th>체선료(예상)</th></tr></thead>
    <tbody>${ops.map((p) => {
      const v = DB.vesselById[p.id];
      const [cls, label] = rowState(p, now);
      return `<tr class="click ${cls}" data-v="${p.id}">
        <td>${label}</td><td class="b">${esc(berthLabel(p.berth))}</td><td class="vn">${esc(v.name)}${alerts.some((a) => a.v.id === p.id) ? '<span class="mark-eta">ETA▲</span>' : ''}</td>
        <td>${esc(v.product)}</td><td class="r num">${Number(v.qty_bbl).toLocaleString()}</td>
        <td class="num">${fmtDT(p.eta)}</td><td class="num etb">${fmtDT(p.etb)}</td><td class="num">${fmtDT(p.hose)}</td><td class="num">${fmtDT(p.etu)}</td>
        <td class="num le">${p.inport ? '-' : fmtDT(p.le)}</td><td class="r">${p.wait > 0 ? p.wait.toFixed(1) : '-'}</td>
        <td class="r">${p.inport ? '-' : `<span class="lnk ${p.dem > 0 ? 't-bad b' : ''}" data-ev="${p.id}">${usd(p.dem)}</span>`}</td></tr>`;
    }).join('')}</tbody></table></div>`;

  const drawBoard = () => renderBoard(el.querySelector('#board'), { set: dset, berthIds: BOARD_GROUPS[S.tab][1], onSelect: (id) => openVessel(id), now });
  drawBoard();
  el.querySelectorAll('#bTabs button').forEach((b) => b.addEventListener('click', () => {
    S.tab = +b.dataset.i;
    el.querySelectorAll('#bTabs button').forEach((x) => x.classList.toggle('on', x === b));
    drawBoard();
  }));
  const m = createMap(el.querySelector('#dMap'), { onSelect: (id) => (m.select(id), openVessel(id)), labels: false, wheel: false });
  m.update(rows);
  el.querySelectorAll('.note li[data-v]').forEach((li) => li.addEventListener('click', () => openVessel(li.dataset.v)));
  el.querySelectorAll('.note li[data-href]').forEach((li) => li.addEventListener('click', () => (location.hash = li.dataset.href)));
  el.querySelectorAll('tr[data-v]').forEach((tr) => tr.addEventListener('click', (e) => {
    if (e.target.closest('[data-ev]')) return;
    openVessel(tr.dataset.v);
  }));
  el.querySelectorAll('[data-ev]').forEach((a) => a.addEventListener('click', (e) => (e.stopPropagation(), openEvidence(a.dataset.ev))));
  const tick = setInterval(() => m.update(vesselsNow()), 30000);
  return () => {
    clearInterval(tick);
    m.destroy();
  };
}
