#!/usr/bin/env python3
"""팀원 데이터(berth_sim 형식) → 우리 요청 JSON 한 개. 팀원 코드의 함수로 읽고 평균 Rate도 팀원 식으로 낸다.

    uv run --project agent --with openpyxl python scripts/team-data-to-case.py            # 기본: ~/Downloads/berth_sim_share
    TEAM_SRC=<팀원 폴더> uv run --project agent --with openpyxl python scripts/team-data-to-case.py

읽는 것 (팀원 data/README.md §5 '실제 데이터로 바꾸기'와 같은 파일)
  Sample data.xlsx '접안계획 예시'     부두 · ETA · ETB · ETU · Biz (선박 54척)       → ETA · 업무 구분 · 현행 계획(실제 부두·ETB)
  data/dummy/current_shipments.csv   선박 제원 · 화물 · 물량 · 계약                 → arrivals[] (값 그대로)
  data/dummy/past_shipments.csv      과거 Shipment                                  → work.by_berth (팀원 average_rate: 선박+자재+부두 → 자재+부두)

우리 형식으로 못 옮기는 것 (결과가 팀원 화면과 다를 수 있는 이유)
  - weather.csv(풍속 예보 → 하역 중단·접안 불가)와 태풍 경로: 우리 요청에는 '하역 중단'이 없다 → 넣지 않는다
  - 부두별 사용 가능 시각(팀원 berth_availability: 그 부두의 첫 실제 ETB 전에는 못 씀) → 부두 제약(WORK)으로 옮긴다:
    [계획 시작, 첫 실제 ETB − Direction) — 우리 부두 제약은 '종료 + Direction'부터 접안이라 결과가 같다
  - 탱크 30기(20~80%): 우리 요청의 inventory는 원유 한 묶음 → 넣지 않는다
  - 작업시간: 우리 식은 물량 ÷ Rate를 분 단위로 올린다(팀원은 초 단위까지) → 배마다 1분 안쪽 차이
과거 실적이 없는 부두는 팀원 코드가 '과거 실적 없음'으로 막으므로, 실적이 있는 부두(+ 실제 배정 부두)만 berths에 넣는다.
"""
import json
import math
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAM_SRC = Path(os.environ.get("TEAM_SRC", Path.home() / "Downloads" / "berth_sim_share")).expanduser()
sys.path.insert(0, str(TEAM_SRC))

from berth_sim.after_etb.s2_work_finish import average_rate, find_past  # noqa: E402
from berth_sim.berth_availability import availability_from_plan  # noqa: E402
from berth_sim.shifting import direction  # noqa: E402
from berth_sim.dummy_data import load  # noqa: E402
from berth_sim.sample_loader import load_berth_plan  # noqa: E402

RULES = json.loads((ROOT / "rules" / "terminal.json").read_text(encoding="utf-8"))
OUR = {b["id"].lstrip("#").upper(): b["id"] for b in RULES["berths"]}   # 팀원 표기 '6' · 'BUOY2' → 우리 '#6' · 'BUOY2'
F = "%Y-%m-%dT%H:%M"


