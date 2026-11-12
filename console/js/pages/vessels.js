// AIS · 입항 예정 선박 — 울산항만공사 PortWise 지도 문법(선박 모양 마커 · 아래 범례 · 선박 카드)과 조회 조건표
import { DB, berthLabel } from '../core/data.js';
import { esc, usd, ICON } from '../core/fmt.js';
import { fmtDT, fmtAgo, fmtDiff, nowMs, MIN } from '../core/time.js';
import { vesselsNow, appliedVersion, ETA_ALERT_H } from '../core/api.js';
import { createMap, legendHTML } from '../ui/map.js';
import { openVessel } from '../ui/vessel.js';
import { pageTitle } from '../ui/shell.js';

const F = { nav: 'all', cls: 'all', q: '', alert: false };

function condHTML() {
  return `<table class="cond">
    <tr><th>항행상태</th><td>${[['all', '전체'], ['underway', '항해'], ['anchored', '정박지 대기'], ['moored', '계류']].map(([k, n]) => `<label class="radio"><input type="radio" name="nav" value="${k}" ${F.nav === k ? 'checked' : ''}>${n}</label>`).join('')}</td>
      <th>선종</th><td><select class="in" id="fCls"><option value="all">전체</option>${Object.entries(DB.master.classes).map(([k, v]) => `<option value="${k}">${esc(v)} (${k})</option>`).join('')}</select></td></tr>
    <tr><th>선박</th><td><input class="in req" id="fQ" placeholder="선박명 · MMSI · 호출부호" style="width:240px"></td>
      <th>ETA 변경</th><td><label class="radio"><input type="checkbox" id="fAlert"> AIS ETA가 계획과 ${ETA_ALERT_H}시간 넘게 다른 선박만</label></td></tr>
  </table>`;
}

function bind(el, apply) {
  el.querySelectorAll('input[name="nav"]').forEach((r) => r.addEventListener('change', () => ((F.nav = r.value), apply())));
  const cls = el.querySelector('#fCls');
  cls.value = F.cls;
  cls.addEventListener('change', () => ((F.cls = cls.value), apply()));
  const q = el.querySelector('#fQ');
  q.value = F.q;
  q.addEventListener('input', () => ((F.q = q.value.trim()), apply()));
  const al = el.querySelector('#fAlert');
  al.checked = F.alert;
  al.addEventListener('change', () => ((F.alert = al.checked), apply()));
}

const filtered = (rows) => {
  const q = F.q.toLowerCase();
  return rows.filter((r) => (F.nav === 'all' || r.ais.nav === F.nav) && (F.cls === 'all' || r.v.class === F.cls) && (!F.alert || r.alert) &&
    (!q || [r.v.name, r.v.mmsi, r.v.call_sign, r.v.imo].some((s) => String(s).toLowerCase().includes(q))));
};

export function renderMap(el) {
  let rows = vesselsNow();
  el.innerHTML = `
  ${pageTitle('AIS', 'Vessel > AIS')}
  ${condHTML()}
  <div class="bar"><div class="g"><span class="range">AIS 기준 ${fmtDT(nowMs())} · T-AIS 육상국 / S-AIS 위성 · 30초 갱신</span></div>
    <div class="g"><span class="count" id="cnt"></span><button class="btn" id="bPort">항만 보기</button><button class="btn" id="bAll">전체 보기</button></div></div>
  <div class="map tall" id="vMap">${legendHTML()}</div>`;
  const m = createMap(el.querySelector('#vMap'), { onSelect: (id) => (m.select(id), openVessel(id)) });
  const apply = () => {
    const f = filtered(rows);
    el.querySelector('#cnt').innerHTML = `조회 선박:<b>${f.length}</b>`;
    m.update(f);
  };
  bind(el, apply);
  apply();
  el.querySelector('#bPort').addEventListener('click', () => m.fitPort());
  el.querySelector('#bAll').addEventListener('click', () => m.fitAll());
  const tick = setInterval(() => ((rows = vesselsNow()), apply()), 30000);
  return () => {
    clearInterval(tick);
    m.destroy();
  };
}

export function renderList(el) {
  const rows = vesselsNow();
  const ver = appliedVersion();
  el.innerHTML = `
  ${pageTitle('입항 예정 선박', 'Vessel > 입항 예정 선박')}
  ${condHTML()}
  <div class="bar"><div class="g"><span class="range">계획 열 기준 : 적용 계획 v${ver.no} ${esc(ver.label)}</span>
      <span class="legend" style="margin-left:18px"><span><i class="berth"></i>계류</span><span><i class="plan"></i>정박지 대기</span><span><i class="dep"></i>출항</span></span></div>
    <div class="g"><span class="count" id="cnt"></span><a class="btn" href="#vessels-map">${ICON.map}지도</a></div></div>
  <div class="tbl-wrap" style="max-height:calc(100vh - 330px)"><table class="tbl">
    <thead><tr><th>선박명</th><th>국적</th><th>선종</th><th>항행상태</th><th>위치</th><th>목적지(AIS)</th><th>ETA(AIS)</th><th>ETA(계획)</th><th data-req="N-002">차이</th><th>계획 선석</th><th>ETB</th><th>체선료(USD)</th><th>AIS 갱신</th></tr></thead>
    <tbody id="tb"></tbody></table></div>`;
  const tb = el.querySelector('#tb');
  const apply = () => {
    const f = filtered(rows);
    el.querySelector('#cnt').innerHTML = `전체 조회 건수:<b>${f.length}</b>`;
    tb.innerHTML = f.map((r) => {
      const { v, ais, plan } = r;
      const cls = ais.nav === 'moored' ? 'berth' : ais.nav === 'anchored' ? 'plan' : ais.nav === 'departed' ? 'dep' : '';
      const old = nowMs() - ais.updatedAt > 10 * MIN;
      const navT = { moored: '계류', anchored: '정박', underway: '항해', departed: '출항' }[ais.nav];
      return `<tr class="click ${cls}" data-v="${v.id}">
        <td class="l vn">${esc(v.name)}</td><td>${esc(v.flag)}</td><td class="l">${esc(v.type)}</td><td>${navT}</td><td class="l">${esc(ais.where)}</td>
        <td title="선장 입력 원문 · 판독 ${esc(v.ais.destination_locode)}">${esc(v.ais.destination_text)}</td>
        <td class="num">${fmtDT(v.ais.etaMs)}</td><td class="num">${fmtDT(v.etaMs)}</td>
        <td>${r.alert ? `<span class="t-bad b">${fmtDiff(r.etaDiff)}</span>` : Math.abs(r.etaDiff) >= MIN ? `<span class="muted">${fmtDiff(r.etaDiff)}</span>` : '<span class="muted">-</span>'}</td>
        <td class="b">${plan ? esc(berthLabel(plan.berth)) : '-'}</td><td class="num etb">${plan ? fmtDT(plan.etb) : '-'}</td>
        <td class="r ${plan?.dem > 0 ? 't-bad b' : ''}">${plan && !plan.inport ? usd(plan.dem) : '-'}</td>
        <td class="${old ? 't-warn' : 'muted'}">${fmtAgo(ais.updatedAt)}</td></tr>`;
    }).join('') || '<tr class="empty"><td colspan="13">조회된 선박이 없습니다</td></tr>';
    tb.querySelectorAll('tr[data-v]').forEach((tr) => tr.addEventListener('click', () => openVessel(tr.dataset.v)));
  };
  bind(el, apply);
  apply();
}
