// 관리자메뉴 — 승인 관리(결재 대기 · 처리 완료), 승인 처리(보고서 + 결재 처리 표), 승인 이력(계획 버전 · 처리 기록)
import { DB, berthLabel, diffPlans, setLabel } from '../core/data.js';
import { esc, usd, pct } from '../core/fmt.js';
import { fmtDT, fmtAgo, fmtDiff, fmtH, nowMs, H, D } from '../core/time.js';
import { role, state } from '../core/store.js';
import { reports, report, pendingApprovals, decide, vesselsNow, appliedVersion, versions } from '../core/api.js';
import { renderGantt, dayFloor } from '../ui/gantt.js';
import { openVessel } from '../ui/vessel.js';
import { openModal, toast } from '../ui/overlay.js';
import { pageTitle, secTitle } from '../ui/shell.js';
import { reportDoc, bindDoc, statusText, progressTable } from './reports.js';

const REASONS = ['금액', '현장 사정', '안전', '화주 · 선주 관계', '기타'];

function denied(el, title) {
  el.innerHTML = `${pageTitle(title, `Admin > ${title}`)}
    <div class="alert stop" data-req="N-033,NFR-17"><span class="ic">!</span><div class="grow"><b>권한이 없습니다.</b> 승인 · 반려는 승인권자 계정만 할 수 있습니다. (상단 사용자 선택에서 승인권자 B로 바꿔 확인할 수 있습니다.)</div></div>`;
}

export function renderQueue(el) {
  if (!role().can.approve) return denied(el, '승인 관리');
  const pend = pendingApprovals();
  const done = reports().filter((r) => r.status === 'approved' || r.status === 'rejected');
  const alerts = vesselsNow().filter((x) => x.alert);
  el.innerHTML = `
  ${pageTitle('승인 관리', 'Admin > 승인 관리')}
  ${secTitle('승인 대기', '접안계획 보고서를 검토하고 적용할 안을 승인합니다.', `<span class="count">전체 조회 건수:<b>${pend.length}</b></span>`)}
  <div class="tbl-wrap"><table class="tbl">
    <thead><tr><th>No</th><th>문서번호</th><th>제목</th><th>요청자</th><th>요청일시</th><th>추천안</th><th>예상 체선료(USD)</th><th>현행 대비</th><th>입력 기준</th><th>재계산</th><th>처리</th></tr></thead>
    <tbody>${pend.map((r, i) => {
      const rec = DB.sets[r.recommended];
      return `<tr class="click" data-id="${r.id}"><td>${pend.length - i}</td><td class="b">${esc(r.id)}</td><td class="l">${esc(r.title)}</td><td>${esc(r.created_by)}</td>
        <td class="num">${fmtDT(r.submitted_at)}</td><td>${esc(setLabel(rec.key))}</td><td class="r num b">${usd(rec.total_usd).replace('$', '')}</td>
        <td class="r num t-ok">${usd(rec.total_usd - DB.sets.current.total_usd, { sign: true }).replace('$', '')}</td><td class="num">${fmtDT(r.input_at)}</td>
        <td data-req="N-002">${alerts.length ? `<span class="t-bad b">필요 (ETA ${alerts.length}척)</span>` : '<span class="muted">-</span>'}</td>
        <td><a class="btn sm red" href="#approval-${r.id}">검토</a></td></tr>`;
    }).join('') || '<tr class="empty"><td colspan="11">승인 대기 중인 보고서가 없습니다</td></tr>'}</tbody></table></div>

  ${secTitle('처리 완료', '', `<a class="lnk" href="#history">승인 이력 ›</a>`)}
  <div class="tbl-wrap"><table class="tbl">
    <thead><tr><th>문서번호</th><th>결정</th><th>선택 안</th><th>추천안과 같음</th><th>사유 구분</th><th>결재 의견</th><th>결재자</th><th>결재일시</th></tr></thead>
    <tbody>${done.map((r) => `<tr class="click" data-id="${r.id}"><td class="b">${esc(r.id)}</td><td>${statusText(r.status)}</td>
      <td>${r.decision.candidate ? esc(setLabel(r.decision.candidate)) : '-'}</td><td>${r.decision.candidate ? (r.decision.candidate === r.recommended ? '예' : '<span class="t-warn b">아니오</span>') : '-'}</td>
      <td>${esc(r.decision.reason_type ?? '-')}</td><td class="l wrap">${esc(r.decision.reason)}</td><td>${esc(r.decision.by)}</td><td class="num">${fmtDT(r.decision.at)}</td></tr>`).join('') || '<tr class="empty"><td colspan="8">처리한 보고서가 없습니다</td></tr>'}</tbody></table></div>`;
  el.querySelectorAll('tr[data-id]').forEach((tr) => tr.addEventListener('click', (e) => {
    if (e.target.closest('a')) return;
    location.hash = `#approval-${tr.dataset.id}`;
  }));
}

