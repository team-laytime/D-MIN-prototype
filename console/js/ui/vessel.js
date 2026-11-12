// 선박 카드 — 울산항만공사 PortWise 선박 카드 구성(AIS 실시간 위치 · Port-MIS 신고 · 업데이트 시간 · 제원 그림 ·
// 국적/선박명/MMSI/호출부호/선박 타입/위치/시설 사용 표 · 출발지 → 목적지 · Status/Speed/Course · 아래 버튼)에
// 접안 계획과 예상 체선료를 더했다. 아래 버튼은 '체선료 산출 근거'.
import { DB, berthLabel, setLabel } from '../core/data.js';
import { esc, usd } from '../core/fmt.js';
import { fmtDT, fmtAgo, fmtH, fmtDiff, nowMs, H, MIN } from '../core/time.js';
import { aisOf } from '../core/ais.js';
import { appliedVersion, appliedSet, displaySet, ETA_ALERT_H } from '../core/api.js';
import { openDrawer, setDrawer } from './overlay.js';

const STEP = {
  P13: '도착 (ETANR)', P7: '접안 (ETB)', P8: '접안 (ETB)', P9: '작업 시작', P10: '작업 완료', P11: '호스분리', P12: '이안 (ETU)',
  P14: '정박개시', P15: '정박개시', P16: '정박종료', P17: '기상 공제', P18: '체선 시간', P19: '체선료',
};
const ORDER = ['P13', 'P7', 'P8', 'P9', 'P10', 'P11', 'P12', 'P14', 'P15', 'P16', 'P17', 'P18', 'P19'];
const yy = (ms) => `${String(new Date(ms).getUTCFullYear()).slice(2)}-${fmtDT(ms).replace('/', '-')}`;
const full = (ms) => `${new Date(ms).getUTCFullYear()}-${fmtDT(ms).replace('/', '-')}`;
const pmisState = (ais, v) => (v.prev && nowMs() >= v.prev.etuMs ? '출항' : ais.nav === 'moored' ? '접안' : ais.nav === 'anchored' ? '입항 (정박)' : '입항 예정');

function shipPanel(v) {
  return `<div class="vc-ship">
    <span class="d" style="left:14px;top:12px">톤수 ${Number(v.grt).toLocaleString()}t</span><span class="d" style="right:14px;top:12px">흘수 ${v.draft}m</span>
    <span class="d" style="left:14px;top:36px">길이 ${v.loa}m</span><span class="d" style="right:14px;top:36px">폭 ${v.beam}m</span>
    <svg viewBox="0 0 400 70" height="70"><rect y="44" width="400" height="26" fill="#5b8fd1"/>
      <path d="M70 30 H318 Q338 33 346 44 Q338 56 318 58 H86 Q72 52 70 44 Z" fill="#2b9a49"/><path d="M74 44 H344 Q338 56 318 58 H86 Q76 53 74 44 Z" fill="#1f7a37"/>
      <rect x="84" y="14" width="36" height="16" fill="#f2f3f5"/><rect x="88" y="18" width="28" height="3" fill="#30486c"/><rect x="92" y="6" width="10" height="8" fill="#d6202f"/>
      <rect x="130" y="27" width="170" height="3" fill="#d9c27a"/></svg>
  </div>`;
}

