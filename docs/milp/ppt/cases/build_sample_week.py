"""샘플 엑셀 '접안계획 예시'(ETB 11/09~11/15, 68행) → 최적화 입력 cases/sample-week.json

    python3 docs/milp/ppt/cases/build_sample_week.py

엑셀에 있는 값 (그대로 씀)
    부두, ETA, ETB, ETU, 업무 구분(EX 수출 · IM 수입 · DI 내수 매입 · DO 내수 판매)
    → 같은 (부두, ETA, ETB, ETU, 업무) 행은 한 배가 화물 여러 개를 싣는 것으로 보고 한 입항 건으로 합친다 (68행 → 54건)
    → 작업시간 = (ETU − ETB) − 1h − 2h  (PPT 09쪽: 작업시작 = ETB + 1h, 이안 = 작업완료 + 2h 를 거꾸로 푼 값)
    → 엑셀의 부두·ETB는 '현행 계획'으로 따로 둔다 (최적화 입력이 아니라 비교 대상)

엑셀에 없는 값 (모두 [가정], 실데이터가 오면 바꿀 곳)
    선박 제원     그 배가 쓴 부두의 크기에 맞는 '선박 제원 Sample' DWT 구간 평균. 소형 부두는 부두 제원 안으로 맞춘다
    제품 그룹     그 부두가 받는 그룹 중에서 고른다. 동일 화물 그룹 부두 묶음에서는 현행 계획에서 겹치는 배끼리 다르게 고른다
    계약          일 체선료 = DWT 구간 평균 일 체선료 · Laytime 원유 72h(CFR False → PPT 10쪽 규칙으로 36h) · 제품 36h · 소형 24h
                  LayCan = ETA 전날 00:00 ~ ETA 다음 날 23:59 · NOR Tender 없음 (ETANR = ETA)
    원유 탱크     PPT 12쪽 '30기, 1,000만 배럴' → 저장용량 1,000만 · 최소 허용 300만 · 처음 550만 · 공정 처리 시간당 3.5만 배럴
    FIX           샘플에 표시가 없어 없음. 계획 시작(11/09 00:00)에 이미 접안해 있는 배 2척만 '작업 중'으로 고정
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
T = json.loads((ROOT / "rules" / "terminal.json").read_text(encoding="utf-8"))
PLAN = json.loads((ROOT / "rules" / "sample_plan.json").read_text(encoding="utf-8"))
BERTH = {b["id"]: b for b in T["berths"]}
BAND = {c["dwt_band"]: c for c in T["ship_classes"]}
START, END = datetime(2026, 11, 9), datetime(2026, 11, 19)
SETS = [set(s) for s in T["pair_rules"]["same_cargo_group"]["berth_sets"]]

PALETTE_OUT = ["DSL", "JET", "R-G", "FO", "KERO", "ASPH", "SULF", "SRFO", "YUBASE", "LPG", "XYL", "TOL", "PX", "SM", "BENZENE"]
PALETTE_IN = ["NAPH", "MEOH", "기유(양하)", "C-HX", "1.3 BD", "BENZENE", "UCO", "O-1", "BT-MIX", "BBR", "PROPYLENE", "BUTENE", "ETHYLENE", "LPG", "MDO", "SLO"]


def ts(s):
    return datetime.strptime(f"2026/{s.strip()}", "%Y/%m/%d %H:%M")


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M")


def calls():
    out = {}
    for r in PLAN["rows"]:
        k = (r["berth"], r["eta"], r["etb"], r["etu"], r["biz"])
        out.setdefault(k, []).append(r["row"])
    res = []
    for (b, eta, etb, etu, biz), rows in out.items():
        res.append({"berth": b, "eta": ts(eta), "etb": ts(etb), "etu": ts(etu), "biz": biz, "rows": rows})
    res.sort(key=lambda c: (c["etb"], c["berth"]))
    return res


def ship_for(c):
    """그 배가 쓴 부두에 맞는 선박 제원 [가정]. (템플릿 이름, 선종, DWT 구간, 제원, 물량, Laytime, CFR)"""
    b, biz = BERTH[c["berth"]], c["biz"]
    stay = (c["etu"] - c["etb"]).total_seconds() / 3600
    if b["id"].startswith("BUOY"):
        band = BAND["29만~30만"]                               # 흘수는 그 배가 실제로 댄 부이의 최대 흘수 안으로 (BUOY2 21.21 < 평균 21.54)
        return "VLCC 원유선", "CR", band, 295000, {"draft": min(band["draft"], round(b["max_draft"] - 0.2, 2))}, 2_000_000, 72, False, "CRUDE"
    if b["id"] == "#8" and biz == "IM" and stay >= 24:
        band = BAND["10만~11만"]
        return "Aframax 원유선", "CR", band, 105000, {}, 700_000, 72, False, "CRUDE"
    if b["id"] in ("#7", "#8") and biz in ("EX", "DO"):
        band = BAND["7만~8만"]
        return "LR1 석유제품선", "PP", band, 75000, {}, 450_000, 36, False, None
    if b["id"] in ("#6", "#7", "#8"):
        band = BAND["4만~5만"]
        return "MR 석유제품선", "PP", band, 45000, {}, 300_000, 36, False, None
    if b["id"] == "#3":
        band = BAND["3만~4만"]
        return "중형 화학·윤활유선", "PC", band, 35000, {}, 200_000, 36, False, None
    # 소형: 부두 제원 안으로 맞춘다
    band = BAND["0~1만"] if b["max_dwt"] < 10000 else BAND["1만~2만"]
    dwt = int(round(b["max_dwt"] * 0.8, -2))
    loa = min(b["max_loa"] - 5, max(b["min_loa"] + 5, band["loa"])) if b.get("max_loa") else band["loa"]
    pbl = max(band["pbl"], (b.get("min_pbl") or 0) + 2)
    draft = round(min(band["draft"], b["max_draft"] - 0.3), 2)
    grt = int(round(dwt * 0.75, -1))
    return "소형 제품선", None, band, dwt, {"loa": round(loa, 1), "pbl": round(pbl, 1), "draft": draft, "grt": grt}, int(dwt * 6.3 * 0.8), 24, False, None


def overlap(x, y):
    return x["etb"] < y["etu"] and y["etb"] < x["etu"]


def main():
    cs = calls()
    chosen = {}
    for n, c in enumerate(cs):
        name, vclass, band, dwt, over, qty, lay, cfr, fixed_group = ship_for(c)
        b = BERTH[c["berth"]]
        if fixed_group:
            group = fixed_group
        else:
            palette = PALETTE_OUT if c["biz"] in ("EX", "DO") else PALETTE_IN
            pool = [g for g in palette if g in b["groups"]] + [g for g in b["groups"] if g not in palette]
            if vclass is None or name.startswith("소형"):
                pool = [g for g in pool if b["groups"][g] != "CR"]
            taken = set()
            for m, other in chosen.items():
                ob = cs[m]["berth"]
                same_set = any(c["berth"] in s and ob in s for s in SETS)
                if (same_set or ob == c["berth"]) and overlap(c, cs[m]):
                    taken.add(other["group"])
            group = next((g for g in pool if g not in taken), pool[0])
        cls = vclass or b["groups"][group]
        chosen[n] = {"group": group, "class": cls, "name": name, "band": band, "dwt": dwt, "over": over, "qty": qty, "lay": lay, "cfr": cfr}

    arrivals, current = [], []
    for n, c in enumerate(cs):
        ch = chosen[n]
        band = ch["band"]
        aid = f"S{c['rows'][0]:02d}"
        stay = (c["etu"] - c["etb"]).total_seconds() / 3600
        work_h = stay - 3.0
        lay_from = datetime(c["eta"].year, c["eta"].month, c["eta"].day) - timedelta(days=1)
        lay_to = datetime(c["eta"].year, c["eta"].month, c["eta"].day) + timedelta(days=1, hours=23, minutes=59)
        v = {
            "id": aid, "vessel": f"{ch['name']} ({band['dwt_band']})", "class": ch["class"], "biz": c["biz"], "cargo_group": ch["group"],
            "qty": ch["qty"], "eta": iso(c["eta"]),
            "grt": ch["over"].get("grt", band["grt"]), "dwt": ch["dwt"], "loa": ch["over"].get("loa", band["loa"]),
            "pbl": ch["over"].get("pbl", band["pbl"]), "draft": ch["over"].get("draft", band["draft"]),
            "contract": {"laycan_from": iso(lay_from), "laycan_to": iso(lay_to), "laytime_h": ch["lay"], "rate_usd_day": band["rate_usd_day"], "cfr": ch["cfr"]},
            "work": {"hours": round(work_h, 4)},
            "source_rows": c["rows"],
        }
        if c["etb"] < START:                                    # 계획 시작에 이미 접안해 있음 → 작업 중 (FR-18)
            v["status"] = "WORKING"
            v["fix"] = {"berth": c["berth"], "etb": iso(c["etb"]), "etu": iso(c["etu"])}
        arrivals.append(v)
        current.append({"id": aid, "berth": c["berth"], "etb": iso(c["etb"]), "etu": iso(c["etu"])})

    doc = {
        "id": "SAMPLE-W46",
        "title": "샘플 접안계획 예시 (ETB 11/09~11/15) — 54건",
        "plan": {"start": iso(START), "end": iso(END)},
        "arrivals": arrivals,
        "restrictions": [],
        "inventory": [{"group": "CRUDE", "opening": 5_500_000, "min": 3_000_000, "max": 10_000_000,
                       "flows": [{"from": iso(START), "to": iso(END), "use_per_h": 35_000}]}],
        "current_plan": current,
        "options": {"max_wait_h": 120, "grid_min": 30},
        "assumptions": __doc__.split("엑셀에 없는 값 (모두 [가정], 실데이터가 오면 바꿀 곳)")[1].strip().splitlines(),
    }
    out = HERE / "sample-week.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    groups = {}
    for v in arrivals:
        groups[v["cargo_group"]] = groups.get(v["cargo_group"], 0) + 1
    print(f"{out.name}: 입항 건 {len(arrivals)} (작업 중 {sum(1 for v in arrivals if v.get('status') == 'WORKING')}) · 제품 그룹 {groups}")


if __name__ == "__main__":
    main()
