"""실시간 공공 API만으로 만드는 예시 시나리오 (가상 시나리오 S01~S16과 별개).

SK 시설(SK부이·SK2/4/5부두)로 신고된 입항 건을 실제로 받아 시나리오 JSON을 만들고, 같은 계산 파이프라인(`demurrage run`)을 돌린다.
값마다 '실제(공공 API)'인지 '가정(공개 자료에 없음)'인지 provenance로 남긴다.

    PUBLIC_DATA_SERVICE_KEY=... PYTHONPATH=src python scripts/live_scenario.py [--out out/live]

실제로 받는 것
  · 선명·호출부호·ETA·예정 시설·총톤수·선종·화물량·전출항지  ← 해양수산부 선박입출항신고
  · 이미 부이에 대었는지·접안 시각                             ← 울산항만공사 항만 내 선박 운항정보
  · 현재 흘수(배가 항내에 있을 때)                             ← 울산항만공사 항내 선박위치정보
가정하는 것(공개 API에 없음): DWT·LOA·흘수(항외 선박)·자재코드·계약 조건(Laytime·체선료 단가)·조석 시간창
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from demurrage.agents.orchestrator import run_pipeline
from demurrage.data import ais, entry
from demurrage.llm.adapter import get_llm

KST = entry.KST
FMT = "%Y-%m-%d %H:%M"

# ── 가정값 (공개 API에 없는 칸). 바꾸면 결과가 바뀐다 ──────────────────────────────────────────
DWT_PER_GT = {"CRUDE": 1.87, "PRODUCT": 1.7, "CHEMICAL": 1.6}  # 원유 160,000 GT ↔ 300,000 DWT 수준(VLCC)
DENSITY = {"CRUDE": 0.86, "PRODUCT": 0.84, "CHEMICAL": 0.9}      # t → kl 환산
DEFAULT_DRAFT = {"CRUDE": 20.5, "PRODUCT": 11.0, "CHEMICAL": 8.0}  # 항외 선박은 만재 흘수를 가정
MATERIAL = {"CRUDE": "CR-ARL", "PRODUCT": "PG-RG92", "CHEMICAL": "CH-PX"}  # 제품명은 신고에 없다. 소형 제품선은 휘발유로 가정
CONTRACT = {  # 데모의 가상 계약서(CT-2611-01 · 04 · 21) 값을 빌린다. 실제 계약이 아니다.
    "CRUDE": {"type": "CFR", "laytime_h": 36, "demurrage_rate_usd_day": 52000},
    "PRODUCT": {"type": "FOB", "laytime_h": 26, "demurrage_rate_usd_day": 28000},
    "CHEMICAL": {"type": "FOB", "laytime_h": 24, "demurrage_rate_usd_day": 20000},
}
TIDE_BASE = datetime(2026, 11, 14, 3, 10, tzinfo=KST)  # 가상 만조(데모 S01과 같은 12시간 25분 주기), ±2시간 창
TIDE_PERIOD = timedelta(minutes=745)
PUMP_T_PER_H = {"CRUDE": 9000, "PRODUCT": 800, "CHEMICAL": 400}  # 하역 능력(t/h). 과거 실적 매칭이 안 되는 선박의 작업시간 가정
DEFAULT_QTY_TON = {"CRUDE": 250000, "PRODUCT": 2500, "CHEMICAL": 2000}


def vtype(kind: str) -> str | None:
    if not kind:
        return None
    if "원유" in kind:
        return "CRUDE"
    if "케미칼" in kind or "화학" in kind:
        return "CHEMICAL"
    if "석유" in kind or "유조선" in kind:
        return "PRODUCT"
    return None


def tide_windows(start: datetime, end: datetime) -> list:
    out, n = [], int((start - TIDE_BASE) / TIDE_PERIOD) - 1
    while True:
        c = TIDE_BASE + n * TIDE_PERIOD
        if c - timedelta(hours=2) > end:
            return out
        out.append([(c - timedelta(hours=2)).strftime(FMT), (c + timedelta(hours=2)).strftime(FMT)])
        n += 1


def build(now: datetime, ahead_days: int = 12) -> dict:
    arr = entry.arrivals(hours_back=24 * 3, hours_ahead=24 * ahead_days, now=now)["arrivals"]
    sk = [a for a in arr if a["facility"] and a["facility"].startswith("SK") and vtype(a["type"])]
    live = {v["callSign"]: v for v in ais.vessels(max_age_min=24 * 60)["vessels"] if v["callSign"]}
    vessels, prov, skipped = [], {}, []
    for a in sorted(sk, key=lambda x: x["eta"]):
        vt = vtype(a["type"])
        eta = datetime.fromisoformat(a["eta"])
        ev = []
        try:
            ev = ais.voyage_events(a["callSign"], a["year"], a["count"])["events"] if a["year"] else []
        except ais.AisError:
            pass
        names = [e["event"] for e in ev]
        left = "출항" in names or "이안" in names
        if left or (eta < now - timedelta(hours=24) and "접안" not in names and "입항" not in names):
            skipped.append((a["name"], "이미 출항했거나 기록이 지난 건"))
            continue
        unload, load = a["unloadTon"] or 0, a["loadTon"] or 0
        qty_t = unload or load or DEFAULT_QTY_TON[vt]
        assumed = ["dwt", "loa", "pbl", "material_code", "contract", "work.hours"]
        pos = live.get(a["callSign"])
        draft = pos["draft"] if pos and pos["draft"] else DEFAULT_DRAFT[vt]
        if not (pos and pos["draft"]):
            assumed.append("draft")
        if not (unload or load):
            assumed.append("qty")
        dwt = round(a["grt"] * DWT_PER_GT[vt])
        loa = 330 if dwt > 200000 else 183 if dwt > 40000 else 100 if dwt > 8000 else 80
        v = {
            "id": a["callSign"], "name": a["name"], "vessel_type": vt, "grt": int(a["grt"]), "dwt": dwt,
            "loa": loa, "pbl": round(loa * 0.5),  # 병행부 길이는 LOA의 절반으로 가정
            "draft": draft, "direction": "IMPORT" if unload else "EXPORT", "material_code": MATERIAL[vt],
            "qty": round(qty_t / DENSITY[vt]), "eta": eta.strftime(FMT), "status": "PLANNED",
            "contract": {**CONTRACT[vt], "laycan_from": (eta - timedelta(days=1)).strftime("%Y-%m-%d"), "laycan_to": (eta + timedelta(days=1)).strftime("%Y-%m-%d")},
            "work": {"hours": round(qty_t / PUMP_T_PER_H[vt] + 1, 1), "hose_term_h": 1},
            "remarks": f"입항 신고 {a['filing']}({a['facility']}) · 전출항지 {a['prevPort'] or '-'}",
        }
        # 이미 부이·부두에 댄 배: 운항정보의 실제 접안(입항) 시각으로 WORKING 처리
        docked = [e for e in ev if e["event"] in ("접안", "입항") and e["facility"] and e["facility"].startswith("SK")]
        if docked and eta <= now:
            at = datetime.fromisoformat(docked[-1]["eventAt"])
            berth = "Buoy" if "부이" in docked[-1]["facility"] else None
            if berth:
                v["status"] = "WORKING"
                v["working"] = {"berth": berth, "etb": at.strftime(FMT), "work_start": (at + timedelta(hours=1)).strftime(FMT)}
                v["eta"] = min(eta, at).strftime(FMT)
                v["remarks"] += f" · 실제 접안 {at.strftime(FMT)}(운항정보)"
        elif eta <= now:
            skipped.append((a["name"], "입항 시각이 지났지만 접안 기록이 없어 제외"))
            continue
        vessels.append(v)
        prov[v["id"]] = {
            "실제(공공 API)": ["name", "eta", "grt", "vessel_type", "qty(톤→kl 환산은 가정)", "예정 시설 " + a["facility"]] + (["draft"] if "draft" not in assumed else []) + (["실제 접안 시각"] if v["status"] == "WORKING" else []),
            "가정": assumed,
        }
    if not vessels:
        raise SystemExit("SK 시설로 신고된 입항 건이 없습니다 (조회 창 안)")
    start = now.replace(minute=0, second=0, microsecond=0)
    end = max(datetime.strptime(v["eta"], FMT).replace(tzinfo=KST) for v in vessels) + timedelta(days=4)
    return {
        "id": "LIVE-" + now.strftime("%Y%m%d-%H%M"),
        "title": f"실시간 예시 — SK 시설 입항 신고 {len(vessels)}척 ({now.strftime('%m/%d %H:%M')} 기준)",
        "description": "공공 API(입항 신고·운항정보·선박위치)로 만든 예시. DWT·계약·조석은 공개 자료에 없어 가정했다.",
        "data_label": "실시간 공공 API + 가정",
        "horizon": {"start": start.strftime(FMT), "end": end.strftime(FMT)},
        "berths": ["#2-7", "#4-1", "#4-2", "#6", "#7", "#8", "Buoy"],
        "vessels": vessels,
        "restrictions": [],
        "tide_windows": {"Buoy": tide_windows(start, end)},
        "inventory": [],
        "provenance": prov,
        "skipped": [{"name": n, "reason": r} for n, r in skipped],
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="out/live")
    p.add_argument("--now", help="기준 시각(테스트용, 예: '2026-11-12 18:00')")
    a = p.parse_args(argv)
    now = datetime.strptime(a.now, FMT).replace(tzinfo=KST) if a.now else datetime.now(KST)
    doc = build(now)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "live-scenario.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"■ {doc['title']}\n  저장: {out / 'live-scenario.json'}")
    for v in doc["vessels"]:
        pv = doc["provenance"][v["id"]]
        print(f"  - {v['name']:<16} {v['vessel_type']:<8} ETA {v['eta']} {v['status']:<8} GT {v['grt']:>7,} → DWT {v['dwt']:>7,}(가정) · 가정 {', '.join(pv['가정'])}")
    for s in doc["skipped"]:
        print(f"  · 제외 {s['name']}: {s['reason']}")
    run = run_pipeline({k: v for k, v in doc.items() if k not in ("provenance", "skipped")}, llm=get_llm(), time_limit_s=20, k=3)
    if run["status"] == "INPUT_ERROR":
        for i in run["input_issues"]:
            print(f"  [{i['level']}] {i['vessel']} {i['field']}: {i['message']}")
        sys.exit(2)
    print(f"\n  기준안(FCFS) {run['baseline']['total_display']}")
    for c in run["candidates"]:
        print(f"  {c['label']} {c['total_display']}  절감 {c['savings_display']} ({c['savings_pct']}%)  위반 {len(c['violations'])}")
    (out / "live-run.json").write_text(json.dumps(run, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
    best = run["candidates"][0] if run["candidates"] else None
    if best:
        print("\n  1안 일정:")
        for r in best.get("schedule", best.get("placements", [])):
            print("   ", json.dumps(r, ensure_ascii=False, default=str)[:210])


if __name__ == "__main__":
    main()
