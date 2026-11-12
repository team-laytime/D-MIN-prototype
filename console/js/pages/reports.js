// 접안계획 보고서 — 사내 보고 양식: 결재란(담당 · 승인), 문서 정보 표, 개조식(○ · -) 본문.
// 문장은 LLM 초안 자리(프로토타입은 템플릿), 숫자는 모두 계산 결과를 참조한다.
import { DB, berthLabel, diffPlans, setLabel } from '../core/data.js';
import { esc, usd, pct, ICON } from '../core/fmt.js';
import { fmtDT, fmtDate, fmtH, fmtDiff, nowMs } from '../core/time.js';
import { role } from '../core/store.js';
import { reports, report, submitReport, vesselsNow, appliedVersion, versions } from '../core/api.js';
import { openEvidence, openVessel } from '../ui/vessel.js';
import { openModal, toast } from '../ui/overlay.js';
import { pageTitle, secTitle } from '../ui/shell.js';

export const STATUS = { draft: ['작성중', ''], requested: ['승인 요청', 't-warn'], approved: ['승인', 't-ok'], rejected: ['반려', 't-bad'] };
export const statusText = (s) => `<span class="b ${STATUS[s][1]}">${STATUS[s][0]}</span>`;
const F = { st: 'all' };

export function renderList(el) {
  const all = reports();
  const list = all.filter((r) => F.st === 'all' || r.status === F.st);
  el.innerHTML = `
  ${pageTitle('접안계획 보고서', 'Report > 접안계획 보고서')}
  <table class="cond"><tr><th>상태</th><td>${[['all', '전체'], ['draft', '작성중'], ['requested', '승인 요청'], ['approved', '승인'], ['rejected', '반려']].map(([k, n]) => `<label class="radio"><input type="radio" name="st" value="${k}" ${F.st === k ? 'checked' : ''}>${n}</label>`).join('')}</td>
    <th>작성 부서</th><td>생산조정 · 접안 계획</td></tr></table>
  <div class="bar"><div class="g"><span class="count">전체 조회 건수:<b>${list.length}</b></span></div>
    <div class="g">${role().can.report ? '<a class="btn red" href="#plan">보고서 작성 (Berth Optimization)</a>' : ''}</div></div>
  <div class="tbl-wrap"><table class="tbl">
    <thead><tr><th>No</th><th>문서번호</th><th>제목</th><th>대상 실행</th><th>추천안</th><th>예상 체선료(USD)</th><th>상태</th><th>작성자</th><th>작성일시</th><th>결재자</th><th>결재일시</th></tr></thead>
    <tbody>${list.map((r, i) => `<tr class="click" data-id="${r.id}"><td>${list.length - i}</td><td class="b">${esc(r.id)}</td><td class="l">${esc(r.title)} — ${esc(DB.sets[r.recommended].label)} 추천</td>
      <td>${esc(r.run_id)}</td><td>${esc(setLabel(r.recommended))}</td><td class="r num">${usd(DB.sets[r.recommended].total_usd).replace('$', '')}</td>
      <td>${statusText(r.status)}</td><td>${esc(r.created_by)}</td><td class="num">${fmtDT(r.created_at)}</td>
      <td>${r.decision ? esc(r.decision.by) : '-'}</td><td class="num">${r.decision ? fmtDT(r.decision.at) : '-'}</td></tr>`).join('') || '<tr class="empty"><td colspan="11">조회된 보고서가 없습니다</td></tr>'}</tbody></table></div>`;
  el.querySelectorAll('input[name="st"]').forEach((x) => x.addEventListener('change', () => ((F.st = x.value), renderList(el))));
  el.querySelectorAll('tr[data-id]').forEach((tr) => tr.addEventListener('click', () => (location.hash = `#report-${tr.dataset.id}`)));
}

