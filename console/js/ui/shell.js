// 화면 틀 — SK Seagate 항무 웹사이트 모양: 상단 링크줄 · 흰 헤더(로고 · 가운데 메뉴 · 알약 버튼) · 대문자 왼쪽 트리 · 어두운 바닥글
import { esc } from '../core/fmt.js';
import { state, update, role, ROLES, resetStore } from '../core/store.js';
import { pendingApprovals, etaAlerts } from '../core/api.js';
import { openModal } from './overlay.js';

// [구역, GNB 이름, LNB 이름, 첫 화면, 항목]. 항목 = [경로, 이름] 또는 ['grp', 묶음 이름, 하위 항목]
export const MENU = [
  ['dash', 'Dashboard', 'DASHBOARD', '#dashboard', [['#dashboard', '운영 현황']]],
  ['vessel', 'Vessel', 'VESSEL', '#vessels-map', [['#vessels-map', 'AIS'], ['#vessels-list', '입항 예정 선박']]],
  ['berth', 'Berth Planning', 'BERTH PLANNING', '#schedule', [
    ['grp', 'Ship Berthing', [['#schedule', 'Berthing Schedule'], ['#plan', 'Berth Optimization'], ['#changes', 'ETB Change Log']]],
  ]],
  ['report', 'Report', 'REPORT', '#reports', [['#reports', '접안계획 보고서']]],
  ['admin', 'Admin', '관리자메뉴', '#approvals', [['#approvals', '승인 관리'], ['#history', '승인 이력']]],
];

