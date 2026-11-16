#!/usr/bin/env python3
"""확인 순서(README '확인') 그대로 위에서부터 검사하고 통과/실패를 찍는다. 표준 라이브러리 + docker만 쓴다(쿠버네티스 없음).

    python3 scripts/verify.py            # 0~10단계 (약 2분)
    FULL=1 python3 scripts/verify.py     # + 11단계 실제 크기(샘플 54건 · 팀원 가상 데이터 54척, 약 5분 더)

멈추는 곳은 둘뿐이다: 1단계에서 컨테이너가 하나도 없을 때, 5단계에서 입구에 닿지 않을 때(뒤 단계는 돌리지 않는다).
'건너뜀'도 둘뿐이다: 8단계는 공공데이터 키가 없을 때, 11단계는 FULL=1이 아닐 때.
그 밖에는 앞 단계가 실패해도 뒤 단계를 그대로 돌린다(실패한 첫 단계부터 보면 된다). 단계 안에서 오류가 나면
그 단계에 '단계 실행 중 오류' 실패를 남기고 다음 단계로 간다.
정답 금액은 server/src/test/resources/golden/의 응답 JSON(make sync-engine이 docs/milp/ppt/out에서 복사)에서 읽는다.
결과는 runtime/verify-result.json에도 남는다(중간에 죽으면 "complete": false).
"""
from __future__ import annotations

import base64
import http.client
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = Path(os.environ.get("ENV_FILE", str(ROOT / ".env")))
SECRETS_FILE = ROOT / "runtime" / "secrets.env"
PROJECT = "dmin"
FULL = os.environ.get("FULL") == "1"
GOLDEN = ROOT / "server" / "src" / "test" / "resources" / "golden"
CURL_IMAGE = "curlimages/curl:8.11.1"


def env_file(path: Path) -> dict[str, str]:
    """KEY=값 파일을 읽는다(따옴표·CR·앞뒤 공백은 벗긴다). 없으면 빈 dict."""
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip("\r").strip("'\"")
    return out


ENV = env_file(ENV_FILE)
BASE = os.environ.get("BASE_URL", f"http://127.0.0.1:{os.environ.get('DMIN_PORT') or ENV.get('DMIN_PORT') or '18089'}").rstrip("/")
GRAFANA = f"http://127.0.0.1:{os.environ.get('GRAFANA_PORT') or ENV.get('GRAFANA_PORT') or '13000'}"

# 떠 있어야 하는 컨테이너 (이름, 상태 확인이 있는가)
CONTAINERS = [("dmin-caddy", True), ("dmin-front", True), ("dmin-server", True), ("dmin-agent", True), ("dmin-postgres", True),
              ("dmin-collector", False), ("dmin-prometheus", True), ("dmin-grafana", True)]
# 네트워크 = 누가 누구에게 닿는가 (이름: (internal, 붙어 있어야 하는 컨테이너))
NETWORKS = {
    "public": (False, {"dmin-caddy", "dmin-grafana"}),
    "outbound": (False, {"dmin-server"}),
    "web": (True, {"dmin-caddy", "dmin-front"}),
    "api": (True, {"dmin-caddy", "dmin-server"}),
    "agent": (True, {"dmin-server", "dmin-agent"}),
    "db": (True, {"dmin-server", "dmin-postgres"}),
    "jobs": (True, {"dmin-collector", "dmin-server"}),
    "metrics": (True, {"dmin-prometheus", "dmin-grafana", "dmin-server"}),
}
# 호스트에 포트를 여는 컨테이너는 이 둘뿐이어야 한다 (컨테이너: 안쪽 포트)
PUBLISHED = {"dmin-caddy": "8080/tcp", "dmin-grafana": "3000/tcp"}

results: list = []
SECRETS: list[str] = []   # 화면·기록에 찍지 않을 값 (공공데이터 키 · 비밀번호)
G, R, Y, B, X = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m"

# 에이전트 컨테이너 안에서 돌리는 인터넷 시험. 서버가 답했으면(HTTP 오류 응답·TLS 오류도) 나간 것 = REACHED,
# 연결 자체가 안 되면(이름 풀이 실패·시간 초과·OSError) BLOCKED.
INTERNET_PROBE = """\
import ssl, urllib.error, urllib.request
try:
    urllib.request.urlopen('https://apis.data.go.kr', timeout=5)
    print('REACHED')
except urllib.error.HTTPError as e:
    print('REACHED HTTPError', e.code)
except urllib.error.URLError as e:
    print('REACHED' if isinstance(e.reason, ssl.SSLError) else 'BLOCKED', 'URLError', type(e.reason).__name__)
except ssl.SSLError as e:
    print('REACHED', type(e).__name__)
except OSError as e:
    print('BLOCKED', type(e).__name__)
except Exception as e:
    print('UNKNOWN', type(e).__name__)
"""
TCP_PROBE = """\
import socket, sys
try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3).close()
    print('CONNECTED')
except OSError as e:
    print('NO_CONNECT', type(e).__name__)
"""


def hide(text):
    for v in SECRETS:
        if v:
            text = text.replace(v, "***")
    return text


def as_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def sh(*args, check=False, timeout=120, inp=None):
    p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout, input=inp)
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:400])
    return p


def dexec(container, *cmd, timeout=60):
    return sh("docker", "exec", container, *cmd, timeout=timeout)


def inspect(name):
    """컨테이너 inspect JSON. 없으면 None."""
    p = sh("docker", "inspect", name)
    return json.loads(p.stdout)[0] if p.returncode == 0 and p.stdout.strip().startswith("[") else None


def psql(user, sql, timeout=30):
    return dexec("dmin-postgres", "psql", "-U", user, "-d", "dmin", "-tAc", sql, timeout=timeout)


