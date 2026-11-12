// 시작: 데이터 불러오기 → 화면 틀 → 해시 라우팅
import { loadData } from './core/data.js';
import { initStore, onChange, state } from './core/store.js';
import { renderShell, renderNav, setWide } from './ui/shell.js';
import { closeDrawer } from './ui/overlay.js';
import * as dashboard from './pages/dashboard.js';
import * as vessels from './pages/vessels.js';
import * as schedule from './pages/schedule.js';
import * as plan from './pages/plan.js';
import * as changes from './pages/changes.js';
import * as reports from './pages/reports.js';
import * as approvals from './pages/approvals.js';

// 주소 해시는 '#plan'처럼 단순한 이름만 쓴다 (공유 링크 · 아티팩트 화면에서도 그대로 넘어가도록)
const ROUTES = [
  [/^#dashboard$/, dashboard.render],
  [/^#vessels-map$/, vessels.renderMap],
  [/^#vessels-list$/, vessels.renderList],
  [/^#schedule$/, schedule.render],
  [/^#plan$/, plan.render],
  [/^#changes$/, changes.render],
  [/^#reports$/, reports.renderList],
  [/^#report-([\w-]+)$/, reports.renderDetail],
  [/^#approvals$/, approvals.renderQueue],
  [/^#approval-([\w-]+)$/, approvals.renderDetail],
  [/^#history$/, approvals.renderHistory],
];

let cleanup = null;

async function route() {
  const hash = location.hash || '#dashboard';
  const path = hash.split('?')[0];
  const query = new URLSearchParams(hash.split('?')[1] || '');
  closeDrawer();
  if (typeof cleanup === 'function') cleanup();
  cleanup = null;
  setWide(false);
  renderNav(path);
  const page = document.getElementById('page');
  const hit = ROUTES.find(([re]) => re.test(path));
  if (!hit) {
    location.hash = '#dashboard';
    return;
  }
  const params = path.match(hit[0]).slice(1);
  page.innerHTML = '';
  window.scrollTo(0, 0);
  try {
    cleanup = await hit[1](page, params, query);
  } catch (err) {
    console.error(err);
    page.innerHTML = `<div class="notice red"><div class="grow"><b>화면을 그리지 못했습니다.</b> ${String(err.message || err)}</div></div>`;
  }
}

async function boot() {
  const app = document.getElementById('app');
  try {
    await loadData();
  } catch (err) {
    app.innerHTML = `<div class="empty-state">데이터를 불러오지 못했습니다: ${String(err.message || err)}<br>로컬 서버(예: <code>python3 -m http.server</code>)로 열어 주세요.</div>`;
    return;
  }
  initStore();
  renderShell(app);
  window.addEventListener('hashchange', route);
  // 역할을 바꾸거나 승인하면 메뉴(배지 · 권한)와 지금 화면을 다시 그린다
  const sigOf = (s) => JSON.stringify({ role: s.role, v: s.versions.length, r: s.reports.map((x) => x.id + x.status).join() });
  let last = sigOf(state());
  onChange((s) => {
    const sig = sigOf(s);
    if (sig !== last) {
      last = sig;
      route();
    }
  });
  route();
}

boot();
