"""접안 가능 여부 표 내보내기(CSV)와 시각화(HTML).

CSV
  matrix.csv   선박 × 부두 한 줄, 5분 칸마다 0/1 (가로로 긴 표) — 경우의 수 입력용
  windows.csv  접안 가능한 연속 구간 (선박, 부두, 시작, 끝, 칸 수, 점유시간)
  summary.csv  선박 × 부두 요약 (가능 여부, 첫 접안 가능 시각, 가능 칸 수, 불가 사유)
HTML
  요약 매트릭스(선박 × 부두) · 타임라인(선박별 / 부두별) · 부두별 접안 가능 선박 수
"""

import csv
import json
from collections import Counter
from pathlib import Path

from .feasibility import REASON_LABEL, FeasibilityTable, Reason


def _hours(td) -> float | None:
    return None if td is None else round(td.total_seconds() / 3600, 2)


def write_csv(tb: FeasibilityTable, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {k: out_dir / f"{k}.csv" for k in ("matrix", "windows", "summary")}
    slot_cols = [f"{tb.time(i):%m/%d %H:%M}" for i in range(tb.n_slots)]

    with paths["matrix"].open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["vessel_id", "berth", "stay_h", *slot_cols])
        for r in tb.rows:
            w.writerow([r.vessel_id, r.berth, _hours(r.stay), *r.feasible()])

    with paths["windows"].open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["vessel_id", "berth", "etb_from", "etb_to", "slots", "stay_h"])
        for r in tb.rows:
            for a, b in r.windows():
                w.writerow([r.vessel_id, r.berth, f"{tb.time(a):%Y-%m-%d %H:%M}", f"{tb.time(b - 1):%Y-%m-%d %H:%M}",
                            b - a, _hours(r.stay)])

    with paths["summary"].open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["vessel_id", "berth", "feasible", "first_etb", "feasible_slots", "stay_h", "blocked_by"])
        for r in tb.rows:
            win = r.windows()
            blocked = Counter(Reason(c) for c in r.codes if c != Reason.OK)
            w.writerow([
                r.vessel_id, r.berth, int(bool(win)), f"{tb.time(win[0][0]):%Y-%m-%d %H:%M}" if win else "",
                sum(b - a for a, b in win), _hours(r.stay),
                r.detail or " / ".join(f"{REASON_LABEL[k]} {v}칸" for k, v in blocked.most_common()),
            ])
    return paths


def _runs(codes: bytes) -> list[list[int]]:
    out: list[list[int]] = []
    for c in codes:
        if out and out[-1][0] == c:
            out[-1][1] += 1
        else:
            out.append([c, 1])
    return out