def http(method, path, body=None, timeout=20, base=None, headers=None):
    req = urllib.request.Request(f"{base or BASE}{path}", data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", ""), e.read()
    except http.client.HTTPException as e:   # 응답을 받다가 잘림(IncompleteRead 등) — 연결 문제와 같게 다룬다
        raise OSError(f"응답이 잘림: {type(e).__name__}") from None


def jhttp(method, path, doc=None, timeout=20):
    code, ctype, raw = http(method, path, None if doc is None else json.dumps(doc).encode(), timeout)
    return code, (json.loads(raw) if "json" in ctype else raw.decode("utf-8", "replace"))


def looks_json(ctype, raw):
    """content-type에 json이 있거나 본문이 JSON 객체·배열로 읽히면 True (= Spring이 답한 것)."""
    if "json" in ctype.lower():
        return True
    try:
        return isinstance(json.loads(raw), (dict, list))
    except ValueError:
        return False


class Step:
    def __init__(self, no, title):
        self.no, self.title, self.items, self.skipped = no, title, [], False
        print(f"\n{B}{no:>2}. {title}{X}")

    def __enter__(self):
        return self

    def __exit__(self, et, e, tb):
        # 단계 안에서 난 오류는 실패 한 줄로 남기고 다음 단계로 간다 (Ctrl-C 같은 것은 그대로 올려 보낸다)
        if et is None or not issubclass(et, Exception):
            return False
        self.check(False, f"단계 실행 중 오류: {type(e).__name__}: {e}"[:300])
        return True

    def check(self, ok, what, detail=""):
        what, detail = hide(str(what)), hide(str(detail))
        self.items.append({"ok": bool(ok), "what": what, "detail": detail})
        mark = f"{G}통과{X}" if ok else f"{R}실패{X}"
        print(f"    {mark}  {what}" + (f"  — {detail}" if detail else ""))
        return ok

    def note(self, what):
        print(f"    {Y}참고{X}  {hide(str(what))}")

    def skip(self, why):
        self.skipped = True
        print(f"    {Y}건너뜀{X} {why}")

    @property
    def ok(self):
        return not self.skipped and all(i["ok"] for i in self.items)


def step(no, title):
    s = Step(no, title)
    results.append(s)
    return s


NC = "nc -z -w 3 {h} {p} >/dev/null 2>&1 && echo CONNECTED || echo NO_CONNECT"


def conn_from(container, host, port):
    """떠 있는 컨테이너 안에서 TCP 연결을 시도한다 (busybox nc). ('CONNECTED' | 'NO_CONNECT' | 'ERROR', 설명)"""
    p = dexec(container, "sh", "-c", NC.format(h=host, p=port), timeout=30)
    last = (p.stdout.strip().splitlines() or [""])[-1]
    return (last, last) if last in ("CONNECTED", "NO_CONNECT") else ("ERROR", (p.stderr.strip() or "출력 없음")[:120])


def conn_from_new(network, host, port):
    """그 네트워크에만 붙인 임시 컨테이너에서 TCP 연결을 시도한다 (아무 권한도 없는 '아무 컨테이너' 자리)."""
    p = sh("docker", "run", "--rm", "--network", f"{PROJECT}_{network}", "--entrypoint", "sh", CURL_IMAGE, "-c", NC.format(h=host, p=port), timeout=60)
    last = (p.stdout.strip().splitlines() or [""])[-1]
    return (last, last) if last in ("CONNECTED", "NO_CONNECT") else ("ERROR", (p.stderr.strip() or "출력 없음")[:120])


def net_check(s, got, want, what):
    """막혀야 하는 길은 NO_CONNECT일 때만, 열려야 하는 길은 CONNECTED일 때만 통과. ERROR는 실패."""
    state, why = got
    if state == "ERROR":
        return s.check(False, what, f"시험을 실행하지 못함 — {why}")
    return s.check(state == want, what, f"TCP {state}")


def heartbeat_age(run_id):
    """RUNNING인 실행의 마지막 맥박이 몇 초 전인지 DB에서 읽는다(앱 계정). 끝났으면 None, 맥박이 비었으면 -1."""
    sql = f"SELECT coalesce(extract(epoch from now()-heartbeat_at)::int,-1) FROM run WHERE id={int(run_id)} AND status='RUNNING'"
    p = psql("dmin_app", sql)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    out = p.stdout.strip()
    return int(out) if out else None


def wait_run(run_id, limit_s, hb=None):
    """끝날 때까지 2초마다 본다. hb(dict)를 주면 RUNNING인 동안 5초마다 DB의 맥박 나이를 재서 hb에 담는다."""
    t0, next_hb = time.time(), 0.0
    while time.time() - t0 < limit_s:
        try:
            _, d = jhttp("GET", f"/api/runs/{run_id}")
        except (OSError, ValueError, http.client.HTTPException):  # 한 번 못 읽은 것(시간 초과·연결 끊김·잘린 응답)은 다시 본다
            d = None
        status = d.get("status") if isinstance(d, dict) else None
        if status in ("SUCCEEDED", "PARTIAL", "FAILED"):
            return d, time.time() - t0
        if hb is not None and status == "RUNNING" and time.time() >= next_hb:
            next_hb = time.time() + 5
            try:
                age = heartbeat_age(run_id)
            except Exception:  # noqa: BLE001 — 못 잰 횟수만 센다
                hb["errors"] += 1
            else:
                if age is not None and age < 0:
                    hb["nulls"] += 1
                elif age is not None:
                    hb["ages"].append(age)
        time.sleep(2)
    return None, time.time() - t0


def eta_rows():
    """eta_snapshot 줄 수(상태 API). 못 읽으면 None."""
    try:
        return int(jhttp("GET", "/api/system/status")[1]["db"]["counts"]["eta_snapshots"])
    except (OSError, TypeError, KeyError, ValueError):
        return None


def system_ok():
    """입구 → Spring → DB·에이전트가 모두 정상이면 True."""
    try:
        code, st = jhttp("GET", "/api/system/status", timeout=5)
        return code == 200 and isinstance(st, dict) and st["db"]["ok"] and st["agent"]["ok"]
    except (OSError, ValueError, KeyError, TypeError):
        return False


def expected(name):
    """정답 응답 JSON(golden/<name>.response.json)에서 기대 값을 읽는다: 1안 총액, 기준안 총액, 현행 계획 위반 건수(없으면 None)."""
    doc = json.loads((GOLDEN / f"{name}.response.json").read_text(encoding="utf-8"))
    cur = doc.get("current_plan")
    return doc["candidates"][0]["total_usd"], doc["baseline"]["total_usd"], (len(cur["violations"]) if cur else None)


ENGINE_TITLE = {("team-cpsat", "team"): "팀 엔진(팀원 코드 · CP-SAT) · 팀 해석", ("ppt-milp", "team"): "기존 엔진(HiGHS) · 팀 해석",
                ("ppt-milp", "ppt"): "기존 엔진(HiGHS) · 기존 해석"}


def golden(s, sample, name, limit_s, watch_heartbeat=False, engine="ppt-milp", profile="ppt"):
    """정답 세트 한 벌: 데이터 넣기 → 실행(엔진·해석 지정) → 1안·기준안 금액·재검증. 팀 해석 정답 파일은 요청에 해석 patch가 들어 있다."""
    expect_first, expect_base, expect_current_violations = expected(name)
    doc = json.loads((ROOT / "data" / "samples" / sample).read_text(encoding="utf-8"))
    req = GOLDEN / f"{name}.request.json"
    if req.exists():
        want = json.loads(req.read_text(encoding="utf-8"))
        if profile != "ppt":   # 팀 해석 정답의 요청 = 데이터 + 해석 patch (Spring이 실행할 때 덮어쓰는 것과 같은 모양)
            want.pop("rule_patch", None)
        if want != {k: v for k, v in doc.items() if k != "rule_patch" or profile == "ppt"}:
            s.note(f"data/samples/{sample}이 정답 요청 {req.name}과 다름 → 금액이 안 맞으면 make sync-engine (팀 해석이면 agent/tests/make_team_golden.py)")
    code, c = jhttp("POST", "/api/cases", doc)
    if not s.check(code in (200, 201), f"데이터 넣기 POST /api/cases ({sample})", f"HTTP {code} · 데이터 #{c.get('id') if isinstance(c, dict) else '?'}"):
        return
    code, r = jhttp("POST", "/api/runs", {"case_id": c["id"], "top": 3, "time_limit_s": 120, "engine": engine, "profile": profile})
    if not s.check(code in (200, 202), f"실행 접수 POST /api/runs → 202 ({ENGINE_TITLE[(engine, profile)]})",
                   f"실행 #{r.get('run_id') if isinstance(r, dict) else '?'}"):
        return
    hb = {"ages": [], "nulls": 0, "errors": 0} if watch_heartbeat else None
    d, took = wait_run(r["run_id"], limit_s, hb)
    ran = s.check(d is not None and d["status"] == "SUCCEEDED", "실행 완료 (INPUT → SOLVE → VERIFY → PUBLISH)",
                  f"{d['status'] if d else '시간 초과'} · {took:.0f}초 · 처리 컨테이너 {d.get('worker') if d else '-'}")
    if hb is not None:
        # 맥박은 10초마다 찍힌다. 계산이 스케줄러 스레드를 붙잡으면 계산 내내(샘플 54건 약 90초) 맥박이 멈춘다.
        worst = max(hb["ages"]) if hb["ages"] else None
        s.check(worst is not None and worst <= 30 and not hb["nulls"], "계산 중 맥박(heartbeat) 나이 최대 ≤ 30초 (스케줄러 스레드가 계산에 막히지 않음)",
                f"최대 {'?' if worst is None else worst}초 · {len(hb['ages'])}번 잼" + (f" · 맥박 빈 값 {hb['nulls']}번" if hb["nulls"] else "")
                + (f" · 못 잰 {hb['errors']}번" if hb["errors"] else ""))
    if not ran:
        if d and d.get("error"):
            s.note(d["error"])
        return
    s.check(d.get("engine") == engine and d.get("profile") == profile and d["summary"].get("run_engine") == engine,
            "실행에 고른 엔진·해석이 그대로 남음", f"{d.get('engine')} · {d.get('profile')} · 엔진 {d['summary'].get('engine', {}).get('version')}")
    rows = {x["name"]: x for x in d["summary"]["schedules"]}
    first, base = rows.get("1안"), rows.get("기준안")
    s.check(first and abs(first["total_usd"] - expect_first) < 0.005, f"1안 총 예상 체선료 = ${expect_first:,.2f}", f"서버 값 ${first['total_usd']:,.2f}" if first else "")
    s.check(base and abs(base["total_usd"] - expect_base) < 0.005, f"기준안 = ${expect_base:,.2f}", f"서버 값 ${base['total_usd']:,.2f}" if base else "")
    v = d["verification"]
    s.check(v["mismatches"] == 0 and v["rules_same"], "Spring 재검증: 솔버 값과 1분·1센트까지 같음",
            f"작업계획 {v['checked_plans']}개 · 불일치 {v['mismatches']} · 규칙 표 같음={v['rules_same']}")
    s.check(all(x["verified"] for x in d["summary"]["schedules"] if x["rank"] > 0), "후보 전부 재검증 통과 (모두 고를 수 있음)",
            f"{d['summary']['verified_candidates']}/{d['summary']['candidates']}")
    if expect_current_violations is not None:
        cur = rows.get("현행 계획")
        s.check(cur and cur["violations"] == expect_current_violations, f"현행 계획(사람이 짠 것) 규칙 위반 {expect_current_violations}건을 Spring도 똑같이 찾음",
                f"Spring {cur['violations'] if cur else '?'}건")
    s.note(f"솔버 {d['summary']['solve_seconds']}초 · 재검증 {d['summary']['verify_ms']}ms")
    return d


def prom_query(expr):
    """Prometheus에 물어본다(밖으로 포트를 열지 않아 컨테이너 안에서). 결과 목록 또는 None."""
    url = "http://127.0.0.1:9090/api/v1/query?query=" + urllib.parse.quote(expr, safe="")
    p = dexec("dmin-prometheus", "wget", "-q", "-O", "-", url, timeout=30)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)["data"]["result"]
    except (ValueError, KeyError):
        return None