const SECTION_OF = {
  dashboard: 'dash', 'vessels-map': 'vessel', 'vessels-list': 'vessel', schedule: 'berth', plan: 'berth', changes: 'berth',
  reports: 'report', report: 'report', approvals: 'admin', approval: 'admin', history: 'admin',
};
export function sectionOf(hash) {
  const name = hash.replace(/^#/, '');
  return SECTION_OF[name] ?? SECTION_OF[name.split('-')[0]] ?? 'dash';
}
const isOn = (p, h) => h === p || (p === '#reports' && h.startsWith('#report-')) || (p === '#approvals' && h.startsWith('#approval-'));

const SITEMAP_ICON = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="6" y="1.5" width="4" height="3"/><rect x="1.5" y="11" width="4" height="3"/><rect x="10.5" y="11" width="4" height="3"/><path d="M8 4.5V8M3.5 11V8h9v3"/></svg>';

export function renderShell(root) {
  root.innerHTML = `
  <div class="util">
    <span class="who" id="uWho"></span>
    <button id="uReset" title="결재 · 보고서 · 적용 계획을 처음 상태로 돌립니다">시연 초기화</button>
    <a href="#dashboard">Home</a>
  </div>
  <header class="hd">
    <a class="logo" href="#dashboard"><b>Berth</b><span>Desk</span></a>
    <nav class="gnb" id="gnb">${MENU.map(([id, g, , href]) => `<a data-sec="${id}" href="${href}">${esc(g)}</a>`).join('')}</nav>
    <div class="tools">
      <select class="pill-sel" id="uRole" title="사용자 (시연용 · 실제로는 로그인 계정)">
        ${Object.values(ROLES).map((r) => `<option value="${r.id}">${esc(r.name)}</option>`).join('')}
      </select>
      <button class="pill-btn" id="uMap">${SITEMAP_ICON}사이트맵</button>
    </div>
  </header>
  <div class="frame" id="frame">
    <aside class="lnb" id="lnb"></aside>
    <main class="content" id="page"></main>
  </div>
  <footer class="ft" data-req="NFR-08,N-314">
    <div class="flogo">Berth Desk</div>
    <div>
      <div class="links"><a href="#dashboard">개인정보처리방침</a><i>|</i><a href="#dashboard">이용안내</a><i>|</i><a href="#dashboard">관련 사이트</a><i>|</i><a href="#" id="fMap">사이트맵</a></div>
      <p>울산 CLX 액체부두 접안 계획 · 체선료 관리 (프로토타입) — 선박명 · MMSI · 계약값은 가상 데이터이며, 화면의 금액은 의사결정 보조용 예상값입니다.</p>
      <p>부두 제원 · 계산 규칙: 현업 멘토링 자료(Sample data) · 팀 규칙 표 ulsan-clx/ppt-v1 · 지도 © OpenStreetMap contributors</p>
    </div>
  </footer>`;

  const sel = root.querySelector('#uRole');
  sel.value = state().role;
  sel.addEventListener('change', () => update((s) => (s.role = sel.value)));
  root.querySelector('#uReset').addEventListener('click', confirmReset);
  root.querySelector('#uMap').addEventListener('click', sitemap);
  root.querySelector('#fMap').addEventListener('click', (e) => (e.preventDefault(), sitemap()));
  // 검토용 요구사항 번호 표시: 주소에 ?review=1
  document.body.classList.toggle('show-req', new URLSearchParams(location.search).has('review'));
}

function confirmReset() {
  const m = openModal({
    title: '시연 초기화',
    body: '<p style="margin:0;line-height:1.7">결재 · 보고서 · 적용 계획 버전을 처음 상태로 돌립니다.<br>이 브라우저에만 저장된 시연 상태입니다.</p>',
    foot: '<button class="btn" data-x>취소</button><button class="btn red" data-ok>초기화</button>',
    width: 420,
  });
  m.el.querySelector('[data-x]').addEventListener('click', m.close);
  m.el.querySelector('[data-ok]').addEventListener('click', () => {
    m.close();
    resetStore();
    location.hash = '#dashboard';
  });
}

function sitemap() {
  const m = openModal({
    title: '사이트맵',
    width: 760,
    body: `<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:18px">${MENU.map(([, g, , , items]) => `
      <div><div style="font-weight:700;border-bottom:2px solid #3d4a5c;padding-bottom:6px;margin-bottom:8px">${esc(g)}</div>
      ${items.map((it) => (it[0] === 'grp' ? it[2] : [it]).map(([p, n]) => `<a href="${p}" data-close style="display:block;padding:4px 0;color:#555">${esc(n)}</a>`).join('')).join('')}</div>`).join('')}</div>`,
  });
  m.el.querySelectorAll('[data-close]').forEach((a) => a.addEventListener('click', m.close));
}

export function renderNav(hash) {
  const sec = sectionOf(hash);
  const h = hash.split('?')[0];
  document.querySelectorAll('#gnb a').forEach((a) => a.classList.toggle('on', a.dataset.sec === sec));
  const r = role();
  document.getElementById('uWho').innerHTML = `<b>${esc(r.name)}</b>(${esc(r.title)})님`;
  const pend = pendingApprovals().length;
  const alerts = etaAlerts().length;
  const cnt = (n) => (n ? `<span class="cnt">${n}</span>` : '');
  document.getElementById('lnb').innerHTML = MENU.map(([id, , lname, href, items]) => {
    if (id === 'admin' && !r.can.approve) return `<div class="lsec off"><div class="lh" title="승인권자만 사용할 수 있습니다">${esc(lname)}<span class="pm">+</span></div></div>`;
    const open = id === sec;
    const body = items.map((it) => {
      if (it[0] === 'grp') {
        return `<div class="li on" style="font-weight:600">${esc(it[1])}<span class="pm" style="background:var(--brand)">−</span></div>` +
          it[2].map(([p, n]) => `<a class="lsub ${isOn(p, h) ? 'on' : ''}" href="${p}">${esc(n)}${p === '#plan' && alerts ? ` <span class="t-bad">(${alerts})</span>` : ''}</a>`).join('');
      }
      const [p, n] = it;
      const extra = p === '#approvals' ? cnt(pend) : '';
      return `<a class="li ${isOn(p, h) ? 'on' : ''}" href="${p}">${esc(n)}${extra}</a>`;
    }).join('');
    return `<div class="lsec ${open ? 'on' : ''}"><div class="lh" data-href="${href}">${esc(lname)}<span class="pm">${open ? '−' : '+'}</span></div><div class="lb">${body}</div></div>`;
  }).join('');
  document.querySelectorAll('#lnb .lh[data-href]').forEach((el) => el.addEventListener('click', () => (location.hash = el.dataset.href)));
}

export function setWide(on) {
  document.getElementById('frame').classList.toggle('wide', on);
}

/** 화면 제목 (SK Seagate 모양: 큰 제목 + 얇은 밑줄) */
export const pageTitle = (title, loc = '') => `<div class="ptitle"><h1>${esc(title)}</h1>${loc ? `<span class="loc">${esc(loc)}</span>` : ''}</div>`;
/** 소제목 (부산항 정보조회서비스 모양: 굵은 제목 + 회색 한 줄 설명) */
export const secTitle = (title, desc = '', right = '') => `<div class="stitle"><h2>${title}</h2>${desc ? `<p>${desc}</p>` : ''}${right ? `<div class="r">${right}</div>` : ''}</div>`;
