"""샘플 엑셀(Sample data.xlsx) + 멘토링 PPT의 표 → rules/terminal.json, rules/sample_plan.json

표준 라이브러리만 쓴다(xlsx는 zip + XML로 직접 읽는다).

    python3 -I docs/milp/ppt/build_master.py "<Sample data.xlsx 경로>"

- 부두 24곳의 제원과 접안 가능 제품 그룹, DWT 구간별 선박 제원, 접안계획 예시는 엑셀 값 그대로다.
- Shifting 소요시간, 동일 화물 그룹·부두 동시 접안 제약, 야간 도선 기준, 작업 시각 상수, 정박개시 규칙은 PPT 07~11쪽 값이다.
- PPT 표에 없는 값은 "assumed"에 따로 적는다(#5-1~#5-4의 Shifting 시간).
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def read_xlsx(path):
    """{시트 이름: {행 번호: {열 글자: 값}}}"""
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = {}
    for s in wb.find("m:sheets", NS):
        target = rels[s.get("{%s}id" % NS["r"])]
        target = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
        rows = {}
        for row in ET.fromstring(z.read(target)).iter("{%s}row" % NS["m"]):
            cells = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS)
                if v is None:
                    continue
                col = re.match(r"[A-Z]+", c.get("r")).group(0)
                cells[col] = ss[int(v.text)] if c.get("t") == "s" else v.text
            if cells:
                rows[int(row.get("r"))] = cells
        out[s.get("name")] = rows
    return out


def num(x):
    if x is None or str(x).strip() in ("", "-"):
        return None
    f = float(x)
    return int(f) if f == int(f) else f


# ---- PPT 07쪽 'Shifting 소요시간(hr)' 표 -------------------------------------------------
SHIFTING = {  # 묶음 이름: (Switching, Direction)
    "#1~2": (1.5, 1.0), "#3": (1.5, 1.0), "#4": (1.0, 1.0), "#5-5": (1.0, 1.0), "GAS1/2": (1.0, 1.0),
    "#6": (2.5, 1.5), "#7": (2.5, 1.5), "#8": (2.5, 1.5), "Buoy": (1.0, 1.5),
}
ASSUMED_SHIFT = {"#5-1": "#5-5", "#5-2": "#5-5", "#5-3": "#5-5", "#5-4": "#5-5"}   # PPT 표에 #5-5만 있다


def shift_group(bid):
    if bid in ("#1-1", "#1-2") or bid.startswith("#2-"):
        return "#1~2"
    if bid == "#3":
        return "#3"
    if bid.startswith("#4-"):
        return "#4"
    if bid.startswith("#5-"):
        return "#5-5"
    if bid.startswith("GAS"):
        return "GAS1/2"
    if bid in ("#6", "#7", "#8"):
        return bid
    if bid.startswith("BUOY"):
        return "Buoy"
    raise ValueError(bid)


def berth_id(name):
    name = str(name).strip()
    return name if name.startswith(("BUOY", "GAS")) else "#" + name


def plan_berth_id(name):
    """접안계획 예시의 부두 표기 → 제원 표의 부두 ID"""
    name = name.strip()
    return {"#2 Buoy": "BUOY2", "#3 Buoy": "BUOY3", "#1 Gas": "GAS1", "#2 Gas": "GAS2"}.get(name, name)


def main(xlsx):
    wb = read_xlsx(xlsx)
    s_groups, s_specs, s_ships, s_plan = (wb[n] for n in ("부두 별 접안 가능 제품 그룹", "부두별 제원", "선박 제원 Sample", "접안계획 예시"))

    # 1) 부두별 접안 가능 제품 그룹 (부두명은 병합 셀이라 아래로 이어진다)
    groups, cur = {}, None
    for r in sorted(s_groups):
        if r == 1:
            continue
        row = s_groups[r]
        if "A" in row:
            cur = berth_id(row["A"])
        if cur and "B" in row:
            groups.setdefault(cur, {})[row["B"].strip()] = row.get("C", "").strip()
    classes = {s_groups[r]["G"]: s_groups[r]["H"] for r in sorted(s_groups) if r >= 2 and "G" in s_groups[r] and "H" in s_groups[r]}

    # 2) 부두별 제원
    berths = []
    for r in sorted(s_specs):
        if r == 1:
            continue
        row = s_specs[r]
        bid = berth_id(row["A"])
        sg = shift_group(bid)
        sw, di = SHIFTING[sg]
        berths.append({
            "id": bid, "size": row.get("G"), "shift_group": sg, "switching_h": sw, "direction_h": di,
            "shift_assumed": bid in ASSUMED_SHIFT,
            "max_dwt": num(row.get("B")), "max_draft": num(row.get("C")), "max_loa": num(row.get("D")),
            "min_loa": num(row.get("E")), "min_pbl": num(row.get("F")),
            "groups": groups.get(bid, {}),
        })

    # 3) 선박 제원 Sample (DWT 구간 평균)
    ship_classes = []
    for r in sorted(s_ships):
        if r == 1:
            continue
        row = s_ships[r]
        ship_classes.append({"dwt_band": row["A"].replace(" ", ""), "ships": num(row["B"]), "grt": num(row["C"]), "draft": num(row["D"]),
                             "loa": num(row["E"]), "pbl": num(row["F"]), "rate_usd_day": num(row["G"]), "work_speed": num(row["H"])})

    # 4) 접안계획 예시
    plan = []
    for r in sorted(s_plan):
        row = s_plan[r]
        if r <= 2 or "A" not in row:
            continue
        plan.append({"row": r, "berth": plan_berth_id(row["A"]), "eta": row["B"].strip(), "etb": row["C"].strip(), "etu": row["D"].strip(), "biz": row["E"].strip()})
    biz = {s_plan[r]["H"]: s_plan[r]["I"] for r in sorted(s_plan) if "H" in s_plan[r] and "I" in s_plan[r]}

    terminal = {
        "version": "ulsan-clx/ppt-v1",
        "source": {
            "berths": "Sample data.xlsx — '부두별 제원', '부두 별 접안 가능 제품 그룹' (값 그대로)",
            "ship_classes": "Sample data.xlsx — '선박 제원 Sample' (DWT 구간 평균, 참고용이라고 적혀 있음. F열 머리글은 'epeo'로 적혀 있어 PBL로 읽었다)",
            "rules": "SKALA 현업 멘토링 PPT 07~12쪽",
        },
        "product_classes": classes,
        "biz": biz,
        "berths": berths,
        "ship_classes": ship_classes,
        "shifting": {"_ppt": "07쪽", "table": {k: {"switching_h": v[0], "direction_h": v[1]} for k, v in SHIFTING.items()},
                     "assumed": {k: f"{v} 값을 씀 (PPT 표에 없음)" for k, v in ASSUMED_SHIFT.items()}},
        "eligibility": {"_ppt": "12쪽 2. 부두 정보", "draft_check_biz": ["IM"]},
        "night_pilotage": {
            "_ppt": "08쪽 ②",
            "last_pob": {
                "subject_any": [{"grt_min": 75000}, {"grt_max": 30000, "biz": ["IM"], "draft_min": 10.5}],
                "sunset_minus_h": [{"grt_max": 50000, "h": 1.5}, {"grt_min_exclusive": 50000, "h": 2.0}],
                "compare": "ETA",
                "release": "08:00",
            },
            "dawn": {"grt_min": 30000, "from": "02:00", "to": "08:00", "release": "08:00"},
        },
        "pair_rules": {
            "_ppt": "07쪽 ① · 08쪽 ③",
            "same_berth": {"gap": "switching", "fix_strict": True},
            "same_cargo_group": {"berth_sets": [["#6", "#7", "#8"], ["#1-1", "#1-2", "#2-7"]], "release_before_etu_h": 2},
            "simultaneous": [{"berths": ["#4-1", "#4-2"], "release_before_etu_h": 2, "exempt_if_all_grt_le": 3000}],
        },
        "restriction": {"_ppt": "08쪽 ③ · 12쪽 4", "release": "end + direction", "scope": "BERTHING"},
        "work": {"_ppt": "09쪽", "setup_h": 1.0, "hose_h": 0.5, "departure_h": 2.0},
        "laytime": {
            "_ppt": "09·10쪽",
            "daylight_classes": ["CR", "PP"],
            "notice_h": 6, "before_laycan_hour": 6, "before_laycan_hour_daylight": 7, "daylight_hour": 7,
            "factor": [{"class": "CR", "cfr": False, "factor": "1/2"}],
        },
        "demurrage": {"_ppt": "11쪽", "weather_ratio": "1/2", "weather_basis": "USED"},
        "location": {"name": "울산", "lat": 35.5384, "lon": 129.3114, "tz_hours": 9},
    }
    (HERE / "rules").mkdir(exist_ok=True)
    (HERE / "rules" / "terminal.json").write_text(json.dumps(terminal, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "rules" / "sample_plan.json").write_text(json.dumps({
        "source": "Sample data.xlsx — '접안계획 예시' (ETB 11.09 ~ 11.15 조회 결과, 값 그대로)", "year": 2026, "biz": biz, "rows": plan}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"부두 {len(berths)}곳 · 제품 그룹 {len({g for b in berths for g in b['groups']})}개 · 선박 제원 구간 {len(ship_classes)}개 · 접안계획 예시 {len(plan)}행")


if __name__ == "__main__":
    main(sys.argv[1])