def run_steps():
    print(f"{B}D-MIN 로컬 실행판(Docker Compose) 확인 순서{X}  (프로젝트 {PROJECT} · 입구 {BASE} · Grafana {GRAFANA})")
    key = None
    insp: dict = {}

    # 0 준비물
    with step(0, "준비물") as s:
        s.check(shutil.which("docker"), "docker 있음")
        s.check(sh("docker", "compose", "version").returncode == 0, "docker compose 있음")
        try:
            mem = sh("docker", "run", "--rm", "--entrypoint", "sh", CURL_IMAGE, "-c", "grep MemAvailable /proc/meminfo", timeout=60).stdout.split()
            avail = int(mem[1]) / 1024 / 1024
            s.check(avail > 0.8, "Docker 가용 메모리", f"{avail:.1f} GiB (솔버가 돌 때 최대 약 0.7 GiB 더 씀)")
        except Exception as e:  # noqa: BLE001
            s.note(f"가용 메모리 확인 못 함: {e}")

    # 1 컨테이너
    with step(1, "컨테이너 (Compose 프로젝트 dmin · 쿠버네티스 없음)") as s:
        names = sh("docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={PROJECT}", "--format", "{{.Names}}").stdout.split()
        if not s.check(bool(names), "프로젝트 dmin의 컨테이너가 있음", " · ".join(sorted(names)) or "없음 → make up"):
            return   # 컨테이너가 없으면 여기서 멈춘다
        for name, has_health in CONTAINERS:
            i = insp[name] = inspect(name)
            st = (i or {}).get("State", {})
            health = st.get("Health", {}).get("Status")
            ok = bool(i) and st.get("Running") and (health == "healthy" if has_health else True)
            s.check(ok, f"{name} 실행 중" + (" · 정상(healthy)" if has_health else ""),
                    "없음" if not i else f"{st.get('Status')}{' · ' + health if health else ''} · {i['Config']['Image']}")
        hard = [n for n, _ in CONTAINERS if (insp.get(n) or {}).get("HostConfig", {}).get("CapDrop") in (["ALL"], ["all"])]
        # Docker는 권한 이름을 CAP_NET_BIND_SERVICE처럼 CAP_을 붙여 돌려주기도 한다 → 떼고 비교한다
        added = {n: [c.removeprefix("CAP_") for c in ((insp.get(n) or {}).get("HostConfig", {}).get("CapAdd") or [])] for n, _ in CONTAINERS}
        extra = {n: a for n, a in added.items() if a}
        s.check(len(hard) == len(CONTAINERS) and extra == {"dmin-caddy": ["NET_BIND_SERVICE"]},
                "모든 컨테이너가 권한(capabilities)을 전부 내려놓고 돈다 (입구만 '포트 열기' 하나를 되돌려 받음)",
                f"{len(hard)}/{len(CONTAINERS)}" + (f" · 되돌려 받은 것 {extra}" if extra != {"dmin-caddy": ["NET_BIND_SERVICE"]} else ""))
        ro = [n for n in ("dmin-caddy", "dmin-front", "dmin-server", "dmin-agent", "dmin-collector", "dmin-prometheus")
              if (insp.get(n) or {}).get("HostConfig", {}).get("ReadonlyRootfs")]
        s.check(len(ro) == 6, "앱 컨테이너 6개는 파일 시스템이 읽기 전용", " · ".join(ro))
        # 메모리: 한도에 붙어 도는 컨테이너가 없는지. 돌려받을 수 없는 메모리(anon)가 한도의 90%를 넘으면 OOM 직전이다
        probe_mem = "cat /sys/fs/cgroup/memory.max; grep '^anon ' /sys/fs/cgroup/memory.stat; grep '^oom_kill ' /sys/fs/cgroup/memory.events"
        usage, tight, killed = [], [], []
        for name, _ in CONTAINERS:
            w = dexec(name, "sh", "-c", probe_mem, timeout=20).stdout.split()
            limit, anon, kills = (as_int(w[0]), as_int(w[2]), as_int(w[4])) if len(w) == 5 else (None, None, None)
            if not limit or anon is None:
                continue   # 한도가 없거나(max) 읽지 못한 컨테이너
            usage.append(f"{name.removeprefix('dmin-')} {anon / limit:.0%}")
            if anon / limit >= 0.9:
                tight.append(f"{name} {anon >> 20}/{limit >> 20}MiB")
            if kills:
                killed.append(f"{name} {kills}번")
        if len(usage) == len(CONTAINERS):
            s.check(not tight, "메모리 한도에 붙어 도는 컨테이너 없음 (모두 한도의 90% 아래)", " · ".join(tight) if tight else " · ".join(usage))
            s.check(not killed, "메모리 부족으로 죽은 적 없음 (oom_kill 0)", " · ".join(killed))
        else:
            s.note(f"메모리 사용량을 {len(CONTAINERS) - len(usage)}개 컨테이너에서 읽지 못함 (cgroup v2가 아니거나 한도 없음)")
        restarts = sum((insp.get(n) or {}).get("RestartCount", 0) for n, _ in CONTAINERS)
        s.note(f"컨테이너 재시작 합 {restarts}회")

    # 2 네트워크·포트
    with step(2, "네트워크와 포트 (누가 누구에게 닿는가 · 쿠버네티스 판의 NetworkPolicy 자리)") as s:
        for net, (internal, want) in NETWORKS.items():
            p = sh("docker", "network", "inspect", f"{PROJECT}_{net}")
            if p.returncode != 0:
                s.check(False, f"네트워크 {net} 있음", "없음")
                continue
            n = json.loads(p.stdout)[0]
            got = {c["Name"] for c in n.get("Containers", {}).values()}
            s.check(n.get("Internal") is internal and got == want,
                    f"{net}: {' ↔ '.join(sorted(want))}" + (" (밖으로 나가는 길 없음)" if internal else " (밖과 통함)"),
                    "" if got == want and n.get("Internal") is internal else f"internal={n.get('Internal')} · 붙은 것 {sorted(got)}")
        opened = {}
        for name, _ in CONTAINERS:
            for port, binds in ((insp.get(name) or {}).get("NetworkSettings", {}).get("Ports") or {}).items():
                for b in binds or []:
                    opened.setdefault(name, []).append((port, b.get("HostIp"), b.get("HostPort")))
        s.check(set(opened) == set(PUBLISHED) and all(p == PUBLISHED[n] for n, lst in opened.items() for p, _, _ in lst),
                "호스트에 포트를 연 컨테이너는 입구(dmin-caddy)와 dmin-grafana 둘뿐", " · ".join(f"{n} {ip}:{hp}" for n, lst in opened.items() for _, ip, hp in lst))
        s.check(all(ip == "127.0.0.1" for lst in opened.values() for _, ip, _ in lst), "연 포트는 모두 127.0.0.1에만 묶임 (같은 망의 다른 기기에서 못 들어옴)")

    # 3 비밀값
    with step(3, "비밀값 (.env · runtime/secrets.env)") as s:
        sec = env_file(SECRETS_FILE)
        key = ENV.get("PUBLIC_DATA_SERVICE_KEY", "")
        for v in [key, *sec.values()]:
            if v:
                SECRETS.append(v)
        for f in (ENV_FILE, SECRETS_FILE):
            ok = f.is_file() and stat.S_IMODE(f.stat().st_mode) == 0o600
            s.check(ok, f"{f.relative_to(ROOT)} 있음 · 권한 600 (나만 읽음)", "" if ok else ("없음" if not f.is_file() else oct(stat.S_IMODE(f.stat().st_mode))))
        s.check(all(sec.get(k) for k in ("OWNER_PASSWORD", "APP_PASSWORD", "GRAFANA_PASSWORD")), "DB 계정 2개·Grafana 비밀번호가 채워져 있음")
        if sh("git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree").returncode == 0:
            ign = all(sh("git", "-C", str(ROOT), "check-ignore", "-q", str(f)).returncode == 0 for f in (ENV_FILE, SECRETS_FILE))
            s.check(ign, "두 파일 모두 .gitignore에 걸림 (커밋되지 않음)")
            listed = sh("git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", ".").stdout.split("\0")
            leaked = []
            for rel in filter(None, listed):
                fp = ROOT / rel
                try:
                    if fp.is_file() and fp.stat().st_size < 2_000_000:
                        text = fp.read_text(encoding="utf-8", errors="ignore")
                        if any(v and v in text for v in SECRETS):
                            leaked.append(rel)
                except OSError:
                    pass
            s.check(not leaked, "커밋될 수 있는 파일 어디에도 키·비밀번호가 없음", ", ".join(leaked[:5]) or f"{len([x for x in listed if x])}개 파일 검사")
        envs = {n: "\n".join((insp.get(n) or {}).get("Config", {}).get("Env") or []) for n, _ in CONTAINERS}
        if key:
            holders = sorted(n for n, e in envs.items() if key in e)
            s.check(holders == ["dmin-server"], "공공데이터 키는 Spring 컨테이너에만 들어 있음", " · ".join(holders) or "어디에도 없음")
        clean = [n for n in ("dmin-agent", "dmin-front", "dmin-caddy", "dmin-collector", "dmin-prometheus") if not any(v in envs.get(n, "") for v in SECRETS)]
        s.check(len(clean) == 5, "Python·Vue·Caddy·수집 타이머·Prometheus 컨테이너에는 비밀값이 하나도 없음", " · ".join(clean))
        s.note("공공데이터 키: " + ("있음 → 8단계에서 실제 API 확인" if key else "없음 → 8단계 건너뜀(나머지는 그대로 동작)"))

    # 4 DB
    with step(4, "DB (Postgres + pgvector · Flyway 마이그레이션 · 계정 분리)") as s:
        vol = sh("docker", "volume", "inspect", f"{PROJECT}_pgdata")
        s.check(vol.returncode == 0, "DB 데이터가 볼륨 dmin_pgdata에 있음 (make down 해도 남음)")
        # 버전은 글자라서 max(version)은 '10' < '9'가 된다 → 숫자로 바꿔 비교한다
        ver = psql("dmin_app", "SELECT max(version::int) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'").stdout.strip()
        bad = psql("dmin_app", "SELECT count(*) FROM flyway_schema_history WHERE NOT success").stdout.strip()
        s.check((as_int(ver) or 0) >= 4 and bad == "0", "마이그레이션 끝남 · 스키마 v4 이상 (V1 pgvector · V2 표 · V3 앱 계정 권한 · V4 엔진·해석)", f"v{ver} · 실패한 마이그레이션 {bad}건")
        mig = (inspect("dmin-migrate") or {}).get("State", {})
        s.check(mig.get("Status") == "exited" and mig.get("ExitCode") == 0, "마이그레이션 컨테이너(dmin-migrate)가 한 번 돌고 정상 종료 (마이그레이션 계정 dmin_owner)",
                f"{mig.get('Status', '없음')} · 종료 코드 {mig.get('ExitCode', '?')}")
        ext = psql("dmin_app", "SELECT extversion FROM pg_extension WHERE extname='vector'").stdout.strip()
        s.check(bool(ext), "pgvector 확장 있음", f"vector {ext}")
        upd = psql("dmin_app", "UPDATE decision_event SET reason = reason WHERE false")
        s.check(upd.returncode != 0 and "permission denied" in upd.stderr, "앱 계정(dmin_app)은 결정 이력을 UPDATE 못 함 (추가 전용)", (upd.stderr.strip().splitlines() or [""])[-1][:90])
        who = ((insp.get("dmin-server") or {}).get("Config", {}).get("Env") or [])
        s.check("SPRING_DATASOURCE_USERNAME=dmin_app" in who, "Spring은 앱 계정으로만 붙음 (표 주인 계정은 마이그레이션 컨테이너만 씀)")

    # 5 밖에서 접속
    with step(5, f"밖에서 접속 ({BASE} · 입구 Caddy)") as s:
        try:
            code, ctype, raw = http("GET", "/")
        except OSError as e:  # URLError(닿지 않음)·시간 초과·연결 끊김
            s.check(False, "입구에 닿음 (GET /)", str(getattr(e, "reason", e)))
            return   # 입구에 닿지 않으면 뒤 단계는 의미가 없어 여기서 멈춘다
        s.check(code == 200 and b'<div id="app">' in raw, "GET / → Vue 화면 (Caddy → nginx)", f"HTTP {code} {ctype.split(';')[0]}")

        def probe(what, fn):
            """요청 하나가 시간 초과·연결 끊김이면 그 검사만 실패로 남기고 다음으로 간다."""
            try:
                fn()
            except OSError as e:
                s.check(False, what, f"요청 실패: {getattr(e, 'reason', e)}")
            except (ValueError, KeyError, TypeError) as e:  # JSON이 아니거나 모양이 다름 — 이 검사만 실패
                s.check(False, what, f"응답 모양이 다름: {type(e).__name__}: {e}"[:200])

        def status_api():
            code, st = jhttp("GET", "/api/system/status")
            ok = code == 200 and isinstance(st, dict)
            s.check(ok, "GET /api/system/status → Spring JSON (Caddy → Spring)", f"HTTP {code}")
            if ok:
                s.check(st["db"]["ok"] and (as_int(st["db"].get("schema_version")) or 0) >= 4, "Spring → DB 정상",
                        f"스키마 v{st['db'].get('schema_version')} · {st['db'].get('counts')}")
                s.check(st["agent"]["ok"], "Spring → Python 에이전트 정상 (agent 네트워크)", f"{st['agent'].get('engine')}")
                s.check(st["agent"].get("rules_same"), "규칙 표가 Spring·Python 같음 (sha256)", st["server"]["rules_sha256"][:16])

        def hidden(method, path, body, what):
            # 숨긴 경로에 Spring이 답하면 JSON이다 → JSON이 아닐 때(Vue의 HTML · nginx 405)만 통과
            code, ctype, raw = http(method, path, body)
            s.check(not looks_json(ctype, raw), what, f"HTTP {code} {ctype.split(';')[0] or '형식 없음'}")

        def apix():
            code, ctype, raw = http("GET", "/apix")
            s.check("text/html" in ctype.lower() and b'<div id="app">' in raw,
                    "GET /apix → Vue 화면 (/api 규칙은 경로 조각 단위라 걸리지 않음)", f"HTTP {code} {ctype.split(';')[0] or '형식 없음'}")

        probe("GET /api/system/status → Spring JSON", status_api)
        probe("/actuator/** 는 밖에서 Spring에 닿지 않음", lambda: hidden("GET", "/actuator/env", None,
              "/actuator/** 는 밖에서 Spring에 닿지 않음 (Caddy가 넘기지 않음 → Vue가 받음)"))
        probe("/actuator/prometheus 도 밖에서 안 보임", lambda: (lambda r: s.check(b"jvm_memory" not in r[2],
              "/actuator/prometheus(지표)도 밖에서 안 보임", f"HTTP {r[0]} {r[1].split(';')[0] or '형식 없음'}"))(http("GET", "/actuator/prometheus")))
        probe("/internal/** 은 밖에서 Spring에 닿지 않음", lambda: hidden("POST", "/internal/collect/eta", b"{}",
              "/internal/** 은 밖에서 Spring에 닿지 않음 (수집 타이머만 jobs 네트워크에서 부름)"))
        probe("GET /apix → Vue 화면", apix)

    # 6 내부 경계
    with step(6, "내부 경계 (실제로 연결해 봄)") as s:
        net_check(s, conn_from_new("public", "dmin-agent", 8000), "NO_CONNECT", "아무 컨테이너 → dmin-agent:8000 막힘 (에이전트는 Spring 요청만 받음)")
        net_check(s, conn_from_new("public", "dmin-postgres", 5432), "NO_CONNECT", "아무 컨테이너 → dmin-postgres:5432 막힘 (DB는 Spring·마이그레이션만)")
        net_check(s, conn_from_new("public", "dmin-server", 8080), "NO_CONNECT", "아무 컨테이너 → dmin-server:8080 막힘 (Spring은 입구·수집 타이머·Prometheus만 받음)")
        net_check(s, conn_from("dmin-front", "dmin-server", 8080), "NO_CONNECT", "Vue 컨테이너 → dmin-server:8080 막힘 (화면은 입구를 거쳐서만 Spring에 감)")
        net_check(s, conn_from("dmin-collector", "dmin-server", 8080), "CONNECTED", "수집 타이머 → dmin-server:8080 열림 (허용한 길은 열려 있음)")
        net_check(s, conn_from("dmin-collector", "dmin-agent", 8000), "NO_CONNECT", "수집 타이머 → dmin-agent:8000 막힘")
        net_check(s, conn_from("dmin-collector", "dmin-postgres", 5432), "NO_CONNECT", "수집 타이머 → dmin-postgres:5432 막힘")
        p = dexec("dmin-agent", "/app/.venv/bin/python", "-c", TCP_PROBE, "dmin-postgres", "5432", timeout=30)
        res = (p.stdout.strip().splitlines() or [""])[-1]
        s.check(res.split(" ")[0] == "NO_CONNECT", "Python 에이전트 → dmin-postgres:5432 막힘 (DB 계정도 없고 길도 없음)", res or p.stderr.strip()[:100])
        p = dexec("dmin-agent", "/app/.venv/bin/python", "-c", INTERNET_PROBE, timeout=40)
        res = (p.stdout.strip().splitlines() or [""])[-1]
        s.check(res.split(" ")[0] == "BLOCKED", "Python 에이전트 → 인터넷 막힘 (LLM 문장 노드를 붙일 때 agent 네트워크만 열면 됨)",
                res or (p.stderr.strip().splitlines() or ["출력 없음"])[-1][:120])

    # 7 정답 세트
    with step(7, "정답 세트 (예시 3척 + FIX 1척 · 기상 악화 6시간) — 팀 엔진 · 기존 엔진") as s:
        golden(s, "example-3.json", "TEAM-CPSAT-EXAMPLE-3", 120, engine="team-cpsat", profile="team")
        golden(s, "example-3.json", "EXAMPLE-3", 120)

    # 8 공공 API
    with step(8, "공공데이터 API (울산항 선박 위치 · 입항 신고 ETA · 매일 수집)") as s:
        if not key:
            s.skip("키 없음 — .env에 PUBLIC_DATA_SERVICE_KEY를 넣고 make restart")
        else:
            code, v = jhttp("GET", "/api/ais/vessels?max_age_min=60", timeout=40)
            n = v.get("count", 0) if isinstance(v, dict) else 0
            s.check(code == 200 and n > 0, "GET /api/ais/vessels → 울산항 선박", f"HTTP {code} · 60분 안 수신 {n}척 / 전체 {v.get('total') if isinstance(v, dict) else '?'} · 수신 {v.get('fetchedAt') if isinstance(v, dict) else ''}")
            code, a = jhttp("GET", "/api/entry/arrivals?hours_ahead=72", timeout=90)
            s.check(code == 200 and isinstance(a, dict), "GET /api/entry/arrivals → 입항 신고(ETA)", f"HTTP {code} · 72시간 안 입항 예정 {a.get('count') if isinstance(a, dict) else '?'}건 · 창 {a.get('window') if isinstance(a, dict) else ''}")
            both = json.dumps(v, ensure_ascii=False) + json.dumps(a, ensure_ascii=False)
            s.check(key not in both, "응답에 서비스 키 없음")
            before = eta_rows()
            t0 = time.time()
            p = dexec("dmin-collector", "sh", "/collector.sh", "once", timeout=330)   # 90초 × 3번 + 쉬는 시간
            after = eta_rows()
            out = p.stdout.strip()
            okline = next((ln for ln in out.splitlines() if '"ok":true' in ln.replace(" ", "")), "")
            s.check(p.returncode == 0, "수집 타이머를 손으로 한 번 실행 (make collect와 같음) → 성공", f"종료 코드 {p.returncode} · {time.time() - t0:.0f}초")
            s.check(bool(okline), '수집 로그에 "ok":true (Spring /internal/collect/eta가 받아 저장)', (okline or out)[:140])
            s.check(before is not None and after is not None and after >= before, "eta_snapshot 줄 수가 줄지 않음 (새 입항 신고가 있을 때만 늘어남 · 같은 신고는 한 번만)",
                    f"{before} → {after}줄")
            log = sh("docker", "logs", "--tail", "5", "dmin-collector").stdout + sh("docker", "logs", "--tail", "5", "dmin-collector").stderr
            s.check("다음 수집까지" in log or "수집 타이머 시작" in log, "타이머가 다음 06:00(KST)을 기다리는 중", (log.strip().splitlines() or [""])[-1][:100])

    # 9 관측
    with step(9, "관측 (Prometheus가 Spring 지표를 모으고 Grafana가 보여 줌 · 정의서 3.2절)") as s:
        up = prom_query('up{job="dmin-server"}')
        s.check(bool(up) and up[0]["value"][1] == "1", "Prometheus가 Spring의 /actuator/prometheus를 모으는 중 (up = 1)", "" if up else "결과 없음 — 막 띄웠다면 15초 뒤 다시")
        bk = prom_query("count(http_server_requests_seconds_bucket)")
        s.check(bool(bk) and float(bk[0]["value"][1]) > 0, "응답 시간 히스토그램(_bucket)이 있음 → p95를 낼 수 있음", f"계열 {bk[0]['value'][1] if bk else 0}개")
        cmd = " ".join((insp.get("dmin-prometheus") or {}).get("Config", {}).get("Cmd") or [])
        s.check("--storage.tsdb.retention.time=3d" in cmd, "지표 보관 3일")
        code, _, raw = http("GET", "/api/health", base=GRAFANA)
        s.check(code == 200 and b'"database"' in raw and b"ok" in raw, "Grafana 정상 (GET /api/health)", f"HTTP {code}")
        code, _, _ = http("GET", "/api/search", base=GRAFANA)
        s.check(code == 401, "Grafana는 로그인 없이는 안 보임 (대시보드에 인증 적용)", f"HTTP {code}")
        pw = env_file(SECRETS_FILE).get("GRAFANA_PASSWORD", "")
        auth = {"Authorization": "Basic " + base64.b64encode(f"admin:{pw}".encode()).decode()}
        code, _, raw = http("GET", "/api/datasources/uid/dmin-prometheus", base=GRAFANA, headers=auth)
        s.check(code == 200, "Grafana 데이터 소스 Prometheus가 연결돼 있음", f"HTTP {code}")
        code, _, raw = http("GET", "/api/dashboards/uid/dmin-server", base=GRAFANA, headers=auth)
        title = json.loads(raw).get("dashboard", {}).get("title") if code == 200 else None
        s.check(code == 200 and bool(title), "대시보드 'D-MIN 서버 지표'가 들어 있음 (요청량·오류율·p95·JVM·DB 연결 풀)", f"HTTP {code} · {title or ''}")

    # 10 장애 복구
    with step(10, "장애 복구 (Spring 프로세스를 죽여도 저절로 다시 뜨는가)") as s:
        before = inspect("dmin-server") or {}
        r0 = before.get("RestartCount", 0)
        # JVM만 죽인다(1번 프로세스는 tini). docker kill 은 '손으로 멈춤'으로 기록돼 restart 정책이 돌지 않으므로 쓰지 않는다
        killer = 'for d in /proc/[0-9]*; do [ "$(cat $d/comm 2>/dev/null)" = "java" ] && kill -9 ${d#/proc/}; done; exit 0'
        dexec("dmin-server", "bash", "-c", killer, timeout=20)
        t0, first_fail, back = time.time(), None, None
        while time.time() - t0 < 180:
            ok = system_ok()
            now = time.time() - t0
            if not ok and first_fail is None:
                first_fail = now
            if ok and first_fail is not None:
                back = now
                break
            time.sleep(0.5)
        r1 = (inspect("dmin-server") or {}).get("RestartCount", 0)
        s.check(r1 > r0, "Docker가 Spring 컨테이너를 다시 띄움 (restart: unless-stopped)", f"재시작 횟수 {r0} → {r1}")
        s.check(back is not None, "입구 → Spring → DB·Python이 다시 정상", "180초 안에 돌아오지 않음" if back is None else f"죽인 뒤 {back:.0f}초")
        if first_fail is not None and back is not None:
            s.note(f"끊긴 시간 약 {back - first_fail:.0f}초 — 컨테이너가 하나라 이만큼은 끊긴다(쿠버네티스 판은 Spring 2개라 0~1번 실패였다)")
        s.check(first_fail is not None, "죽인 것이 실제로 보였음 (그 사이 /api/system/status 실패가 있었음)", "실패가 한 번도 안 보임 — 죽이지 못했을 수 있음" if first_fail is None else f"{first_fail:.1f}초부터")

    # 11 실제 크기
    with step(11, "실제 크기 데이터 (샘플 주간 54건 · 팀원 가상 데이터 54척 두 엔진)") as s:
        if not FULL:
            s.skip("FULL=1 일 때만 (약 5분 더) — make verify-full")
        else:
            golden(s, "sample-week-54.json", "SAMPLE-W46", 900, watch_heartbeat=True)
            golden(s, "team-week-54.json", "TEAM-CPSAT-TEAM-W46", 900, engine="team-cpsat", profile="team")
            golden(s, "team-week-54.json", "PPT-MILP-TEAM-W46", 900, engine="ppt-milp", profile="team")


