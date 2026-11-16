// Spring 서버(/api) 호출. 같은 주소에서 Caddy가 /api를 Spring으로, 나머지를 이 화면(nginx)으로 보낸다.
// GitHub Pages처럼 서버가 없는 곳에서는 /api가 404(HTML)라 static=true 오류가 나고, 화면은 안내만 보여 준다.
// JSON이 아닌 5xx(Caddy가 Spring에 닿지 못함 등)는 static=false 서버 오류로 따로 알린다.
const BASE = './api'

async function req(path, { method = 'GET', json, form, timeout = 15000 } = {}) {
  const headers = { Accept: 'application/json' }
  let body
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form) {
    body = form
  }
  let r
  try {
    r = await fetch(`${BASE}${path}`, { method, headers, body, signal: AbortSignal.timeout(timeout) })
  } catch (e) {
    throw Object.assign(new Error(`서버에 닿지 않음 (${e.name})`), { offline: true })
  }
  const isJson = (r.headers.get('content-type') || '').includes('json')
  if (!isJson) {
    // JSON이 아닌 응답: 404 = 서버 없는 정적 사이트(GitHub Pages), 5xx = 서버·입구 오류, 그 밖 = 예상 밖
    if (r.status === 404) throw Object.assign(new Error('서버 없음 (HTTP 404, JSON이 아님)'), { static: true, status: r.status })
    if (r.status >= 500) throw Object.assign(new Error(`서버 오류 (HTTP ${r.status}) — 컨테이너 상태를 확인하세요 (make status)`), { static: false, status: r.status })
    throw Object.assign(new Error(`예상하지 못한 응답 (HTTP ${r.status})`), { static: false, status: r.status })
  }
  const data = await r.json()
  if (!r.ok) throw Object.assign(new Error(data.detail || data.error || `HTTP ${r.status}`), { status: r.status, data })
  return data
}

export const api = {
  status: () => req('/system/status', { timeout: 6000 }),
  cases: () => req('/cases?limit=20'),
  createCase: (doc) => req('/cases', { method: 'POST', json: doc }),
  importFile: (file, extra = {}) => {
    const form = new FormData()
    form.append('file', file)
    for (const [k, v] of Object.entries(extra)) if (v) form.append(k, v)
    return req('/cases/import', { method: 'POST', form, timeout: 30000 })
  },
  runs: () => req('/runs?limit=20'),
  run: (id) => req(`/runs/${id}`),
  // engine: team-cpsat(팀원 코드 berth_sim) · ppt-milp(기존 엔진), profile: team(팀원 코드 해석) · ppt(기존 해석)
  startRun: (caseId, { top = 3, timeLimitS = 120, engine, profile } = {}) =>
    req('/runs', { method: 'POST', json: { case_id: caseId, top, time_limit_s: timeLimitS, engine, profile } }),
  decide: (runId, d) => req(`/runs/${runId}/decisions`, { method: 'POST', json: d }),
}

export const usd = (v) => (v == null ? '-' : `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
export const signed = (v) => (v == null ? '-' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${usd(Math.abs(v))}`)
export const when = (t) => (t ? new Date(t).toLocaleString('ko-KR', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-')