function cardHTML(v, plan, set, ais) {
  const diff = v.ais.etaMs - v.etaMs;
  const alert = Math.abs(diff) >= ETA_ALERT_H * H && ais.nav === 'underway';
  const ver = appliedVersion();
  const reqBerth = DB.sets.current.byId[v.id]?.berth ?? v.prev?.berth;
  const allot = v.prev ? v.prev.berth : ver.no > 1 ? appliedSet().byId[v.id]?.berth : null;
  const stale = nowMs() - ais.updatedAt > 10 * MIN;
  const navShort = { moored: '계류', anchored: '정박', underway: '항해(동력)', departed: '항해(출항)' }[ais.nav];
  const use = ais.nav === 'moored' ? `${esc(berthLabel(ais.berth))} 사용 중 (${fmtDT(v.prev?.etbMs ?? v.fix?.etbMs ?? plan?.etb)} ~)` : v.prev && nowMs() >= v.prev.etuMs ? `${esc(berthLabel(v.prev.berth))} 사용 끝 (${fmtDT(v.prev.etuMs)} 이안)` : '-';
  return `
  <div class="vc-two">
    <div>AIS 실시간 위치<b>위치 : ${esc(ais.where)}</b>ETA : ${yy(v.ais.etaMs)}</div>
    <div>Port-MIS 신고<b>${pmisState(ais, v)}</b>ETA : ${yy(v.etaMs)}</div>
  </div>
  <div class="vc-upd" data-req="N-001">업데이트 시간 : ${full(ais.updatedAt)}:${String(Math.floor((ais.updatedAt / 1000) % 60)).padStart(2, '0')}${stale ? ' <span class="t-warn">(위성 수신 · 지연)</span>' : ''}</div>
  ${shipPanel(v)}
  <div class="vc-act" data-req="N-002">${alert ? `<span class="t-bad b">AIS ETA ${fmtDiff(diff)} — 계획 재계산 필요</span>` : `<span class="muted">AIS ETA ${Math.abs(diff) < MIN ? '계획 입력과 같음' : `${fmtDiff(diff)} (허용 범위)`}</span>`}
    ${plan ? '<button class="btn sm" data-ev>체선료 산출 근거</button>' : ''}</div>
  <table class="kv">
    <tr><th>국적</th><td>${esc(v.flag)}</td></tr>
    <tr><th>선박명</th><td>${esc(v.name)} <span class="muted">(가상 선명)</span></td></tr>
    <tr><th>MMSI</th><td>${esc(v.mmsi)}</td></tr>
    <tr><th>IMO · 호출부호</th><td>${esc(v.imo)} · ${esc(v.call_sign)}</td></tr>
    <tr><th>선박 타입</th><td>${esc(v.type)} <span class="muted">(AIS ${v.ais_type})</span></td></tr>
    <tr><th>선박 위치</th><td class="num">${ais.lat.toFixed(5)}, ${ais.lng.toFixed(5)}</td></tr>
    <tr><th>DWT</th><td>${Number(v.dwt).toLocaleString()} t</td></tr>
    <tr><th>화물</th><td>${esc(v.biz_kr)} · ${esc(v.product)} (${esc(v.product_kr)}) · ${Number(v.qty_bbl).toLocaleString()} BBL</td></tr>
    <tr><th>시설 신청</th><td>${esc(berthLabel(reqBerth))} <span class="muted">(입항 ${v.port_mis.year} · 항차 ${esc(v.port_mis.voyage)})</span></td></tr>
    <tr><th>시설 배정</th><td>${allot ? `${esc(berthLabel(allot))} <span class="muted">(${v.prev ? '이전 계획 확정' : `계획 v${ver.no} 승인`})</span>` : '<span class="muted">배정 대기</span>'}</td></tr>
    <tr><th>시설 사용</th><td>${use}</td></tr>
    ${plan && !plan.inport ? `<tr><th>접안 계획</th><td>${esc(berthLabel(plan.berth))} · ETB ${fmtDT(plan.etb)} → ETU ${fmtDT(plan.etu)}<br><span class="muted">${esc(set === appliedSet() ? `적용 계획 v${ver.no}` : setLabel(set.key))}${plan.wait > 0 ? ` · 접안 전 대기 ${fmtH(plan.wait)}` : ''}</span></td></tr>
    <tr><th>예상 체선료</th><td><b class="${plan.dem > 0 ? 't-bad' : 't-ok'}">${usd(plan.dem, { cents: true })}</b> <span class="muted">(체선 ${fmtH(plan.demH, 2)} · 일 ${usd(v.contract.rate_usd_day)})</span>${set.violById?.[v.id] ? `<br><span class="t-bad">규칙 위반: ${esc(set.violById[v.id].join(' / '))}</span>` : ''}</td></tr>` : ''}
    ${plan?.inport ? `<tr><th>접안 계획</th><td>이전 계획 확정분 — 이번 계획 대상 아님<br><span class="muted">이안 예정 ${fmtDT(plan.etu)}</span></td></tr>` : ''}
  </table>
  <div class="vc-route"><div>출발지<b>${esc(v.ais.prev_port)}</b></div><span class="arr">→</span><div style="text-align:right">목적지<b>${esc(v.ais.destination_text)}</b></div></div>
  <div class="vc-three"><div>Status<b>${navShort}</b></div><div>Speed<b>${ais.sog.toFixed(1)}kn</b></div><div>Course<b>${ais.cog}°</b></div></div>
  ${plan && !plan.inport ? '<button class="vc-btn" data-ev>체선료 산출 근거 보기</button>' : ''}`;
}