def main() -> None:
    xlsx = TEAM_SRC / "Sample data.xlsx"
    sequences, original_etb = load_berth_plan(xlsx)
    data = load(TEAM_SRC / "data" / "dummy")
    vessels = [v for seq in sequences.values() for v in seq]
    start = min(original_etb.values())                          # 팀원 접안 가능 표의 시작 = 첫 실제 ETB를 5분 칸으로 내림
    start = start.replace(minute=start.minute - start.minute % 5, second=0, microsecond=0)
    end = max(v.eta for v in vessels) + max(v.stay for v in vessels) + timedelta(days=1)
    end = end.replace(hour=0, minute=0) + timedelta(days=1)
    arrivals, current, notes = [], [], []
    for v in vessels:
        p = data.profiles[v.vessel_id]
        rates = {}
        for b in OUR:
            if find_past(data.history, p.vessel_code, p.material_code, b)[0]:
                rates[OUR[b]] = round(average_rate(data.history, p.vessel_code, p.material_code, b).rate, 6)
        home = OUR[v.berth]
        if home not in rates:                                    # 팀원 코드도 실제 배정 부두는 실적 없이 넘기지 않는다(계산 불가)
            notes.append(f"{v.vessel_id}: 실제 배정 부두 {home}에 과거 실적 없음")
            continue
        arrivals.append({
            "id": v.vessel_id, "vessel": f"{p.vessel_code} {p.ship_class}", "class": p.product_class, "biz": v.biz,
            "cargo_group": p.cargo_group, "qty": round(p.qty, 4), "eta": f"{v.eta:{F}}",
            **({"nor_tender": f"{p.nr_tender:{F}}"} if p.nr_tender else {}),
            "grt": p.grt, "dwt": p.dwt, "loa": p.loa, "pbl": p.pbl, "draft": p.draft,
            "contract": {"laycan_from": f"{p.laycan_from:{F}}", "laycan_to": f"{p.laycan_to:{F}}",
                         "laytime_h": p.laytime / timedelta(hours=1), "rate_usd_day": p.demurrage_rate, "cfr": p.cfr},
            "work": {"rate_per_h": rates[home], "by_berth": rates},
            "status": "PLANNED", "berths": sorted(rates, key=lambda b: [x["id"] for x in RULES["berths"]].index(b)),
        })
        current.append({"id": v.vessel_id, "berth": home, "etb": f"{original_etb[v.vessel_id]:{F}}"})
    restrictions = []
    for b, t in availability_from_plan(sequences, original_etb, list(OUR)).items():
        if t <= start:
            continue
        until = t - direction(b)                                   # 우리 부두 제약은 [시작, 종료 + Direction) 접안 금지 → 종료 = t − Direction
        since = start if until > start else until - timedelta(minutes=5)   # 계획 시작 전부터 걸어 [계획 시작, t)를 모두 막는다
        restrictions.append({"id": f"AVAIL-{b}", "reason": "WORK", "berths": [OUR[b]], "start": f"{since:{F}}", "end": f"{until:{F}}",
                             "note": f"팀원 berth_availability: #{b} 첫 실제 ETB {t:%m/%d %H:%M} 전 점유 정보 없음 → 그 전 접안 금지"})
    case = {
        "id": "TEAM-W46", "title": "팀원 가상 데이터 54척 (berth_sim data/dummy · 기상 예보·탱크 제외)",
        "request_id": "TEAM-W46",
        "plan": {"start": f"{start:{F}}", "end": f"{end:{F}}"},
        "arrivals": arrivals, "restrictions": restrictions, "current_plan": current,
        "_source": {"team_folder": "berth_sim_share", "seed": data.seed, "files": ["Sample data.xlsx", "data/dummy/current_shipments.csv",
                    "data/dummy/past_shipments.csv"], "not_included": ["weather.csv", "data/typhoon", "tanks"], "notes": notes},
    }
    text = json.dumps(case, ensure_ascii=False, indent=1) + "\n"
    for d in (ROOT / "data" / "samples", ROOT / "front" / "public" / "samples"):
        (d / "team-week-54.json").write_text(text, encoding="utf-8")
    n_b = [len(a["berths"]) for a in arrivals]
    print(f"입항 {len(arrivals)}건 · 계획 {case['plan']['start']} ~ {case['plan']['end']} · 배마다 부두 후보 {min(n_b)}~{max(n_b)}개 "
          f"(평균 {sum(n_b) / len(n_b):.1f}) → data/samples/team-week-54.json · front/public/samples/team-week-54.json")
    for n in notes:
        print("  !", n)
    print("  작업시간 차이(팀원 초 단위 vs 우리 분 올림) 최대",
          max(math.ceil(a["qty"] / a["work"]["rate_per_h"] * 60) - a["qty"] / a["work"]["rate_per_h"] * 60 for a in arrivals).__round__(3), "분")


if __name__ == "__main__":
    main()
