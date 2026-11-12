// AIS 위치 · 항행 상태 목업
// 실제 솔루션에서는 AIS 수신(해양수산부 T-AIS·S-AIS, 또는 aisstream 같은 상용 스트림)을 서버가 받아
// 선박별 마지막 위치를 내려 준다 (docs/data-sources.md). 프로토타입은 '지금' 시각과 ETA · 적용 계획으로 위치를 만든다.
import { DB } from './data.js';
import { nowMs, H, MIN } from './time.js';
import { seeded } from './fmt.js';

const PILOT = [35.434, 129.418];
// 남쪽에서 오는 배: 대한해협 → 동중국해 → 대만 → 남중국해 (육지를 피한 대략의 항로)
const SOUTH = [PILOT, [35.3, 129.5], [35.0, 129.56], [34.78, 129.12], [34.25, 128.62], [33.55, 127.95], [32.6, 127.1], [31.2, 125.9],
  [29.2, 124.4], [26.5, 122.6], [23.0, 120.9], [20.0, 119.5], [15.0, 116.0], [10.0, 112.0], [5.0, 106.0], [1.3, 104.0]];
const NORTH = [PILOT, [35.55, 129.55], [35.9, 129.62], [36.03, 129.45]];

export const NAV = {
  underway: { code: 0, kr: '항해 중 (엔진 사용)' },
  anchored: { code: 1, kr: '정박 (Anchored)' },
  moored: { code: 5, kr: '계류 (Moored)' },
  departed: { code: 0, kr: '항해 중 (출항)' },
};

const SPEED = (v) => (/VLCC/.test(v.type) ? 13 : /Aframax|LR1/.test(v.type) ? 13.5 : /MR/.test(v.type) ? 13 : /케미컬/.test(v.type) ? 12.5 : 10.5);
const rad = (d) => (d * Math.PI) / 180;

function legKm(a, b) {
  const x = rad(b[1] - a[1]) * Math.cos(rad((a[0] + b[0]) / 2));
  const y = rad(b[0] - a[0]);
  return Math.sqrt(x * x + y * y) * 6371;
}
function bearing(a, b) {
  const x = rad(b[1] - a[1]) * Math.cos(rad((a[0] + b[0]) / 2));
  const y = rad(b[0] - a[0]);
  return (Math.round((Math.atan2(x, y) * 180) / Math.PI) + 360) % 360;
}
/** 도선 구역에서 항로를 거슬러 km만큼 간 지점과 그 지점의 진행 방향(울산 쪽) */
function alongRoute(route, km) {
  let rem = Math.max(0, km);
  for (let i = 0; i < route.length - 1; i++) {
    const L = legKm(route[i], route[i + 1]);
    if (rem <= L) {
      const f = rem / L;
      const pos = [route[i][0] + (route[i + 1][0] - route[i][0]) * f, route[i][1] + (route[i + 1][1] - route[i][1]) * f];
      return { pos, cog: bearing(pos, route[i]) };
    }
    rem -= L;
  }
  const last = route[route.length - 1];
  return { pos: last, cog: bearing(last, route[route.length - 2]) };
}

let anchorSlots = null;
function anchorSpot(v, now) {
  if (!anchorSlots || anchorSlots.now !== now) anchorSlots = { now, map: new Map(), count: {} };
  if (anchorSlots.map.has(v.id)) return anchorSlots.map.get(v.id);
  const a = DB.anchorages.find((x) => v.dwt <= x.max_dwt) ?? DB.anchorages[DB.anchorages.length - 1];
  const k = (anchorSlots.count[a.id] = (anchorSlots.count[a.id] ?? -1) + 1);
  const ang = rad(k * 137.5);
  const r = 0.0032 * Math.sqrt(k + 0.6);
  const spot = { a, lat: a.lat + r * Math.cos(ang), lng: a.lng + (r * Math.sin(ang)) / Math.cos(rad(a.lat)) };
  anchorSlots.map.set(v.id, spot);
  return spot;
}

/**
 * 선박 한 척의 지금 AIS 상태
 * @param v 선박 (DB.vessels)
 * @param plan 적용 계획의 이 선박 줄 (없으면 null)
 */
export function aisOf(v, plan, now = nowMs()) {
  const r = seeded(v.id);
  const etb = v.fix?.etbMs ?? v.prev?.etbMs ?? plan?.etb;
  const etu = v.fix?.etuMs ?? v.prev?.etuMs ?? plan?.etu;
  const berthId = v.fix?.berth ?? v.prev?.berth ?? plan?.berth;
  const speed = SPEED(v) + (r() - 0.5) * 1.2;
  const route = v.ais.prev_port === 'POHANG' ? NORTH : SOUTH;
  let o;
  if (etb != null && now >= etb && now < etu) {
    const b = DB.berthById[berthId];
    o = { nav: 'moored', lat: b.lat + 0.0003, lng: b.lng + 0.0006, sog: 0, cog: Math.round(r() * 359), hdg: Math.round(200 + r() * 40), berth: berthId, where: `${b.label} 계류` };
  } else if (etu != null && now >= etu) {
    const km = ((now - etu) / H) * speed * 1.852;
    const p = alongRoute(route, km);
    o = { nav: 'departed', lat: p.pos[0], lng: p.pos[1], sog: +speed.toFixed(1), cog: (p.cog + 180) % 360, hdg: (p.cog + 182) % 360, where: '출항 후 항해' };
  } else if (now >= v.ais.etaMs) {
    const s = anchorSpot(v, Math.floor(now / (10 * MIN)));
    o = { nav: 'anchored', lat: s.lat, lng: s.lng, sog: +(r() * 0.3).toFixed(1), cog: Math.round(r() * 359), hdg: Math.round(280 + r() * 50), anchorage: s.a.id, where: `${s.a.label} 대기` };
  } else {
    const hours = (v.ais.etaMs - now) / H;
    const km = hours * speed * 1.852;
    const p = alongRoute(route, km);
    const jitter = (r() - 0.5) * 0.02;
    o = {
      nav: 'underway', lat: p.pos[0] + jitter, lng: p.pos[1] - jitter, sog: +speed.toFixed(1), cog: p.cog, hdg: (p.cog + Math.round((r() - 0.5) * 6) + 360) % 360,
      distNm: Math.round(km / 1.852), where: `울산 도선구역까지 ${Math.round(km / 1.852).toLocaleString()}nm`,
    };
  }
  const far = (o.distNm ?? 0) > 40;
  o.source = far ? 'S-AIS (위성)' : 'T-AIS (육상국)';
  o.updatedAt = now - (far ? (6 + Math.round(r() * 28)) * MIN : (3 + Math.round(r() * 140)) * 1000);
  o.navKr = NAV[o.nav].kr;
  o.navCode = NAV[o.nav].code;
  o.inPort = o.nav === 'moored' || o.nav === 'anchored' || (o.distNm ?? 999) < 25;
  return o;
}