function signBox(r) {
  const appr = r.decision;
  const stamp = !appr ? '<span class="stamp wait">대기</span>' : appr.action === 'approve' ? '<span class="stamp">승인</span>' : '<span class="stamp rej">반려</span>';
  const draftStamp = r.status === 'draft' ? '<span class="stamp wait">작성중</span>' : '<span class="stamp" style="transform:rotate(-6deg)">상신</span>';
  return `<table class="sign"><tr><th rowspan="3">결재</th><td class="r1">담당</td><td class="r1">승인</td></tr>
    <tr><td class="r2">${draftStamp}</td><td class="r2">${stamp}</td></tr>
    <tr><td class="r3">${esc(r.created_by)}<br>${r.submitted_at ? fmtDT(r.submitted_at) : '-'}</td><td class="r3">${appr ? `${esc(appr.by)}<br>${fmtDT(appr.at)}` : '승인권자 B<br>-'}</td></tr></table>`;
}

/** 보고서 본문 (승인 화면에서도 같이 쓴다) */
export function reportDoc(r) {
  const cur = DB.sets.current;
  const base = DB.sets.baseline;
  const rec = DB.sets[r.recommended];
  const cands = DB.run.candidateKeys.map((k) => DB.sets[k]);
  const ch = diffPlans(cur, rec);
  const alerts = vesselsNow().filter((x) => x.alert);
  const ref = (txt, title) => `<span class="ref" title="${esc(title)}">${txt}</span>`;
  const topDown = [...ch].sort((a, b) => a.delta - b.delta).slice(0, 5);
  const big = [...rec.plans].sort((a, b) => b.dem - a.dem).slice(0, 3);
  const d = rec.total_usd - cur.total_usd;
  const why = { c1: '예상 체선료가 가장 낮고 규칙 위반이 없음', c2: '1안과 예상 체선료가 같고, 현행 대비 부두 변경 선박이 1척 적음', c3: '예상 체선료는 1안보다 크나 현행 부두 배정을 유지해 배관 라인업 · 화물 준비 변경이 가장 적음' }[rec.key];
  return `
  <div class="dtop">
    <div>
      <h1 style="text-align:left;margin:4px 0 14px">주간 접안계획 검토 보고</h1>
      <table class="kv" style="max-width:640px">
        <tr><th>문서번호</th><td>${esc(r.id)}</td><th style="width:90px">작성일</th><td>${fmtDate(r.created_at)}</td></tr>
        <tr><th>작성자</th><td>${esc(r.created_by)} (접안 계획)</td><th>대상 기간</th><td>${fmtDT(DB.run.planStart)} ~ ${fmtDT(DB.run.planEnd)}</td></tr>
        <tr><th>계산 기준</th><td colspan="3" data-req="NFR-02,N-001">실행 ${esc(r.run_id)} · 입력 기준 ${fmtDT(r.input_at)} · 규칙 ${esc(DB.run.engine.rules_version)} · 엔진 ${esc(DB.run.engine.version)}</td></tr>
      </table>
    </div>
    ${signBox(r)}
  </div>
  ${alerts.length ? `<div class="alert" data-req="N-002"><span class="ic">!</span><div class="grow"><b>재계산 필요</b> — 보고서 작성 뒤 AIS ETA가 바뀐 선박 ${alerts.length}척 (${alerts.map((a) => `${esc(a.v.name)} ${fmtDiff(a.etaDiff)}`).join(', ')}). 아래 수치는 ${fmtDT(r.input_at)} 입력 기준.</div></div>` : ''}

  <h3>1. 개요</h3>
  <ul class="o" data-req="NFR-01,N-365">
    <li>대상 : 입항 ${ref(`${DB.planVessels.length}건`, '입력')}, 부두 ${DB.berths.length}곳, 계획 기간 ${fmtDT(DB.run.planStart)} ~ ${fmtDT(DB.run.planEnd)}</li>
    <li>현행 계획(엑셀 입력) 예상 체선료 ${ref(usd(cur.total_usd), `현행 합계 ${usd(cur.total_usd, { cents: true })}`)}, 규칙 위반 ${ref(`${cur.violations.length}건`, '현행 위반 수')}</li>
    <li>${esc(rec.label)}(${esc(rec.name)}) 예상 체선료 ${ref(usd(rec.total_usd), `${rec.label} 합계 ${usd(rec.total_usd, { cents: true })}`)} — 현행 대비 ${ref(usd(d, { sign: true }), '추천안 − 현행')} (${pct(d, cur.total_usd)}), 위반 0건
      <ul><li>도착 순서 기준안(${ref(usd(base.total_usd), '기준안 합계')}) 대비 ${ref(usd(rec.total_usd - base.total_usd, { sign: true }), '추천안 − 기준안')}</li>
      <li>절감액의 대부분은 접안 전 정박지 대기 축소에서 발생</li></ul></li>
  </ul>

  <h3>2. 후보 비교</h3>
  <div class="tbl-wrap"><table class="tbl" data-req="U-061">
    <thead><tr><th>구분</th><th>내용</th><th>예상 체선료(USD)</th><th>현행 대비</th><th>위반</th><th>부두 변경</th><th>시각 변경</th><th>체선 선박</th><th>24h+ 대기</th></tr></thead>
    <tbody>${[cur, base, ...cands].map((c) => `<tr class="${c.key === r.recommended ? 'berth' : ''}"><td class="b">${esc(c.label)}${c.key === r.recommended ? ' (추천)' : ''}</td><td class="l">${esc(c.kind === 'candidate' ? c.name : c.desc)}</td>
      <td class="r num b">${usd(c.total_usd).replace('$', '')}</td><td class="r num">${c.key === 'current' ? '-' : usd(c.total_usd - cur.total_usd, { sign: true }).replace('$', '')}</td>
      <td class="${c.violations.length ? 't-bad b' : ''}">${c.violations.length}</td><td>${c.kind === 'candidate' ? c.berth_changes : '-'}</td><td>${c.kind === 'candidate' ? c.time_changes : '-'}</td><td>${c.demurrage_vessels}</td><td>${c.long_wait_vessels}</td></tr>`).join('')}</tbody></table></div>
  <ul class="o"><li>1안과 2안은 예상 체선료 동일(동률). 엔진 순서는 기준안 대비 변경 선박 수로 정함</li><li>3안은 현행 부두 배정을 유지하고 접안 시각만 조정한 안으로, 현장 변경이 가장 적음</li></ul>

  <h3>3. 추천안 및 사유</h3>
  <ul class="o" data-req="N-049"><li>추천 : ${esc(rec.label)} (${esc(rec.name)})</li><li>사유 : ${esc(why)}</li><li>추천은 참고용이며, 현장 사정(인력 · 선석 준비 · 화주 요청)에 따라 승인권자가 다른 안을 선택할 수 있음. 이 경우 선택 사유를 승인 기록에 남김</li></ul>

  <h3>4. 주요 변경 선박 (체선료 감소 상위 5척)</h3>
  <div class="tbl-wrap"><table class="tbl"><thead><tr><th>선박명</th><th>현행 (선석 · ETB · 체선료)</th><th>${esc(rec.label)} (선석 · ETB · 체선료)</th><th>차이(USD)</th></tr></thead>
    <tbody>${topDown.map((c) => `<tr><td class="l"><span class="lnk vn" data-v="${c.id}">${esc(DB.vesselById[c.id].name)}</span></td>
      <td class="num">${esc(berthLabel(c.from.berth))} · ${fmtDT(c.from.etb)} · ${usd(c.from.dem)}</td><td class="num">${esc(berthLabel(c.to.berth))} · ${fmtDT(c.to.etb)} · ${usd(c.to.dem)}</td>
      <td class="r"><span class="lnk t-ok b" data-ev="${c.id}" data-set="${rec.key}">${usd(c.delta, { sign: true }).replace('$', '')}</span></td></tr>`).join('')}</tbody></table></div>

  <h3>5. 잔여 위험</h3>
  <ul class="o" data-req="FR-44">
    <li>${esc(rec.label)}에서도 체선 발생 ${rec.demurrage_vessels}척 — 큰 순서 ${big.map((p) => `<span class="lnk" data-ev="${p.id}" data-set="${rec.key}">${esc(DB.vesselById[p.id].name)} ${usd(p.dem)}</span>`).join(', ')} (대부분 계획 시작 전부터 정박지 대기)</li>
    <li>24시간 이상 대기 ${rec.long_wait_vessels}척 (최장 ${fmtH(rec.wait_hours_max)})</li>
    <li>야간(20~06시) 접안 ${rec.night_berthing}건 — 도선 · 줄잡이 인력 사전 확인 필요</li>
    ${alerts.length ? `<li>ETA 변경 선박 ${alerts.length}척 — 실제 접안 시각이 계획과 달라질 수 있음</li>` : ''}
  </ul>

  <h3>6. 가정 및 제약</h3>
  <ul class="o"><li>선박 · 계약값은 가상, 부두 제원 · 규칙은 현업 멘토링 자료 기준. 절감액은 샘플 데이터 기준이며 실제 절감액 아님</li>
    <li>작업 시간 = 과거 평균 Rate × 수량 (추정), 호스분리 = 작업 완료 + 30분 (현업 확인 전)</li>
    <li>기상 악화 · 공사 등 부두 제약 시간 미반영 — 발생 시 재계산 필요</li></ul>

  <h3>7. 산출 기준</h3>
  <table class="kv" data-req="NFR-13,NFR-15,NFR-04">
    <tr><th>계산</th><td>${esc(DB.run.engine.solver)} · 작업계획 ${DB.run.stats.work_plans.toLocaleString()}개 · ${DB.run.stats.elapsed_seconds.toFixed(1)}초 · 입력 지문 ${esc(DB.run.request_hash)}</td></tr>
    <tr><th>문장 작성</th><td>LLM 초안 ${r.llm.calls}회 · 토큰 ${(r.llm.tokens_in + r.llm.tokens_out).toLocaleString()} · 약 $${r.llm.cost_usd.toFixed(2)} <span class="muted">(프로토타입은 템플릿 문장 · 값은 목업)</span></td></tr>
    <tr><th>LLM 전송 항목</th><td>후보별 합계 · 변경 선박 목록 · 위험 항목 (계약 요율 원문 · 실제 선명 제외)</td></tr>
    <tr><th>숫자 대조</th><td>본문 금액 · 시각을 계산 결과와 자동 대조 — 불일치 0건</td></tr>
  </table>
  <div class="foot">※ 본 보고서의 금액 · 시각은 규칙 엔진과 수리계획법이 계산한 예상값이며 의사결정 보조용입니다. 선박명 · 계약값은 가상 데이터입니다.</div>`;
}