/** 선박 카드 열기. setKey가 있으면 그 계획(후보)의 줄로 보여 준다 */
export function openVessel(id, { setKey } = {}) {
  const v = DB.vesselById[id];
  if (!v) return;
  const set = setKey ? DB.sets[setKey] : displaySet();
  const plan = set.byId[id] ?? null;
  const ais = aisOf(v, displaySet().byId[id] ?? null);
  const head = `<span style="color:#b9bdc3;margin-right:4px">★</span>${esc(v.name)}`;
  const el = openDrawer({ title: head, body: cardHTML(v, plan, set, ais), foot: '출처: AIS(해양수산부 T-AIS · S-AIS, 목적지 · ETA는 선장 입력) · Port-MIS(입출항 · 시설사용) · 계약 DB · 계산 엔진 — 프로토타입 값은 가상입니다.' });
  const bind = () => el.querySelectorAll('[data-ev]').forEach((b) => b.addEventListener('click', () => {
    setDrawer({ title: `${esc(v.name)} — 체선료 산출 근거`, body: `<button class="btn sm" data-back style="margin-bottom:10px">← 선박 정보</button>${evidenceHTML(v, plan, set)}` });
    el.querySelector('[data-back]').addEventListener('click', () => {
      setDrawer({ title: head, body: cardHTML(v, plan, set, ais) });
      bind();
    });
  }));
  bind();
}

