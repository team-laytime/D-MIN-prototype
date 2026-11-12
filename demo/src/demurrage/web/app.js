/* Demurrage Planner — 화면 스크립트 (프레임워크 없이 한 파일).
   원칙: 숫자는 서버(엔진)가 낸 값만 그대로 보여 준다. 화면은 계산하지 않는다(합·차이·시간 길이 같은 표시용 계산만). */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = encodeURIComponent;
const usd = (v) => (v == null ? "-" : (v < 0 ? "−" : "") + "$" + Math.round(Math.abs(v)).toLocaleString("en-US"));
const usdS = (v) => (v == null ? "-" : Math.round(v) === 0 ? "$0" : (v > 0 ? "+" : "−") + "$" + Math.round(Math.abs(v)).toLocaleString("en-US"));
const short = (iso) => (iso ? `${iso.slice(5, 7)}/${iso.slice(8, 10)} ${iso.slice(11, 16)}` : "-");
const ms = (iso) => Date.parse(String(iso).replace(" ", "T") + ":00+09:00");
const hrs = (a, b) => (ms(b) - ms(a)) / 3.6e6;
const fh = (h) => (h == null ? "-" : `${(Math.round(h * 10) / 10).toLocaleString("en-US")}h`);
const pct = (v) => (v == null ? "" : `${v > 0 ? "−" : v < 0 ? "+" : ""}${Math.abs(v).toFixed(1)}%`);
const code = (sid) => String(sid || "").split("-")[0];
const WD = ["일", "월", "화", "수", "목", "금", "토"];

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch (e) { /* 본문 없음 */ }
    throw new Error(`${r.status} ${msg}`);
  }
  return (r.headers.get("content-type") || "").includes("json") ? r.json() : r.text();
}

/* ---------- 아이콘(직접 그린 선 아이콘) ---------- */
const sv = (d, extra = "") => `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" ${extra}>${d}</svg>`;
const I = {
  plan: sv('<path d="M3 5.5h7M6 10h10M4 14.5h7"/><path d="M3 3v14" opacity=".5"/>'),
  ship: sv('<path d="M3 13.5l1.6 3h10.8l1.6-3z"/><path d="M6 13.5V8h6l2.5 2.6v2.9"/><path d="M9 8V5"/>'),
  berth: sv('<path d="M2.5 16h15"/><path d="M5 16V9.5M10 16V6.5M15 16V9.5"/><path d="M3.5 9.5h3M8.5 6.5h3M13.5 9.5h3"/>'),
  sheet: sv('<path d="M6 2.8h6l3.5 3.5V17H6z"/><path d="M12 2.8v3.5h3.5M8.3 10h5M8.3 13h3.5"/>'),
  risk: sv('<path d="M10 3.2l7.3 13H2.7z"/><path d="M10 8.4v3.4M10 14.1v.1"/>'),
  doc: sv('<path d="M5 2.8h7.5L15.5 6v11.2H5z"/><path d="M7.6 8.6h5.4M7.6 11.5h5.4M7.6 14.4h3"/>'),
  report: sv('<path d="M4 3h12v14H4z"/><path d="M7 13.5v-3M10 13.5V7.5M13 13.5v-5"/>'),
  check: sv('<circle cx="10" cy="10" r="7.2"/><path d="M6.8 10.2l2.2 2.2 4.3-4.6"/>'),
  layers: sv('<path d="M10 3l7 3.8-7 3.8-7-3.8z"/><path d="M3 10.6l7 3.8 7-3.8"/><path d="M3 14l7 3.8 7-3.8" opacity=".55"/>'),
  shield: sv('<path d="M10 2.6l6 2.6v4.6c0 3.8-2.7 6.2-6 7.6-3.3-1.4-6-3.8-6-7.6V5.2z"/><path d="M7.2 10l2 2 3.8-4"/>'),
  blocks: sv('<path d="M3 3h6v5H3zM11 3h6v5h-6zM7 12h6v5H7z"/><path d="M6 8v2h8V8M10 10v2"/>'),
  caret: sv('<path d="M6 8l4 4 4-4"/>'),
  close: sv('<path d="M5 5l10 10M15 5L5 15"/>'),
  play: sv('<path d="M6.5 4.5v11l9-5.5z"/>'),
  refresh: sv('<path d="M15.5 8A6 6 0 0 0 4.6 6.4M4.5 12a6 6 0 0 0 10.9 1.6"/><path d="M4.3 3.2v3.4h3.4M15.7 16.8v-3.4h-3.4"/>'),
  download: sv('<path d="M10 3.5v9M6.3 9l3.7 3.7L13.7 9"/><path d="M4 16.5h12"/>'),
  ext: sv('<path d="M11 3.5h5.5V9M16.5 3.5L9.5 10.5"/><path d="M14 11.5v5H3.5V6H8.5"/>'),
  copy: sv('<path d="M7 7h9v9.5H7z"/><path d="M4 13V3.5h9"/>'),
  lock: sv('<rect x="4.5" y="9" width="11" height="8" rx="1.5"/><path d="M7 9V6.5a3 3 0 0 1 6 0V9"/>'),
};

/* ---------- 상수 ---------- */
const CARGO_COLOR = {
  CRUDE: "#5d4a3b", DIESEL: "#2f6fe0", GASOLINE: "#d7891c", KEROSENE: "#7357e6", NAPHTHA: "#119b8b",
  BUNKER: "#5f6b7d", BASE_OIL: "#8c6d45", CHEMICAL: "#bf3f78", SOLVENT: "#6d8a3c", LPG: "#0b8fb0",
};
const tint = (hex, a) => {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  const m = (c) => Math.round(c + (255 - c) * a);
  return `rgb(${m(r)},${m(g)},${m(b)})`;
};
const STATUS_KO = { PLANNED: "계획", ORDERED: "오더", WORKING: "작업 중", FIX: "FIX", COMPLETED: "완료" };
const DIR_KO = { IMPORT: "입고", EXPORT: "출하" };
const RISK_CLS = { APPLIES: "applies", CAUTION: "caution", NOT_APPLICABLE: "na", UNKNOWN: "unknown" };
const RISK_PILL = { APPLIES: "pill-red", CAUTION: "pill-amber", NOT_APPLICABLE: "pill-green", UNKNOWN: "pill-gray" };
const STATE_PILL = { "추천": "pill-brand", "선택됨": "pill-green", "현업 반영 완료": "pill-violet" };
const EVENT_KO = { RUN_CREATED: "계산 실행", DECISION_SELECT: "후보 확정", DECISION_CANCEL: "확정 취소", DECISION_APPLIED: "현업 반영 완료", EXPORT_DOCX: "보고서 Word 내려받기" };
const STAGES = ["입력 검증", "제약 정리", "후보 탐색", "체선료 계산", "리스크 점검", "보고서 작성", "결과 검증"];

const NAV = [
  { g: "선석 운영", items: [["plan", "접안 계획 비교", "plan"], ["vessels", "입항 예정 선박", "ship"], ["berths", "부두 · 제약", "berth"]] },
  { g: "체선료", items: [["sheets", "선박별 계산서", "sheet"], ["risk", "리스크 · 민감도", "risk"]] },
  { g: "계약", items: [["contracts", "계약서", "doc"]] },
  { g: "보고 · 결정", items: [["report", "보고서 · 메일", "report"], ["decisions", "확정 · 이력", "check"]] },
  { g: "시나리오", items: [["scenarios", "시나리오 라이브러리", "layers"]] },
  { g: "관리", items: [["qa", "검증", "shield"], ["arch", "아키텍처", "blocks"]] },
];

const S = {
  meta: null, rules: null, scenarios: [], contracts: [], ctDocs: {},
  sid: null, doc: null, edits: {}, runs: {}, run: null, label: "1안",
  busy: false, verify: null, route: null,
};

/* ---------- 공통 UI ---------- */
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("on");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("on"), 2600);
}

function renderNav() {
  const cur = parseHash().name;
  $("#sideNav").innerHTML = NAV.map((g) => `
    <div class="nav-group"><div class="nav-group-t">${g.g}</div>
      ${g.items.map(([k, label, ic]) => `<a class="nav-item ${cur === k ? "on" : ""}" href="#/${k}">${I[ic]}<span>${label}</span>${navCount(k)}</a>`).join("")}
    </div>`).join("");
}
function navCount(k) {
  if (k === "contracts" && S.contracts.length) return `<span class="count">${S.contracts.length}</span>`;
  if (k === "scenarios" && S.scenarios.length) return `<span class="count">${S.scenarios.length}</span>`;
  return "";
}

function renderCrumbs() {
  const cur = parseHash().name;
  for (const g of NAV) for (const [k, label] of g.items) {
    if (k === cur) { $("#crumbs").innerHTML = `<span>${g.g}</span><span class="sep">/</span><b>${label}</b>`; return; }
  }
  $("#crumbs").innerHTML = "";
}

function renderPick() {
  const sc = S.scenarios.find((x) => x.id === S.sid);
  $("#scenarioPick").innerHTML = sc
    ? `<span class="code">${code(sc.id)}</span><span class="t">${esc(sc.title)}</span>${S.run && S.run.edited ? '<span class="pill pill-amber">수정본</span>' : ""}${I.caret}`
    : `<span class="t">시나리오 선택</span>${I.caret}`;
}

function openPick() {
  const pop = $("#pop");
  if (pop.classList.contains("on")) { pop.classList.remove("on"); return; }
  const groups = groupScenarios();
  pop.innerHTML = groups.map(([cat, list]) => `<div class="pop-g">${esc(cat)}</div>` + list.map((s) => {
    const run = S.runs[s.id];
    const res = run && run.candidates && run.candidates[0] ? `${usd(run.baseline.complete ? run.baseline.total_usd : null)} → ${usd(run.candidates[0].total_usd)}` : `선박 ${s.vessels}척`;
    return `<div class="pop-i ${s.id === S.sid ? "on" : ""}" data-sid="${esc(s.id)}"><span class="code">${code(s.id)}</span><span class="t">${esc(s.title)}</span><small>${res}</small></div>`;
  }).join("")).join("");
  const b = $("#scenarioPick").getBoundingClientRect();
  pop.style.left = `${b.left}px`;
  pop.style.top = `${b.bottom + 6}px`;
  pop.classList.add("on");
}

function groupScenarios() {
  const m = new Map();
  for (const s of [...S.scenarios].sort((a, b) => a.order - b.order)) {
    if (!m.has(s.category)) m.set(s.category, []);
    m.get(s.category).push(s);
  }
  return [...m.entries()];
}