const A = { id: null, pick: null, tab: 'doc', reason: '', type: '금액', checks: {} };

function checksFor(pick, alerts) {
  const inPick = alerts.filter((a) => pick.byId[a.v.id]);
  const items = [];
  if (inPick.length) items.push(['ETA 변경', `AIS ETA 변경 ${inPick.length}척 (${inPick.map((a) => `${a.v.name} ${fmtDiff(a.etaDiff)}`).join(', ')}) — 수치는 이전 입력 기준`]);
  items.push(['장기 대기', `24시간 이상 대기 ${pick.long_wait_vessels}척 · 최장 ${fmtH(pick.wait_hours_max)}`]);
  items.push(['야간 접안', `20~06시 접안 ${pick.night_berthing}건 — 도선 · 줄잡이 인력`]);
  items.push(['부두 변경', `부두 변경 ${pick.berth_changes}척 — 배관 라인업 · 화물 준비`]);
  return items;
}

export function renderDetail(el, [id]) {
  if (!role().can.approve) return denied(el, '승인 처리');
  const r = report(id);
  if (!r) {
    el.innerHTML = `${pageTitle('승인 처리')}<div class="empty">보고서를 찾을 수 없습니다. <a class="lnk" href="#approvals">목록</a></div>`;
    return;
  }
  if (A.id !== id) Object.assign(A, { id, pick: r.recommended, tab: 'doc', reason: '', type: '금액', checks: {} });
  const open = r.status === 'requested';
  const cur = DB.sets.current;
  const pick = DB.sets[open ? A.pick : r.decision?.candidate ?? r.recommended];
  const alerts = vesselsNow().filter((x) => x.alert);
  const ver = appliedVersion();
  const items = checksFor(pick, alerts);
  const checked = open ? A.checks : Object.fromEntries((r.decision?.risks_checked ?? []).map((n) => [n, true]));

  el.innerHTML = `
  ${pageTitle('승인 처리', `Admin > 승인 관리 > ${r.id}`)}
  <div class="bar" style="margin-top:-8px"><div class="g">${esc(r.id)} · ${esc(r.created_by)} · ${fmtDT(r.submitted_at)} 요청 · 상태 ${statusText(r.status)}</div><div class="g"><a class="btn" href="#approvals">목록</a></div></div>
  ${!open ? `<div class="alert ${r.status === 'approved' ? 'done' : 'stop'}"><span class="ic">${r.status === 'approved' ? '✓' : '!'}</span><div class="grow"><b>${r.status === 'approved' ? `${esc(DB.sets[r.decision.candidate].label)} 승인 완료` : '반려'}</b> — ${esc(r.decision.by)} · ${fmtDT(r.decision.at)} · ${esc(r.decision.reason)}</div>${r.status === 'approved' ? '<a href="#schedule">Berthing Schedule</a>' : ''}</div>` : ''}
  <div class="side-doc">
    <div>
      <div class="tabs sm" id="aTabs">${[['doc', '보고서'], ['graph', `변경 미리보기 (${pick.label})`]].map(([k, n]) => `<button data-t="${k}" class="${A.tab === k ? 'on' : ''}">${esc(n)}</button>`).join('')}</div>
      <div id="aBody"></div>
    </div>
    <div class="sticky">
      ${secTitle('결재 처리', '')}
      <table class="kv" data-req="U-038,N-033,N-004">
        <tr><th>선택 안</th><td>${DB.run.candidateKeys.map((k) => {
          const c = DB.sets[k];
          return `<label class="radio" style="display:flex;margin:3px 0"><input type="radio" name="pick" value="${k}" ${pick.key === k ? 'checked' : ''} ${open ? '' : 'disabled'}><b style="margin:0 4px">${esc(c.label)}</b>${esc(c.name)} · ${usd(c.total_usd)}${k === r.recommended ? ' <span class="t-bad">(추천)</span>' : ''}</label>`;
        }).join('')}</td></tr>
        <tr><th>예상 체선료</th><td><b>${usd(pick.total_usd)}</b> <span class="t-ok">(현행 대비 ${usd(pick.total_usd - cur.total_usd, { sign: true })})</span>${open && pick.key !== r.recommended ? '<br><span class="t-warn">추천안과 다른 안 — 사유가 기록됩니다</span>' : ''}</td></tr>
        <tr><th>확인 사항</th><td>${items.map(([n, x]) => `<label class="radio" style="display:flex;align-items:flex-start;white-space:normal;margin:4px 0;gap:6px"><input type="checkbox" data-n="${esc(n)}" ${checked[n] ? 'checked' : ''} ${open ? '' : 'disabled'} style="margin-top:3px"><span><b>${esc(n)}</b> <span class="muted" style="font-size:12px">${esc(x)}</span></span></label>`).join('')}</td></tr>
        <tr><th>사유 구분</th><td><select class="in" id="aType" ${open ? '' : 'disabled'}>${REASONS.map((x) => `<option ${(open ? A.type : r.decision?.reason_type) === x ? 'selected' : ''}>${x}</option>`).join('')}</select></td></tr>
        <tr><th>결재 의견 <span class="t-bad">*</span></th><td><textarea class="in" id="aReason" ${open ? '' : 'disabled'} placeholder="선택 이유를 적어 주세요">${esc(open ? A.reason : r.decision?.reason ?? '')}</textarea></td></tr>
        <tr><th>결재자</th><td>${esc(open ? role().name : r.decision.by)} <span class="muted">(로그인 계정)</span><br><span class="muted" style="font-size:12px">${open ? `승인 시 Berthing Schedule v${ver.no} → v${ver.no + 1} · 입력 기준 ${fmtDT(r.input_at)} · 실행 ${esc(r.run_id)}에 묶여 기록` : `입력 기준 ${fmtDT(r.input_at)} · 실행 ${esc(r.run_id)}`}</span></td></tr>
      </table>
      ${open ? '<div class="bar" style="justify-content:center;margin-top:12px"><button class="btn lg" id="aReject">반려</button><button class="btn red lg" id="aApprove">승인</button></div>' : ''}
      ${secTitle('진행', '')}${progressTable(r, { vertical: true })}
    </div>
  </div>`;

  const drawTab = () => {
    const box = el.querySelector('#aBody');
    if (A.tab === 'graph') {
      box.innerHTML = `<div class="bar" style="margin-top:0"><span class="range">현행 계획 → ${esc(pick.label)} : 바뀐 선박 ${diffPlans(cur, pick).length}척 (빗금 점선 = 현행 자리)</span></div><div id="aG"></div>`;
      const from = dayFloor(DB.run.planStart) - D;
      renderGantt(box.querySelector('#aG'), { set: pick, from, to: from + 9 * D, ghost: cur, onSelect: (vid) => openVessel(vid, { setKey: pick.key }), maxHeight: 640, highlight: new Set(alerts.map((a) => a.v.id)) });
    } else {
      box.innerHTML = `<div class="doc">${reportDoc(r)}</div>`;
      bindDoc(box);
    }
  };
  drawTab();
  el.querySelectorAll('#aTabs button').forEach((b) => b.addEventListener('click', () => ((A.tab = b.dataset.t), renderDetail(el, [id]))));
  if (!open) return;

  const keep = () => {
    A.reason = el.querySelector('#aReason').value;
    A.type = el.querySelector('#aType').value;
    el.querySelectorAll('input[data-n]').forEach((c) => (A.checks[c.dataset.n] = c.checked));
  };
  el.querySelectorAll('input[name="pick"]').forEach((x) => x.addEventListener('change', () => (keep(), (A.pick = x.value), renderDetail(el, [id]))));
  el.querySelector('#aReason').addEventListener('input', keep);
  el.querySelector('#aType').addEventListener('change', keep);
  el.querySelectorAll('input[data-n]').forEach((c) => c.addEventListener('change', keep));

  el.querySelector('#aReject').addEventListener('click', async () => {
    keep();
    if (!A.reason.trim()) return toast('결재 의견(반려 사유)을 적어 주세요');
    await decide(id, { action: 'reject', reason: A.reason.trim(), reasonType: A.type });
    toast(`${id}를 반려했습니다`);
  });
  el.querySelector('#aApprove').addEventListener('click', () => {
    keep();
    if (!A.reason.trim()) return toast('결재 의견(선택 이유)을 적어 주세요');
    const checkedNames = items.map(([n]) => n).filter((n) => A.checks[n]);
    const unchecked = items.map(([n]) => n).filter((n) => !A.checks[n]);
    const m = openModal({
      title: `${pick.label} 승인`,
      width: 560,
      body: `<table class="kv">
        <tr><th>문서</th><td>${esc(r.id)} · ${esc(r.title)}</td></tr>
        <tr><th>선택 안</th><td><b>${esc(setLabel(pick.key))}</b>${pick.key !== r.recommended ? ' <span class="t-warn">(추천안과 다름)</span>' : ''}</td></tr>
        <tr><th>예상 체선료</th><td><b>${usd(pick.total_usd)}</b> · 현행 대비 ${usd(pick.total_usd - cur.total_usd, { sign: true })} (${pct(pick.total_usd - cur.total_usd, cur.total_usd)}, 샘플 기준)</td></tr>
        <tr><th>바뀌는 선박</th><td>${diffPlans(cur, pick).length}척 (부두 변경 ${pick.berth_changes} · 시각 변경 ${pick.time_changes})</td></tr>
        <tr><th>확인 사항</th><td>${checkedNames.length ? esc(checkedNames.join(', ')) : '-'}${unchecked.length ? `<br><span class="t-warn">미확인: ${esc(unchecked.join(', '))} (기록에 남음)</span>` : ''}</td></tr>
        <tr><th>결재 의견</th><td>[${esc(A.type)}] ${esc(A.reason)}</td></tr>
        <tr><th>적용</th><td>Berthing Schedule v${ver.no} → <b>v${ver.no + 1}</b></td></tr></table>`,
      foot: `<span class="who">결재자 ${esc(role().name)} · ${fmtDT(nowMs())}</span><button class="btn" data-x>취소</button><button class="btn red" data-ok>승인</button>`,
    });
    m.el.querySelector('[data-x]').addEventListener('click', m.close);
    m.el.querySelector('[data-ok]').addEventListener('click', async (e) => {
      e.target.disabled = true;
      const v = await decide(id, { action: 'approve', candidate: pick.key, reason: A.reason.trim(), reasonType: A.type, risksChecked: checkedNames, staleAck: !!A.checks['ETA 변경'] });
      m.close();
      toast(`${pick.label} 승인 — Berthing Schedule v${v.no} 적용`, { href: '#schedule', text: '보기' });
    });
  });
}

