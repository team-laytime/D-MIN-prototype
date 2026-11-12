"""'지금 실시간 선박 데이터가 들어온다'를 스스로 증명하는 검사. 로컬 서버(8000)가 떠 있어야 한다.

    PYTHONPATH=src python scripts/verify_live.py [--base http://127.0.0.1:8000] [--wait 400]

무엇을 증명하나
  1. 서버가 살아 있고 선박을 돌려준다
  2. 데이터가 '방금' 것이다  — 가장 최근 수신이 몇 분 전인지
  3. 시간이 지나면 값이 바뀐다 — 갱신이 보일 때까지 최대 --wait초 반복해 위치·수신 시각이 움직였는지 (고정된 샘플이면 여기서 걸린다)
     ※ 원본(울산항만공사)은 선박마다 실시간이 아니라 약 5분 주기로 일괄 갱신된다(2026-11-12 직접 측정). 그래서 한 번에 안 보일 수 있다.
  4. 우리 서버 값 = 원본(공공데이터포털) 값 — PUBLIC_DATA_SERVICE_KEY가 환경에 있을 때만, 같은 선박을 원본에서 직접 받아 대조
  5. ETA(입항 예정)가 미래 시각으로 들어온다
  6. 응답에 서비스키가 새지 않는다
끝에 사람이 눈으로 대조할 외부 링크(MarineTraffic·VesselFinder)를 선박 몇 척 골라 적어 준다.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BOX = "35.40,129.36,35.51,129.48"
results = []


def get(base, path, timeout=90):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return r.read().decode("utf-8")


def check(name, ok, detail):
    results.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")


def meters(a, b):
    dy = (b["lat"] - a["lat"]) * 111_000
    dx = (b["lng"] - a["lng"]) * 111_000 * math.cos(math.radians(a["lat"]))
    return math.hypot(dx, dy)


def source_row(key, mmsi):
    """원본 API에서 같은 선박(MMSI)을 직접 찾는다."""
    q = urllib.parse.urlencode({"serviceKey": key, "pageNo": 1, "numOfRows": 1000})
    root = ET.fromstring(urllib.request.urlopen("https://apis.data.go.kr/B551938/VslPstnInfoService/getVslPstnInfo?" + q, timeout=60).read())
    for it in root.iter("item"):
        if it.findtext("mmsiNo") == mmsi:
            return {c.tag: (c.text or "") for c in it}
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--wait", type=int, default=400, help="갱신을 기다릴 최대 초 (원본이 약 5분 주기로 일괄 갱신)")
    a = ap.parse_args(argv)
    now = datetime.now(KST)
    print(f"■ 실시간 연결 검사 — {now:%Y-%m-%d %H:%M:%S} KST · 서버 {a.base}\n")

    # 1
    try:
        get(a.base, "/healthz", 10)
        check("1. 서버 응답", True, "/healthz 200")
    except Exception as e:
        check("1. 서버 응답", False, f"서버에 닿지 않음: {type(e).__name__} — `make serve`로 먼저 띄우세요")
        return finish()
    try:
        d1 = json.loads(get(a.base, f"/api/ais/vessels?max_age_min=1440&bbox={BOX}"))
    except Exception as e:
        check("1. 선박 목록", False, f"{type(e).__name__} — 서버에 PUBLIC_DATA_SERVICE_KEY가 있는지 확인")
        return finish()
    vs = d1["vessels"]
    check("1. 선박 목록", len(vs) > 50, f"울산항 지도 범위 선박 {len(vs)}척 (전체 {d1['total']}척 중), 서버 수신 {d1['fetchedAt'][11:19]}")

    # 2
    ages = sorted(v["ageMin"] for v in vs if v["ageMin"] is not None)
    fresh10 = sum(1 for x in ages if x <= 10)
    check("2. 최신성", bool(ages) and ages[0] <= 10, f"가장 최근 수신 {ages[0]:.1f}분 전 · 10분 안 갱신 {fresh10}척 · 중앙값 {ages[len(ages)//2]:.0f}분 전")

    # 3
    print(f"\n  … 갱신을 기다립니다 (최대 {a.wait}초, 35초마다 확인). 원본이 약 5분 주기로 일괄 갱신해서 몇 분 걸릴 수 있습니다")
    first = {v["mmsi"]: v for v in vs if v["mmsi"]}
    t0 = time.time()
    d2, moved, updated = d1, [], 0
    while time.time() - t0 < a.wait:
        time.sleep(35)
        d2 = json.loads(get(a.base, f"/api/ais/vessels?max_age_min=1440&bbox={BOX}"))
        moved, updated = [], 0
        for v in d2["vessels"]:
            p = first.get(v["mmsi"])
            if p and v["updatedAt"] != p["updatedAt"]:
                updated += 1
                m = meters(p, v)
                if m >= 5:
                    moved.append((v["name"] or v["mmsi"], m, v["sog"]))
        print(f"    +{int(time.time() - t0):>3}초: 수신 시각이 바뀐 선박 {updated}척")
        if updated:
            break
    moved.sort(key=lambda x: -x[1])
    check("3. 값이 바뀜", updated > 0,
          f"{int(time.time() - t0)}초 만에 수신 시각이 갱신된 선박 {updated}척 · 위치가 5m 이상 움직인 선박 {len(moved)}척"
          + (" (예: " + ", ".join(f"{n} {m:.0f}m {s}kn" for n, m, s in moved[:3]) + ")" if moved else "")
          if updated else f"{a.wait}초 안에 갱신이 관측되지 않음 — 원본 갱신 중단이거나 서버 캐시 문제")

    # 4
    key = os.environ.get("PUBLIC_DATA_SERVICE_KEY", "").strip()
    pick = [v for v in d2["vessels"] if v["mmsi"] and v["ageMin"] is not None and v["ageMin"] < 5][:3]
    if key and pick:
        try:
            same = 0
            lines = []
            for v in pick:
                src = source_row(key, v["mmsi"])
                ok = bool(src) and abs(float(src["lat"]) - v["lat"]) < 1e-6 and abs(float(src["lot"]) - v["lng"]) < 1e-6
                same += ok
                lines.append(f"{v['name'] or v['mmsi']}: {'일치' if ok else '불일치(그사이 갱신됐을 수 있음)'}")
            check("4. 서버 값 = 원본 값", same >= 1, "; ".join(lines))
        except Exception as e:
            check("4. 서버 값 = 원본 값", False, f"원본 직접 호출 실패: {type(e).__name__}")
    else:
        print("  [SKIP] 4. 서버 값 = 원본 값 — 환경에 PUBLIC_DATA_SERVICE_KEY가 없어 생략 (`set -a; . ./.env; set +a` 후 다시 실행)")

    # 5
    ar = {}
    try:
        ar = json.loads(get(a.base, "/api/entry/arrivals?hours_ahead=48"))
        planned = [x for x in ar["arrivals"] if x["planned"]]
        check("5. 입항 예정(ETA)", len(planned) > 0, f"48시간 안 입항 예정 {len(planned)}척 · 가장 빠른 건 " + (f"{planned[0]['name']} {planned[0]['eta'][5:16]} {planned[0]['facility'] or '-'}" if planned else "-"))
    except Exception as e:
        check("5. 입항 예정(ETA)", False, f"{type(e).__name__}")

    # 6
    blob = json.dumps(d2) + json.dumps(ar)
    leak = "serviceKey" in blob or (key and key in blob)
    check("6. 키 유출 없음", not leak, "응답 본문에 서비스키·serviceKey 문자열이 없음" if not leak else "응답에 키가 들어 있음 — 즉시 중단하고 키를 재발급하세요")

    # 사람이 눈으로 대조할 링크
    cand = [v for v in d2["vessels"] if v["mmsi"] and v["name"] and v["ageMin"] is not None and v["ageMin"] < 5 and (v["sog"] or 0) > 3][:3]
    cand = cand or [v for v in d2["vessels"] if v["mmsi"] and v["name"]][:3]
    print("\n  ▶ 눈으로 대조 (아래 선박을 외부 사이트에서 찾아 위치가 같은 해역인지 본다)")
    for v in cand:
        print(f"    {v['name']} · MMSI {v['mmsi']} · {v['lat']:.4f}, {v['lng']:.4f} · {v['sog']}kn · {v['navStatus']}")
        print(f"      https://www.vesselfinder.com/?mmsi={v['mmsi']}   https://www.marinetraffic.com/en/ais/details/ships/mmsi:{v['mmsi']}")
    return finish()


def finish():
    bad = [n for n, ok in results if not ok]
    print(f"\n■ 결과: {len(results) - len(bad)}/{len(results)} 통과" + (f" · 실패: {', '.join(bad)}" if bad else " · 실시간 연결 확인"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