/** 체선료 산출 근거 (도착 → 접안 → 작업 → 호스분리 → 정박개시 → 정박종료 → 체선 → 금액) */
export function evidenceHTML(v, plan, set) {
  const rate = v.contract.rate_usd_day;
  const steps = [...plan.trace].sort((a, b) => ORDER.indexOf(a.rule) - ORDER.indexOf(b.rule));
  const check = Math.round(((plan.demH * rate) / 24) * 100) / 100;
  const t0 = Math.min(plan.eta ?? plan.etb, plan.ls) - 2 * H;
  const t1 = Math.max(plan.hose, plan.le, plan.etu) + 2 * H;
  const X = (ms) => `${(2 + ((ms - t0) / (t1 - t0)) * 96).toFixed(2)}%`;
  const W = (a, b) => `${Math.max(0.4, ((b - a) / (t1 - t0)) * 96).toFixed(2)}%`;
  const ds = plan.le + (plan.deductH || 0) * H;
  return `
  <table class="kv" data-req="NFR-02">
    <tr><th>계획</th><td>${esc(setLabel(set.key))} · 실행 ${esc(DB.run.run_id)}</td></tr>
    <tr><th>부두 · 접안</th><td>${esc(berthLabel(plan.berth))} · ETB ${fmtDT(plan.etb)} → ETU ${fmtDT(plan.etu)}</td></tr>
    <tr><th>정박 시간</th><td>${fmtDT(plan.ls)} ~ ${fmtDT(plan.le)} (허용 ${plan.allowed}h)</td></tr>
    <tr><th>체선</th><td><b class="${plan.dem > 0 ? 't-bad' : 't-ok'}">${fmtH(plan.demH, 2)} · ${usd(plan.dem, { cents: true })}</b></td></tr>
  </table>
  <div class="vc-sec">시간 흐름 <small>점선 대기 · 파랑 작업 · 초록 허용 정박시간 · 빨강 체선</small></div>
  <div class="tl"><div class="ax"></div>
    ${plan.eta < plan.etb ? `<div class="sg wait" style="left:${X(plan.eta)};width:${W(plan.eta, plan.etb)}"></div>` : ''}
    <div class="sg prep" style="left:${X(plan.etb)};width:${W(plan.etb, plan.ws)}"></div><div class="sg work" style="left:${X(plan.ws)};width:${W(plan.ws, plan.we)}"></div><div class="sg prep" style="left:${X(plan.we)};width:${W(plan.we, plan.hose)}"></div>
    <div class="sg lay" style="left:${X(plan.ls)};width:${W(plan.ls, plan.le)}"></div>${plan.demH > 0 ? `<div class="sg dem" style="left:${X(ds)};width:${W(ds, plan.hose)}"></div>` : ''}
    <span class="tk" style="left:${X(plan.eta)}">ETA ${fmtDT(plan.eta).slice(6)}</span><span class="tk" style="left:${X(plan.hose)}">호스분리 ${fmtDT(plan.hose).slice(6)}</span>
    <span class="tk b" style="left:${X(plan.ls)}">정박개시</span><span class="tk b" style="left:${X(plan.le)}">정박종료 ${fmtDT(plan.le).slice(6)}</span></div>
  <div class="vc-sec">산출 순서 <small>규칙 번호 = 규칙 표 · 정답 사례 번호</small></div>
  <table class="calc" data-req="NFR-06,U-034"><thead><tr><th style="width:34px">No</th><th style="width:44px">규칙</th><th style="width:96px">항목</th><th>내용</th></tr></thead>
    <tbody>${steps.map((s, i) => `<tr><td style="text-align:center">${i + 1}</td><td class="rid">${esc(s.rule)}</td><td class="it">${esc(STEP[s.rule] ?? s.rule)}</td><td>${esc(s.text)}</td></tr>`).join('')}</tbody></table>
  <div class="formula" data-req="NFR-07">체선료 = 체선 시간 ${plan.demH}h × 일 체선료 ${usd(rate, { cents: true })} ÷ 24<br>
    <span class="res ${plan.dem > 0 ? 't-bad' : 't-ok'}">= ${usd(plan.dem, { cents: true })}</span> <span class="muted">(검산 ${usd(check, { cents: true })} ${Math.abs(check - plan.dem) < 0.011 ? '일치' : '불일치'})</span></div>
  <table class="kv">
    <tr><th>ETA</th><td>${fmtDT(v.etaMs)} <span class="muted">(계획 입력)</span> · ${fmtDT(v.ais.etaMs)} <span class="muted">(AIS)</span></td></tr>
    <tr><th>Laycan · Laytime</th><td>${fmtDT(v.contract.from)} ~ ${fmtDT(v.contract.to)} · ${v.contract.laytime_h}h <span class="muted">(계약)</span></td></tr>
    <tr><th>작업 시간</th><td>${v.work_hours}h <span class="muted">(추정 · 과거 평균 Rate × 수량)</span></td></tr>
    <tr><th>ETB를 정한 조건</th><td>${esc(plan.why)}</td></tr>
    <tr><th>계산 기준</th><td>규칙 ${esc(DB.run.engine.rules_version)} · 엔진 ${esc(DB.run.engine.version)} · LLM 사용 안 함</td></tr>
  </table>`;
}

/** 금액을 누르면 곧바로 산출 근거를 연다 */
export function openEvidence(id, setKey) {
  const v = DB.vesselById[id];
  const set = DB.sets[setKey] ?? appliedSet();
  const plan = set.byId[id];
  if (!plan) return;
  openDrawer({ title: `${esc(v.name)} — 체선료 산출 근거`, body: evidenceHTML(v, plan, set), wide: true, foot: '화면 · 보고서 · 메일의 금액은 모두 이 계산 결과를 참조합니다 (NFR-04).' });
}

export const fmtAgoExport = fmtAgo;