def main():
    complete = False
    try:
        run_steps()
        complete = True
    finally:
        rc = finish(complete)   # 중간에 죽어도(Ctrl-C 등) 기록은 남긴다
    return rc


def finish(complete=True):
    total = [i for s in results for i in s.items]
    bad = [f"{s.no}. {s.title} — {i['what']}" for s in results for i in s.items if not i["ok"]]
    skipped = [f"{s.no}. {s.title}" for s in results if s.skipped]
    print(f"\n{B}결과{X}: 검사 {len(total)}개 중 {G}통과 {len(total) - len(bad)}{X} · {R if bad else ''}실패 {len(bad)}{X}" + (f" · 건너뜀 {len(skipped)}단계" if skipped else ""))
    for b in bad:
        print(f"  {R}✗{X} {b}")
    if not complete:
        print(f"  {R}✗{X} 검사가 중간에 멈춤 (complete=false)")
    out = ROOT / "runtime" / "verify-result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "base_url": BASE, "full": FULL, "complete": complete,
                               "steps": [{"no": s.no, "title": s.title, "ok": s.ok, "skipped": s.skipped, "items": s.items} for s in results]},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  기록: {out.relative_to(ROOT)}")
    return 1 if bad or not complete else 0


if __name__ == "__main__":
    sys.exit(main())