def payload(tb: FeasibilityTable, profiles, original_etb, files: dict[str, str]) -> dict:
    s = tb.start
    return {
        "start": [s.year, s.month, s.day, s.hour, s.minute],
        "step_min": int(tb.step.total_seconds() // 60),
        "n": tb.n_slots,
        "berths": list(tb.berths),
        "reasons": [{"code": int(k), "label": v} for k, v in REASON_LABEL.items()],
        "files": files,
        "vessels": [
            {
                "id": v.vessel_id, "berth": v.berth, "biz": v.biz or "",
                "eta": int((v.eta - s).total_seconds() // tb.step.total_seconds()),
                "etb": int((original_etb[v.vessel_id] - s).total_seconds() // tb.step.total_seconds()),
                "cls": profiles[v.vessel_id].ship_class, "cargo": profiles[v.vessel_id].cargo_group,
                "dwt": profiles[v.vessel_id].dwt, "grt": profiles[v.vessel_id].grt,
            }
            for v in tb.vessels
        ],
        "rows": {
            f"{r.vessel_id}|{r.berth}": {"stay": _hours(r.stay), "detail": r.detail, "runs": _runs(r.codes)}
            for r in tb.rows
        },
    }


def build_html(data: dict) -> str:
    return PAGE.replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


PAGE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>접안 가능 시각표</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#16202c;--mut:#667085;--line:#d0d5dd;--accent:#1d5fd1;
--r0:#2e9e5b;--r1:#eceff3;--r2:#d5dae1;--r3:#f4f5f7;--r4:#e1e5eb;--r5:#7b7fe0;--r6:#e3a008;--r7:#d64545;--r8:#0e9aa7;--heat:#1d5fd1}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f141a;--card:#161d25;--ink:#e6eaf0;--mut:#93a0b0;--line:#2c3743;
--accent:#7aa7f5;--r0:#46c07c;--r1:#1d242d;--r2:#2e3743;--r3:#1a2028;--r4:#27303b;--r5:#8f93f0;--r6:#f0b429;--r7:#ef6b6b;--r8:#2cc3cf;--heat:#7aa7f5}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif}
main{max-width:1440px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:0 0 4px}
.lead,.sub{color:var(--mut);margin:0 0 12px;font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-top:16px}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.stat{border:1px solid var(--line);border-radius:10px;padding:6px 12px;background:var(--card)}
.stat b{display:block;font-size:18px;font-variant-numeric:tabular-nums}.stat span{font-size:12px;color:var(--mut)}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;margin:8px 0}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-2px;border:1px solid var(--line)}
.files a{color:var(--accent);margin-right:12px;font-size:13px}
.ctrl{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}.seg button{border:0;background:var(--card);color:var(--ink);padding:6px 12px;font:inherit;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--ink);color:var(--bg)}
select{font:inherit;padding:5px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);max-width:100%}
.canvaswrap{position:relative;overflow-x:auto}canvas{display:block}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);font-size:12px;padding:6px 8px;border-radius:6px;display:none;z-index:9;max-width:320px;white-space:pre-line}
.matrix{overflow:auto;max-height:640px;border:1px solid var(--line);border-radius:10px}
.matrix table{border-collapse:collapse;font-size:11.5px}.matrix th,.matrix td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:3px 5px;white-space:nowrap;text-align:center}
.matrix thead th{position:sticky;top:0;background:var(--card);z-index:2}.matrix tbody th{position:sticky;left:0;background:var(--card);text-align:left;z-index:1;font-family:ui-monospace,Menlo,monospace;cursor:pointer}
.matrix td.ok{background:color-mix(in srgb,var(--r0) 22%,transparent);cursor:pointer;font-variant-numeric:tabular-nums}.matrix td.no{color:var(--mut)}
.matrix td.real{outline:2px solid var(--ink);outline-offset:-2px;font-weight:700}.matrix tr.sel th{color:var(--accent)}
.mut{color:var(--mut)}
</style></head><body><main>
<h1>접안 가능 시각표</h1>
<p class="lead">선박 × 부두 × 5분 칸마다 "이 시각에 접안(ETB)을 시작할 수 있는가". 선박 한 척 기준 조건(부두 적합성 · 과거 실적 · 도착 · 사용 가능 시각 · 야간 도선 · 부두 제약 · FIX 충돌)만 반영했다.
같은 부두 앞 선박 · 동일 화물 그룹 · #4 동시 접안처럼 다른 선박 배치에 따라 달라지는 조건은 경우의 수를 조합할 때 판정한다.</p>
<div class="stats" id="stats"></div>
<div class="legend" id="legend"></div>
<div class="files" id="files"></div>

<section class="card"><h2>1. 선박별 접안 가능 부두 요약</h2><p class="sub">칸 = 첫 접안 가능 시각 / 가능 시간(h). 굵은 테두리 = 실제 계획 부두. 회색 점 = 불가(마우스를 올리면 사유). 행이나 칸을 누르면 아래 타임라인이 그 선박으로 바뀐다.</p>
<div class="matrix" id="matrix"></div></section>

