// ===== shared runtime for deterministic frame rendering =====
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const easeOut = p => 1 - Math.pow(1 - p, 3);
const easeInOut = p => p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
function seg(lt, start, dur = 0.6) { return easeOut(clamp((lt - start) / dur, 0, 1)); }
function lin(lt, start, dur) { return clamp((lt - start) / dur, 0, 1); }
function rv(el, k, dy = 14) { if (!el) return; el.style.opacity = k; el.style.transform = `translateY(${(1 - k) * dy}px)`; }
function pad(n) { return String(n).padStart(2, '0'); }
function fmtUSD(x) { return '$' + Math.round(x).toLocaleString('en-US'); }
function fmtT(t) { let d = Math.floor(t / 24), h = t - d * 24, hh = Math.floor(h + 1e-9), mm = Math.round((h - hh) * 60); if (mm === 60) { mm = 0; hh++; } if (hh === 24) { hh = 0; d++; } return `D${d + 1} ${pad(hh)}:${pad(mm)}`; }
function fmtH(h) { h = Math.max(0, h); let hh = Math.floor(h + 1e-9), mm = Math.round((h - hh) * 60); if (mm === 60) { mm = 0; hh++; } return `${hh}h ${pad(mm)}m`; }
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const C = { bg: '#0d1218', surface: '#151c25', surface2: '#1d2631', fg: '#e6ecf3', muted: '#97a5b4', line: '#293441', line2: '#3a4756', accent: '#4fcfc3', blue: '#3987e5', blueSoft: '#1c5cab', red: '#d03b3b', orange: '#ec835a', notice: '#48545f', excl: '#6c7a8a', night: 'rgba(255,255,255,0.06)', prior: '#4e5a67', warn: '#fab219' };

