// Berthing Schedule — SK Seagate 화면(조회 조건 · 조석 줄 · 부두별 표)에 부산항 선석배정 표의 문법
// (▶ 조회기간 줄, 상태별 행 색과 범례, 전체 조회 건수, 프린트 · 엑셀)을 더했다. 승인된(적용 중인) 계획 버전을 보여 준다.
import { DB, berthLabel, diffPlans } from '../core/data.js';
import { esc, usd, ICON } from '../core/fmt.js';
import { fmtDT, fmtDate, fmtD, parseRaw, nowMs, H, D } from '../core/time.js';
import { role } from '../core/store.js';
import { appliedVersion, appliedSet, displaySet, versions, vesselsNow, ETA_ALERT_H } from '../core/api.js';
import { renderGantt, dayFloor } from '../ui/gantt.js';
import { openVessel, openEvidence } from '../ui/vessel.js';
import { openModal, toast } from '../ui/overlay.js';
import { setWide, pageTitle } from '../ui/shell.js';
import { BOARD_GROUPS } from '../ui/board.js';
import { rowState } from './dashboard.js';

const V = { from: null, to: null, span: '7', view: 'berth', wide: false, group: 'all', sort: 'berth' };

export function render(el) {
  const ver = appliedVersion();
  const base = appliedSet();
  const set = displaySet(base);
  const vs = versions();
  const prev = vs.length > 1 ? DB.sets[vs[vs.length - 2].set] : null;
  const chgById = Object.fromEntries((prev ? diffPlans(prev, base) : []).map((c) => [c.id, c]));
  const alertIds = new Set(vesselsNow().filter((r) => r.alert).map((r) => r.v.id));
  const now = nowMs();
  if (V.from == null) {
    V.from = dayFloor(now);
    V.to = V.from + 6 * D;
  }
  const tide = DB.tides[fmtDate(V.from)];
  const groups = [['all', '전체'], ...BOARD_GROUPS.map(([n], i) => [String(i), n])];
  const inGroup = (bid) => V.group === 'all' || BOARD_GROUPS[+V.group][1].includes(bid);
  const inWin = (p) => p.etb < V.to + D && p.etu > V.from && inGroup(p.berth);
  const list = set.plans.filter(inWin);

  el.innerHTML = `
  ${pageTitle('Berthing Schedule', 'Berth Planning > Ship Berthing > Berthing Schedule')}
  <table class="cond">
    <tr><th>ETB</th>
      <td><span class="date"><input type="date" id="sFrom" value="${fmtDate(V.from)}">${ICON.cal}</span> ~ <span class="date"><input type="date" id="sTo" value="${fmtDate(V.to)}">${ICON.cal}</span>
        <span style="margin-left:14px">${[['4', '4일'], ['7', '일주일'], ['14', '2주'], ['x', '직접 입력']].map(([k, n]) => `<label class="radio"><input type="radio" name="span" value="${k}" ${V.span === k ? 'checked' : ''}>${n}</label>`).join('')}</span></td>
      <th>View Type</th>
      <td><select class="in" id="sView" style="width:200px">
        <option value="berth">Table(for Berth)</option><option value="vessel">Table(for Vessel)</option><option value="graph">Graphic(for Berth)</option></select></td></tr>
    <tr><th>선석구분</th><td>${groups.map(([k, n]) => `<label class="radio"><input type="radio" name="grp" value="${k}" ${V.group === k ? 'checked' : ''}>${esc(n)}</label>`).join('')}</td>
      <th>정렬기준</th><td>${[['berth', '선석'], ['etb', '접안예정일시'], ['etu', '이안예정일시']].map(([k, n]) => `<label class="radio"><input type="radio" name="sort" value="${k}" ${V.sort === k ? 'checked' : ''}>${n}</label>`).join('')}</td></tr>
  </table>
  <div class="bar no-print">
    <div class="g"><button class="btn dark" id="sWide">${ICON.expand}${V.wide ? '접어보기' : '펼쳐보기'}</button></div>
    <div class="g">
      <button class="btn red" id="sSearch">${ICON.search}검색</button>
      <button class="btn" id="sMail" data-req="FR-52,NFR-17">접안계획메일링</button>
      ${role().can.run ? '<a class="btn" href="#plan">Auto Plan</a>' : ''}
    </div>
  </div>
  <table class="sum" style="margin-bottom:14px">
    <thead><tr><th colspan="2">만조</th><th colspan="2">간조</th><th rowspan="2">일출</th><th rowspan="2">일몰</th><th rowspan="2" style="width:42%">remarks</th></tr><tr><th>시간1</th><th>시간2</th><th>시간3</th><th>시간4</th></tr></thead>
    <tbody><tr style="font-size:12.5px"><td>${tide?.high[0] ?? '-'}</td><td>${tide?.high[1] ?? '-'}</td><td>${tide?.low[0] ?? '-'}</td><td>${tide?.low[1] ?? '-'}</td><td>${tide?.sunrise ?? '-'}</td><td>${tide?.sunset ?? '-'}</td>
      <td style="text-align:left;font-size:12px;color:#666">${fmtD(V.from)} 기준. 조석은 접안 계산에 쓰지 않음 · 일출 · 일몰은 Daylight 정박개시 산정에 씀</td></tr></tbody>
  </table>
  <table class="kv" style="margin-bottom:14px" data-req="N-004,N-033,NFR-02">
    <tr><th>적용 계획</th><td><b>v${ver.no}</b> ${esc(ver.label)}${prev ? ` <span class="t-warn">(v${ver.no - 1} 대비 ${Object.keys(chgById).length}척 변경)</span>` : ''}</td>
      <th>${ver.no > 1 ? '승인' : '적용'}</th><td>${fmtDT(ver.applied_at)} · ${esc(ver.applied_by)}</td>
      <th>예상 체선료</th><td><b class="${base.violations.length ? 't-bad' : ''}">${usd(base.total_usd)}</b>${base.violations.length ? ` · <span class="t-bad">규칙 위반 ${base.violations.length}건</span>` : ' · 위반 0'} <a class="lnk" href="#changes" style="margin-left:8px">ETB Change Log ›</a></td></tr>
  </table>
  ${alertIds.size ? `<div class="alert" data-req="N-002"><span class="ic">!</span><div class="grow">AIS ETA가 계획 입력과 ${ETA_ALERT_H}시간 넘게 다른 선박 ${alertIds.size}척이 있습니다 (<span class="mark-eta" style="margin:0">ETA▲</span> 표시).</div></div>` : ''}
  <div class="bar">
    <div class="g"><span class="range">조회기간 : ${fmtDate(V.from).replaceAll('-', '')} ~ ${fmtDate(V.to).replaceAll('-', '')}</span>
      <span class="legend" style="margin-left:18px"><span><i class="dep"></i>출항</span><span><i class="berth"></i>작업중</span><span><i class="plan"></i>계획</span></span></div>
    <div class="g"><span class="count">전체 조회 건수:<b>${list.length}</b></span>
      ${window.top === window.self ? `<button class="btn slate" id="sPrint">${ICON.print}프린트</button>` : ''}<button class="btn slate" id="sCsv">엑셀파일 다운로드</button></div>
  </div>
  <div id="sBody"></div>`;

  const body = el.querySelector('#sBody');
  el.querySelector('#sView').value = V.view;
  setWide(V.wide);

  const cellRow = (p, berthCell, withBerth) => {
    const v = DB.vesselById[p.id];
    const c = chgById[p.id];
    const [cls, label] = rowState(p, now);
    const viol = set.violById?.[p.id];
    return `<tr class="click ${cls}" data-v="${p.id}">${berthCell}
      <td class="${viol ? 't-bad b' : ''}" title="${viol ? esc(viol.join(' / ')) : ''}">${viol ? '위반' : label}</td>
      ${withBerth ? `<td class="b ${c?.berthChanged ? 'chg' : ''}">${esc(berthLabel(p.berth))}${c?.berthChanged ? `<span class="was">${esc(berthLabel(c.from.berth))}</span>` : ''}</td>` : ''}
      <td class="num dt">${fmtDT(p.eta)}${alertIds.has(p.id) ? '<span class="mark-eta">ETA▲</span>' : ''}</td>
      <td class="num dt etb ${c?.timeChanged || (!withBerth && c?.berthChanged) ? 'chg' : ''}">${fmtDT(p.etb)}${c?.timeChanged ? `<span class="was">${fmtDT(c.from.etb)}</span>` : ''}${!withBerth && c?.berthChanged ? `<span class="was">${esc(berthLabel(c.from.berth))}에서</span>` : ''}</td>
      <td class="num dt">${fmtDT(p.etu)}</td>
      <td title="${esc(v.biz_kr)}">${esc(v.biz)}</td><td>${esc(v.shipment)}</td><td class="l vn">${esc(v.name)}</td>
      <td title="${esc(v.product_kr)}">${esc(v.product)}</td><td class="r num">${Number(v.qty_bbl).toLocaleString()}</td>
      <td class="num dt">${fmtDT(p.hose)}</td><td class="num dt le">${p.inport ? '-' : fmtDT(p.le)}</td>
      <td class="r">${p.wait > 0 ? p.wait.toFixed(1) : '-'}</td>
      <td class="r">${p.inport ? '-' : `<span class="lnk ${p.dem > 0 ? 't-bad b' : ''}" data-ev="${p.id}">${usd(p.dem)}</span>`}</td></tr>`;
  };
  const head = (withBerth, first) => `<thead><tr>${first ? '<th>Berth</th>' : ''}<th>상태</th>${withBerth ? '<th>Berth</th>' : ''}<th>ETA</th><th>ETB</th><th>ETU</th><th>Biz</th><th>Shipment</th><th>Vessel</th><th>Product</th><th>Qty(BBL)</th><th>호스분리</th><th>정박종료</th><th>대기(h)</th><th>체선료(USD)</th></tr></thead>`;
  const sorter = (a, b) => (V.sort === 'etu' ? a.etu - b.etu : a.etb - b.etb);

  function draw() {
    const maxH = V.wide ? 'calc(100vh - 260px)' : '640px';
    if (V.view === 'graph') {
      body.innerHTML = '<div id="sG"></div>';
      renderGantt(body.querySelector('#sG'), {
        set: { ...set, plans: set.plans.filter((p) => inGroup(p.berth)) }, from: dayFloor(V.from), to: dayFloor(V.to) + D, ghost: prev,
        showAll: true, onSelect: (id) => openVessel(id), maxHeight: V.wide ? window.innerHeight - 250 : 640, highlight: alertIds,
      });
    } else if (V.view === 'vessel' || V.sort !== 'berth') {
      body.innerHTML = `<div class="tbl-wrap" style="max-height:${maxH}"><table class="tbl">${head(true, false)}<tbody>${[...list].sort(sorter).map((p) => cellRow(p, '', true)).join('') || '<tr class="empty"><td colspan="14">조회된 선박이 없습니다</td></tr>'}</tbody></table></div>`;
    } else {
      const by = {};
      for (const p of list) (by[p.berth] ??= []).push(p);
      const rows = DB.berths.filter((b) => inGroup(b.id)).map((b) => {
        const ps = (by[b.id] ?? []).sort(sorter);
        if (!ps.length) return `<tr class="empty"><td class="bn">${esc(b.label)}</td><td colspan="14"></td></tr>`;
        return ps.map((p, i) => cellRow(p, i === 0 ? `<td class="bn" rowspan="${ps.length}">${esc(b.label)}</td>` : '', false)).join('');
      }).join('');
      body.innerHTML = `<div class="tbl-wrap" style="max-height:${maxH}"><table class="tbl">${head(false, true)}<tbody>${rows}</tbody></table></div>`;
    }
    body.querySelectorAll('tr[data-v]').forEach((tr) => tr.addEventListener('click', (e) => {
      if (e.target.closest('[data-ev]')) return;
      openVessel(tr.dataset.v);
    }));
    body.querySelectorAll('[data-ev]').forEach((a) => a.addEventListener('click', (e) => (e.stopPropagation(), openEvidence(a.dataset.ev))));
  }

  const read = () => {
    const f = parseRaw(el.querySelector('#sFrom').value);
    const t = parseRaw(el.querySelector('#sTo').value);
    if (f == null || t == null || t < f) {
      toast('ETB 기간을 확인해 주세요');
      return false;
    }
    V.from = f;
    V.to = t;
    V.view = el.querySelector('#sView').value;
    V.group = el.querySelector('input[name="grp"]:checked').value;
    V.sort = el.querySelector('input[name="sort"]:checked').value;
    return true;
  };
  el.querySelectorAll('input[name="span"]').forEach((r) => r.addEventListener('change', () => {
    V.span = r.value;
    if (r.value !== 'x') {
      const f = parseRaw(el.querySelector('#sFrom').value) ?? V.from;
      el.querySelector('#sTo').value = fmtDate(f + (+r.value - 1) * D);
    }
  }));
  el.querySelector('#sSearch').addEventListener('click', () => read() && render(el));
  el.querySelector('#sView').addEventListener('change', () => read() && render(el));
  el.querySelector('#sWide').addEventListener('click', () => ((V.wide = !V.wide), render(el)));
  el.querySelector('#sPrint')?.addEventListener('click', () => window.print());
  el.querySelector('#sCsv').addEventListener('click', () => downloadCsv(list.slice().sort(sorter), ver));
  el.querySelector('#sMail').addEventListener('click', () => mailDraft(set, ver));
  draw();
  return () => setWide(false);
}

