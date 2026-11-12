// Berth Optimization — 조회 조건표 · 실행 정보 · 후보 비교 표(라디오) · 탭(변경 내역 / 선석배정 그래프 / 선박별 체선료 / 검토 사항)
import { DB, berthLabel, diffPlans, setLabel } from '../core/data.js';
import { esc, usd, pct, ICON } from '../core/fmt.js';
import { fmtDT, fmtDate, fmtH, fmtDiff, nowMs, H, D } from '../core/time.js';
import { role } from '../core/store.js';
import { latestRun, vesselsNow, startRun, createReport, reports, appliedVersion, ETA_ALERT_H } from '../core/api.js';
import { renderGantt, dayFloor } from '../ui/gantt.js';
import { openVessel, openEvidence } from '../ui/vessel.js';
import { toast } from '../ui/overlay.js';
import { pageTitle, secTitle } from '../ui/shell.js';

const P = { sel: 'c1', tab: 'chg', allChg: false };

export function render(el) {
  const r = role();
  const run = latestRun();
  const alerts = vesselsNow().filter((x) => x.alert);
  const cur = DB.sets.current;
  const base = DB.sets.baseline;
  const cands = DB.run.candidateKeys.map((k) => DB.sets[k]);
  const sel = DB.sets[P.sel];
  const mine = reports().filter((x) => x.run_id === run.run_id);
  const requested = mine.find((x) => x.status === 'requested');
  const draft = mine.find((x) => x.status === 'draft');
  const approved = mine.find((x) => x.status === 'approved');
  const st = requested ? 5 : draft ? 4 : approved ? 6 : 3;
  const s = DB.run.stats;
  const fixed = DB.planVessels.filter((v) => v.fix).length;
  const chg = diffPlans(cur, sel);

  el.innerHTML = `
  ${pageTitle('Berth Optimization', 'Berth Planning > Ship Berthing > Berth Optimization')}
  <div class="bar" style="margin:-8px 0 14px"><div class="steps" data-req="FR-60,NFR-21">${['입력 확인', '후보 계산', '후보 비교', '보고서 작성', '승인 요청'].map((n, i) => `<span class="${i + 1 < st ? 'done' : i + 1 === st ? 'now' : ''}">${i + 1}. ${n}</span>`).join('<i>›</i>')}</div></div>
  ${alerts.length ? `<div class="alert" data-req="N-002"><span class="ic">!</span><div class="grow"><b>재계산 필요</b> — 아래 결과는 ${fmtDT(run.input_at)} 입력 기준입니다. 이후 AIS ETA가 바뀐 선박 ${alerts.length}척: ${alerts.map((a) => `${esc(a.v.name)} ${fmtDiff(a.etaDiff)}`).join(', ')}</div>${r.can.run ? '<a href="javascript:void 0" data-run>재계산</a>' : ''}</div>` : ''}
  <table class="cond">
    <tr><th>계획 기간</th><td><span class="date"><input type="date" value="${fmtDate(DB.run.planStart)}" disabled>${ICON.cal}</span> ~ <span class="date"><input type="date" value="${fmtDate(DB.run.planEnd)}" disabled>${ICON.cal}</span></td>
      <th>기준 시점</th><td data-req="N-011"><input class="in" value="${fmtDate(run.input_at)} ${fmtDT(run.input_at).slice(6)}" disabled style="width:150px"> <span class="muted">이 시각 이전으로는 ETB를 만들지 않음</span></td></tr>
    <tr><th>최적화 범위</th><td><label class="radio"><input type="radio" name="scope" checked>전체 부두 (부두 · 순서 함께)</label><label class="radio"><input type="radio" name="scope">부두 유지 (순서만)</label></td>
      <th>탐색 설정</th><td>대기 상한 <input class="in" value="${DB.run.options.max_wait_h}" style="width:52px"> h · 시간 눈금 <select class="in"><option>${DB.run.options.grid_min}분</option><option>60분</option></select> · 후보 3개</td></tr>
    <tr><th>부두 제약 시간</th><td colspan="3">등록된 제약 없음 <span class="muted">(기상 악화 · 공사 시간을 등록하면 그 시간에는 접안하지 않음)</span></td></tr>
  </table>
  <div class="bar">
    <div class="g"><span class="range">대상 : 입항 ${DB.planVessels.length}건 (작업 고정 ${fixed}) · 부두 ${DB.berths.length}곳 · 계약 ${DB.planVessels.length}건 · 규칙 ${esc(DB.run.engine.rules_version)}</span></div>
    <div class="g">${r.can.run ? `<button class="btn red" data-run>${ICON.play}최적화 실행</button>` : '<button class="btn" disabled title="접안 계획 담당만">최적화 실행</button>'}</div>
  </div>
  <div id="prog"></div>

  ${secTitle('실행 정보', '같은 입력 지문이면 같은 결과를 돌려줍니다.')}
  <table class="sum" data-req="NFR-02,NFR-09,NFR-18">
    <thead><tr><th>실행 ID</th><th>입력 기준</th><th>입력 지문</th><th>작업계획 수</th><th>엔진</th><th>솔버</th><th>소요(초)</th><th>결과</th></tr></thead>
    <tbody><tr style="font-size:13px"><td class="b">${esc(run.run_id)}</td><td class="num">${fmtDT(run.input_at)}</td><td><code>${esc(DB.run.request_hash)}</code></td>
      <td class="num">${s.work_plans.toLocaleString()}</td><td>${esc(DB.run.engine.version)}</td><td>HiGHS · ${s.grid_min}분 눈금</td><td class="num">${s.elapsed_seconds.toFixed(1)}</td><td class="t-ok b">최적해 3건</td></tr></tbody>
  </table>

  ${secTitle('후보 비교', '체선료 합계와 바뀌는 선박을 비교해 보고서로 보낼 안을 고릅니다.', '<span>금액은 샘플 데이터 기준</span>')}
  <div class="tbl-wrap" data-req="U-061,N-130"><table class="tbl">
    <thead><tr><th style="width:44px">선택</th><th>구분</th><th>설명</th><th>예상 체선료(USD)</th><th>현행 대비</th><th>규칙 위반</th><th>부두 변경</th><th>시각 변경</th><th>체선 선박</th><th>24h+ 대기</th><th>야간 접안</th><th>결과</th></tr></thead>
    <tbody>${[cur, base, ...cands].map((c) => {
      const d = c.total_usd - cur.total_usd;
      const isC = c.kind === 'candidate';
      return `<tr class="${isC ? 'click' : ''} ${P.sel === c.key ? 'sel' : ''}" ${isC ? `data-k="${c.key}"` : ''} style="${isC ? '' : 'color:#666'}">
        <td>${isC ? `<input type="radio" name="cand" ${P.sel === c.key ? 'checked' : ''}>` : ''}</td>
        <td class="b">${esc(c.label)}${isC ? ` · ${esc(c.name)}` : ''}</td><td class="l wrap" style="max-width:300px;font-size:12px">${esc(c.desc)}</td>
        <td class="r num b">${usd(c.total_usd).replace('$', '')}</td>
        <td class="r num ${d < 0 ? 't-ok' : ''}">${c.key === 'current' ? '-' : `${usd(d, { sign: true }).replace('$', '')} (${pct(d, cur.total_usd)})`}</td>
        <td class="${c.violations.length ? 't-bad b' : ''}">${c.violations.length}</td>
        <td>${isC ? c.berth_changes : '-'}</td><td>${isC ? c.time_changes : '-'}</td>
        <td>${c.demurrage_vessels}</td><td class="${c.long_wait_vessels ? 't-warn' : ''}">${c.long_wait_vessels}</td><td>${c.night_berthing}</td>
        <td>${isC ? '<span class="t-ok">최적</span>' : c.key === 'current' ? '<span class="muted">적용 중</span>' : '<span class="muted">비교용</span>'}</td></tr>`;
    }).join('')}</tbody></table></div>
  <div class="glegend">1안 · 2안은 총액이 같습니다(동률). 엔진 순서는 기준안 대비 바뀐 선박 수, 현행 대비로는 2안이 부두 변경 ${Math.abs(DB.sets.c1.berth_changes - DB.sets.c2.berth_changes)}척 적음 — 2차 기준은 팀 결정 필요.</div>

  <div class="tabs sm" style="margin-top:24px" id="pTabs">
    ${[['chg', `변경 내역 (${chg.length})`], ['graph', '선석배정 그래프'], ['ves', '선박별 체선료'], ['risk', '검토 사항']].map(([k, n]) => `<button data-t="${k}" class="${P.tab === k ? 'on' : ''}">${n}</button>`).join('')}
  </div>
  <div id="pBody"></div>

  ${secTitle('보고서 작성', '선택한 안을 추천안으로 접안계획 보고서를 만들어 승인권자에게 올립니다.')}
  <table class="kv">
    <tr><th>추천안</th><td><b>${esc(setLabel(sel.key))}</b> · ${usd(sel.total_usd)} (현행 대비 ${usd(sel.total_usd - cur.total_usd, { sign: true })})</td></tr>
    <tr><th>이 실행의 보고서</th><td>${mine.length ? mine.map((x) => `<a class="lnk" href="#report-${x.id}">${esc(x.id)}</a> (${{ draft: '작성중', requested: '승인 요청', approved: '승인', rejected: '반려' }[x.status]})`).join(' · ') : '<span class="muted">없음</span>'}${approved ? ` → Berthing Schedule v${appliedVersion().no}` : ''}</td></tr>
  </table>
  <div class="bar" style="justify-content:center;margin-top:14px">${r.can.report ? `<button class="btn red lg" id="mkReport">${esc(sel.label)} 추천으로 보고서 작성</button>` : '<span class="muted">보고서는 접안 계획 담당이 작성합니다</span>'}</div>`;

  drawTab(el, sel, cur, chg, alerts);
  el.querySelectorAll('tr[data-k]').forEach((tr) => tr.addEventListener('click', () => ((P.sel = tr.dataset.k), render(el))));
  el.querySelectorAll('#pTabs button').forEach((b) => b.addEventListener('click', () => {
    P.tab = b.dataset.t;
    el.querySelectorAll('#pTabs button').forEach((x) => x.classList.toggle('on', x === b));
    drawTab(el, sel, cur, chg, alerts);
  }));
  el.querySelectorAll('[data-run]').forEach((b) => b.addEventListener('click', () => runNow(el)));
  el.querySelector('#mkReport')?.addEventListener('click', () => {
    const id = createReport(run.run_id, sel.key);
    toast(`보고서 ${id}를 작성했습니다`);
    location.hash = `#report-${id}`;
  });
}