// A horizontal time track drawn into an <svg>. Items are drawn in order.
class Track {
  constructor(svg, o = {}) {
    this.svg = svg;
    Object.assign(this, { hours: 48, offset: 0, night: false, dayStart: 7, dayEnd: 17.5, left: 110, right: 1130, axisY: 26, labelStep: 6, height: 190, labelEvery: 12 }, o);
  }
  x(t) { return this.left + (t - this.offset) / this.hours * (this.right - this.left); }
  render(items, emph = null) {
    const { left: L, right: R } = this;
    let s = `<defs><pattern id="hatch" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)"><rect width="8" height="8" fill="${C.surface2}"/><line x1="0" y1="0" x2="0" y2="8" stroke="${C.excl}" stroke-width="3"/></pattern></defs>`;
    if (this.night) {
      const a = this.offset, b = this.offset + this.hours;
      for (let d = Math.floor(a / 24) - 1; d <= Math.floor(b / 24) + 1; d++) {
        const n0 = Math.max(a, d * 24 + this.dayEnd), n1 = Math.min(b, (d + 1) * 24 + this.dayStart);
        if (n1 > n0) s += `<rect x="${this.x(n0)}" y="${this.axisY}" width="${this.x(n1) - this.x(n0)}" height="${this.height - this.axisY}" fill="${C.night}"/>`;
      }
    }
    const step = this.labelStep;
    for (let h = Math.ceil(this.offset / step) * step; h <= this.offset + this.hours + 1e-9; h += step) {
      const x = this.x(h), major = ((h % 24) + 24) % 24 === 0;
      s += `<line x1="${x}" y1="${this.axisY}" x2="${x}" y2="${this.height}" stroke="${major ? C.line2 : C.line}" stroke-width="${major ? 1.5 : 1}"/>`;
      if (((h % this.labelEvery) + this.labelEvery) % this.labelEvery === 0 && h < this.offset + this.hours - 1e-9) s += `<text x="${x + 5}" y="${this.axisY - 8}" fill="${C.muted}" font-size="13" class="mono">${fmtT(h)}</text>`;
    }
    for (const it of items) {
      const op = emph && it.key && !emph.includes(it.key) ? 0.3 : (it.opacity ?? 1);
      s += `<g opacity="${op}">`;
      if (it.type === 'rowlabel') { s += `<text x="${L - 12}" y="${it.y + 5}" text-anchor="end" fill="${it.color || C.fg}" font-size="${it.size || 16}" font-weight="600">${esc(it.text)}</text>`; if (it.sub) s += `<text x="${L - 12}" y="${it.y + 24}" text-anchor="end" fill="${C.muted}" font-size="12">${esc(it.sub)}</text>`; }
      if (it.type === 'bar' || it.type === 'hatch') {
        const x0 = this.x(it.from), x1 = this.x(Math.max(it.from, it.to)); if (x1 - x0 > 0.01) {
          s += `<rect x="${x0}" y="${it.y}" width="${x1 - x0}" height="${it.h || 32}" rx="${it.rx ?? 4}" fill="${it.type === 'hatch' ? 'url(#hatch)' : it.fill}"/>`;
          if (it.label && x1 - x0 > (it.minLabel || 40)) s += `<text x="${x0 + 8}" y="${it.y + (it.h || 32) / 2 + 5}" fill="${it.labelColor || '#fff'}" font-size="14" font-weight="600">${esc(it.label)}</text>`;
        }
      }
      if (it.type === 'band') { const x0 = this.x(it.from), x1 = this.x(it.to); s += `<rect x="${x0}" y="${this.axisY}" width="${x1 - x0}" height="${this.height - this.axisY}" fill="${it.fill}"/>`; if (it.label) s += `<text x="${(x0 + x1) / 2}" y="${this.axisY + 16}" text-anchor="middle" fill="${it.color || C.orange}" font-size="13" font-weight="600">${esc(it.label)}</text>`; }
      if (it.type === 'mark') { const x = this.x(it.t); s += `<line x1="${x}" y1="${it.y0}" x2="${x}" y2="${it.y1}" stroke="${it.color || C.accent}" stroke-width="${it.w || 2}" ${it.dash ? `stroke-dasharray="${it.dash}"` : ''}/>`; if (it.label) s += `<text x="${x + (it.anchor === 'end' ? -6 : 6)}" y="${it.ly ?? it.y1 + 18}" text-anchor="${it.anchor || 'start'}" fill="${it.color || C.accent}" font-size="${it.size || 14}" font-weight="600">${esc(it.label)}</text>`; }
      if (it.type === 'flag') { const x = this.x(it.t); s += `<path d="M${x},${it.y} l-7,-11 l14,0 z" fill="${it.color || C.fg}"/>`; if (it.label) s += `<text x="${x}" y="${it.y - 16}" text-anchor="middle" fill="${it.color || C.fg}" font-size="14" font-weight="600">${esc(it.label)}</text>`; }
      if (it.type === 'span') { const x0 = this.x(it.from), x1 = this.x(it.to), y = it.y; s += `<path d="M${x0},${y - 8} L${x0},${y} L${x1},${y} L${x1},${y - 8}" fill="none" stroke="${it.color || C.accent}" stroke-width="2"/>`; if (it.label) s += `<text x="${(x0 + x1) / 2}" y="${y + 20}" text-anchor="middle" fill="${it.color || C.accent}" font-size="${it.size || 15}" font-weight="600">${esc(it.label)}</text>`; }
      if (it.type === 'text') { const x = it.x ?? this.x(it.t); s += `<text x="${x}" y="${it.y}" text-anchor="${it.anchor || 'start'}" fill="${it.color || C.fg}" font-size="${it.size || 15}" font-weight="${it.weight || 500}" ${it.mono ? 'class="mono"' : ''}>${esc(it.text)}</text>`; }
      if (it.type === 'cursor') { const x = this.x(it.t); s += `<line x1="${x}" y1="${this.axisY - 4}" x2="${x}" y2="${this.height}" stroke="${C.accent}" stroke-width="2"/><text x="${x}" y="${this.height + 18}" text-anchor="middle" fill="${C.accent}" font-size="13" font-weight="600" class="mono">${fmtT(it.t)}</text>`; }
      s += '</g>';
    }
    this.svg.innerHTML = s;
  }
}

// ---- scene registry & frame renderer ----
window.__TL = null; const SCENES = {};
function registerScene(id, draw) { SCENES[id] = { el: $('s-' + id), draw }; }
window.__setTimeline = tl => { window.__TL = tl; };
window.__render = t => {
  const tl = window.__TL; if (!tl) return;
  let cur = tl[tl.length - 1];
  for (const s of tl) if (t >= s.start && t < s.start + s.dur) { cur = s; break; }
  for (const s of tl) { const sc = SCENES[s.id]; if (sc) sc.el.classList.toggle('on', s.id === cur.id); }
  const lt = t - cur.start, sc = SCENES[cur.id];
  if (sc) { sc.draw(lt, cur.dur, t); sc.el.style.opacity = clamp(Math.min(lt / 0.4, (cur.dur - lt) / 0.4), 0, 1); }
  $('cap').textContent = cur.caption;
  const total = tl[tl.length - 1].start + tl[tl.length - 1].dur;
  $('prog').style.width = (t / total * 100) + '%';
};
// counter helper: animate number from 0 to v over [start, start+dur]
function count(lt, start, dur, v) { return v * easeOut(lin(lt, start, dur)); }
