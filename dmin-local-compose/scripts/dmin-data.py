#!/usr/bin/env python3
"""데이터 넣기 → 후보 계산 → 결과 요약. 표준 라이브러리만 쓴다(설치할 것 없음).

    python3 scripts/dmin-data.py load data/inbox/my-week.json     # 넣기만, 계산 안 함 (검사 통과하면 저장 — 지우는 API는 없다)
    python3 scripts/dmin-data.py run  data/inbox/my-week.csv      # 넣기 + 후보 계산 + 끝날 때까지 기다려 요약
    python3 scripts/dmin-data.py inbox                            # data/inbox/의 *.json · *.csv를 이름순으로 run (검사에 걸린 파일은 건너뜀)
    python3 scripts/dmin-data.py status                           # 시스템 상태

입구 주소는 BASE_URL(기본 http://127.0.0.1:18089). 같은 파일을 다시 넣어도 새로 만들지 않는다(지문이 같으면 기존 데이터).
엔진은 ENGINE(team-cpsat = 팀원 코드 · ppt-milp = 기존), 규칙 해석은 PROFILE(team · ppt). 비우면 서버 기본값(팀 엔진 · 팀 해석).
요약이 생긴 실행(PUBLISH까지 간 것)은 요약 + 솔버 응답 원본을 data/out/<데이터 키>-run<번호>.json에 남긴다(같은 이름이 있으면 -2, -3…).
PUBLISH 전에 FAILED가 되면(입력 검사·솔버 호출·솔버 응답 모양·서버 오류·맥박 끊김) 요약이 없어 파일도 없다(이유는 화면·GET /api/runs/{id}).
종료 코드: 0 성공 · 2 넣기 검사에 걸림·파일 없음 · 3 입구가 JSON이 아닌 응답(Spring이 아직 안 떴을 때 등) · 1 그 밖(서버에 닿지 않음·시간 초과·
접수 실패·FAILED·PARTIAL, inbox에서 하나라도 실패). inbox는 넣기 검사에 걸린 파일만 건너뛰고, 서버 쪽 문제면 거기서 멈추고 남은 파일을 알려 준다.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:18089").rstrip("/")


def call(method: str, path: str, body: bytes | None = None, ctype: str | None = None, timeout: float = 60):
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method)
    req.add_header("Accept", "application/json")
    if ctype:
        req.add_header("Content-Type", ctype)
    slow = f"✗ {timeout:.0f}초 안에 응답이 없습니다 ({method} {path}) — 서버가 바쁘거나 멈췄을 수 있습니다 (make status · make logs)"
    try:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                code, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, raw = e.code, e.read()
    except urllib.error.URLError as e:
        if isinstance(e.reason, (TimeoutError, socket.timeout)):
            sys.exit(slow)
        sys.exit(f"✗ 서버에 닿지 않습니다 ({BASE}): {e.reason} — 컨테이너가 떠 있나요? (make up · make status)")
    except (TimeoutError, socket.timeout):  # 연결 뒤 읽는 중에 시간 초과
        sys.exit(slow)
    except (OSError, http.client.HTTPException) as e:  # 응답을 받다가 연결이 끊기거나 잘림(컨테이너 재시작 등)
        sys.exit(f"✗ 응답을 받다가 연결이 끊겼습니다 ({method} {path}): {type(e).__name__} — make status · make logs")
    if not raw.strip() and code < 400:
        return code, None   # 본문 없는 성공 응답
    try:
        return code, json.loads(raw)
    except ValueError:  # JSON이 아님(본문 없는 오류 응답 포함): 입구(Caddy·nginx)의 HTML·텍스트 오류 페이지, 잘못된 BASE_URL 같은 것
        text = " ".join(raw.decode("utf-8", "replace")[:200].split()) or "(본문 없음)"
        print(f"✗ JSON이 아닌 응답: HTTP {code} ({method} {path})\n    {text}\n    막 켰다면 Spring이 뜰 때까지 잠시 뒤 다시 (make status)")
        sys.exit(3)   # 서버(입구) 쪽 문제 — 넣기 검사 거절(2)과 구분한다


def multipart(path: Path, fields: dict[str, str]) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        if v:
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: text/csv\r\n\r\n'.encode())
    parts.append(path.read_bytes())
    parts.append(f"\r\n--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


def load(path: Path) -> dict:
    if path.suffix.lower() == ".csv":
        body, ctype = multipart(path, {"plan_start": os.environ.get("PLAN_START", ""), "plan_end": os.environ.get("PLAN_END", "")})
        code, doc = call("POST", "/api/cases/import", body, ctype)
    elif path.suffix.lower() == ".json":
        code, doc = call("POST", "/api/cases", path.read_bytes(), "application/json")
    else:
        sys.exit(f"✗ .json 또는 .csv만 받습니다: {path}")
    if code not in (200, 201):
        print(f"✗ {path.name}: {doc.get('detail')}")
        for e in doc.get("errors", []):
            print(f"    - {e}")
        sys.exit(2)
    tag = "이미 있는 데이터" if doc["duplicate"] else "저장"
    print(f"✓ {path.name} → 데이터 #{doc['id']} {doc['case_key']} ({tag}) · 입항 {doc['arrivals']}건 · {doc['plan_start']} ~ {doc['plan_end']} · 지문 {doc['payload_hash']}")
    for w in doc.get("warnings", []):
        print(f"    ! {w}")
    return doc


def pad(text, width, right=False):
    """한글은 터미널에서 두 칸을 차지한다 — 화면 폭 기준으로 맞춘다."""
    w = sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(text))
    fill = " " * max(0, width - w)
    return fill + str(text) if right else str(text) + fill


def usd(v):
    return "-" if v is None else f"${v:,.2f}"


def run(path: Path, top: int = 3, time_limit: int = 120) -> bool:
    case = load(path)
    body = {"case_id": case["id"], "top": top, "time_limit_s": time_limit}
    for key, env in (("engine", "ENGINE"), ("profile", "PROFILE")):
        if os.environ.get(env):
            body[key] = os.environ[env]
    code, r = call("POST", "/api/runs", json.dumps(body).encode(), "application/json")
    if code not in (200, 202):
        sys.exit(f"✗ 실행 접수 실패: {r}")
    rid = r["run_id"]
    _, d0 = call("GET", f"/api/runs/{rid}")
    eng = {"team-cpsat": "팀 엔진(팀원 코드 berth_sim · CP-SAT)", "ppt-milp": "기존 엔진(HiGHS)"}.get(d0.get("engine"), d0.get("engine"))
    print(f"  실행 #{rid} 접수 — {eng} · 규칙 해석 {d0.get('profile')} — Spring 작업 큐 → Python 엔진 → Spring 재검증", flush=True)
    t0, last = time.time(), None
    while True:
        _, d = call("GET", f"/api/runs/{rid}")
        steps = " → ".join(f"{s['name']}:{s['status']}" for s in d.get("steps", []))
        if steps != last:
            print(f"  [{time.time() - t0:5.0f}s] {d['status']:9s} {steps}", flush=True)
            last = steps
        if d["status"] in ("SUCCEEDED", "PARTIAL", "FAILED"):
            break
        if time.time() - t0 > 1800:
            sys.exit("✗ 30분 넘게 끝나지 않음")
        time.sleep(2)
    if d.get("error"):
        print(f"  ! {d['error']}")
    s = d.get("summary")
    if s:
        print("\n  " + pad("일정", 10) + pad("총 예상 체선료", 18, True) + pad("기준안 대비", 16, True) + pad("위반", 6, True)
              + pad("바뀐 배", 9, True) + "  재검증")
        for row in s["schedules"]:
            delta = row.get("delta_vs_baseline_usd")
            print("  " + pad(row["name"], 10) + pad(usd(row["total_usd"]), 18, True) + pad("" if delta is None else f"{delta:+,.2f}", 16, True)
                  + pad(row["violations"], 6, True) + pad("" if not row["rank"] else f"{row['changes']}척", 9, True)
                  + "  " + ("통과" if row["verified"] else "실패"))
        v = d.get("verification") or {}
        print(f"\n  솔버 {s['solve_seconds']}초 · 재검증 작업계획 {v.get('checked_plans')}개 불일치 {v.get('mismatches')} · "
              f"규칙 표 Spring {v.get('spring_rules')} / Python {v.get('agent_rules')}")
        out = ROOT / "data" / "out"
        out.mkdir(parents=True, exist_ok=True)
        _, result = call("GET", f"/api/runs/{rid}/result", timeout=120)
        key = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", str(case["case_key"])).strip("._") or "case"   # id에 / · .. 가 있어도 data/out 안에만
        f = out / f"{key}-run{rid}.json"
        n = 2
        while f.exists():   # DB를 새로 만들면(make down → up) 실행 번호가 1부터 다시 매겨진다 — 옛 결과를 덮지 않는다
            f = out / f"{key}-run{rid}-{n}.json"
            n += 1
        try:
            f.write_text(json.dumps({"run": d, "result": result}, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  결과 파일: {f.relative_to(ROOT)}")
        except OSError as e:
            print(f"  ! 결과 파일을 쓰지 못함 ({type(e).__name__}) — 결과는 GET /api/runs/{rid}/result")
    return d["status"] == "SUCCEEDED"


def status():
    _, s = call("GET", "/api/system/status", timeout=10)
    print(json.dumps(s, ensure_ascii=False, indent=1))


def main(argv):
    if len(argv) < 2 or argv[1] not in ("load", "run", "inbox", "status"):
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "status":
        status()
        return 0
    if cmd == "inbox":
        files = sorted(p for p in (ROOT / "data" / "inbox").iterdir() if p.suffix.lower() in (".json", ".csv"))
        if not files:
            print("data/inbox/에 .json·.csv 파일이 없습니다. (계약: data/README.md · 예시: data/samples/ · CSV 틀: data/templates/arrivals.csv)")
            return 1
        failed = []
        for i, p in enumerate(files):
            print(f"\n=== {p.name}")
            try:
                if not run(p):
                    failed.append(p.name)
            except SystemExit as e:
                if e.code == 2:   # 넣기 검사에 걸린 파일은 건너뛰고 다음 파일로
                    failed.append(p.name)
                    continue
                if isinstance(e.code, str):   # 서버에 닿지 않음·시간 초과 등 — 다음 파일도 같으니 여기서 멈춘다
                    print(e.code)
                left = [q.name for q in files[i + 1:]]
                print(f"\n✗ {p.name}에서 멈춤 (서버 쪽 문제)" + (f" · 실패 {', '.join(failed)}" if failed else "")
                      + (f" · 안 한 파일 {', '.join(left)}" if left else ""))
                return e.code if isinstance(e.code, int) and e.code else 1
        if failed:
            print(f"\n✗ {len(files)}개 중 {len(failed)}개 실패: {', '.join(failed)}")
        return 1 if failed else 0
    if len(argv) < 3:
        print(__doc__)
        return 1
    path = Path(argv[2]).expanduser()   # zsh는 FILE=~/x의 ~를 펼치지 않는다
    if not path.is_file():
        print(f"✗ 파일이 없습니다: {argv[2]} (dmin-local-compose 폴더 기준 상대 경로나 절대 경로)")
        return 2
    if cmd == "load":
        load(path)
        return 0
    return 0 if run(path) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