function drawTab(el, sel, cur, chg, alerts) {
  const box = el.querySelector('#pBody');
  const bindRows = () => {
    box.querySelectorAll('tr[data-v]').forEach((tr) => tr.addEventListener('click', (e) => {
      if (e.target.closest('[data-ev]')) return;
      openVessel(tr.dataset.v, { setKey: sel.key });
    }));
    box.querySelectorAll('[data-ev]').forEach((a) => a.addEventListener('click', (e) => (e.stopPropagation(), openEvidence(a.dataset.ev, sel.key))));
  };
  if (P.tab === 'graph') {
    box.innerHTML = '<div id="pG"></div>';
    const from = dayFloor(DB.run.planStart) - D;
    renderGantt(box.querySelector('#pG'), { set: sel, from, to: from + 9 * D, ghost: cur, onSelect: (id) => openVessel(id, { setKey: sel.key }), maxHeight: 620, highlight: new Set(alerts.map((a) => a.v.id)) });
    return;
  }
  if (P.tab === 'ves') {
    const ps = [...sel.plans].sort((a, b) => a.etb - b.etb);
    box.innerHTML = `<div class="tbl-wrap" style="max-height:520px"><table class="tbl">
      <thead><tr><th>선석</th><th>선박명</th><th>화물</th><th>ETA</th><th>ETB</th><th>ETU</th><th>대기(h)</th><th>정박종료</th><th>호스분리</th><th>체선(h)</th><th>체선료(USD)</th></tr></thead>
      <tbody>${ps.map((p) => {
        const v = DB.vesselById[p.id];
        return `<tr class="click" data-v="${p.id}"><td class="b">${esc(berthLabel(p.berth))}</td><td class="l vn">${esc(v.name)}</td><td>${esc(v.product)}</td>
          <td class="num">${fmtDT(p.eta)}</td><td class="num etb">${fmtDT(p.etb)}</td><td class="num">${fmtDT(p.etu)}</td><td class="r">${p.wait > 0 ? p.wait.toFixed(1) : '-'}</td>
          <td class="num le">${fmtDT(p.le)}</td><td class="num">${fmtDT(p.hose)}</td><td class="r">${p.demH ? p.demH.toFixed(2) : '-'}</td>
          <td class="r"><span class="lnk ${p.dem > 0 ? 't-bad b' : ''}" data-ev="${p.id}">${usd(p.dem, { cents: true }).replace('$', '')}</span></td></tr>`;
      }).join('')}</tbody>
      <tfoot><tr><td colspan="10" class="r">합계</td><td class="r">${usd(sel.total_usd, { cents: true }).replace('$', '')}</td></tr></tfoot></table></div>`;
    bindRows();
    return;
  }
  if (P.tab === 'risk') {
    const inSel = alerts.filter((a) => sel.byId[a.v.id]);
    const rows = [
      ['ETA 변경', inSel.length ? `AIS ETA가 바뀐 선박 ${inSel.length}척 — ${inSel.map((a) => `${a.v.name} ${fmtDiff(a.etaDiff)}`).join(', ')}` : '없음', inSel.length ? ['t-bad', '재계산 필요'] : ['t-ok', '양호']],
      ['규칙 위반', sel.violations.length ? sel.violations.slice(0, 3).join(' / ') : '없음', sel.violations.length ? ['t-bad', '불가'] : ['t-ok', '양호']],
      ['장기 대기', `24시간 이상 대기 ${sel.long_wait_vessels}척 · 최장 ${fmtH(sel.wait_hours_max)} · 대기 합 ${fmtH(sel.wait_hours_sum)}`, sel.long_wait_vessels ? ['t-warn', '주의'] : ['t-ok', '양호']],
      ['야간 접안', `20~06시 접안 ${sel.night_berthing}건 (현행 ${cur.night_berthing}건) — 도선 · 줄잡이 인력 확인`, ['muted', '참고']],
      ['부두 변경', `부두가 바뀌는 선박 ${sel.berth_changes}척 — 배관 라인업 · 화물 준비 변경`, sel.berth_changes > 20 ? ['t-warn', '주의'] : ['muted', '참고']],
      ['체선 발생', `${sel.demurrage_vessels}척 · 최대 ${usd(Math.max(...sel.plans.map((p) => p.dem)))}`, ['muted', '참고']],
    ];
    box.innerHTML = `<div class="tbl-wrap"><table class="tbl"><thead><tr><th style="width:120px">항목</th><th>내용</th><th style="width:110px">판단</th></tr></thead>
      <tbody>${rows.map(([a, b, [c, d]]) => `<tr><td class="b">${a}</td><td class="l wrap">${esc(b)}</td><td class="${c} b">${d}</td></tr>`).join('')}</tbody></table></div>`;
    return;
  }
  const down = chg.filter((c) => c.delta < 0).reduce((a, c) => a + c.delta, 0);
  const up = chg.filter((c) => c.delta > 0).reduce((a, c) => a + c.delta, 0);
  const sorted = [...chg].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  const list = P.allChg ? sorted : sorted.slice(0, 12);
  box.innerHTML = `<div class="bar" style="margin-top:0"><span class="range">현행 계획 → ${esc(sel.label)} : 바뀐 선박 ${chg.length}척 · 줄어든 체선료 ${usd(down)} · 늘어난 체선료 ${usd(up, { sign: true })}</span>
      ${chg.length > 12 ? `<button class="btn sm" id="allChg">${P.allChg ? '상위 12척만' : `${chg.length}척 모두`}</button>` : ''}</div>
    <div class="tbl-wrap" style="max-height:520px"><table class="tbl">
      <thead><tr><th>선박명</th><th>화물</th><th>현행 선석</th><th>현행 ETB</th><th>변경 선석</th><th>변경 ETB</th><th>ETB 차이</th><th>현행 체선료</th><th>변경 체선료</th><th>차이(USD)</th></tr></thead>
      <tbody>${list.map((c) => {
        const v = DB.vesselById[c.id];
        return `<tr class="click" data-v="${c.id}"><td class="l vn">${esc(v.name)}</td><td>${esc(v.product)}</td>
          <td>${esc(berthLabel(c.from.berth))}</td><td class="num">${fmtDT(c.from.etb)}</td>
          <td class="b ${c.berthChanged ? 't-steel' : ''}">${esc(berthLabel(c.to.berth))}</td><td class="num etb">${fmtDT(c.to.etb)}</td>
          <td class="num">${c.timeChanged ? fmtDiff(c.to.etb - c.from.etb) : '-'}</td>
          <td class="r num">${usd(c.from.dem).replace('$', '')}</td><td class="r num">${usd(c.to.dem).replace('$', '')}</td>
          <td class="r"><span class="lnk b ${c.delta < 0 ? 't-ok' : c.delta > 0 ? 't-bad' : ''}" data-ev="${c.id}">${usd(c.delta, { sign: true }).replace('$', '')}</span></td></tr>`;
      }).join('')}</tbody></table></div>`;
  box.querySelector('#allChg')?.addEventListener('click', () => ((P.allChg = !P.allChg), drawTab(el, sel, cur, chg, alerts)));
  bindRows();
}