/* ---------- 라우팅 ---------- */
function parseHash() {
  const h = location.hash.replace(/^#\/?/, "");
  const [path, qs] = h.split("?");
  const [name, ...rest] = (path || "").split("/");
  return { name: name || "plan", arg: rest.length ? decodeURIComponent(rest.join("/")) : null, q: new URLSearchParams(qs || "") };
}

const PAGES = {};
function route() {
  const h = parseHash();
  S.route = h;
  renderNav();
  renderCrumbs();
  closeDrawer();
  $("#pop").classList.remove("on");
  const fn = PAGES[h.name] || PAGES.plan;
  try {
    fn(h.arg, h.q);
  } catch (e) {
    console.error(e);
    $("#page").innerHTML = `<div class="empty"><h3>화면을 그리지 못했습니다</h3><p>${esc(e.message)}</p></div>`;
  }
  window.scrollTo(0, 0);
}

/* ---------- 시나리오·실행 ---------- */
async function useScenario(sid, { run = true, force = false } = {}) {
  S.sid = sid;
  S.doc = await api(`/api/scenarios/${enc(sid)}`);
  S.edits = {};
  S.run = S.runs[sid] || null;
  renderPick();
  if (run && (force || !S.run)) await runScenario();
}

async function runScenario(docOverride = null) {
  if (S.busy) return;
  S.busy = true;
  const sc = S.scenarios.find((x) => x.id === S.sid);
  const t0 = performance.now();
  const page = $("#page");
  page.innerHTML = `<div class="loading"><div class="loading-card">
      <h3><span class="spin"></span>${esc(sc ? sc.title : S.sid)} 계산 중</h3>
      <p>도착 순서 기준안과 총 예상 체선료가 낮은 후보 3개를 찾습니다. 큰 시나리오는 최대 20초까지 걸립니다. <b id="elapsed">0.0초</b></p>
      <div class="muted" style="font-size:11.5px;margin-bottom:6px">처리 순서 — 끝나면 단계별 소요 시간을 '확정 · 이력'에서 볼 수 있습니다</div>
      <ol class="stage-list">${STAGES.map((s) => `<li><i></i>${s}</li>`).join("")}</ol></div></div>`;
  const timer = setInterval(() => {
    const el = $("#elapsed");
    if (el) el.textContent = `${((performance.now() - t0) / 1000).toFixed(1)}초`;
  }, 100);
  try {
    const body = docOverride ? { scenario: docOverride } : { scenario_id: S.sid };
    const slim = await api("/api/runs", { method: "POST", body: JSON.stringify(body) });
    const run = await api(`/api/runs/${slim.run_id}`);
    run.edited = Boolean(docOverride);
    S.runs[S.sid] = run;
    S.run = run;
    S.label = run.candidates && run.candidates.length ? run.candidates[0].label : "기준안";
  } catch (e) {
    toast(`계산 실패: ${e.message}`);
  } finally {
    clearInterval(timer);
    S.busy = false;
    renderPick();
    route();
  }
}

const sched = (label) => (!S.run ? null : label === "기준안" ? S.run.baseline : S.run.candidates.find((c) => c.label === label) || null);
const allSched = () => [S.run.baseline, ...S.run.candidates];
const vesselOf = (sch, vid) => sch.vessels.find((v) => v.vessel_id === vid);
const inputVessel = (vid) => ((S.run && S.run.input) || S.doc || { vessels: [] }).vessels.find((v) => v.id === vid) || {};
const cargoKo = (g) => (S.rules && S.rules.cargo.group_names[g]) || g;
const contractSum = (id) => S.contracts.find((c) => c.id === id);

function needRun() {
  if (S.busy) return true;
  if (!S.run) {
    $("#page").innerHTML = `<div class="empty"><h3>계산 결과가 없습니다</h3><p>시나리오를 고르고 계산을 실행해 주세요.</p><a class="btn btn-primary" href="#/scenarios">시나리오 라이브러리</a></div>`;
    return true;
  }
  if (S.run.status === "INPUT_ERROR") {
    $("#page").innerHTML = `<div class="page-head"><div><div class="eyebrow"><span class="code">${code(S.sid)}</span>입력 검증</div><h1>입력값을 고쳐야 계산할 수 있습니다</h1>
      <p class="lede">계산 전에 필수값·형식·시각 순서·참조를 검사했고, 아래 항목에서 멈췄습니다.</p></div></div>
      <div class="card"><table class="tbl"><tr><th>선박</th><th>항목</th><th>코드</th><th>내용</th></tr>
      ${S.run.input_issues.map((i) => `<tr><td>${esc(i.vessel)}</td><td class="mono">${esc(i.field)}</td><td><span class="tag">${esc(i.code)}</span></td><td>${esc(i.message)}</td></tr>`).join("")}</table></div>`;
    return true;
  }
  return false;
}

function segHTML(labels, cur, id, small = false) {
  return `<div class="seg ${small ? "small" : ""}" id="${id}">${labels.map((l) => {
    const s = sched(l);
    const sav = s && s.savings_pct != null && l !== "기준안" ? `<span class="d">${pct(s.savings_pct)}</span>` : "";
    return `<button data-label="${esc(l)}" class="${l === cur ? "on" : ""}"><span class="l">${l === "기준안" ? "기준안(도착 순서)" : esc(l)}${sav}</span>${small ? "" : `<span class="v">${s && (l !== "기준안" || s.complete) ? usd(s.total_usd) : "성립 안 함"}</span>`}</button>`;
  }).join("")}</div>`;
}
function bindSeg(id, onPick) {
  $$(`#${id} button`).forEach((b) => b.addEventListener("click", () => onPick(b.dataset.label)));
}

/* ---------- 1. 접안 계획 비교 ---------- */
PAGES.plan = function () {
  if (needRun()) return;
  const r = S.run, sc = r.scenario, card = sc.card || {};
  if (!sched(S.label)) S.label = r.candidates.length ? r.candidates[0].label : "기준안";
  const s = sched(S.label);
  const labels = ["기준안", ...r.candidates.map((c) => c.label)];
  $("#page").innerHTML = `
    <div class="page-head">
      <div>
        <div class="eyebrow"><span class="code">${code(sc.id)}</span>${esc(card.category || "")}${r.edited ? ' · <span class="pill pill-amber">입력 수정본</span>' : ""}</div>
        <h1>${esc(sc.title)}</h1>
        <p class="lede">${esc(card.question || sc.description || "")}</p>
      </div>
      <div class="head-actions">
        <button class="btn" id="btnRerun">${I.refresh}다시 계산</button>
        <a class="btn" href="#/report">${I.report}보고서 초안</a>
        <button class="btn btn-primary" id="btnDecide">${I.check}후보 확정</button>
      </div>
    </div>
    ${briefHTML(sc)}
    ${kpiHTML(s)}
    <div class="card">
      <div class="card-head">${segHTML(labels, S.label, "planSeg")}
        <div class="legend">
          <span><i class="lg lg-work"></i>작업</span><span><i class="lg lg-prep"></i>접안 준비·이안</span>
          <span><i class="lg lg-dem"></i>체선(정박종료 이후)</span><span><i class="lg lg-wait"></i>대기(ETA→접안)</span>
          <span><i class="lg lg-wx"></i>강풍 제한</span><span><i class="lg lg-mt"></i>정비</span><span><i class="lg lg-night"></i>야간</span>
          ${sc.berths.includes("Buoy") ? '<span><i class="lg lg-tide"></i>조석 창</span>' : ""}
        </div>
      </div>
      <div class="gantt" id="gantt"></div>
    </div>
    <div class="grid-2">
      <div class="card"><div class="card-head"><h3>${S.label === "기준안" ? "기준안이란" : `기준안 대비 ${esc(S.label)}에서 바뀐 것`}</h3><span class="sub">선박을 누르면 계산서가 열립니다</span></div>${changesHTML(s)}</div>
      <div class="card"><div class="card-head"><h3>이 안의 근거</h3></div><div class="card-body">${groundsHTML(s)}</div></div>
    </div>
    <div class="card"><div class="card-head"><h3>선박별 예상 체선료 — ${S.label === "기준안" ? "기준안" : esc(S.label)}</h3><span class="sub">총 ${usd(s.total_usd)} · 선박별 금액의 합</span>
      <div class="right"><a class="btn btn-sm" href="/api/runs/${r.run_id}/schedule.csv?label=${enc(S.label)}">${I.download}일정 CSV</a></div></div>
      <div class="tbl-wrap">${vesselTableHTML(s)}</div></div>`;
  bindSeg("planSeg", (l) => { S.label = l; PAGES.plan(); });
  $("#btnRerun").onclick = () => runScenario(r.edited ? applyEdits() : null);
  $("#btnDecide").onclick = () => openDecide();
  drawGantt($("#gantt"), s);
  $$("[data-vid]").forEach((el) => el.addEventListener("click", () => openSheet(S.label, el.dataset.vid)));
};

function briefHTML(sc) {
  const c = sc.card || {};
  const clauses = (c.clauses || []).map((t) => {
    const m = /^(CT-\d{4}-\d{2})\s*(.*)$/.exec(t);
    if (!m) return `<span class="chip">${esc(t)}</span>`;
    const ref = m[2].replace(/\s*\(.*\)$/, "").replace(/\s+(상당|부분 화물 비례|기상 감면 없음).*$/, "");
    return `<a class="chip chip-contract" href="#/contracts/${enc(m[1])}${ref ? `?c=${enc(ref)}` : ""}">${I.doc}${esc(m[1])} ${esc(m[2])}</a>`;
  }).join("");
  const rules = (c.rules || []).map((id) => `<span class="chip chip-rule" title="${esc(ruleText(id))}">${esc(id)} <b>${esc(ruleName(id))}</b></span>`).join("");
  return `<div class="card brief">
    <div><h4>상황</h4><p>${esc(c.situation || sc.description || "")}</p><h4>판단할 점</h4><p class="q">${esc(c.question || "")}</p></div>
    <div><h4>결과에서 확인할 것</h4><ul class="checks">${(c.watch || []).map((w) => `<li>${esc(w)}</li>`).join("")}</ul>
      ${rules ? `<h4>관련 운영 기준</h4><div class="chips" style="margin-bottom:10px">${rules}</div>` : ""}
      ${clauses ? `<h4>관련 계약 조항</h4><div class="chips">${clauses}</div>` : ""}</div></div>`;
}
const ruleName = (id) => { const r = S.rules && S.rules.registry.find((x) => x.id === id); return r ? r.name : ""; };
const ruleText = (id) => { const r = S.rules && S.rules.registry.find((x) => x.id === id); return r ? `${r.text} (${r.source})` : ""; };

function kpiHTML(s) {
  const r = S.run, b = r.baseline, best = r.candidates[0];
  const missing = (b.infeasible || []).map((x) => x.vessel);
  const risks = s.label === "기준안" ? [] : (r.risks[s.label] || []).filter((x) => x.status === "APPLIES");
  const st = r.search, stats = st.stats || {};
  const isBase = s.label === "기준안";
  const savTile = !b.complete
    ? `<div class="kpi"><div class="kpi-l">절감액</div><div class="kpi-v">비교 불가</div><div class="kpi-s">기준안이 성립하지 않음</div></div>`
    : isBase
      ? `<div class="kpi"><div class="kpi-l">최대 절감(1안)</div><div class="kpi-v">${usd(best ? best.savings_usd : null)}<small>${best ? pct(best.savings_pct) : ""}</small></div><div class="kpi-s">기준안 대비</div></div>`
      : `<div class="kpi good"><div class="kpi-l">절감액</div><div class="kpi-v">${usd(s.savings_usd)}<small>${pct(s.savings_pct)}</small></div><div class="kpi-s">배정이 바뀐 선박 ${(s.changed_vessels || []).length}척</div></div>`;
  return `<div class="kpis">
    <div class="kpi"><div class="kpi-l">기준안 · 도착 순서</div><div class="kpi-v">${b.complete ? usd(b.total_usd) : "성립 안 함"}</div>
      <div class="kpi-s">${b.complete ? "비교 기준 · 현행 실적 아님" : `${esc(missing.join(", "))} 배정 불가 — ${esc((b.infeasible[0] || {}).detail || "")}`}</div></div>
    <div class="kpi accent"><div class="kpi-l">${isBase ? "기준안 총 예상 체선료" : `${esc(s.label)} 총 예상 체선료`}</div><div class="kpi-v">${s.complete || !isBase ? usd(s.total_usd) : "-"}</div>
      <div class="kpi-s">${isBase ? "도착 순서대로, 가장 이른 부두" : `${esc(st.status_ko)} · 탐색 ${(stats.bnb || {}).nodes ?? "-"}개 상태 · ${stats.elapsed_s ?? "-"}초`}</div></div>
    ${savTile}
    <div class="kpi ${s.violations.length ? "warn" : ""}"><div class="kpi-l">하드 제약 위반</div><div class="kpi-v">${s.violations.length}건</div>
      <div class="kpi-s">${isBase ? "도착 순서 배정" : `독립 검증기로 다시 확인 · 후보 ${r.candidates.length}개`}</div></div>
    <div class="kpi ${risks.length ? "warn" : ""}"><div class="kpi-l">남은 리스크</div><div class="kpi-v">${isBase ? "-" : `${risks.length}건`}</div>
      <div class="kpi-s">${isBase ? "후보에서 점검" : risks.length ? esc(risks.map((x) => x.name).join(" · ")) : "해당 없음"}</div></div>
  </div>`;
}

function changesHTML(s) {
  const r = S.run;
  if (s.label === "기준안") {
    const miss = r.baseline.infeasible || [];
    return `<div class="card-body"><p class="note-box">선박을 <b>도착(ETA) 순서</b>대로, 그때 가장 일찍 붙일 수 있는 부두에 배정한 비교 기준입니다. 실제 현장 실적이 아니라, 후보가 얼마나 줄였는지를 재는 잣대입니다.</p>
      ${miss.length ? `<p class="note-box bad" style="margin-top:10px"><b>기준안이 성립하지 않습니다.</b> ${miss.map((x) => `${esc(x.vessel)}: ${esc(x.reason)} — ${esc(x.detail)}`).join("<br>")}</p>` : ""}</div>`;
  }
  const rows = s.vessels.filter((v) => v.changed || (v.delta_usd && Math.abs(v.delta_usd) >= 1));
  if (!rows.length) return `<div class="card-body"><p class="note-box">기준안과 배정이 같습니다.</p></div>`;
  rows.sort((a, b) => (a.delta_usd ?? 0) - (b.delta_usd ?? 0));
  return `<ul class="chg">${rows.map((v) => {
    const bl = v.baseline;
    const mv = bl ? `${esc(bl.berth)} ${short(bl.etb)} → ${esc(v.berth)} ${short(v.etb)}` : `기준안에서 배정 불가 → ${esc(v.berth)} ${short(v.etb)}`;
    const d = v.delta_usd;
    const cls = d == null ? "" : d < 0 ? "delta-dn" : d > 0 ? "delta-up" : "muted";
    return `<li data-vid="${esc(v.vessel_id)}"><span class="who">${esc(v.vessel_id)}<small>${esc(v.name)}</small></span><span class="amt ${cls}">${d == null ? usd(v.amount_usd) : usdS(d)}</span>
      <span class="mv">${mv}</span><span class="why">${esc(v.sheet.summary)}</span></li>`;
  }).join("")}</ul>`;
}

function groundsHTML(s) {
  const r = S.run;
  if (s.label === "기준안") {
    return `<div class="kv"><span class="k">배정 방식</span><span class="v">ETA 순서 · 가장 이른 접안 가능 부두</span>
      <span class="k">운영 기준</span><span class="v">${esc(ruleName("OPT-01"))} (OPT-01)</span>
      <span class="k">제약 위반</span><span class="v">${s.violations.length}건</span>
      <span class="k">총 예상 체선료</span><span class="v">${s.complete ? usd(s.total_usd) : "성립 안 함"}</span></div>`;
  }
  const st = r.search, stats = st.stats || {}, bnb = stats.bnb || {};
  const checks = r.checks.filter((c) => c.what.startsWith(s.label) || !/^(기준안|\d안)/.test(c.what));
  const risks = (r.risks[s.label] || []).filter((x) => x.status === "APPLIES");
  const unconfirmed = (s.statuses || []).filter((x) => x !== "확정 규칙만 사용");
  return `<div class="kv">
      <span class="k">탐색 결과</span><span class="v">${esc(st.optimality_ko || st.status_ko)}</span>
      <span class="k">탐색 규모</span><span class="v">상태 ${bnb.nodes ?? "-"}개 확인 · ${bnb.pruned ?? "-"}개 가지치기 · ${stats.elapsed_s ?? "-"}초${st.gap ? ` · 갭 ${(st.gap * 100).toFixed(1)}%` : ""}</span>
      <span class="k">후보 순위</span><span class="v">${s.meta.rank}위 / ${r.candidates.length}개 (후보끼리 1척 이상 배정이 다름)</span>
      <span class="k">규칙 상태</span><span class="v">${unconfirmed.length ? `<span class="pill pill-amber">${esc(unconfirmed.join(" · "))}</span>` : "확정·팀 정의 규칙만 사용"}</span>
      <span class="k">남은 리스크</span><span class="v">${risks.length ? `${esc(risks.map((x) => x.name).join(" · "))} — <a href="#/risk">점검 보기</a>` : "해당 없음"}</span>
    </div>
    <div style="margin-top:12px" class="chips">${checks.map((c) => `<span class="chip ${c.ok ? "" : "chip-contract"}">${c.ok ? '<span class="ok-ic">✓</span>' : '<span class="bad-ic">✕</span>'} ${esc(c.what)}</span>`).join("")}</div>`;
}

function vesselTableHTML(s) {
  const rows = [...s.vessels].sort((a, b) => ms(a.etb) - ms(b.etb));
  return `<table class="tbl"><tr><th>선박</th><th>계약서</th><th>부두</th><th>ETA</th><th>접안(ETB)</th><th class="n">대기</th><th>정박종료</th><th>호스 분리</th><th class="n">체선</th><th class="n">예상 체선료</th>${s.label === "기준안" ? "" : '<th class="n">기준안 대비</th>'}</tr>
    ${rows.map((v) => {
      const iv = inputVessel(v.vessel_id);
      const wait = hrs(v.eta, v.etb);
      const tags = [v.kind === "FIX" ? '<span class="tag tag-fix">FIX</span>' : "", v.kind === "WORKING" ? '<span class="tag tag-work">작업 중</span>' : "", v.priority === "URGENT" ? '<span class="tag tag-urgent">긴급</span>' : ""].join(" ");
      const ct = v.contract_id ? `<a href="#/contracts/${enc(v.contract_id)}" onclick="event.stopPropagation()">${esc(v.contract_id)}</a><span class="vsub">${esc(v.contract_type)} · 허용 ${fh(v.laytime_minutes / 60)} · $${v.rate_usd_day.toLocaleString("en-US")}/일</span>` : '<span class="muted">조건 직접 입력</span>';
      const d = v.delta_usd;
      return `<tr class="click" data-vid="${esc(v.vessel_id)}">
        <td><span class="vname"><span class="swatch" style="background:${CARGO_COLOR[v.cargo_group] || "#999"}"></span>${esc(v.vessel_id)} ${esc(v.name)}</span> ${tags}<span class="vsub">${esc(v.vessel_type_ko)} · ${esc(cargoKo(v.cargo_group))} ${esc(DIR_KO[v.direction] || "")} ${iv.qty ? `${Number(iv.qty).toLocaleString("en-US")} kl` : ""}</span></td>
        <td>${ct}</td><td><b>${esc(v.berth)}</b></td><td class="mono-n">${short(v.eta)}</td><td class="mono-n"><b>${short(v.etb)}</b></td>
        <td class="n">${wait > 0.01 ? fh(wait) : '<span class="amt-zero">0</span>'}</td><td class="mono-n">${short(v.laytime_end)}</td><td class="mono-n">${short(v.hose_off)}</td>
        <td class="n">${v.demurrage_hours > 0 ? fh(v.demurrage_hours) : '<span class="amt-zero">0</span>'}</td>
        <td class="n ${v.amount_usd > 0 ? "amt-pos" : "amt-zero"}">${usd(v.amount_usd)}</td>
        ${s.label === "기준안" ? "" : `<td class="n ${d < 0 ? "delta-dn" : d > 0 ? "delta-up" : "amt-zero"}">${d == null ? "신규 배정" : usdS(d)}</td>`}</tr>`;
    }).join("")}
    <tr><td colspan="9" style="text-align:right;font-weight:600">합계</td><td class="n"><b>${usd(s.total_usd)}</b></td>${s.label === "기준안" ? "" : `<td class="n delta-dn">${s.savings_usd != null ? usdS(-s.savings_usd) : "-"}</td>`}</tr></table>`;
}

/* ---------- 간트 ---------- */
const ROWH = 68;
function drawGantt(host, s) {
  const r = S.run, sc = r.scenario, berths = sc.berths;
  const H = 3.6e6, H6 = 6 * H, KST = 9 * H;
  let t0 = ms(sc.horizon.start), t1 = ms(sc.horizon.end);
  for (const v of s.vessels) { t0 = Math.min(t0, ms(v.eta), ms(v.etb)); t1 = Math.max(t1, ms(v.etu)); }
  t0 = Math.floor((t0 + KST) / H6) * H6 - KST;
  t1 = Math.ceil((t1 + KST) / H6) * H6 - KST;
  const hours = (t1 - t0) / H;
  const avail = Math.max(640, host.clientWidth - 106);
  const pxh = Math.max(9, avail / hours);
  const W = Math.round(hours * pxh);
  const X = (iso) => ((ms(iso) - t0) / H) * pxh;
  const clipX = (a, b) => [Math.max(0, X(a)), Math.min(W, X(b))];

  let axis = "", grid = "", nights = "";
  const DAYMS = 24 * H;
  const firstMid = Math.ceil((t0 + KST) / DAYMS) * DAYMS - KST;
  const skipFirst = firstMid !== t0 && ((firstMid - t0) / H) * pxh < 76;
  for (let t = t0; t <= t1; t += H6) {
    const x = ((t - t0) / H) * pxh;
    const d = new Date(t + KST);
    const hh = d.getUTCHours();
    if (hh === 0 || (t === t0 && !skipFirst)) axis += `<div class="g-day" style="left:${x}px">${String(d.getUTCMonth() + 1).padStart(2, "0")}/${String(d.getUTCDate()).padStart(2, "0")}<small>(${WD[d.getUTCDay()]})</small></div>`;
    if (hh !== 0 && t !== t0 && t !== t1) axis += `<div class="g-hr" style="left:${x}px">${String(hh).padStart(2, "0")}</div>`;
    grid += `<div class="g-grid ${hh === 0 ? "day" : ""}" style="left:${x}px"></div>`;
  }
  for (const [a, b] of sc.nights || []) {
    const [x1, x2] = clipX(a, b);
    if (x2 > x1) nights += `<div class="g-night" style="left:${x1}px;width:${x2 - x1}px"></div>`;
  }
  const labeled = new Set();
  const rows = berths.map((bid, i) => {
    let inner = "";
    for (const rs of r.restrictions) {
      if (!(rs.berths.includes(bid) || rs.berths.includes("*"))) continue;
      const [x1, x2] = clipX(rs.start, rs.end);
      if (x2 <= x1) continue;
      const cls = rs.reason === "WEATHER" ? "wx" : rs.reason === "MAINTENANCE" ? "mt" : "user";
      const key = `${rs.reason}|${rs.start}|${rs.end}`;
      const wind = /(\d+(?:\.\d+)?) m\/s/.exec(rs.note || "");
      const t = rs.reason === "WEATHER" ? `강풍 접안 금지${wind ? ` · ${wind[1]} m/s` : ""}` : esc(rs.note || "부두 제한");
      inner += `<div class="g-band ${cls}" style="left:${x1}px;width:${x2 - x1}px" title="${esc(rs.note || "")} ${short(rs.start)}~${short(rs.end)}">${labeled.has(key) ? "" : `<span class="g-band-t" style="top:auto;bottom:3px">${t}</span>`}</div>`;
      labeled.add(key);
    }
    for (const [a, b] of (sc.tide_windows || {})[bid] || []) {
      const [x1, x2] = clipX(a, b);
      if (x2 > x1) inner += `<div class="g-tide" style="left:${x1}px;width:${x2 - x1}px" title="조석 시간창 ${short(a)}~${short(b)}"></div>`;
    }
    const here = s.vessels.filter((v) => v.berth === bid).sort((a, b) => ms(a.etb) - ms(b.etb));
    here.forEach((v, k) => {
      const col = CARGO_COLOR[v.cargo_group] || "#667085";
      const xe = X(v.eta), xb = X(v.etb), xu = X(v.etu);
      const lane = 3 + (k % 2) * 5;
      if (xb - xe > 2) inner += `<div class="g-wait" style="left:${xe}px;width:${xb - xe}px;top:${lane + 2}px;border-color:${col}"></div>`;
      inner += `<div class="g-eta" style="left:${xe}px;top:${lane - 3}px;border-top-color:${col}" title="${esc(v.vessel_id)} ETA ${short(v.eta)}"></div>`;
      const seg = (a, b, c, cls = "") => { const w = Math.max(0, X(b) - X(a)); return w > 0 ? `<div class="g-seg ${cls}" style="width:${w}px;background:${c}"></div>` : ""; };
      const kindCls = v.kind === "FIX" ? "fix" : v.kind === "WORKING" ? "working" : "";
      inner += `<div class="g-bar ${kindCls}" data-vid="${esc(v.vessel_id)}" style="left:${xb}px;width:${Math.max(4, xu - xb)}px">
        ${seg(v.etb, v.work_start, tint(col, 0.62))}${seg(v.work_start, v.work_end, col, "w")}${seg(v.work_end, v.etu, tint(col, 0.62))}
        <div class="g-txt">${v.kind === "FIX" ? I.lock.replace("<svg", '<svg style="width:12px;height:12px;flex:none"') : ""}${esc(v.vessel_id)}<span>${esc(String(v.name).replace(/^MT\s+/, ""))}</span></div></div>`;
      if (v.amount_usd > 0) {
        const xl = Math.max(xb, X(v.laytime_end)), xh = X(v.hose_off);
        inner += `<div class="g-lt" style="left:${X(v.laytime_end)}px" title="정박종료 ${short(v.laytime_end)}"></div>`;
        inner += `<div class="g-dem" style="left:${xl}px;width:${Math.max(3, xh - xl)}px"></div><div class="g-dem-t" style="left:${xl}px">${usd(v.amount_usd)}</div>`;
      }
    });
    return `<div class="g-row" style="top:${i * ROWH}px">${inner}</div>`;
  }).join("");
  const labels = berths.map((bid) => {
    const b = S.rules && S.rules.terminal.berths.find((x) => x.id === bid);
    const groups = b ? b.cargo_groups.map(cargoKo).join("·") : "";
    return `<div class="g-label" title="${esc(groups)}"><b>${esc(bid)}</b><small>${b ? (b.type === "BUOY" ? "부이" : "부두") : ""} · ${esc(groups)}</small></div>`;
  }).join("");
  host.innerHTML = `<div class="g-wrap"><div class="g-labels"><div class="g-axis-sp"></div>${labels}</div>
    <div class="g-scroll"><div class="g-canvas" style="width:${W}px"><div class="g-axis">${axis}</div>
      <div class="g-body" style="height:${berths.length * ROWH}px">${nights}${grid}${rows}</div></div></div></div>`;
  $$(".g-bar", host).forEach((el) => {
    const v = vesselOf(s, el.dataset.vid);
    el.addEventListener("mousemove", (e) => showTip(e, v));
    el.addEventListener("mouseleave", hideTip);
  });
}

function showTip(e, v) {
  const t = $("#tip");
  t.innerHTML = `<b>${esc(v.vessel_id)} ${esc(v.name)}</b> · ${esc(v.vessel_type_ko)} · ${esc(cargoKo(v.cargo_group))}
    <div class="r"><span>ETA</span><span>${short(v.eta)}</span><span>접안(ETB)</span><span>${short(v.etb)} · ${esc(v.berth)}</span>
    <span>작업</span><span>${short(v.work_start)} ~ ${short(v.work_end)}</span><span>호스 분리</span><span>${short(v.hose_off)}</span>
    <span>정박종료</span><span>${short(v.laytime_end)}</span><span>예상 체선료</span><span class="${v.amount_usd > 0 ? "dem" : ""}">${usd(v.amount_usd)}${v.demurrage_hours > 0 ? ` (${fh(v.demurrage_hours)})` : ""}</span></div>`;
  t.classList.add("on");
  const x = Math.min(window.innerWidth - 340, e.clientX + 14), y = Math.min(window.innerHeight - 190, e.clientY + 14);
  t.style.left = `${x}px`;
  t.style.top = `${y}px`;
}
function hideTip() { $("#tip").classList.remove("on"); }

/* ---------- 계산서(서랍) ---------- */
function chipHTML(b) {
  const t = esc(b.text);
  if (b.kind === "계약") {
    if (b.contract_id && b.clauses && b.clauses.length) return `<a class="chip chip-contract" href="#/contracts/${enc(b.contract_id)}?c=${enc(b.clauses[0])}" title="계약서 조항으로 이동">${I.doc}${t}</a>`;
    if (b.contract_id) return `<a class="chip chip-contract" href="#/contracts/${enc(b.contract_id)}">${I.doc}${t}</a>`;
    return `<span class="chip chip-contract">${I.doc}${t}</span>`;
  }
  if (b.kind === "운영 기준") return `<span class="chip chip-rule" title="${esc(b.detail || "")}">${esc(b.rule_id || "")} <b>${esc(String(b.text).replace(b.rule_id || "", "").trim())}</b></span>`;
  if (b.kind === "부두 기준") return `<span class="chip chip-berth" title="${esc(b.detail || "")}">${t}</span>`;
  if (b.kind === "입력") return `<span class="chip chip-input">입력 · ${t}</span>`;
  if (b.kind === "실적") return `<span class="chip chip-record" title="${esc(b.detail || "")}">실적 · ${t}</span>`;
  return `<span class="chip chip-calc" title="${esc(b.detail || "")}">${t}</span>`;
}

function sheetHTML(v, label) {
  const sh = v.sheet, c = sh.contract || {};
  const cs = c.id ? contractSum(c.id) : null;
  const base = label !== "기준안" ? vesselOf(S.run.baseline, v.vessel_id) : null;
  const steps = sh.steps.map((st, i) => {
    const cls = i === 1 || i === 4 ? "key" : i === 8 ? "money" : "";
    const pushes = (st.pushes || []).length ? `<ul class="pushes">${st.pushes.map((p) => `<li><b>${esc(p.rule_id)}</b>${esc(p.category)} ${short(p.from)} → ${short(p.to)} (${fh(p.minutes / 60)}) — ${esc(p.detail)}</li>`).join("")}</ul>` : "";
    return `<li class="${cls}"><div class="step-n">${i + 1}</div><div class="step-main">
      <div class="step-top"><span class="step-title">${esc(st.title)}</span><span class="step-val">${esc(st.value)}</span></div>
      <div class="formula">${esc(st.formula)}</div>${st.note ? `<div class="step-note">${esc(st.note)}</div>` : ""}${pushes}
      <div class="chips">${st.basis.map(chipHTML).join("")}</div></div></li>`;
  }).join("");
  const ctBox = c.id ? `<div class="ct-mini">
      <div class="head">${I.doc.replace("<svg", '<svg style="width:15px;height:15px;color:var(--brand)"')}<a href="#/contracts/${enc(c.id)}">${esc(c.id)}</a><span class="muted">${esc(c.title)} · ${esc(c.counterparty)}</span></div>
      <div><div class="k">허용 정박시간</div><div class="v">${esc(c.laytime)}${cs && cs.pro_rata ? " (비례)" : ""}</div></div>
      <div><div class="k">체선료율</div><div class="v">$${Number(c.rate_usd_day).toLocaleString("en-US")}/일</div></div>
      <div><div class="k">기상 대기</div><div class="v">${c.weather_ratio ? `${c.weather_ratio * 100}% 공제` : "공제 없음"}</div></div>
      <div><div class="k">주간 NOR</div><div class="v">${c.daylight_nor ? "적용" : "미적용"}</div></div></div>` : "";
  const cmp = base ? `<h4 style="margin:18px 0 8px;font-size:13px">기준안과 비교</h4><div class="cmp-box"><table class="tbl">
      <tr><th></th><th>기준안</th><th>${esc(label)}</th></tr>
      <tr><td>부두 · 접안</td><td>${esc(base.berth)} ${short(base.etb)}</td><td><b>${esc(v.berth)} ${short(v.etb)}</b></td></tr>
      <tr><td>호스 분리</td><td>${short(base.hose_off)}</td><td>${short(v.hose_off)}</td></tr>
      <tr><td>체선 시간</td><td>${fh(base.demurrage_hours)}</td><td>${fh(v.demurrage_hours)}</td></tr>
      <tr><td>예상 체선료</td><td>${usd(base.amount_usd)}</td><td><b>${usd(v.amount_usd)}</b> <span class="${v.delta_usd < 0 ? "delta-dn" : v.delta_usd > 0 ? "delta-up" : "muted"}">${usdS(v.delta_usd)}</span></td></tr></table></div>` : "";
  return `<div class="sheet-sum ${v.amount_usd > 0 ? "pos" : "zero"}"><div class="amt">${usd(v.amount_usd)}</div><p>${esc(sh.summary)}</p></div>
    ${ctBox}<ol class="steps">${steps}</ol>${cmp}`;
}

function openSheet(label, vid) {
  const s = sched(label);
  const v = s && vesselOf(s, vid);
  if (!v) return;
  const iv = inputVessel(vid);
  $("#drawer").innerHTML = `<div class="drawer-head"><div><div class="eyebrow">${esc(label === "기준안" ? "기준안" : label)} · 체선료 계산서</div>
      <h2>${esc(v.vessel_id)} ${esc(v.name)}</h2>
      <div class="sub">${esc(v.vessel_type_ko)} · ${esc(cargoKo(v.cargo_group))} ${esc(DIR_KO[v.direction] || "")}${iv.qty ? ` ${Number(iv.qty).toLocaleString("en-US")} kl` : ""} · GRT ${Number(v.grt).toLocaleString("en-US")}${iv.remarks ? ` · ${esc(iv.remarks)}` : ""}</div></div>
      <button class="icon-btn" id="drawerClose" title="닫기">${I.close}</button></div>
    <div class="drawer-body">${sheetHTML(v, label)}</div>`;
  $("#drawer").classList.add("on");
  $("#scrim").classList.add("on");
  $("#drawerClose").onclick = closeDrawer;
  $$(".g-bar").forEach((el) => el.classList.toggle("sel", el.dataset.vid === vid));
}
function closeDrawer() {
  $("#drawer").classList.remove("on");
  $("#scrim").classList.remove("on");
  $$(".g-bar.sel").forEach((el) => el.classList.remove("sel"));
}

/* ---------- 2. 입항 예정 선박 ---------- */
function applyEdits() {
  const doc = JSON.parse(JSON.stringify(S.doc));
  for (const v of doc.vessels) if (S.edits[v.id]) v.eta = S.edits[v.id];
  return doc;
}
PAGES.vessels = function () {
  if (!S.doc) { $("#page").innerHTML = '<div class="empty"><h3>시나리오를 골라 주세요</h3></div>'; return; }
  const issues = (S.run && S.run.input_issues) || [];
  const vs = S.doc.vessels;
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow"><span class="code">${code(S.sid)}</span>입항 예정 선박</div><h1>선박 ${vs.length}척 · ${esc(S.doc.title)}</h1>
      <p class="lede">ETA를 바꾸면 같은 규칙·계약으로 다시 계산합니다(원본 시나리오는 바뀌지 않음). 작업 중·FIX 선박은 일정이 고정되어 재배정하지 않습니다.</p></div>
      <div class="head-actions"><button class="btn" id="btnReset">원래대로</button><button class="btn btn-primary" id="btnRecalc">${I.play}변경 내용으로 다시 계산</button></div></div>
    ${issues.length ? `<div class="note-box warn" style="margin-bottom:14px">${issues.map((i) => `${esc(i.vessel)} ${esc(i.field)}: ${esc(i.message)}`).join("<br>")}</div>` : ""}
    <div class="card"><div class="tbl-wrap"><table class="tbl">
      <tr><th>선박</th><th>상태</th><th>화물</th><th class="n">물량</th><th class="n">GRT</th><th class="n">LOA</th><th class="n">흘수</th><th>ETA (KST)</th><th>계약서</th><th>비고</th></tr>
      ${vs.map((v) => {
        const cs = contractSum(v.contract_id);
        const fixed = v.status === "FIX" ? `FIX ${esc(v.fixed.berth)} ${short(v.fixed.etb)}` : v.status === "WORKING" ? `작업 중 ${esc(v.working.berth)}` : STATUS_KO[v.status] || v.status;
        const g = S.rules ? S.rules.cargo.map[v.material_code] : "";
        return `<tr><td><span class="vname"><span class="swatch" style="background:${CARGO_COLOR[g] || "#999"}"></span>${esc(v.id)} ${esc(v.name)}</span>${v.priority === "URGENT" ? ' <span class="tag tag-urgent">긴급</span>' : ""}<span class="vsub">${esc((S.rules && S.rules.terminal && v.vessel_type) ? ({ CRUDE: "원유선", PRODUCT: "제품선", SPECIAL_PRODUCT: "특수제품선", BASE_OIL: "기유선", CHEMICAL: "화학선", LPG: "가스선" }[v.vessel_type] || v.vessel_type) : v.vessel_type)}</span></td>
          <td>${v.status === "FIX" ? `<span class="tag tag-fix">${fixed}</span>` : v.status === "WORKING" ? `<span class="tag tag-work">${fixed}</span>` : `<span class="tag">${fixed}</span>`}</td>
          <td>${esc(cargoKo(g))} ${esc(DIR_KO[v.direction] || "")}<span class="vsub mono">${esc(v.material_code)}</span></td>
          <td class="n">${Number(v.qty).toLocaleString("en-US")} kl</td><td class="n">${Number(v.grt).toLocaleString("en-US")}</td><td class="n">${v.loa} m</td><td class="n">${v.draft} m</td>
          <td>${v.status === "PLANNED" || v.status === "ORDERED" ? `<input class="inp sm ${S.edits[v.id] ? "changed" : ""}" data-eta="${esc(v.id)}" value="${esc(S.edits[v.id] || v.eta)}">` : `<span class="mono">${esc(v.eta)}</span>`}</td>
          <td>${cs ? `<a href="#/contracts/${enc(cs.id)}">${esc(cs.id)}</a><span class="vsub">${esc(cs.type)} · ${cs.laytime_hours}h${cs.pro_rata ? "(비례)" : ""} · $${cs.rate_usd_day.toLocaleString("en-US")}/일</span>` : '<span class="muted">직접 입력</span>'}</td>
          <td class="muted" style="max-width:260px">${esc(v.remarks || "")}</td></tr>`;
      }).join("")}</table></div></div>`;
  $$("[data-eta]").forEach((el) => el.addEventListener("change", () => {
    const v = vs.find((x) => x.id === el.dataset.eta);
    if (el.value.trim() && el.value.trim() !== v.eta) S.edits[v.id] = el.value.trim(); else delete S.edits[v.id];
    el.classList.toggle("changed", Boolean(S.edits[v.id]));
  }));
  $("#btnReset").onclick = async () => { S.edits = {}; if (S.run && S.run.edited) { delete S.runs[S.sid]; await useScenario(S.sid, { force: true }); } else PAGES.vessels(); };
  $("#btnRecalc").onclick = async () => {
    if (!Object.keys(S.edits).length) { toast("바뀐 ETA가 없습니다"); return; }
    const doc = applyEdits();
    location.hash = "#/plan";
    await runScenario(doc);
  };
};

/* ---------- 3. 부두 · 제약 ---------- */
PAGES.berths = function () {
  if (needRun()) return;
  const r = S.run, sc = r.scenario, T = S.rules.terminal;
  const act = sc.berths;
  const bs = T.berths.filter((b) => act.includes(b.id));
  const seen = new Map();
  for (const rs of r.restrictions) {
    if (!rs.berths.some((b) => act.includes(b) || b === "*")) continue;
    const k = `${rs.reason}|${rs.start}|${rs.end}|${rs.note}`;
    if (!seen.has(k)) seen.set(k, { ...rs, berths: [] });
    seen.get(k).berths.push(...rs.berths.filter((b) => act.includes(b) || b === "*"));
  }
  const wx = r.input.weather_forecast;
  const inv = r.input.inventory || [];
  const elig = r.eligibility || {};
  const vids = Object.keys(elig);
  const lim = (T.weather_limits || {}).berthing_wind_ms || {};
  const limit = typeof lim === "number" ? lim : Math.min(...Object.values(lim));
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow"><span class="code">${code(sc.id)}</span>부두 · 제약</div><h1>이 시나리오에 걸린 부두 조건</h1>
      <p class="lede">부두 제원·Shifting 시간은 기준 정보 표(${esc(T.version)}), 제한은 예보와 입력에서 만들었습니다. 계산은 이 표들만 읽습니다.</p></div></div>
    <div class="card"><div class="card-head"><h3>부두 ${bs.length}곳</h3><span class="sub">멘토링 PPT 06쪽 Shifting 표 · 가상 제원</span></div><div class="tbl-wrap"><table class="tbl">
      <tr><th>부두</th><th>형태</th><th>취급 화물</th><th class="n">최대 DWT</th><th class="n">LOA</th><th class="n">최소 PBL</th><th class="n">최대 흘수(입고)</th><th class="n">Direction</th><th class="n">Switching</th></tr>
      ${bs.map((b) => { const sh = T.shifting_hours[b.shift_group] || {}; return `<tr><td><b>${esc(b.id)}</b></td><td>${b.type === "BUOY" ? "부이" : "부두"}</td><td>${b.cargo_groups.map((g) => `<span class="tag"><span class="swatch" style="background:${CARGO_COLOR[g] || "#999"}"></span>${esc(cargoKo(g))}</span>`).join(" ")}</td>
        <td class="n">${b.max_dwt.toLocaleString("en-US")}</td><td class="n">${b.min_loa}~${b.max_loa} m</td><td class="n">${b.min_pbl} m</td><td class="n">${b.max_draft} m</td><td class="n">${sh.direction ?? "-"}h</td><td class="n">${sh.switching ?? "-"}h</td></tr>`; }).join("")}
    </table></div></div>
    <div class="grid-2">
      <div class="card"><div class="card-head"><h3>부두 사용 제한</h3><span class="sub">제한 동안 새 접안 불가 · 이미 붙은 배는 작업 계속</span></div>
        ${seen.size ? `<table class="tbl"><tr><th>사유</th><th>부두</th><th>시작</th><th>끝</th><th>내용</th></tr>${[...seen.values()].map((x) => `<tr><td><span class="tag">${x.reason === "WEATHER" ? "기상" : x.reason === "MAINTENANCE" ? "정비" : "사용자"}</span></td><td>${esc([...new Set(x.berths)].join(", "))}</td><td class="mono-n">${short(x.start)}</td><td class="mono-n">${short(x.end)}</td><td>${esc(x.note)}</td></tr>`).join("")}</table>` : '<div class="card-body muted">등록된 제한이 없습니다.</div>'}</div>
      <div class="card"><div class="card-head"><h3>기상 예보</h3><span class="sub">${wx ? `${esc(wx.source)} · 발표 ${esc(wx.issued_at)}` : "예보 없음"}</span></div>
        ${wx ? `<table class="tbl"><tr><th>구간</th><th class="n">풍속</th><th>판정</th></tr>${wx.segments.map((g) => `<tr><td class="mono-n">${short(g.from)} ~ ${short(g.to)}</td><td class="n">${g.wind_ms} m/s</td><td>${limit != null && g.wind_ms >= limit ? '<span class="pill pill-amber">접안 금지</span>' : '<span class="pill pill-green">접안 가능</span>'}</td></tr>`).join("")}</table><div class="card-body muted" style="padding-top:10px">${esc(wx.note || "")} · 접안 한계 ${limit ?? "-"} m/s (WX-01)</div>` : '<div class="card-body muted">이 시나리오는 기상 예보를 넣지 않았습니다(날씨 급변 리스크는 "판단 불가").</div>'}</div>
    </div>
    <div class="grid-2">
      <div class="card"><div class="card-head"><h3>야간 · 조석 · 동시 접안</h3></div><div class="card-body"><div class="kv">
        <span class="k">야간 도선</span><span class="v">Last POB(일몰 − 1.5~2h) 뒤 도착한 대형선은 다음 날 08:00 이후 · GRT 3만톤 이상은 02~08시 접안 금지 (ETB-03·04)</span>
        <span class="k">동일 화물 그룹</span><span class="v">${T.same_cargo_group_combos.combos.map((c) => esc(c.join("·"))).join(" / ")} — 같은 화물은 앞 배 ETU − 2h 전까지 함께 작업 불가 (ETB-05)</span>
        <span class="k">부두 쌍</span><span class="v">${T.simultaneous_berthing_pairs.pairs.map((p) => `${esc(p.berths.join("·"))} 동시 접안 불가(둘 다 GRT ${p.exempt_if_all_grt_le.toLocaleString("en-US")}톤 이하면 가능)`).join(" / ")} (ETB-06)</span>
        <span class="k">조석 시간창</span><span class="v">${Object.entries(sc.tide_windows || {}).map(([b, w]) => `${esc(b)}: 흘수 20 m 이상은 고조 ±2시간 창 ${w.length}개 안에서만`).join(" / ") || "해당 부두 없음"} (ETB-08)</span>
      </div></div></div>
      <div class="card"><div class="card-head"><h3>재고(탱크)</h3><span class="sub">작업 시작일 일말 재고로 판단 (ETB-09)</span></div>
        ${inv.length ? `<table class="tbl"><tr><th>화물</th><th class="n">용량</th><th class="n">시작 재고</th><th class="n">하루 증감</th><th class="n">최소</th></tr>${inv.map((g) => `<tr><td>${esc(cargoKo(g.group))}</td><td class="n">${g.capacity.toLocaleString("en-US")} ${esc(g.unit)}</td><td class="n">${g.opening.toLocaleString("en-US")}</td><td class="n">${g.daily_net > 0 ? "+" : ""}${g.daily_net.toLocaleString("en-US")}</td><td class="n">${g.minimum.toLocaleString("en-US")}</td></tr>`).join("")}</table>` : '<div class="card-body muted">재고 제약을 넣지 않은 시나리오입니다.</div>'}</div>
    </div>
    <div class="card"><div class="card-head"><h3>선박 × 부두 적합성</h3><span class="sub">제원·화물 그룹·작업 실적으로 배정 가능한 부두 (ELG-01·02)</span></div><div class="tbl-wrap"><table class="tbl">
      <tr><th>선박</th>${act.map((b) => `<th>${esc(b)}</th>`).join("")}</tr>
      ${vids.map((vid) => `<tr><td><b>${esc(vid)}</b> <span class="muted">${esc(inputVessel(vid).name || "")}</span></td>${act.map((b) => {
        const e = elig[vid];
        if (e.eligible.includes(b)) return '<td><span class="ok-ic">가능</span></td>';
        const why = (e.excluded[b] || ["작업 실적 없음"]).join(" / ");
        return `<td class="muted" title="${esc(why)}" style="font-size:11.5px;max-width:220px">${esc(why.length > 42 ? why.slice(0, 42) + "…" : why)}</td>`;
      }).join("")}</tr>`).join("")}</table></div></div>`;
};

/* ---------- 4. 선박별 계산서 ---------- */
PAGES.sheets = function (arg, q) {
  if (needRun()) return;
  const r = S.run;
  const labels = ["기준안", ...r.candidates.map((c) => c.label)];
  const s = sched(S.label) || r.baseline;
  const vs = [...s.vessels].sort((a, b) => b.amount_usd - a.amount_usd || ms(a.etb) - ms(b.etb));
  const vid = q.get("v") || (vs[0] && vs[0].vessel_id);
  const v = vesselOf(s, vid) || vs[0];
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow"><span class="code">${code(S.sid)}</span>체선료 계산서</div><h1>선박별 계산서</h1>
      <p class="lede">아홉 단계 모두 '식에 숫자를 넣은 줄'과 근거(계약 조항·운영 기준·부두 기준·입력·실적)를 붙였습니다. 이 값들만으로 손계산하면 같은 금액이 나옵니다.</p></div>
      <div class="head-actions">${segHTML(labels, s.label, "sheetSeg", true)}</div></div>
    <div style="display:grid;grid-template-columns:300px minmax(0,1fr);gap:16px;align-items:start">
      <div class="card"><div class="card-head"><h3>${esc(s.label)} · 총 ${usd(s.total_usd)}</h3></div>
        <table class="tbl">${vs.map((x) => `<tr class="click ${x.vessel_id === v.vessel_id ? "sel" : ""}" data-pick="${esc(x.vessel_id)}"><td><span class="vname"><span class="swatch" style="background:${CARGO_COLOR[x.cargo_group] || "#999"}"></span>${esc(x.vessel_id)}</span><span class="vsub">${esc(x.name)} · ${esc(x.berth)}</span></td><td class="n ${x.amount_usd > 0 ? "amt-pos" : "amt-zero"}">${usd(x.amount_usd)}</td></tr>`).join("")}</table></div>
      <div class="card"><div class="card-head"><h3>${esc(v.vessel_id)} ${esc(v.name)}</h3><span class="sub">${esc(v.vessel_type_ko)} · ${esc(cargoKo(v.cargo_group))} · ${esc(v.berth)}</span></div>
        <div class="card-body">${sheetHTML(v, s.label)}</div></div>
    </div>`;
  bindSeg("sheetSeg", (l) => { S.label = l; location.hash = `#/sheets?v=${enc(v.vessel_id)}`; PAGES.sheets(null, new URLSearchParams(`v=${v.vessel_id}`)); });
  $$("[data-pick]").forEach((el) => el.addEventListener("click", () => { history.replaceState(null, "", `#/sheets?v=${enc(el.dataset.pick)}`); PAGES.sheets(null, new URLSearchParams(`v=${el.dataset.pick}`)); }));
};

/* ---------- 5. 리스크 · 민감도 ---------- */
PAGES.risk = function () {
  if (needRun()) return;
  const r = S.run;
  if (!r.candidates.length) { $("#page").innerHTML = '<div class="empty"><h3>후보가 없습니다</h3></div>'; return; }
  const label = sched(S.label) && S.label !== "기준안" ? S.label : r.candidates[0].label;
  const ORDER = { APPLIES: 0, CAUTION: 1, UNKNOWN: 2, NOT_APPLICABLE: 3 };
  const risks = [...(r.risks[label] || [])].sort((a, b) => (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9));
  const sens = r.sensitivity || { rows: [] };
  const cols = ["기준안", ...r.candidates.map((c) => c.label)];
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow"><span class="code">${code(S.sid)}</span>리스크 · 민감도</div><h1>남은 리스크와 입력이 바뀔 때</h1>
      <p class="lede">총액이 가장 낮은 안이라도 현장 리스크가 남을 수 있습니다. 후보마다 다섯 가지를 점검하고, ETA ±${sens.shift_hours || 6}시간·예보 변경에 순위가 바뀌는지 다시 계산했습니다.</p></div>
      <div class="head-actions">${segHTML(r.candidates.map((c) => c.label), label, "riskSeg", true)}</div></div>
    <div class="risk-grid">${risks.map((x) => `<div class="risk ${RISK_CLS[x.status] || "unknown"}"><div class="risk-h"><b>${esc(x.name)}</b><span class="pill ${RISK_PILL[x.status] || ""}">${esc(x.status_ko)}</span></div>
      <ul>${x.evidence.slice(0, 5).map((e) => `<li>${esc(e)}</li>`).join("")}${x.evidence.length > 5 ? `<li class="muted">외 ${x.evidence.length - 5}건</li>` : ""}</ul>
      ${x.alternatives && x.alternatives.length ? `<div class="note-box" style="margin-top:8px;font-size:12px">${x.alternatives.map(esc).join("<br>")}</div>` : ""}</div>`).join("")}</div>
    <div class="card" style="margin-top:16px"><div class="card-head"><h3>민감도 — 후보 순서는 그대로 두고 입력만 바꿔 다시 계산</h3><span class="sub">금액은 바뀐 입력에서의 총 예상 체선료, 괄호는 원래 대비</span></div><div class="tbl-wrap">
      <table class="tbl"><tr><th>바뀐 입력</th>${cols.map((c) => `<th class="n">${c === "기준안" ? "기준안" : esc(c)}</th>`).join("")}<th>순위 변화</th></tr>
      <tr><td class="muted">원래 입력</td>${cols.map((c) => `<td class="n"><b>${usd(sens.base_totals_usd[c])}</b></td>`).join("")}<td></td></tr>
      ${sens.rows.map((row) => `<tr><td>${esc(row.label)}</td>${cols.map((c) => { const d = row.delta_usd[c]; return `<td class="n">${row.infeasible && row.infeasible[c] ? '<span class="muted">배정 불가</span>' : `${usd(row.totals_usd[c])} <span class="${d > 0 ? "delta-up" : d < 0 ? "delta-dn" : "amt-zero"}" style="font-size:11px">(${usdS(d)})</span>`}</td>`; }).join("")}
        <td>${row.rank_changed && row.rank_changed.length ? `<span class="rank-chg">${esc(row.rank_changed.map((x) => (typeof x === "string" ? x : `${x.label || x.candidate || ""} ${x.from ?? ""}→${x.to ?? ""}`)).join(", "))}</span>` : '<span class="muted">변화 없음</span>'}</td></tr>`).join("")}</table></div></div>
    <div class="card"><div class="card-head"><h3>계산에 깔린 가정 — 현업 확인이 필요한 것</h3><span class="sub">${r.open_assumptions.length}건</span></div><div class="card-body"><ol style="margin:0;padding-left:18px;line-height:1.75;color:var(--ink-2)">${r.open_assumptions.map((a) => `<li>${esc(a)}</li>`).join("")}</ol></div></div>`;
  bindSeg("riskSeg", (l) => { S.label = l; PAGES.risk(); });
};

/* ---------- 6. 계약서 ---------- */
PAGES.contracts = async function (arg, q) {
  if (arg) return contractDetail(arg, q.get("c"));
  const type = q.get("t") || "ALL";
  const TYPES = [["ALL", "전체"], ["CP", "용선계약"], ["FOB", "FOB 매매"], ["CFR", "CFR 매매"], ["CFR_PLUS", "CFR Plus"]];
  const list = S.contracts.filter((c) => type === "ALL" || c.type === type);
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow">계약</div><h1>계약서 ${S.contracts.length}건</h1>
      <p class="lede">계산에 쓰는 허용 정박시간·체선료율·NOR 통지·기상 감면·주간 NOR은 모두 이 계약서에서 읽습니다. 조항마다 엔진 규칙을 연결해 두어, 계산서의 근거가 조항 번호로 표시됩니다.</p></div>
      <div class="head-actions"><span class="pill pill-amber">모두 가상 예시 — 실제 계약 아님</span></div></div>
    <div class="card"><div class="card-head"><div class="seg small" id="ctSeg">${TYPES.map(([k, l]) => `<button data-t="${k}" class="${k === type ? "on" : ""}"><span class="l">${l} ${k === "ALL" ? S.contracts.length : S.contracts.filter((c) => c.type === k).length}</span></button>`).join("")}</div></div>
      <div class="tbl-wrap"><table class="tbl"><tr><th>계약서</th><th>종류</th><th>상대방</th><th>선박</th><th>Laycan</th><th class="n">허용 정박시간</th><th class="n">체선료율</th><th>기상 대기</th><th>주간 NOR</th><th>쓰는 시나리오</th></tr>
      ${list.map((c) => `<tr class="click" data-ct="${esc(c.id)}"><td><span class="vname">${esc(c.id)}</span><span class="vsub">${esc(c.title)}</span></td><td><span class="tag">${esc(c.type)}</span><span class="vsub">${esc(c.kind)}</span></td>
        <td>${esc(c.counterparty)}</td><td>${esc(c.vessel)}<span class="vsub">${esc(c.vessel_class)}</span></td><td class="mono-n">${esc(c.laycan.from.slice(5))} ~ ${esc(c.laycan.to.slice(5))}</td>
        <td class="n">${c.laytime_hours}h${c.pro_rata ? '<span class="vsub">부분 화물 비례</span>' : ""}</td><td class="n">$${c.rate_usd_day.toLocaleString("en-US")}/일</td>
        <td>${c.weather_deduction_ratio ? `${c.weather_deduction_ratio * 100}% 공제` : '<span class="pill pill-red">감면 없음</span>'}</td><td>${c.daylight_nor ? "적용" : '<span class="muted">미적용</span>'}</td>
        <td>${c.used_in.length ? `${esc([...new Set(c.used_in.map((u) => code(u.scenario)))].join(" "))}` : '<span class="muted">-</span>'}</td></tr>`).join("")}</table></div></div>`;
  $$("#ctSeg button").forEach((b) => b.addEventListener("click", () => { location.hash = `#/contracts?t=${b.dataset.t}`; }));
  $$("[data-ct]").forEach((el) => el.addEventListener("click", () => { location.hash = `#/contracts/${enc(el.dataset.ct)}`; }));
};

async function contractDetail(id, clause) {
  $("#page").innerHTML = '<div class="loading"><span class="spin"></span>계약서를 여는 중</div>';
  let d = S.ctDocs[id];
  if (!d) {
    try { d = S.ctDocs[id] = await api(`/api/contracts/${enc(id)}`); } catch (e) { $("#page").innerHTML = `<div class="empty"><h3>계약서 ${esc(id)}를 찾지 못했습니다</h3></div>`; return; }
  }
  const t = d.terms, lay = t.laytime;
  const isCP = d.type === "CP" || d.type === "CFR_PLUS";
  const ports = d.ports.load ? `선적 ${d.ports.load} → 양하 ${d.ports.discharge}` : d.ports.product_port;
  const box = (k, v, engine = false, ref = "") => `<div class="box ${engine ? "engine" : ""}"><div class="k">${ref ? `<b>${esc(ref)}</b>` : ""}${esc(k)}${engine ? ' <span class="pill pill-brand" style="height:17px;font-size:10px;padding:0 6px">계산에 사용</span>' : ""}</div><div class="v">${v}</div></div>`;
  const ruleMap = {};
  for (const c of d.clauses) for (const rid of c.rules) (ruleMap[rid] = ruleMap[rid] || []).push(c.ref);
  const used = d.used_in || [];
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow"><a href="#/contracts">계약서</a> / ${esc(d.id)}</div><h1>${esc(d.title)}</h1>
      <p class="lede">${esc(d.kind)} · ${esc(d.form)}</p></div>
      <div class="head-actions"><span class="pill pill-amber">가상 예시</span></div></div>
    <div class="ct-layout">
      <article class="paper">
        <div class="paper-label">${esc(d.label.split(".")[0])}</div>
        <div class="paper-kind">${esc(d.kind)}</div>
        <h1>${esc(d.title)}</h1>
        <div class="paper-meta">계약 번호 ${esc(d.id)} · 체결일 ${esc(d.signed_on)} · ${esc(d.form)}</div>
        <div class="parties">${d.parties.map((p) => `<div><div class="k">${esc(p.role)}</div><div class="v">${esc(p.name)}</div></div>`).join("")}</div>
        <h3>${isCP ? "Part I — 주요 조건" : "주요 조건"}</h3>
        <div class="boxes">
          ${box("선박", `${esc(d.vessel.name)} · ${esc(d.vessel.class)} ${Number(d.vessel.dwt).toLocaleString("en-US")} DWT`, false, isCP ? "(A)" : "")}
          ${box("화물", esc(d.cargo), false, isCP ? "(B)" : "")}
          ${box("Laycan", `${esc(d.laycan.from)} ~ ${esc(d.laycan.to)}`, true, isCP ? "(C)" : "")}
          ${box(isCP ? "선적항 · 양하항" : "항로", esc(ports), false, isCP ? "(D)" : "")}
          ${box("허용 정박시간", `${lay.hours}시간 ${esc(lay.basis || "")}${lay.pro_rata ? ` · 전량 ${Number(lay.full_qty).toLocaleString("en-US")} kl 기준 비례` : ""}`, true, isCP ? "(H)" : "")}
          ${box("체선료율", `USD ${t.demurrage_rate_usd_day.toLocaleString("en-US")} / 일 (시간 비례)`, true, isCP ? "(I)" : "")}
          ${box("NOR 통지시간", `${t.notice_hours}시간`, true)}
          ${box("기상 대기", t.weather_deduction_ratio ? `체선 기간 안 기상 대기의 ${t.weather_deduction_ratio * 100}% 공제` : "감면 없음", true)}
          ${box("주간 NOR", t.daylight_nor ? "적용 (일출~일몰)" : "미적용", true)}
        </div>
        <h3>조항</h3>
        ${d.clauses.map((c) => `<div class="clause ${clause && c.ref === clause ? "hl" : ""}" data-ref="${esc(c.ref)}"><div class="clause-ref">${esc(c.ref)}</div><div><h4>${esc(c.title)}</h4><p>${esc(c.text)}</p>
          ${c.rules.length ? `<div class="rule-tags">${c.rules.map((rid) => `<span class="chip chip-rule" title="${esc(ruleText(rid))}">${esc(rid)} <b>${esc(ruleName(rid))}</b></span>`).join("")}</div>` : ""}</div></div>`).join("")}
        ${d.recap ? `<h3>Recap (요약 전문)</h3><pre class="recap">${esc(d.recap)}</pre>` : ""}
        <div class="paper-foot">${esc(d.payer_note || "")}<br>${esc(d.label)}</div>
      </article>
      <div class="stack">
        <div class="card side-card"><div class="card-head"><h3>계산에 쓰는 조건</h3></div><div class="card-body"><div class="kv">
          <span class="k">허용 정박시간</span><span class="v">${lay.hours}h${lay.pro_rata ? " × 실은 양 ÷ 전량" : ""}</span>
          <span class="k">체선료율</span><span class="v">$${t.demurrage_rate_usd_day.toLocaleString("en-US")}/일</span>
          <span class="k">NOR 통지</span><span class="v">${t.notice_hours}h</span>
          <span class="k">기상 감면</span><span class="v">${t.weather_deduction_ratio ? `× ${t.weather_deduction_ratio}` : "없음"}</span>
          <span class="k">주간 NOR</span><span class="v">${t.daylight_nor ? "적용" : "미적용"}</span>
          <span class="k">종료 시점</span><span class="v">${esc(t.end_event || "호스 분리")}</span>
          <span class="k">계약 유형</span><span class="v">${esc(d.type)}${d.type === "CFR_PLUS" ? ' <span class="pill pill-amber">미확정 규칙</span>' : ""}</span></div></div></div>
        <div class="card side-card"><div class="card-head"><h3>엔진 규칙 ↔ 조항</h3></div><div class="card-body"><ul class="map-list">
          ${Object.entries(ruleMap).sort().map(([rid, refs]) => `<li><code>${esc(rid)}</code><span>${refs.map((x) => `<a href="#/contracts/${enc(d.id)}?c=${enc(x)}">${esc(x)}</a>`).join(" · ")} <span class="muted">${esc(ruleName(rid))}</span></span></li>`).join("")}</ul></div></div>
        <div class="card side-card"><div class="card-head"><h3>이 계약서를 쓰는 시나리오</h3><span class="sub">${used.length}곳</span></div><div class="card-body">
          ${used.length ? `<ul class="map-list">${used.map((u) => `<li><code>${esc(code(u.scenario))}</code><span><a href="#" data-run="${esc(u.scenario)}">${esc(u.scenario_title)}</a> <span class="muted">· ${esc(u.vessel)}</span></span></li>`).join("")}</ul>` : '<span class="muted">없음</span>'}</div></div>
      </div>
    </div>`;
  $$("[data-run]").forEach((el) => el.addEventListener("click", async (e) => { e.preventDefault(); location.hash = "#/plan"; await useScenario(el.dataset.run); }));
  const hl = $(".clause.hl");
  if (hl) setTimeout(() => hl.scrollIntoView({ block: "center", behavior: "smooth" }), 60);
}

/* ---------- 7. 보고서 · 메일 ---------- */
PAGES.report = function () {
  if (needRun()) return;
  const r = S.run, rep = r.report, au = rep.audit || {};
  const gen = rep.narrative.generated_by === "template" ? "템플릿(정해진 문장 틀)" : `LLM 문장 · ${esc(rep.narrative.generated_by)}`;
  const total = (au.report ? au.report.checked : 0) + (au.mail ? au.mail.checked : 0);
  const mism = (au.report ? au.report.mismatches.length : 0) + (au.mail ? au.mail.mismatches.length : 0);
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow"><span class="code">${code(S.sid)}</span>보고서 · 메일</div><h1>후보 제안 보고서 초안</h1>
      <p class="lede">숫자는 모두 엔진 결과에서 가져오고, 문장 안의 금액·시각을 엔진 값과 다시 대조했습니다. 메일은 초안만 만들며 발송은 담당자가 직접 합니다.</p></div>
      <div class="head-actions"><a class="btn" href="/api/runs/${r.run_id}/report.html" target="_blank">${I.ext}새 창</a></div></div>
    <div class="report-layout">
      <div class="card"><div class="card-head"><h3>보고서 미리보기</h3><span class="sub">실행 ${esc(r.run_id)} · ${esc(r.created_at)}</span></div>
        <iframe class="report-frame" src="/api/runs/${r.run_id}/report.html" title="보고서 미리보기"></iframe></div>
      <div class="stack">
        <div class="card"><div class="card-head"><h3>문장과 숫자 점검</h3></div><div class="card-body"><div class="kv">
          <span class="k">문장 작성</span><span class="v">${gen}</span>
          <span class="k">숫자 대조</span><span class="v">${mism === 0 ? `<span class="ok-ic">✓</span> 금액·시각 ${total}개 모두 일치` : `<span class="bad-ic">✕</span> 불일치 ${mism}건`}</span>
          <span class="k">단정 표현</span><span class="v">${r.checks.find((c) => c.what.startsWith("단정"))?.ok ? '<span class="ok-ic">✓</span> 없음' : '<span class="bad-ic">✕</span> 있음'}</span>
          <span class="k">결과 지문</span><span class="v mono">${esc(r.fingerprint)}</span></div></div></div>
        <div class="card"><div class="card-head"><h3>내려받기</h3></div><div class="card-body"><div class="dl-list">
          <a href="/api/runs/${r.run_id}/report.docx">${I.download}보고서 Word<small>.docx</small></a>
          <a href="/api/runs/${r.run_id}/report.md">${I.download}보고서 Markdown<small>.md</small></a>
          <a href="/api/runs/${r.run_id}/schedule.csv?label=${enc(r.candidates[0] ? r.candidates[0].label : "기준안")}">${I.download}1안 접안 일정<small>.csv</small></a>
          <a href="/api/runs/${r.run_id}/mail.txt">${I.download}메일 초안<small>.txt</small></a></div></div></div>
        <div class="card"><div class="card-head"><h3>메일 초안</h3><span class="sub">받는 사람: ${esc(r.mail.to)}</span><div class="right"><button class="btn btn-sm" id="btnCopy">${I.copy}복사</button></div></div>
          <div class="card-body"><div class="mail-subj">${esc(r.mail.subject)}</div><textarea class="mail-body" id="mailBody" spellcheck="false">${esc(r.mail.body)}</textarea></div></div>
      </div>
    </div>`;
  $("#btnCopy").onclick = async () => {
    try { await navigator.clipboard.writeText(`제목: ${r.mail.subject}\n\n${$("#mailBody").value}`); toast("메일 초안을 복사했습니다"); } catch (e) { toast("복사하지 못했습니다 — 직접 선택해 복사해 주세요"); }
  };
};

/* ---------- 8. 확정 · 이력 ---------- */
async function loadDecisions() {
  const r = S.run;
  const [d, au] = await Promise.all([api(`/api/runs/${r.run_id}/decisions`), api(`/api/runs/${r.run_id}/audit`)]);
  r.candidate_states = d.states;
  return { history: d.history, events: au.events };
}

PAGES.decisions = async function () {
  if (needRun()) return;
  const r = S.run;
  const { history, events } = await loadDecisions();
  const st = r.candidate_states || {};
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow"><span class="code">${code(S.sid)}</span>확정 · 이력</div><h1>담당자 결정과 기록</h1>
      <p class="lede">후보 확정·취소·현업 반영은 사람만 합니다. 기록은 덧붙이기만 되고 고치거나 지울 수 없습니다(DB 트리거로 막음).</p></div>
      <div class="head-actions"><button class="btn btn-primary" id="btnDecide2">${I.check}후보 확정</button></div></div>
    <div class="state-row">${r.candidates.map((c) => `<div class="state"><b>${esc(c.label)}</b><span class="pill ${STATE_PILL[st[c.label]] || ""}">${esc(st[c.label] || "추천")}</span><small>${usd(c.total_usd)} · ${c.savings_usd != null ? `기준안 대비 ${usd(c.savings_usd)}` : esc(c.meta.optimality)}</small></div>`).join("")}</div>
    <div class="grid-2" style="margin-top:16px">
      <div class="card"><div class="card-head"><h3>결정 기록</h3><span class="sub">${history.length}건 · 덧붙이기 전용</span></div>
        ${history.length ? `<table class="tbl"><tr><th>시각</th><th>동작</th><th>후보</th><th>담당자</th><th>이유</th></tr>${history.map((h) => `<tr><td class="mono-n">${esc(String(h.created_at).slice(5, 16))}</td><td><span class="tag">${esc({ SELECT: "확정", CANCEL: "확정 취소", APPLIED: "현업 반영" }[h.action] || h.action)}</span></td><td><b>${esc(h.candidate)}</b></td><td>${esc(h.actor)}</td><td>${esc(h.reason)}</td></tr>`).join("")}</table>` : '<div class="card-body muted">아직 결정이 없습니다.</div>'}</div>
      <div class="card"><div class="card-head"><h3>감사 기록</h3><span class="sub">실행·결정 이벤트</span></div>
        <ul class="timeline-list">${events.map((e) => `<li><time>${esc(String(e.ts || e.created_at || "").slice(5, 16))}</time><span><b>${esc(EVENT_KO[e.kind] || e.kind)}</b> <span class="muted">${esc(e.actor === "system" ? "시스템" : e.actor)}${e.detail && e.detail.candidate ? ` · ${esc(e.detail.candidate)}` : ""}</span></span></li>`).join("")}</ul></div>
    </div>
    <div class="card"><div class="card-head"><h3>처리 단계</h3><span class="sub">순서는 코드가 고정 · 숫자를 다루는 단계는 LLM을 쓰지 않음</span></div>
      <table class="tbl"><tr><th>#</th><th>단계</th><th class="n">소요</th><th>결과</th></tr>
      ${r.agent_log.map((a) => `<tr><td>${a.seq}</td><td><b>${esc(a.label || a.agent)}</b><span class="vsub">${esc(a.stage)}${a.uses_llm ? " · 문장만 LLM(선택)" : ""}</span></td><td class="n">${a.elapsed_ms.toLocaleString("en-US")} ms</td><td class="mono" style="font-size:11px;color:var(--ink-2)">${esc(Object.entries(a.output || {}).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ").slice(0, 220))}</td></tr>`).join("")}</table></div>
    <div class="card"><div class="card-head"><h3>재현 정보</h3></div><div class="card-body"><div class="kv">
      <span class="k">실행 ID</span><span class="v mono">${esc(r.run_id)}</span><span class="k">시나리오</span><span class="v mono">${esc(r.scenario.id)} #${esc(r.scenario.hash)}</span>
      <span class="k">규칙 버전</span><span class="v mono">${esc(r.versions.rules.version)}</span><span class="k">엔진</span><span class="v mono">${esc(r.versions.engine)} · ${esc(r.versions.solver.method)}</span>
      <span class="k">결과 지문</span><span class="v mono">${esc(r.fingerprint)} — 같은 입력·규칙이면 같은 값</span></div></div></div>`;
  $("#btnDecide2").onclick = () => openDecide();
};

function openDecide() {
  const r = S.run;
  if (!r || !r.candidates.length) { toast("확정할 후보가 없습니다"); return; }
  let pick = S.label !== "기준안" && sched(S.label) ? S.label : r.candidates[0].label;
  const m = $("#modal");
  const draw = () => {
    const risks = (r.risks[pick] || []).filter((x) => x.status === "APPLIES");
    m.innerHTML = `<div class="modal-card"><div class="modal-head"><h3>접안 순서 후보 확정</h3><p>확정은 담당자 기록으로 남고, 실제 반영(현업 시스템 입력)은 별도로 합니다.</p></div>
      <div class="modal-body"><div class="cand-opts">${r.candidates.map((c) => `<div class="cand-opt ${c.label === pick ? "on" : ""}" data-c="${esc(c.label)}"><input type="radio" ${c.label === pick ? "checked" : ""}><div><b>${esc(c.label)} · ${usd(c.total_usd)}</b><small>${c.savings_usd != null ? `기준안 대비 ${usd(c.savings_usd)} 절감` : "기준안 비교 불가"} · ${esc(c.meta.optimality)} · 위반 ${c.violations.length}건</small></div><span class="pill ${STATE_PILL[(r.candidate_states || {})[c.label]] || ""}">${esc((r.candidate_states || {})[c.label] || "추천")}</span></div>`).join("")}</div>
        <label class="field" style="margin-top:14px"><span>담당자</span><input id="dActor" placeholder="예: 선박 스케줄러 김OO" value="${esc(localStorage.getItem("actor") || "")}"></label>
        <label class="field"><span>선택 이유</span><textarea id="dReason" rows="3" placeholder="예: 긴급 출하 V05를 강풍 전에 접안 — 절감액이 가장 큼"></textarea></label>
        ${risks.length ? `<label class="ack"><input type="checkbox" id="dAck"><span>남은 리스크 ${risks.length}건(${esc(risks.map((x) => x.name).join(", "))})을 확인했습니다.</span></label>` : ""}</div>
      <div class="modal-foot"><button class="btn" id="dCancel">닫기</button><button class="btn btn-primary" id="dOk">${esc(pick)} 확정</button></div></div>`;
    $$(".cand-opt", m).forEach((el) => el.addEventListener("click", () => { pick = el.dataset.c; draw(); }));
    $("#dCancel").onclick = () => m.classList.remove("on");
    $("#dOk").onclick = async () => {
      const actor = $("#dActor").value.trim();
      if (!actor) { toast("담당자 이름을 적어 주세요"); return; }
      if (risks.length && !$("#dAck").checked) { toast("남은 리스크 확인에 체크해 주세요"); return; }
      try {
        const out = await api(`/api/runs/${r.run_id}/decisions`, { method: "POST", body: JSON.stringify({ candidate: pick, action: "SELECT", actor, reason: $("#dReason").value.trim() }) });
        localStorage.setItem("actor", actor);
        r.candidate_states = out.states;
        m.classList.remove("on");
        toast(`${pick} 확정을 기록했습니다`);
        if (parseHash().name === "decisions") PAGES.decisions();
      } catch (e) { toast(`기록 실패: ${e.message}`); }
    };
  };
  draw();
  m.classList.add("on");
}

/* ---------- 9. 시나리오 라이브러리 ---------- */
PAGES.scenarios = function () {
  const groups = groupScenarios();
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow">시나리오</div><h1>시나리오 라이브러리</h1>
      <p class="lede">울산 CLX에서 체선료가 갈리는 대표 상황 ${S.scenarios.length}가지입니다. 카드마다 상황·판단할 점·결과에서 확인할 것을 적어 두었고, 선박마다 가상 계약서가 붙어 있습니다.</p></div>
      <div class="head-actions"><span class="pill">계약서 ${S.contracts.length}건</span><span class="pill">검증 시나리오 4개 별도(완전 탐색 비교)</span></div></div>
    ${groups.map(([cat, list]) => `<div class="lib-group"><h3>${esc(cat)} <small>${list.length}</small></h3><div class="lib-grid">${list.map(scCardHTML).join("")}</div></div>`).join("")}`;
  $$("[data-go]").forEach((el) => el.addEventListener("click", async () => { location.hash = "#/plan"; await useScenario(el.dataset.go); }));
};

function scCardHTML(s) {
  const c = s.card || {}, run = S.runs[s.id];
  let res = "";
  if (run && run.status !== "INPUT_ERROR" && run.candidates.length) {
    const b = run.baseline, best = run.candidates[0];
    res = `<div class="sc-res"><span class="muted">기준안</span><b>${b.complete ? usd(b.total_usd) : "성립 안 함"}</b><span class="arrow">→</span><span class="muted">1안</span><b>${usd(best.total_usd)}</b>${best.savings_pct != null ? `<span class="delta-dn">${pct(best.savings_pct)}</span>` : ""}</div>`;
  }
  return `<div class="sc-card ${s.id === S.sid ? "on" : ""}">
    <div class="sc-top"><span class="code">${code(s.id)}</span><span class="tag">${esc(s.category)}</span>${s.id === S.sid ? '<span class="pill pill-brand">보는 중</span>' : ""}</div>
    <h4>${esc(s.title)}</h4><p>${esc(c.situation || s.description)}</p><div class="q">${esc(c.question || "")}</div>
    <ul class="checks">${(c.watch || []).slice(0, 3).map((w) => `<li>${esc(w)}</li>`).join("")}</ul>${res}
    <div class="sc-meta" style="margin-top:14px"><span class="pill">선박 ${s.vessels}척</span><span class="pill">부두 ${s.berths.length}곳</span>${s.has_weather ? '<span class="pill pill-amber">강풍</span>' : ""}${s.restrictions ? '<span class="pill">정비</span>' : ""}${s.has_inventory ? '<span class="pill">재고</span>' : ""}<span class="pill">계약서 ${s.contracts.length}</span>
      <button class="btn btn-sm ${s.id === S.sid ? "" : "btn-primary"}" data-go="${esc(s.id)}">${s.id === S.sid ? "결과 보기" : "계산하고 보기"}</button></div></div>`;
}

/* ---------- 10. 검증 ---------- */
PAGES.qa = function () {
  const v = S.verify;
  const r = S.run;
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow">관리</div><h1>검증</h1>
      <p class="lede">손으로 계산한 정답 세트(272칸)와 엔진 결과를 칸마다 대조하고, 작은 검증 시나리오는 가능한 순서를 모두 따져 본 완전 탐색과 1안이 같은지 확인합니다.</p></div>
      <div class="head-actions"><button class="btn" id="btnQuick">정답 세트만</button><button class="btn btn-primary" id="btnFull">${I.play}전체 검증 실행</button></div></div>
    ${v ? qaHTML(v) : '<div class="card"><div class="card-body muted">검증을 실행하면 결과가 여기에 나옵니다. 전체 검증은 몇 초 걸립니다.</div></div>'}
    ${r && r.checks ? `<div class="card"><div class="card-head"><h3>지금 보는 실행의 자체 검사</h3><span class="sub">${esc(r.scenario.id || "")} · ${r.checks.filter((c) => c.ok).length}/${r.checks.length} 통과</span></div>
      <table class="tbl">${r.checks.map((c) => `<tr><td style="width:36px">${c.ok ? '<span class="ok-ic">✓</span>' : '<span class="bad-ic">✕</span>'}</td><td>${esc(c.what)}</td></tr>`).join("")}</table></div>` : ""}`;
  const go = async (quick) => {
    $("#page").querySelector(".head-actions").innerHTML = '<span class="muted"><span class="spin"></span>검증 중…</span>';
    try { S.verify = await api(`/api/verify?quick=${quick}`, { method: "POST" }); } catch (e) { toast(`검증 실패: ${e.message}`); }
    PAGES.qa();
  };
  $("#btnQuick").onclick = () => go(true);
  $("#btnFull").onclick = () => go(false);
};

function qaHTML(v) {
  const g = v.golden, sc = (v.scenarios && v.scenarios.scenarios) || [];
  return `<div class="grid-3">
      <div class="card"><div class="card-body"><div class="kpi-l">정답 세트 일치</div><div class="big-n" style="color:${g.passed === g.total ? "var(--green)" : "var(--red)"}">${(g.match_rate * 100).toFixed(1)}%</div><div class="muted">${g.passed}/${g.total}칸 · 불일치 ${g.mismatches.length} · 입력 오류 ${g.errors.length}</div></div></div>
      <div class="card"><div class="card-body"><div class="kpi-l">검증 시나리오</div><div class="big-n">${sc.length ? `${sc.filter((x) => x.optimal_match).length}/${sc.filter((x) => "optimal_match" in x).length}` : "-"}</div><div class="muted">완전 탐색 최적값과 1안 일치</div></div></div>
      <div class="card"><div class="card-body"><div class="kpi-l">후보 제약 위반</div><div class="big-n">${v.scenarios && v.scenarios.violations_total != null ? v.scenarios.violations_total : "-"}</div><div class="muted">독립 검증기 재검사</div></div></div>
    </div>
    <div class="card"><div class="card-head"><h3>정답 세트 ${groupGC(v).length}묶음 · 사례 ${v.golden_by_case.length}개</h3><span class="sub">멘토링 PPT 규칙을 손으로 계산한 기대값</span></div><div class="card-body"><div class="gc-grid">
      ${groupGC(v).map((x) => `<div class="gc"><div class="id">${esc(x.gc)}</div><div class="t">${esc((v.golden_titles || {})[x.gc] || "")}</div><div class="bar"><i style="width:${(x.passed / x.total) * 100}%;${x.passed < x.total ? "background:var(--red)" : ""}"></i></div><div class="n">${x.passed}/${x.total}칸 · 사례 ${x.cases}개</div></div>`).join("")}</div></div></div>
    ${sc.length ? `<div class="card"><div class="card-head"><h3>검증 시나리오 — 완전 탐색 비교</h3></div><table class="tbl"><tr><th>시나리오</th><th class="n">선박</th><th class="n">기준안</th><th class="n">1안</th><th class="n">완전 탐색 최적</th><th class="n">따져 본 순서</th><th>결과</th></tr>
      ${sc.map((x) => `<tr><td><b>${esc(x.scenario)}</b><span class="vsub">${esc(x.title)}</span></td><td class="n">${x.vessels}</td><td class="n">${usd(x.baseline_usd)}</td><td class="n">${usd(x.best_usd)}</td><td class="n">${usd(x.brute_force_usd)}</td><td class="n">${x.brute_force_plans != null ? x.brute_force_plans.toLocaleString("en-US") : "-"}</td><td>${x.optimal_match ? '<span class="pill pill-green">일치</span>' : '<span class="pill pill-red">불일치</span>'}</td></tr>`).join("")}</table></div>` : ""}
    ${g.mismatches.length ? `<div class="card"><div class="card-head"><h3>불일치</h3></div><table class="tbl">${g.mismatches.map((m) => `<tr><td>${esc(m.gc)}</td><td>${esc(m.case)}</td><td>${esc(m.item)} ${esc(m.field)}</td><td>기대 ${esc(m.expected)} / 실제 ${esc(m.actual)}</td></tr>`).join("")}</table></div>` : ""}`;
}
function groupGC(v) {
  const m = new Map();
  for (const x of v.golden_by_case) {
    if (!m.has(x.gc)) m.set(x.gc, { gc: x.gc, total: 0, passed: 0, cases: 0 });
    const o = m.get(x.gc);
    o.total += x.total; o.passed += x.passed; o.cases += 1;
  }
  return [...m.values()];
}

/* ---------- 11. 아키텍처 ---------- */
PAGES.arch = function () {
  $("#page").innerHTML = `
    <div class="page-head"><div><div class="eyebrow">관리</div><h1>아키텍처</h1>
      <p class="lede">계산은 결정론 엔진(규칙 표 + 계약서)이 하고, LLM은 보고서 문장에만 선택적으로 씁니다. 사람만 후보를 확정하며, 결정 기록은 덧붙이기 전용입니다.</p></div></div>
    <div class="card"><div class="card-head"><h3>프로젝트 아키텍처</h3><span class="sub">데이터 → 엔진 → 결과 → 사람의 결정</span><div class="right"><a class="btn btn-sm" href="/static/assets/architecture-project.svg" target="_blank">${I.ext}원본</a></div></div>
      <img class="diagram" src="/static/assets/architecture-project.svg" alt="프로젝트 아키텍처 다이어그램"></div>
    <div class="card"><div class="card-head"><h3>백엔드 아키텍처</h3><span class="sub">FastAPI · 처리 단계 7개 · 저장소</span><div class="right"><a class="btn btn-sm" href="/static/assets/architecture-backend.svg" target="_blank">${I.ext}원본</a></div></div>
      <img class="diagram" src="/static/assets/architecture-backend.svg" alt="백엔드 아키텍처 다이어그램"></div>`;
};

/* ---------- 시작 ---------- */
async function boot() {
  renderNav();
  $("#scenarioPick").onclick = (e) => { e.stopPropagation(); openPick(); };
  $("#pop").addEventListener("click", async (e) => {
    const it = e.target.closest("[data-sid]");
    if (!it) return;
    $("#pop").classList.remove("on");
    if (!["plan", "vessels", "berths", "sheets", "risk", "report", "decisions"].includes(parseHash().name)) location.hash = "#/plan";
    await useScenario(it.dataset.sid);
    route();
  });
  document.addEventListener("click", (e) => { if (!e.target.closest("#pop") && !e.target.closest("#scenarioPick")) $("#pop").classList.remove("on"); });
  $("#scrim").onclick = closeDrawer;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeDrawer(); $("#modal").classList.remove("on"); $("#pop").classList.remove("on"); } });
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") $("#modal").classList.remove("on"); });
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if (parseHash().name === "plan" && S.run && $("#gantt")) drawGantt($("#gantt"), sched(S.label)); }, 150); });
  window.addEventListener("hashchange", route);
  try {
    [S.meta, S.rules, S.scenarios, S.contracts] = await Promise.all([api("/api/meta"), api("/api/rules"), api("/api/scenarios"), api("/api/contracts")]);
  } catch (e) {
    $("#page").innerHTML = `<div class="empty"><h3>서버에 연결하지 못했습니다</h3><p>${esc(e.message)}</p></div>`;
    return;
  }
  renderNav();
  const first = (S.scenarios.find((s) => s.id === "S05-storm-rush") || S.scenarios[0]).id;
  await useScenario(first, { run: false });
  if (!location.hash) location.hash = "#/plan";
  await runScenario();
}
boot();
