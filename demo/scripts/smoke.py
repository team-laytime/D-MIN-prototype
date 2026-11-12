"""배포 직후 정답 검문 — 살아 있는 서비스에 정답 사례를 물어 본다(인프라 가이드 4-5, NFR-19).

사용: python scripts/smoke.py http://localhost:8000
  1) /healthz, /readyz
  2) 정답 사례 GC-01(두 척·한 부두): 기준안 52,000 → 1안 6,000 이어야 통과
  3) 대표 데모 S05: 후보 위반 0건, 절감 > 0, 실행 검사 전부 통과
하나라도 틀리면 종료 코드 1 → CI가 배포를 멈춘다.
"""
import json
import pathlib
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
ROOT = pathlib.Path(__file__).resolve().parents[1]


def call(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw.startswith(("{", "[")) else raw


def main() -> int:
    ok = True
    print("■ health", call("/healthz"))
    print("■ ready ", call("/readyz"))
    gc = json.loads((ROOT / "data/golden/GC-01_two_vessels_one_berth.json").read_text(encoding="utf-8"))["cases"][0]["scenario"]
    r = call("/api/runs", {"scenario": gc})
    b, c = r["baseline"]["total_usd"], r["candidates"][0]["total_usd"]
    good = abs(b - 52000) < 0.005 and abs(c - 6000) < 0.005 and all(x["ok"] for x in r["checks"])
    print(f"■ GC-01 정답 검문: 기준안 ${b:,.2f} / 1안 ${c:,.2f} (기대 52,000 / 6,000) → {'통과' if good else '실패'}")
    ok &= good
    r = call("/api/runs", {"scenario_id": "S05-storm-rush"})
    s = r["candidates"][0]["savings_usd"]
    good = s > 0 and all(x["ok"] for x in r["checks"])
    print(f"■ S05 대표 데모: {r['search']['status_ko']} · 기준안 {r['baseline']['total_display']} → 1안 {r['candidates'][0]['total_display']} "
          f"(절감 ${s:,.0f}) · 실행 검사 {sum(x['ok'] for x in r['checks'])}/{len(r['checks'])} → {'통과' if good else '실패'}")
    ok &= good
    m = [ln for ln in call("/metrics").splitlines() if ln.startswith(("demurrage_runs_total", "demurrage_db_runs"))]
    print("■ metrics", " · ".join(m))
    print("검문 통과" if ok else "검문 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