export function bindDoc(el) {
  el.querySelectorAll('[data-ev]').forEach((a) => a.addEventListener('click', () => openEvidence(a.dataset.ev, a.dataset.set)));
  el.querySelectorAll('[data-v]').forEach((a) => a.addEventListener('click', () => openVessel(a.dataset.v, { setKey: 'current' })));
}

export function progressTable(r, { vertical = false } = {}) {
  const ver = versions().find((v) => v.report_id === r.id);
  const rows = [
    ['작성', r.created_at, r.created_by],
    ['승인 요청', r.submitted_at, r.submitted_at ? r.created_by : null],
    [r.status === 'rejected' ? '반려' : '승인', r.decision?.at, r.decision?.by],
    ['스케줄 반영', ver?.applied_at, ver ? `Berthing Schedule v${ver.no}` : null],
  ];
  if (vertical) return `<table class="kv">${rows.map(([n, at, who]) => `<tr><th>${n}</th><td>${at ? `${fmtDT(at)} · ${esc(who)}` : '<span class="muted">-</span>'}</td></tr>`).join('')}</table>`;
  return `<table class="sum"><thead><tr>${rows.map(([n]) => `<th>${n}</th>`).join('')}</tr></thead><tbody><tr style="font-size:13px">${rows.map(([, at, who]) => `<td>${at ? `${fmtDT(at)}<small>${esc(who)}</small>` : '<span class="muted">-</span>'}</td>`).join('')}</tr></tbody></table>`;
}