async function runNow(el) {
  const box = el.querySelector('#prog');
  el.querySelectorAll('[data-run]').forEach((b) => (b.disabled = true));
  const t0 = performance.now();
  box.innerHTML = `<div class="prog" data-req="NFR-09"><div><b id="pgStep">준비</b> <span class="muted">· 경과 <span id="pgSec">0.0</span>초 · 제한 120초 (넘으면 그때까지의 최선안과 최적성 갭을 표시)</span></div><div class="pb"><i id="pgBar"></i></div><ol id="pgList"></ol></div>`;
  const tick = setInterval(() => {
    const s = el.querySelector('#pgSec');
    if (s) s.textContent = ((performance.now() - t0) / 1000).toFixed(1);
  }, 100);
  const names = [];
  await startRun((e) => {
    if (e.done) return;
    names[e.step] = `${e.name} — ${e.detail}`;
    const bar = el.querySelector('#pgBar');
    if (!bar) return;
    bar.style.width = `${((e.step + 1) / e.total) * 100}%`;
    el.querySelector('#pgStep').textContent = `${e.step + 1}/${e.total} ${e.name}`;
    el.querySelector('#pgList').innerHTML = names.map((n, i) => `<li class="${i < e.step ? 'done' : 'now'}">${esc(n)}</li>`).join('');
  });
  clearInterval(tick);
  toast('계산을 마쳤습니다 (프로토타입: 엔진 미연결 — 같은 실행 결과를 다시 표시)');
  render(el);
}