<section class="card"><h2>2. 타임라인</h2>
<div class="ctrl"><div class="seg" role="group" aria-label="보기"><button id="mv" aria-pressed="true">선박별</button><button id="mb" aria-pressed="false">부두별</button></div>
<select id="pick" aria-label="대상 선택"></select><label class="mut"><input type="checkbox" id="onlyfit" checked> 접안 가능한 행만</label></div>
<p class="sub" id="tlsub"></p><div class="canvaswrap"><canvas id="tl"></canvas></div></section>

<section class="card"><h2>3. 부두별 · 시각별 접안 가능 선박 수</h2><p class="sub">진할수록 그 시각에 그 부두로 들어갈 수 있는 선박이 많다 (경우의 수가 몰리는 곳).</p>
<div class="canvaswrap"><canvas id="heat"></canvas></div></section>
<div id="tip"></div>
<script type="application/json" id="data">/*DATA*/</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const S = Date.UTC(D.start[0], D.start[1]-1, D.start[2], D.start[3], D.start[4]);
const STEP = D.step_min*60000, N = D.n;
const pad = x => String(x).padStart(2,'0');
const at = i => new Date(S + i*STEP);
const fmt = i => { const t = at(i); return `${pad(t.getUTCMonth()+1)}/${pad(t.getUTCDate())} ${pad(t.getUTCHours())}:${pad(t.getUTCMinutes())}`; };
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const LABEL = Object.fromEntries(D.reasons.map(r => [r.code, r.label]));
const row = (v, b) => D.rows[v + '|' + b];
const V = Object.fromEntries(D.vessels.map(v => [v.id, v]));
const okSlots = r => r.runs.reduce((s, [c, n]) => s + (c === 0 ? n : 0), 0);
const firstOk = r => { let i = 0; for (const [c, n] of r.runs) { if (c === 0) return i; i += n; } return -1; };
const domCode = r => { const c = {}; for (const [k, n] of r.runs) if (k) c[k] = (c[k]||0) + n; return +Object.entries(c).sort((a,b)=>b[1]-a[1])[0]?.[0]; };
const tip = document.getElementById('tip');
const showTip = (e, text) => { tip.textContent = text; tip.style.display = 'block';
  tip.style.left = Math.min(e.clientX + 12, innerWidth - 330) + 'px'; tip.style.top = (e.clientY + 12) + 'px'; };
const hideTip = () => tip.style.display = 'none';

// 상단 통계 · 범례 · 파일
const pairs = D.vessels.flatMap(v => D.berths.map(b => row(v.id, b)));
const okPairs = pairs.filter(r => okSlots(r) > 0).length;
const okCells = pairs.reduce((s, r) => s + okSlots(r), 0);
document.getElementById('stats').innerHTML = [
  [D.vessels.length + '척', '선박'], [D.berths.length + '곳', '부두'],
  [N.toLocaleString() + '칸', `${D.step_min}분 단위 · ${fmt(0)} ~ ${fmt(N-1)}`],
  [okPairs + ' / ' + pairs.length, '접안 가능한 (선박, 부두) 쌍'], [okCells.toLocaleString(), '접안 가능 칸 (경우의 수)'],
].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join('');
document.getElementById('legend').innerHTML = D.reasons.map(r => `<span><i style="background:var(--r${r.code})"></i>${r.label}</span>`).join('');
document.getElementById('files').innerHTML = '내려받기: ' + Object.entries(D.files).map(([k, p]) => `<a href="${p}">${k}.csv</a>`).join('');

// 1. 요약 매트릭스
const mx = document.getElementById('matrix');
mx.innerHTML = '<table><thead><tr><th>선박</th><th>등급 / 화물</th>' + D.berths.map(b => `<th>#${b}</th>`).join('') + '</tr></thead><tbody>' +
  D.vessels.map(v => `<tr data-v="${v.id}"><th title="ETA ${fmt(v.eta)} · 실제 ETB ${fmt(v.etb)}">${v.id}</th><td class="mut">${v.cls} · ${v.cargo}</td>` +
    D.berths.map(b => { const r = row(v.id, b), n = okSlots(r), real = b === v.berth ? ' real' : '';
      if (!n) { const c = domCode(r); return `<td class="no${real}" title="${(r.detail || LABEL[c])}"><span style="color:var(--r${c === 1 ? 2 : c})">●</span></td>`; }
      return `<td class="ok${real}" data-b="${b}" title="첫 접안 가능 ${fmt(firstOk(r))} · 가능 ${(n*D.step_min/60).toFixed(1)}h · 점유 ${r.stay}h">${fmt(firstOk(r)).slice(0,11)}<br><span class="mut">${(n*D.step_min/60).toFixed(0)}h</span></td>`;
    }).join('') + '</tr>').join('') + '</tbody></table>';