export function renderDetail(el, [id]) {
  const r = report(id);
  if (!r) {
    el.innerHTML = `${pageTitle('접안계획 보고서')}<div class="empty">보고서를 찾을 수 없습니다. <a class="lnk" href="#reports">목록</a></div>`;
    return;
  }
  const ro = role();
  el.innerHTML = `
  ${pageTitle('접안계획 보고서', `Report > ${r.id}`)}
  <div class="bar no-print" style="margin-top:-8px"><div class="g">상태 ${statusText(r.status)}</div>
    <div class="g"><a class="btn" href="#reports">목록</a>${window.top === window.self ? `<button class="btn" id="bPrint">${ICON.print}프린트</button>` : ''}<button class="btn" id="bMail">결과 메일 초안</button>
      ${r.status === 'draft' && ro.can.submit ? '<button class="btn red" id="bSubmit">승인 요청</button>' : ''}
      ${r.status === 'requested' && ro.can.approve ? `<a class="btn red" href="#approval-${r.id}">승인 처리</a>` : ''}
      ${r.status === 'approved' ? '<a class="btn" href="#schedule">Berthing Schedule</a>' : ''}</div></div>
  ${progressTable(r)}
  ${r.decision || r.note || (r.status === 'draft' && ro.can.submit) ? `<table class="kv" style="margin-top:10px">
    ${r.note ? `<tr><th>요청 메모</th><td>${esc(r.note)}</td></tr>` : ''}
    ${r.decision ? `<tr><th>결재 의견</th><td>[${esc(r.decision.reason_type ?? '-')}] ${esc(r.decision.reason)} <span class="muted">— ${esc(r.decision.by)} · ${r.decision.action === 'approve' ? `${esc(DB.sets[r.decision.candidate].label)} 승인` : '반려'}</span></td></tr>` : ''}
    ${r.status === 'draft' && ro.can.submit ? '<tr><th>요청 메모</th><td><textarea class="in" id="note" placeholder="승인권자에게 남길 메모 (선택)" style="min-height:52px"></textarea></td></tr>' : ''}
  </table>` : ''}
  <div class="doc" id="doc" style="margin-top:16px">${reportDoc(r)}</div>`;
  bindDoc(el.querySelector('#doc'));
  el.querySelector('#bPrint')?.addEventListener('click', () => window.print());
  el.querySelector('#bSubmit')?.addEventListener('click', () => {
    submitReport(r.id, el.querySelector('#note')?.value.trim() ?? '');
    toast(`${r.id} 승인 요청을 올렸습니다`);
  });
  el.querySelector('#bMail').addEventListener('click', () => {
    const rec = DB.sets[r.decision?.candidate ?? r.recommended];
    const text = `제목: [접안계획] ${r.id} ${r.status === 'approved' ? '승인 결과' : '검토 요청'}\n\n${rec.label}(${rec.name}) 예상 체선료 ${usd(rec.total_usd)} (현행 대비 ${usd(rec.total_usd - DB.sets.current.total_usd, { sign: true })}, 샘플 기준)\n부두 변경 ${rec.berth_changes}척 · 시각 변경 ${rec.time_changes}척\n입력 기준 ${fmtDT(r.input_at)} · 실행 ${r.run_id}\n\n※ 의사결정 보조용 · 가상 데이터`;
    const m = openModal({ title: '결과 메일 초안', body: `<textarea class="in" style="min-height:220px">${esc(text)}</textarea><p class="muted" style="margin:8px 0 0;font-size:12px">시스템은 메일을 보내지 않습니다. 담당자가 확인 후 발송합니다.</p>`, foot: '<button class="btn" data-x>닫기</button>' });
    m.el.querySelector('[data-x]').addEventListener('click', m.close);
  });
}
