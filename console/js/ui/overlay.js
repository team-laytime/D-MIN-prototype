// 오른쪽 서랍 · 모달 · 토스트
import { esc } from '../core/fmt.js';

let drawerEl = null;

/** 서랍을 연다. 화면을 옮기지 않고 옆에서 연다 (U-033) */
export function openDrawer({ title, sub = '', body = '', foot = '', wide = false, onClose } = {}) {
  closeDrawer();
  const back = document.createElement('div');
  back.className = 'drawer-back';
  const el = document.createElement('aside');
  el.className = `drawer ${wide ? 'wide' : ''}`;
  el.innerHTML = `<div class="dh"><h2>${title}</h2><button class="x" aria-label="닫기">×</button></div>${sub ? `<div class="s">${sub}</div>` : ''}
    <div class="db">${body}</div>${foot ? `<div class="df">${foot}</div>` : ''}`;
  document.body.append(back, el);
  const close = () => closeDrawer();
  back.addEventListener('click', close);
  el.querySelector('.x').addEventListener('click', close);
  drawerEl = { back, el, onClose };
  document.addEventListener('keydown', escClose);
  return el;
}

function escClose(e) {
  if (e.key === 'Escape') closeDrawer();
}

export function closeDrawer() {
  if (!drawerEl) return;
  drawerEl.back.remove();
  drawerEl.el.remove();
  const cb = drawerEl.onClose;
  drawerEl = null;
  document.removeEventListener('keydown', escClose);
  cb?.();
}

/** 서랍 본문만 바꾼다 (선박 카드 → 계산 근거) */
export function setDrawer({ title, sub, body, foot }) {
  if (!drawerEl) return null;
  const el = drawerEl.el;
  if (title != null) el.querySelector('.dh h2').innerHTML = title;
  if (sub != null) {
    let s = el.querySelector(':scope > .s');
    if (!s) {
      s = document.createElement('div');
      s.className = 's';
      el.querySelector('.dh').after(s);
    }
    s.innerHTML = sub;
  }
  if (body != null) el.querySelector('.db').innerHTML = body;
  if (foot != null) {
    let f = el.querySelector('.df');
    if (!f) {
      f = document.createElement('div');
      f.className = 'df';
      el.append(f);
    }
    f.innerHTML = foot;
  }
  el.querySelector('.db').scrollTop = 0;
  return el;
}

export function openModal({ title, body, foot = '', width } = {}) {
  const back = document.createElement('div');
  back.className = 'modal-back';
  back.innerHTML = `<div class="modal" role="dialog" aria-modal="true" ${width ? `style="width:${width}px"` : ''}>
    <div class="mh"><h2>${title}</h2><button class="x" aria-label="닫기">×</button></div>
    <div class="mb">${body}</div>${foot ? `<div class="mf">${foot}</div>` : ''}</div>`;
  document.body.append(back);
  const close = () => back.remove();
  back.querySelector('.x').addEventListener('click', close);
  back.addEventListener('mousedown', (e) => {
    if (e.target === back) close();
  });
  return { el: back.querySelector('.modal'), close };
}

export function toast(msg, link) {
  const box = document.getElementById('toasts');
  const t = document.createElement('div');
  t.className = 'toast';
  t.innerHTML = esc(msg) + (link ? `<a href="${link.href}">${esc(link.text)}</a>` : '');
  box.append(t);
  setTimeout(() => t.remove(), 6000);
}