export function renderHistory(el) {
  if (!role().can.approve) return denied(el, '승인 이력');
  const log = [...state().log].sort((a, b) => b.at - a.at);
  const vs = [...versions()].reverse();
  el.innerHTML = `
  ${pageTitle('승인 이력', 'Admin > 승인 이력')}
  ${secTitle('계획 버전', '승인으로 적용된 접안 계획 버전입니다. 기록은 고치거나 지우지 않습니다.')}
  <div class="tbl-wrap" data-req="N-004"><table class="tbl">
    <thead><tr><th>버전</th><th>계획</th><th>예상 체선료(USD)</th><th>적용일시</th><th>적용자</th><th>보고서</th><th>실행 · 입력 기준</th><th>규칙 · 엔진</th><th>사유</th></tr></thead>
    <tbody>${vs.map((v, i) => `<tr class="${i === 0 ? 'berth' : ''}"><td class="b">v${v.no}${i === 0 ? ' (적용 중)' : ''}</td><td class="l">${esc(v.label)}</td><td class="r num">${usd(DB.sets[v.set].total_usd).replace('$', '')}</td>
      <td class="num">${fmtDT(v.applied_at)}</td><td>${esc(v.applied_by)}</td><td>${v.report_id ? `<a class="lnk" href="#report-${v.report_id}">${esc(v.report_id)}</a>` : '-'}</td>
      <td>${v.run_id ? `${esc(v.run_id)} · ${fmtDT(v.input_at)}` : '-'}</td><td>${v.rules_version ? `${esc(v.rules_version)} · ${esc(v.engine_version)}` : '-'}</td>
      <td class="l wrap">${esc(v.reason_type ? `[${v.reason_type}] ` : '')}${esc(v.reason ?? '')}${v.stale_ack ? ' <span class="t-warn">(ETA 변경 확인 후 승인)</span>' : ''}</td></tr>`).join('')}</tbody></table></div>
  ${secTitle('처리 기록', '작성 · 요청 · 승인 · 반려 · 적용을 시간 순으로 남깁니다.', `<span class="count">전체 조회 건수:<b>${log.length}</b></span>`)}
  <div class="tbl-wrap" data-req="NFR-18,N-033"><table class="tbl">
    <thead><tr><th>일시</th><th>처리자</th><th>역할</th><th>처리</th><th>대상</th><th>내용</th></tr></thead>
    <tbody>${log.map((x) => `<tr><td class="num">${fmtDT(x.at)}</td><td>${esc(x.who)}</td><td>${esc(x.role)}</td><td class="b">${esc(x.action)}</td><td>${esc(x.target)}</td><td class="l wrap">${esc(x.detail)}</td></tr>`).join('')}</tbody></table></div>`;
}