mx.addEventListener('click', e => { const tr = e.target.closest('tr[data-v]'); if (!tr) return; setMode('v'); pick.value = tr.dataset.v; draw();
  document.getElementById('tl').scrollIntoView({behavior: 'smooth', block: 'center'}); });

// 2. 타임라인
const tl = document.getElementById('tl'), pick = document.getElementById('pick'), onlyfit = document.getElementById('onlyfit');
let mode = 'v';
function setMode(m) { mode = m; document.getElementById('mv').setAttribute('aria-pressed', m === 'v'); document.getElementById('mb').setAttribute('aria-pressed', m === 'b');
  pick.innerHTML = (m === 'v' ? D.vessels.map(v => `<option value="${v.id}">${v.id} · ${v.cls} · ${v.cargo} · ETA ${fmt(v.eta)}</option>`)
                              : D.berths.map(b => `<option value="${b}">#${b}</option>`)).join(''); }
document.getElementById('mv').onclick = () => { setMode('v'); draw(); };
document.getElementById('mb').onclick = () => { setMode('b'); draw(); };
pick.onchange = draw; onlyfit.onchange = draw;

const GUT = 92, AXIS = 30, RH = 20;
function axis(ctx, W, top) {
  ctx.fillStyle = css('--mut'); ctx.font = '11px -apple-system, sans-serif'; ctx.strokeStyle = css('--line');
  const perDay = 1440 / D.step_min, first = (24*60 - (D.start[3]*60 + D.start[4])) / D.step_min % perDay;
  for (let i = first; i < N; i += perDay / 4) { const x = GUT + (W - GUT) * i / N, day = Math.abs((i - first) % perDay) < 1e-6;
    ctx.globalAlpha = day ? 1 : .35; ctx.beginPath(); ctx.moveTo(x, top - 6); ctx.lineTo(x, ctx.canvas.height); ctx.stroke(); ctx.globalAlpha = 1;
    if (day) ctx.fillText(fmt(i).slice(0, 5), x + 3, top - 10); }
}
function draw() {
  const key = pick.value; let rows;
  if (mode === 'v') rows = D.berths.map(b => ({label: '#' + b, r: row(key, b), real: b === V[key].berth}));
  else rows = D.vessels.map(v => ({label: v.id, r: row(v.id, key), real: v.berth === key, v}));
  if (onlyfit.checked) rows = rows.filter(x => okSlots(x.r) > 0);
  const v = mode === 'v' ? V[key] : null;
  document.getElementById('tlsub').textContent = mode === 'v'
    ? `${v.id} · ${v.cls} · ${v.cargo} · DWT ${v.dwt.toLocaleString()} · GRT ${v.grt.toLocaleString()} · Biz ${v.biz} · ETA ${fmt(v.eta)} · 실제 #${v.berth} ETB ${fmt(v.etb)} — 접안 가능 부두 ${rows.filter(x => okSlots(x.r)).length}곳`
    : `#${key}에 접안할 수 있는 선박 ${rows.filter(x => okSlots(x.r)).length}척 (세로선: 실제 ETB)`;
  const dpr = devicePixelRatio || 1, W = Math.max(tl.parentElement.clientWidth, 900), H = AXIS + rows.length * RH + 8;
  tl.width = W * dpr; tl.height = H * dpr; tl.style.width = W + 'px'; tl.style.height = H + 'px';
  const ctx = tl.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
  const col = D.reasons.map(r => css('--r' + r.code)), sx = (W - GUT) / N;
  rows.forEach((x, k) => { const y = AXIS + k * RH; let i = 0;
    for (const [c, n] of x.r.runs) { ctx.fillStyle = col[c]; ctx.fillRect(GUT + i * sx, y + 2, n * sx + .5, RH - 4); i += n; }
    ctx.fillStyle = css('--ink'); ctx.font = (x.real ? '600 ' : '') + '12px ui-monospace, Menlo, monospace'; ctx.fillText(x.label, 6, y + RH - 6);
    const mark = mode === 'v' ? (x.real ? v.etb : -1) : (x.real ? x.v.etb : -1);
    if (mark >= 0) { ctx.fillStyle = css('--ink'); ctx.fillRect(GUT + mark * sx - 1, y, 2, RH); } });
  axis(ctx, W, AXIS);
  if (v) { ctx.fillStyle = css('--accent'); ctx.fillRect(GUT + v.eta * sx - 1, AXIS - 6, 2, H); ctx.fillText('ETA', GUT + v.eta * sx + 3, AXIS + 10 - 14); }
  tl.onmousemove = e => { const b = tl.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top, k = Math.floor((y - AXIS) / RH), i = Math.floor((x - GUT) / sx);
    if (k < 0 || k >= rows.length || i < 0 || i >= N) return hideTip(); let j = 0, c = 0; for (const [cc, n] of rows[k].r.runs) { if (i < j + n) { c = cc; break; } j += n; }
    showTip(e, `${rows[k].label} · ${fmt(i)}\n${c === 0 ? '✔ 접안 가능' : '✕ ' + (rows[k].r.detail || LABEL[c])}${rows[k].r.stay ? `\n점유 ${rows[k].r.stay}h → ETU ${fmt(i + Math.round(rows[k].r.stay * 60 / D.step_min))}` : ''}`); };
  tl.onmouseleave = hideTip;
}

