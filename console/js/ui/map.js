// 선박 지도 (Leaflet) — 울산항만공사 PortWise 모양: 선박 모양 마커(목적지 울산 = 빨강, 그 외 = 초록), 아래쪽 범례
// portwise에서 3D · 해운 · 해무 · 혼잡도 패널은 뺐다. 접안 계획에 쓰는 선박 · 부두 · 정박지만 둔다.
import { DB } from '../core/data.js';
import { esc, usd } from '../core/fmt.js';
import { fmtDT } from '../core/time.js';
import { berthLabel } from '../core/data.js';

const L = window.L;
export const PORT_BOUNDS = [[35.405, 129.345], [35.515, 129.47]];

/** PortWise처럼 위에서 본 배 모양. 빨강 = 울산행(입항 예정 · 대기), 초록 = 계류, 회색 = 출항 */
function shipSVG(nav, cog, sel, alert) {
  const fill = nav === 'moored' ? '#2ea043' : nav === 'departed' ? '#9aa0a8' : '#e5484d';
  const stroke = sel ? '#111' : '#fff';
  const rot = nav === 'moored' || nav === 'anchored' ? (cog % 360) : cog;
  const ring = alert ? '<circle r="11" fill="none" stroke="#e3a008" stroke-width="2" stroke-dasharray="3 2"/>' : '';
  return `<svg width="22" height="22" viewBox="-11 -11 22 22">${ring}<g transform="rotate(${rot})"><path d="M0 -8 L4 -3 L4 7 L-4 7 L-4 -3 Z" fill="${fill}" stroke="${stroke}" stroke-width="${sel ? 1.8 : 1}" stroke-linejoin="round"/><rect x="-2.6" y="2" width="5.2" height="3" fill="#fff" opacity=".85"/></g></svg>`;
}

export function legendHTML() {
  return `<div class="map-legend">
    <span>${shipSVG('underway', 0)}입항 예정 · 정박지 대기</span>
    <span>${shipSVG('moored', 0)}부두 계류</span>
    <span>${shipSVG('departed', 0)}출항</span>
    <span>${shipSVG('underway', 0, false, true)}ETA 변경</span>
  </div>`;
}

function facilities() {
  const g = new Map();
  for (const b of DB.berths) {
    const key = b.id.startsWith('#') ? b.id.split('-')[0] : b.id.startsWith('GAS') ? 'GAS' : b.id;
    const label = key === 'GAS' ? 'Gas' : b.id.startsWith('BUOY') ? b.label : key;
    if (!g.has(key)) g.set(key, { key, label, lat: b.lat, lng: b.lng, berths: [] });
    g.get(key).berths.push(b);
  }
  return [...g.values()];
}

export function createMap(el, { onSelect, labels = true, wheel = true } = {}) {
  const map = L.map(el, { zoomControl: true, minZoom: 3, maxZoom: 16, scrollWheelZoom: wheel }).fitBounds(PORT_BOUNDS);
  const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, subdomains: 'abc', attribution: '© OpenStreetMap contributors' }).addTo(map);
  let errors = 0;
  let coast = null;
  tiles.on('tileerror', () => {
    errors++;
    if (errors === 2 && DB.coast && !coast) {
      map.removeLayer(tiles);
      coast = L.layerGroup(DB.coast.land.map((poly) => L.polygon(poly, { color: '#b9b2a2', weight: 1, fillColor: '#efe9dc', fillOpacity: 1, interactive: false }))).addTo(map);
      el.classList.add('offline');
    }
  });
  for (const a of DB.anchorages) {
    L.circle([a.lat, a.lng], { radius: 650, color: '#b8942a', weight: 1, dashArray: '4 4', fillColor: '#f4e3a1', fillOpacity: 0.15, interactive: false }).addTo(map);
    L.marker([a.lat, a.lng], { icon: L.divIcon({ className: '', html: `<span class="amk">${esc(a.label)}</span>`, iconSize: [0, 0] }), interactive: false }).addTo(map);
  }
  for (const f of facilities()) {
    const tip = f.berths.map((b) => `${b.label} · 최대 ${Number(b.max_dwt).toLocaleString()} DWT · 흘수 ${b.max_draft}m`).join('<br>');
    L.marker([f.lat, f.lng], { icon: L.divIcon({ className: '', html: `<span class="bmk">${esc(f.label)}</span>`, iconSize: [0, 0] }), zIndexOffset: -100 })
      .bindTooltip(`<b>${esc(f.label)}</b><br>${tip}`, { direction: 'top' }).addTo(map);
  }
  const layer = L.layerGroup().addTo(map);
  let rows = [];
  let sel = null;
  function draw() {
    layer.clearLayers();
    const z = map.getZoom();
    for (const r of rows) {
      const { v, ais, plan } = r;
      const html = `<div class="vmk">${shipSVG(ais.nav, ais.cog, sel === v.id, r.alert)}${labels && (z >= 14 || sel === v.id) ? `<span class="lbl">${esc(v.name)}</span>` : ''}</div>`;
      const m = L.marker([ais.lat, ais.lng], { icon: L.divIcon({ className: '', html, iconSize: [22, 22], iconAnchor: [11, 11] }), zIndexOffset: sel === v.id ? 1000 : 0 });
      m.bindTooltip(`<b>${esc(v.name)}</b> [${esc(v.flag)}] at ${ais.sog.toFixed(1)}kn/${ais.cog}°<br>목적지: ${esc(v.ais.destination_text)}<br>업데이트 시간 : ${fmtDT(ais.updatedAt)}${plan ? `<br>계획 ${esc(berthLabel(plan.berth))} · ETB ${fmtDT(plan.etb)} · ${usd(plan.dem)}` : ''}`, { direction: 'top', offset: [0, -8] });
      m.on('click', () => onSelect?.(v.id));
      m.addTo(layer);
    }
  }
  map.on('zoomend', draw);
  return {
    map,
    update(r) { rows = r; draw(); },
    select(id, pan = false) {
      sel = id;
      draw();
      const r = rows.find((x) => x.v.id === id);
      if (pan && r) map.setView([r.ais.lat, r.ais.lng], Math.max(map.getZoom(), r.ais.inPort ? 13 : 7));
    },
    fitAll() { const pts = rows.map((r) => [r.ais.lat, r.ais.lng]); if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.08)); },
    fitPort() { map.fitBounds(PORT_BOUNDS); },
    destroy() { map.remove(); },
  };
}