function downloadCsv(list, ver) {
  const head = ['Berth', 'ETA', 'ETB', 'ETU', 'Biz', 'Shipment', 'Vessel', 'Product', 'Qty(BBL)', '호스분리', '정박종료', '대기(h)', '예상체선료(USD)', '계획버전'];
  const lines = list.map((p) => {
    const v = DB.vesselById[p.id];
    return [berthLabel(p.berth), fmtDT(p.eta), fmtDT(p.etb), fmtDT(p.etu), v.biz, v.shipment, v.name, v.product, v.qty_bbl, fmtDT(p.hose), p.inport ? '' : fmtDT(p.le), Math.max(0, p.wait), p.dem.toFixed(2), `v${ver.no}`];
  });
  const csv = [head, ...lines].map((r) => r.map((x) => `"${String(x).replace(/"/g, '""')}"`).join(',')).join('\r\n');
  const m = openModal({
    title: `엑셀파일 다운로드 · 계획 v${ver.no} · ${lines.length}건`,
    body: `<textarea class="in" style="min-height:250px;font-family:monospace;font-size:11.5px" id="csvText">${esc(csv)}</textarea>`,
    foot: '<button class="btn" data-x>닫기</button><button class="btn" data-copy>복사</button><button class="btn red" data-dl>파일 받기</button>',
  });
  m.el.querySelector('[data-x]').addEventListener('click', m.close);
  m.el.querySelector('[data-copy]').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(csv);
      toast('복사했습니다');
    } catch {
      m.el.querySelector('#csvText').select();
      toast('글을 선택해 두었습니다 (Ctrl+C)');
    }
  });
  m.el.querySelector('[data-dl]').addEventListener('click', () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
    a.download = `berthing-schedule-v${ver.no}-${fmtDate(nowMs())}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
}

function mailDraft(set, ver) {
  const now = nowMs();
  const ps = set.plans.filter((p) => !p.inport && p.etb >= now && p.etb < now + 48 * H).sort((a, b) => a.etb - b.etb);
  const lines = ps.map((p) => {
    const v = DB.vesselById[p.id];
    return `${fmtDT(p.etb)}  ${berthLabel(p.berth).padEnd(8)} ${v.name} (${v.product} ${Number(v.qty_bbl).toLocaleString()} BBL)`;
  });
  const text = `제목: [접안계획] ${fmtD(now)} 기준 48시간 접안 예정 (계획 v${ver.no})\n\n수신: 작업 지시 · 대리점\n\n적용 계획 v${ver.no}(${ver.label}) 기준 48시간 내 접안 예정입니다.\n\n${lines.join('\n') || '(접안 예정 없음)'}\n\n승인: ${fmtDT(ver.applied_at)} ${ver.applied_by}\n※ 의사결정 보조용 · 가상 데이터`;
  const m = openModal({
    title: '접안계획메일링',
    body: `<div class="alert" style="margin-bottom:10px"><span class="ic">i</span><div class="grow">메일은 담당자가 확인 후 메일 프로그램에서 보냅니다. 시스템은 초안만 만듭니다.</div></div>
      <textarea class="in" style="min-height:280px;font-family:monospace;font-size:12px" id="mText">${esc(text)}</textarea>`,
    foot: '<button class="btn" data-x>닫기</button><button class="btn red" data-copy>본문 복사</button>',
  });
  m.el.querySelector('[data-x]').addEventListener('click', m.close);
  m.el.querySelector('[data-copy]').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(m.el.querySelector('#mText').value);
      toast('본문을 복사했습니다');
    } catch {
      m.el.querySelector('#mText').select();
      toast('본문을 선택해 두었습니다 (Ctrl+C)');
    }
  });
}