// 3. 부두별 접안 가능 선박 수
function heat() {
  const cv = document.getElementById('heat'), counts = D.berths.map(b => { const a = new Uint16Array(N);
    for (const v of D.vessels) { let i = 0; for (const [c, n] of row(v.id, b).runs) { if (c === 0) for (let j = i; j < i + n; j++) a[j]++; i += n; } } return a; });
  const max = Math.max(1, ...counts.map(a => Math.max(...a)));
  const dpr = devicePixelRatio || 1, W = Math.max(cv.parentElement.clientWidth, 900), H = AXIS + D.berths.length * 16 + 8;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + 'px'; cv.style.height = H + 'px';
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); const sx = (W - GUT) / N, heatc = css('--heat');
  D.berths.forEach((b, k) => { const y = AXIS + k * 16;
    for (let i = 0; i < N; i++) if (counts[k][i]) { ctx.globalAlpha = .12 + .88 * counts[k][i] / max; ctx.fillStyle = heatc; ctx.fillRect(GUT + i * sx, y + 1, sx + .5, 14); }
    ctx.globalAlpha = 1; ctx.fillStyle = css('--ink'); ctx.font = '12px ui-monospace, Menlo, monospace'; ctx.fillText('#' + b, 6, y + 12); });
  axis(ctx, W, AXIS);
  cv.onmousemove = e => { const r = cv.getBoundingClientRect(), k = Math.floor((e.clientY - r.top - AXIS) / 16), i = Math.floor((e.clientX - r.left - GUT) / sx);
    if (k < 0 || k >= D.berths.length || i < 0 || i >= N) return hideTip(); showTip(e, `#${D.berths[k]} · ${fmt(i)}\n접안 가능 선박 ${counts[k][i]}척`); };
  cv.onmouseleave = hideTip;
}
setMode('v'); draw(); heat();
addEventListener('resize', () => { draw(); heat(); });
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { draw(); heat(); });
</script></main></body></html>
"""
