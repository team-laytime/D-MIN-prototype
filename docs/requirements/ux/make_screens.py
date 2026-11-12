#!/usr/bin/env python3
"""화면 그림 7장 (페인 포인트 기반 UI/UX 특징, 15-hidden-requirements.md의 U 항목).

실행: python3 docs/requirements/ux/make_screens.py [조각을 따로 받을 폴더]
- 금액과 시각은 데모 S05 실행(demo/out/3068fa86f727/run.json)에서 읽는다. 가상 데이터다.
- 그림 2의 부두 24곳 배치는 자리 표시용으로 만든 값이다 (멘토 샘플 값은 쓰지 않는다).
- screen-N-*.html을 만들고 Chrome 헤드리스로 같은 이름의 PNG를 뜬다.
"""
import json
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = json.loads((ROOT / "demo/out/3068fa86f727/run.json").read_text(encoding="utf-8"))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = (
    ".dp{font:12px/1.45 Pretendard,'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#0E1726;background:#F3F5F8;"
    "border:1px solid #D5DBE5;border-radius:12px;overflow:hidden;max-width:680px;text-align:left}"
    ".dp *{box-sizing:border-box}"
    ".dp .tb{background:#0B1F33;color:#fff;padding:7px 12px;display:flex;align-items:center;gap:8px}"
    ".dp .tb b{font-weight:600;font-size:13px}.dp .tb .s{color:#B7C4D6;font-size:11px}"
    ".dp .bd{padding:10px 12px;display:flex;flex-direction:column;gap:8px}"
    ".dp .r{display:flex;gap:8px;align-items:stretch}"
    ".dp .c{background:#fff;border:1px solid #E2E7EE;border-radius:10px;padding:8px 10px;flex:1;min-width:0}"
    ".dp .h{font-size:11px;color:#667085;margin-bottom:3px;display:flex;gap:5px;align-items:center}"
    ".dp .n{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.2px;line-height:1.25}"
    ".dp .m{color:#667085}.dp .x{font-size:11px}.dp .f{font-variant-numeric:tabular-nums}"
    ".dp .rd{color:#C13A32}.dp .gn{color:#127A45}.dp .sb{font-weight:600}"
    ".dp .p{display:inline-block;padding:0 6px;border-radius:999px;font-size:11px;line-height:17px;border:1px solid #D5DBE5;"
    "background:#fff;color:#344054;white-space:nowrap}"
    ".dp .pb{background:#E8F0FE;border-color:#B9D0FB;color:#174EA6}.dp .pg{background:#E6F4EC;border-color:#B4DCC5;color:#0E6B3B}"
    ".dp .pa{background:#FFF3DC;border-color:#F3D69A;color:#8A5300}.dp .pr{background:#FDECEA;border-color:#F3BDB8;color:#A12A23}"
    ".dp .pv{background:#EEEBFB;border-color:#CFC8F3;color:#43359E}.dp .pt{background:#E2F5F2;border-color:#A9DDD5;color:#08695D}"
    ".dp .pk{background:#0B1F33;border-color:#0B1F33;color:#fff}"
    ".dp .k{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;"
    "background:#E4572E;color:#fff;font-size:11px;font-weight:700;flex:none;line-height:1}"
    ".dp .lg{background:#fff;border-top:1px solid #E2E7EE;padding:9px 12px;display:grid;grid-template-columns:1fr 1fr;"
    "gap:4px 14px;font-size:11.5px;color:#344054}.dp .lg div{display:flex;gap:6px;align-items:flex-start}"
    ".dp .bt{display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:600;background:#1B5FD9;"
    "color:#fff;white-space:nowrap}.dp .bo{background:#fff;color:#344054;border:1px solid #D5DBE5}"
    ".dp .ln{display:flex;gap:6px;align-items:baseline;padding:2px 0}.dp .ln+.ln{border-top:1px solid #F0F2F6}"
    ".dp .sp{flex:1}"
    ".dp .g{position:relative}.dp .gr{position:relative;display:flex;align-items:center;height:26px;border-top:1px solid #EEF1F5}"
    ".dp .gl{width:42px;flex:none;font-size:11px;color:#344054;font-weight:600}.dp .gt{position:relative;flex:1;height:100%}"
    ".dp .ov{position:absolute;left:42px;right:0;top:0;bottom:0}.dp .ov i{position:absolute;top:0;bottom:0}"
    ".dp .nt{background:rgba(14,23,38,.07)}"
    ".dp .wx{background:repeating-linear-gradient(135deg,rgba(178,106,0,.22) 0 3px,rgba(178,106,0,.06) 3px 7px)}"
    ".dp .dl{border-left:1px solid #D5DBE5}.dp .nw{border-left:1.5px solid #1B5FD9}"
    ".dp .b{position:absolute;top:4px;height:16px;border-radius:3px;color:#fff;font-size:11px;line-height:16px;padding:0 3px;"
    "overflow:hidden;white-space:nowrap}"
    ".dp .b u{text-decoration:none;display:inline-block;background:rgba(0,0,0,.35);border-radius:2px;padding:0 2px;margin-right:3px;"
    "line-height:13px}"
    ".dp .w{position:absolute;top:11px;height:0;border-top:1.5px dashed #98A2B3}"
    ".dp .d{position:absolute;top:21px;height:3px;background:#C13A32;border-radius:2px}"
    ".dp .e{position:absolute;top:2px;height:22px;width:0;border-left:2px solid #C13A32}"
    ".dp .o{position:absolute;top:2px;height:20px;border:1.5px dashed #667085;border-radius:3px;font-size:11px;line-height:17px;"
    "color:#344054;white-space:nowrap;overflow:hidden}"
    ".dp .hx{background-image:repeating-linear-gradient(135deg,rgba(255,255,255,.35) 0 2px,transparent 2px 5px)}"
    ".dp .tab{flex:1;min-width:0;border:1px solid #E2E7EE;border-radius:8px;padding:5px 8px;background:#fff}"
    ".dp .on{border:1.5px solid #1B5FD9;background:#F2F7FF}"
    ".dp .st{display:flex;gap:4px;align-items:center;font-size:11px}.dp .st span{padding:2px 7px;border-radius:999px;background:#fff;"
    "border:1px solid #E2E7EE;color:#344054;white-space:nowrap}"
    ".dp .dim{opacity:.45}.dp .tx{background:#fff;border:1px solid #D5DBE5;border-radius:6px;padding:5px 8px;color:#344054}"
    ".dp .mk{background:#FFF1B8}.dp .ck{display:inline-block;width:13px;height:13px;border:1.5px solid #98A2B3;border-radius:3px;"
    "flex:none;position:relative;top:2px}.dp .cy{background:#1B5FD9;border-color:#1B5FD9}"
    ".dp .mono{font-size:11px;color:#344054;font-variant-numeric:tabular-nums}"
)

CARGO = {"CRUDE": "#5D4A3B", "DIESEL": "#2F6FE0", "GASOLINE": "#D7891C", "KEROSENE": "#7357E6", "NAPHTHA": "#119B8B",
         "BUNKER": "#5F6B7D"}
RULE = {"기상": "기", "선행 선박 대기": "선", "야간 도선": "야", "조석": "조", "동시 접안 제한": "동"}
T0 = datetime(2026, 11, 10, 0, 0)
SPAN = 84 * 60  # 11/10 00:00 ~ 11/13 12:00


def dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def pos(s):
    return (dt(s) - T0).total_seconds() / 60 / SPAN * 100


def box(a, b):
    left = max(0.0, pos(a))
    right = min(100.0, pos(b))
    return f"left:{left:.2f}%;width:{max(right - left, 0.3):.2f}%"


def k(n):
    return f'<span class="k">{n}</span>'


def usd(x):
    return "${:,.0f}".format(x)


PLANS = {p["label"]: p for p in [RUN["baseline"]] + RUN["candidates"]}


def vessel(plan, vid):
    return next(v for v in PLANS[plan]["vessels"] if v["vessel_id"] == vid)


def check_numbers():
    """그림에 적은 숫자가 실행 결과와 같은지 본다."""
    t = {name: round(p["total_usd"]) for name, p in PLANS.items()}
    assert t == {"기준안": 112919, "1안": 87489, "2안": 91235, "3안": 92300}, t
    assert round(PLANS["1안"]["savings_usd"]) == 25431 and PLANS["1안"]["savings_pct"] == 22.5
    assert PLANS["1안"]["changed_vessels"] == ["V05", "V09", "V06", "V04", "V03"]
    v6 = vessel("1안", "V06")
    assert (v6["etb"], v6["laytime_end"], v6["hose_off"]) == ("2026-11-12 20:51", "2026-11-12 16:00", "2026-11-13 10:17")
    assert v6["demurrage_raw_minutes"] == 1097 and v6["amount_cents"] == 1218889 and v6["rate_usd_day"] == 16000
    assert [(r["category"], r["minutes"]) for r in v6["reasons"]] == [("접안 후 작업", 806), ("선행 선박 대기", 291)]
    assert round(vessel("기준안", "V05")["amount_usd"]) == 24650 and round(vessel("기준안", "V09")["amount_usd"]) == 12969
    b5 = vessel("기준안", "V05")
    assert (b5["demurrage_raw_minutes"], b5["weather_minutes"], b5["demurrage_minutes"]) == (1271, 570, 986.0)
    amounts = {v["vessel_id"]: round(v["amount_usd"]) for v in PLANS["1안"]["vessels"]}
    assert amounts["V02"] == 42856 and amounts["V07"] == 11250 and amounts["V01"] == 11194 and amounts["V08"] == 10000
    rows = {r["label"]: r for r in RUN["sensitivity"]["rows"]}
    eta = [round(r["totals_usd"]["1안"]) for r in RUN["sensitivity"]["rows"] if r["kind"] == "ETA"]
    assert (min(eta), max(eta)) == (70072, 96989), (min(eta), max(eta))
    s = rows["V09 ETA +6시간"]
    assert {n: round(x) for n, x in s["totals_usd"].items()} == {"기준안": 107169, "1안": 87489, "2안": 85485, "3안": 92300}
    assert s["ranks"]["2안"] == 1 and s["ranks"]["1안"] == 2
    assert [f["input"] for f in RUN["sensitivity"]["flagged"]["1안"]] == ["V09 ETA +6시간", "강풍 구간 6시간 늦게", "강풍 예보 해제"]
    assert RUN["eligibility"]["V06"]["eligible"] == ["#6", "#7", "#8"]


def overlay(now=None):
    out = []
    for a, b in RUN["scenario"]["nights"]:
        if pos(b) > 0 and pos(a) < 100:
            out.append(f'<i class="nt" style="{box(a, b)}"></i>')
    out.append(f'<i class="wx" style="{box("2026-11-11 09:00", "2026-11-12 03:00")}"></i>')
    for d in (11, 12, 13):
        out.append(f'<i class="dl" style="left:{pos("2026-11-%d 00:00" % d):.2f}%"></i>')
    return '<div class="ov">' + "".join(out) + "</div>"


def axis():
    labels = "".join(
        f'<span style="position:absolute;left:{pos("2026-11-%d 00:00" % d):.2f}%;padding-left:3px" class="x m">11/{d}</span>'
        for d in (10, 11, 12, 13))
    return f'<div class="gr" style="height:16px;border-top:0"><div class="gl"></div><div class="gt">{labels}</div></div>'


def gantt(plan, selected=None, related=None, ghost=None, dim=False):
    """부두 네 줄. selected: 고른 선박, related: 그 배를 기다리게 한 선박, ghost: (부두, 시작, 끝, 글자)."""
    rows = []
    for berth in RUN["scenario"]["berths"]:
        waits, cells = [], []
        for v in PLANS[plan]["vessels"]:
            if v["berth"] != berth:
                continue
            vid = v["vessel_id"]
            late = v["demurrage_minutes"] > 0 and dt(v["laytime_end"]) < dt(v["etb"])  # 접안 전에 이미 체선
            if (dt(v["etb"]) - dt(v["eta"])).total_seconds() > 2 * 3600:
                waits.append(f'<div class="w" style="{box(v["eta"], v["laytime_end"] if late else v["etb"])}"></div>')
                if late:
                    waits.append(f'<div class="w" style="{box(v["laytime_end"], v["etb"])};border-color:#C13A32"></div>')
            style = box(v["etb"], v["etu"]) + ";background:" + CARGO[v["cargo_group"]]
            cls = "b"
            label = vid
            if v["kind"] == "WORKING":
                cls += " hx"
                label = vid + " 작업 중"
            if v["kind"] == "FIX":
                label = vid + " FIX"
                style += ";box-shadow:inset 0 0 0 1.5px #0E1726"
            if v.get("pushes"):
                label = f'<u>{RULE[v["pushes"][-1]["category"]]}</u>' + label
            if vid == selected:
                style += ";outline:2px solid #0E1726;outline-offset:1px"
            if vid == related:
                style += ";outline:2px solid #1B5FD9;outline-offset:1px"
            cells.append(f'<div class="{cls}" style="{style}">{label}</div>')
            if v["demurrage_minutes"] > 0:
                if not late:
                    cells.append(f'<div class="e" style="left:{pos(v["laytime_end"]):.2f}%"></div>')
                cells.append(f'<div class="d" style="{box(v["etb"] if late else v["laytime_end"], v["hose_off"])}"></div>')
        if ghost and ghost[0] == berth:
            waits.append(f'<div class="o" style="{box(ghost[1], ghost[2])};padding-left:46px;background:rgba(255,255,255,.9)">{ghost[3]}</div>')
        rows.append(f'<div class="gr"><div class="gl">{berth}</div><div class="gt">{"".join(waits + cells)}</div></div>')
    cls = "g dim" if dim else "g"
    return f'<div class="{cls}">{axis()}<div style="position:relative">{overlay()}{"".join(rows)}</div></div>'


LEGEND_LINE = ('<div class="x m" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:5px">'
               '<span>색 = 화물</span><span>점선 = 대기 (빨간 점선은 접안 전에 쌓이는 체선)</span><span>빨간 띠 = 체선</span>'
               '<span>빗금 = 강풍 제한</span><span>회색 = 야간</span>'
               '<span>막대의 글자 = 접안을 민 조건: 기상 · 선행 선박 · 야간 도선 · 조석 · 동시 접안 제한</span></div>')


def frame(crumb, body, legend, note=""):
    lg = "".join(f"<div>{k(i)}<span>{text}</span></div>" for i, text in enumerate(legend, 1))
    if note:
        lg += f'<div style="grid-column:1/-1" class="m x">{note}</div>'
    return (f'<style>{CSS}</style><div class="dp"><div class="tb"><b>Demurrage Planner</b><span class="s">{crumb}</span>'
            '<span class="sp"></span><span class="s">계산 11/09 21:19 · 실행 3068fa · 규칙 #1cd0b2</span>'
            '<span class="p pa">가상 데이터</span></div>'
            f'<div class="bd">{body}</div><div class="lg">{lg}</div></div>')


def screen1():
    tiles = (
        '<div class="r">'
        '<div class="c"><div class="h">기준안 (도착 순서)</div><div class="n">$112,919</div><div class="x m">비교용, 현행 실적 아님</div></div>'
        f'<div class="c"><div class="h">1안 {k(7)}</div><div class="n">$87,489</div><div class="x m">ETA ±6시간이면 $70,072 ~ $96,989</div></div>'
        '<div class="c"><div class="h">차이</div><div class="n gn">−$25,431</div><div class="x m">22.5% · 예상 절감</div></div>'
        '<div class="c"><div class="h">제약 위반 · 남은 리스크</div><div class="n">0 · 2</div><div class="x m">날씨 급변, 현장 안전</div></div>'
        '</div>')
    look = (
        f'<div class="c" style="flex:.9"><div class="h">{k(1)}이 상황에서 볼 것</div>'
        '<div class="ln"><span class="sb">가장 비싼 배</span><span class="sp"></span><span>V02 <b class="f">$42,856</b></span></div>'
        '<div class="x m" style="margin-bottom:2px">어느 안에서도 같음 (Buoy, 야간 도선 대기 포함)</div>'
        '<div class="ln"><span class="sb">가장 큰 변화</span><span class="sp"></span><span>V05 <b class="f gn">−$24,650</b></span></div>'
        '<div class="x m" style="margin-bottom:2px">강풍 제한 전에 접안</div>'
        '<div class="ln"><span class="sb">남은 리스크</span><span class="sp"></span><span>F1(FIX) 접안</span></div>'
        '<div class="x m">고정 일정 11/11 14:00이 강풍 구간 안</div></div>')
    diff = (
        f'<div class="c" style="flex:1.5"><div class="h">{k(2)}바뀐 것 · 기준안 → 1안 · 5척</div>'
        '<div class="ln"><span class="sb">V05</span><span class="m">#6 11/12 04:30 → 11/11 02:30</span><span class="sp"></span><b class="f gn">−$24,650</b></div>'
        '<div class="ln"><span class="sb">V09</span><span class="m">#6 11/12 19:41 → 11/12 04:30</span><span class="sp"></span><b class="f gn">−$12,969</b></div>'
        '<div class="ln"><span class="sb">V06</span><span class="m">#8 11/11 02:08 → #6 11/12 20:51</span><span class="sp"></span><b class="f rd">+$12,189</b></div>'
        '<div class="ln"><span class="sb">V04 · V03</span><span class="m">부두만 바뀜 (#6 → #7, #7 → #8)</span><span class="sp"></span><b class="f m">$0</b></div>'
        '<div class="x" style="margin-top:4px">줄어든 금액 <b class="f gn">−$37,619</b> · 늘어난 금액 <b class="f rd">+$12,189</b></div></div>')
    tabs = (
        '<div class="r">'
        '<div class="tab"><div class="x m">기준안</div><b class="f">$112,919</b><div class="x m">도착 순서</div></div>'
        f'<div class="tab on" style="flex:1.5"><div class="x m">1안 {k(3)} <span class="p pg">최적 증명</span></div><b class="f">$87,489</b>'
        '<div class="x">#6에서 V05·V09를 V06보다 먼저</div></div>'
        '<div class="tab"><div class="x m">2안</div><b class="f">$91,235</b><div class="x m">V05만 V06 앞으로</div></div>'
        '<div class="tab"><div class="x m">3안</div><b class="f">$92,300</b><div class="x m">V06을 #8 맨 뒤로</div></div>'
        '<div class="tab" style="flex:.6;border-style:dashed"><div class="x m">내 안</div><b>+ 추가</b></div>'
        '</div>'
        '<div class="x" style="margin-top:-3px"><b>1안이 뒤집히는 조건</b> · V09가 6시간 늦으면 2안 · 강풍이 6시간 늦게 오면 3안 · 강풍 예보가 풀리면 2안</div>')
    line = (
        f'<div class="x" style="margin-top:6px;padding:5px 8px;background:#F6F8FB;border-radius:6px;display:flex;gap:6px;align-items:center">'
        f'{k(6)}<span><b>V06</b> · 선행 선박 V09 이안 11/12 18:21 + 교대 2.5h → 20:51 접안 · 정박종료 11/12 16:00 · '
        '체선 18.28h <b class="f rd">$12,189</b></span><span class="sp"></span><span class="bt bo">계산 보기</span></div>')
    timeline = (
        f'<div class="c"><div class="h">{k(4)}부두별 타임라인 · 1안 <span class="sp"></span>{k(5)}<span>막대의 글자가 접안을 민 조건</span></div>'
        + gantt("1안", selected="V06", related="V09", ghost=("#8", "2026-11-11 02:08", "2026-11-11 20:08", "V06 기준안 자리"))
        + LEGEND_LINE + line + '</div>')
    foot = (
        f'<div class="r" style="align-items:center"><div class="c" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
        '<span class="sb">남은 리스크</span><span class="p pa">1안 날씨 급변 · 현장 안전</span><span class="p">2안 같음</span>'
        '<span class="p">3안 같음</span><span class="sp"></span><span class="x m">설비 · 탱크 · 긴급 출하는 해당 없음</span></div>'
        f'<span class="bt bo">보고서 초안</span><span class="bt">확정…</span>{k(8)}</div>')
    body = tiles + '<div class="r">' + look + diff + '</div>' + tabs + timeline + foot
    legend = [
        "요약 세 줄이 먼저. 조건 10가지를 다 읽기 전에 볼 곳을 정해 준다",
        "안 전체보다 차이가 먼저. 줄어든 금액과 늘어난 금액을 따로 보인다",
        "안 이름 옆에 무엇이 다른지 한 줄, 아래에 이 안이 뒤집히는 조건",
        "야간, 강풍 제한, FIX, 체선을 목록이 아니라 시간축에 겹친다",
        "선박마다 접안 시각을 정한 조건 하나만 막대에 붙인다",
        "고른 배의 원래 자리(점선 상자)와 기다리게 한 배(파란 테두리)를 같이 보인다",
        "금액 옆에 범위와 '예상 절감'. 위쪽에는 늘 가상 데이터 표시",
        "확정이 비교 화면에서 바로 닿는다",
    ]
    return frame("S05 강풍 예보 + 선박 집중 · 11척 · 11/10 ~ 11/13", body, legend,
                 "금액과 시각은 데모 S05 실행 결과다. 민감도 범위는 선박마다 ETA를 ±6시간 옮겨 다시 계산한 값의 최소와 최대다.")


def screen2():
    berths = ["#1-1", "#1-2", "#2-1", "#2-2", "#2-4", "#2-5", "#2-6", "#2-7", "#3", "#4-1", "#4-2", "#4-3", "#5-1", "#5-2",
              "#5-3", "#5-4", "#5-5", "#6", "#7", "#8", "BUOY2", "BUOY3", "GAS1", "GAS2"]
    idle = {"#2-2", "#2-5", "#4-3", "#5-1", "#5-2", "#5-3", "BUOY3", "GAS1"}
    rnd = random.Random(11)
    week = 7 * 24
    wx = (33.0, 51.0)  # 2일째 09:00 ~ 3일째 03:00
    colors = list(CARGO.values())
    rows, total, dem, hit, changed = [], 0, 0, 0, 0
    for b in berths:
        if b in idle:
            continue
        t, cells, busy = rnd.uniform(0, 30), [], 0.0
        while t < week - 6:
            dur = rnd.uniform(14, 40)
            if wx[0] <= t < wx[1]:
                t = wx[1] + 1.5
                hit += 1
            end = min(t + dur, week)
            total += 1
            style = f"left:{t / week * 100:.2f}%;width:{(end - t) / week * 100:.2f}%;background:{rnd.choice(colors)};top:3px;height:13px"
            mark = ""
            if total % 9 == 4 and changed < 5:
                style += ";outline:2px solid #0E1726;outline-offset:1px"
                changed += 1
            cells.append(f'<div class="b" style="{style};line-height:13px">{mark}</div>')
            if rnd.random() < 0.2:
                dem += 1
                s = t + dur * rnd.uniform(0.3, 0.7)
                cells.append(f'<div class="d" style="left:{s / week * 100:.2f}%;width:{(end - s) / week * 100:.2f}%;top:17px;height:2px"></div>')
            busy += end - t
            t = end + rnd.uniform(6, 34)
        free = round((1 - busy / week) * 100)
        rows.append(f'<div class="gr" style="height:20px"><div class="gl">{b}</div><div class="gt">{"".join(cells)}</div>'
                    f'<div class="x m f" style="width:62px;text-align:right;flex:none">{free}%</div></div>')
    days = "".join(f'<span style="position:absolute;left:{d / 7 * 100:.2f}%;padding-left:3px" class="x m">11/{9 + d}</span>' for d in range(7))
    ov = "".join(f'<i class="dl" style="left:{d / 7 * 100:.2f}%"></i>' for d in range(1, 7))
    for d in range(-1, 7):
        a, b = max(d * 24 + 17.3, 0), min(d * 24 + 30.9, week)
        if b > a:
            ov += f'<i class="nt" style="left:{a / week * 100:.2f}%;width:{(b - a) / week * 100:.2f}%"></i>'
    ov += f'<i class="wx" style="left:{wx[0] / week * 100:.2f}%;width:{(wx[1] - wx[0]) / week * 100:.2f}%"></i>'
    ov += f'<i class="nw" style="left:{8 / week * 100:.2f}%"></i>'
    head = (
        '<div class="r" style="align-items:center;flex-wrap:wrap">'
        f'{k(3)}<span class="p pk">전체 {total}</span><span class="p">체선이 생기는 배 {dem}</span><span class="p">바뀐 배 {changed}</span>'
        f'<span class="sp"></span>{k(5)}<span class="p pa">강풍 제한으로 밀린 배 {hit}척</span>'
        f'{k(4)}<span class="st"><span>하루</span><span>3일</span><span style="background:#0B1F33;color:#fff;border-color:#0B1F33">1주일</span></span></div>')
    table = (
        '<div class="c" style="padding:6px 10px"><div class="g">'
        f'<div class="gr" style="height:18px;border-top:0"><div class="gl x m">{k(1)}</div><div class="gt">{days}</div>'
        f'<div class="x m" style="width:62px;flex:none;display:flex;gap:3px;justify-content:flex-end;align-items:center">{k(7)}빈 시간</div></div>'
        f'<div style="position:relative"><div class="ov" style="right:62px">{ov}</div>{"".join(rows)}</div>'
        f'<div class="gr" style="height:22px"><div class="x m" style="display:flex;gap:6px;align-items:center">{k(2)}'
        '쓰지 않는 부두 8곳 접힘 · #2-2 · #2-5 · #4-3 · #5-1 · #5-2 · #5-3 · BUOY3 · GAS1 <span class="p">펼치기</span></div></div>'
        '</div></div>')
    grp = '<span style="display:inline-flex;gap:5px;align-items:center;white-space:nowrap">'
    note = (f'<div class="x m" style="display:flex;gap:4px 12px;flex-wrap:wrap">{grp}{k(6)}파란 세로선 = 지금 (11/09 08:00)</span>'
            f'{grp}검은 테두리 = 기준안에서 바뀐 배</span>{grp}빗금 = 강풍 제한 (전 부두)</span>'
            f'{grp}{k(8)}부두 이름과 날짜 줄은 스크롤해도 고정</span></div>')
    print("  그림 2: 접안", total, "건, 체선", dem, ", 밀린 배", hit)
    legend = [
        "부두 줄은 현업이 쓰는 순서로 고정한다. 익숙한 자리에 있어야 찾지 않는다",
        "그 주에 쓰지 않는 부두는 한 줄로 접는다",
        "볼 것만 거른다. 수십 건 가운데 따질 배는 몇 척이다",
        "1주일로 보고 하루로 좁힌다. 좁혀도 고른 배는 그대로다",
        "같은 원인의 경고는 묶어서 한 번만 보인다",
        "지금 시각 선이 지난 일과 앞으로의 일을 가른다",
        "줄 끝에 빈 시간. 비어 있는데 못 쓰는 부두가 보인다",
        "24줄을 내려도 어느 부두, 어느 날인지 잃지 않는다",
    ]
    return frame("부두 24곳 · 1주일 보기", head + table + note, legend,
                 "이 그림의 배치는 자리 표시용으로 만든 값이다(부두 24곳, 60건). 멘토 샘플 규모(부두 24곳, 1주일 54건)에서 화면이 읽히는지 보려는 것이다.")


def screen3():
    v = vessel("1안", "V06")
    assert v["sheet"]["steps"][8]["value"] == "$12,188.89"
    head = (
        '<div class="c"><div style="display:flex;gap:8px;align-items:center"><b style="font-size:14px">V06 MT TAEBAEK</b>'
        '<span class="m x">특수제품선 · 경유 40,000 · 수출 · #6</span><span class="sp"></span>'
        '<span class="p pb">계약서 CT-2611-06 · FOB</span></div>'
        f'<div style="display:flex;gap:10px;align-items:center;margin-top:4px"><div class="n rd">$12,189</div>'
        f'<div style="flex:1;display:flex;gap:6px;align-items:flex-start">{k(1)}<span>11/10 22:00 도착 → 선행 선박을 45.35h 기다려 '
        '11/12 20:51 접안 → 정박종료(11/12 16:00)보다 18.28h 늦게 호스분리</span></div></div></div>')
    steps = [
        ("도착 · NOR", "11/10 22:00", "NOR 제출 시각 없음 → ETA를 씀", '<span class="p pb">계약 제9조</span><span class="p">운영 LAY-01</span><span class="p" style="border-style:dashed">입력</span>', ""),
        ("접안 (ETB)", "11/12 20:51", "ETA + Direction 1.5h = 11/10 23:30 → 선행 선박 V09 이안 18:21 + Switching 2.5h", '<span class="p pt">부두 #6 Shifting 표</span><span class="p">운영 ETB-01</span>', ""),
        ("작업", "11/12 21:51 ~ 11/13 09:17", "ETB + 1h · 40,000 ÷ 3,500/h = 11.43h", '<span class="p pv">실적 2건 평균</span><span class="p">운영 WRK-01 · 02</span>', "est"),
        ("호스분리 · 이안", "11/13 10:17 · 11:17", "작업완료 + 1h · 작업완료 + 2h", '<span class="p pb">계약 제12조</span><span class="p">운영 WRK-03</span>', ""),
        ("정박개시", "11/11 04:00", "ETANR 11/10 22:00 + 6h", '<span class="p pb">계약 제9조</span><span class="p">운영 LAY-05</span>', ""),
        ("Laytime", "36h", "36시간 SHINC", '<span class="p pb">계약 제10조</span>', ""),
        ("정박종료", "11/12 16:00", "정박개시 11/11 04:00 + 36h", '<span class="p">운영 LAY-07</span>', ""),
        ("체선 시간", "18.28h", "호스분리 11/13 10:17 − 정박종료 11/12 16:00 = 1,097분 · 기상 공제 0", '<span class="p pb">계약 제11 · 12 · 13조</span>', ""),
        ("예상 체선료", "$12,188.89", "1,097분 × $16,000 ÷ 1,440분", '<span class="p pb">계약 제11조</span><span class="p">운영 DEM-03</span>', ""),
    ]
    lines = []
    for i, (name, value, formula, chips, flag) in enumerate(steps, 1):
        est = f' <span class="p pa" style="border-style:dashed">추정</span> {k(4)}' if flag else ""
        bg = ";background:#FFFBF0" if flag else ""
        lines.append(
            f'<div style="padding:4px 0;border-top:1px solid #F0F2F6{bg}"><div style="display:flex;gap:6px;align-items:baseline">'
            f'<span class="m x" style="width:12px">{i}</span><span class="sb" style="width:84px;flex:none">{name}</span>'
            f'<b class="f">{value}</b>{est}</div>'
            f'<div style="padding-left:18px;display:flex;gap:3px 6px;flex-wrap:wrap;align-items:center;margin-top:1px">'
            f'<span class="mono">{formula}</span>{chips}</div></div>')
    left = (f'<div class="c" style="flex:1.45"><div class="h">{k(2)}계산 순서 · 식에 숫자를 넣은 줄 <span class="sp"></span>{k(3)}근거 칩</div>'
            + "".join(lines) + '</div>')
    # 구간 띠: 정박개시 11/11 04:00 ~ 호스분리 11/13 10:17 (54h 17m)
    a, b, c, d = dt("2026-11-11 04:00"), dt("2026-11-12 16:00"), dt("2026-11-12 20:51"), dt("2026-11-13 10:17")
    whole = (d - a).total_seconds()
    w1, w2, w3 = [(y - x).total_seconds() / whole * 100 for x, y in ((a, b), (b, c), (c, d))]
    band = (
        '<div style="display:flex;height:16px;border-radius:4px;overflow:hidden;margin:4px 0 2px">'
        f'<div style="width:{w1:.2f}%;background:#D5DBE5"></div>'
        f'<div style="width:{w2:.2f}%;background:#E58A84" class="hx"></div><div style="width:{w3:.2f}%;background:#C13A32"></div></div>'
        '<div class="x m" style="position:relative;height:32px"><span style="position:absolute;left:0">정박개시<br>11/11 04:00</span>'
        f'<span style="position:absolute;left:{w1:.2f}%;transform:translateX(-100%);text-align:right;padding-right:3px">정박종료<br>11/12 16:00</span>'
        '<span style="position:absolute;right:0;text-align:right">호스분리<br>11/13 10:17</span></div>')
    right = (
        '<div style="flex:1;display:flex;flex-direction:column;gap:8px;min-width:0">'
        f'<div class="c" style="flex:none"><div class="h">{k(5)}금액을 구간으로 · 체선 18.28h</div>{band}'
        '<div class="ln"><span style="width:9px;height:9px;background:#D5DBE5;border-radius:2px;display:inline-block"></span><span>Laytime 36h</span><span class="sp"></span><b class="f m">$0</b></div>'
        '<div class="ln"><span style="width:9px;height:9px;background:#E58A84;border-radius:2px;display:inline-block"></span><span>선행 선박 대기 4.85h</span><span class="sp"></span><b class="f">$3,233</b></div>'
        '<div class="ln"><span style="width:9px;height:9px;background:#C13A32;border-radius:2px;display:inline-block"></span><span>접안 후 작업 13.43h</span><span class="sp"></span><b class="f">$8,956</b></div>'
        '<div class="x m" style="margin-top:3px">띠의 색과 줄의 색이 같다. 합 $12,189</div></div>'
        f'<div class="c" style="flex:none"><div class="h">{k(6)}공제 전과 후 · 기준안의 V05</div>'
        '<div class="ln"><span>공제 전 체선</span><span class="sp"></span><span class="f">21.18h · $31,775</span></div>'
        '<div class="ln"><span>기상과 겹친 9.50h의 절반</span><span class="sp"></span><span class="f">−4.75h · −$7,125</span></div>'
        '<div class="ln"><span class="sb">공제 후</span><span class="sp"></span><b class="f">16.43h · $24,650</b></div>'
        '<div class="x" style="margin-top:3px"><span class="p pa" style="border-style:dashed">미확정 규칙</span> 기상 체선의 정의는 확인 전</div></div>'
        f'<div class="c" style="flex:none"><div class="h">{k(7)}이 배만 놓고 보면</div>'
        '<div class="ln"><span class="m">기준안</span><span>#8 11/11 02:08 접안</span><span class="sp"></span><b class="f">$0</b></div>'
        '<div class="ln"><span class="m">1안</span><span>#6 11/12 20:51 접안</span><span class="sp"></span><b class="f rd">+$12,189</b></div>'
        '<div class="x m" style="margin-top:3px">Laytime 36시간, 하루 $16,000. 기다려도 비용이 작은 배라 뒤로 갔다</div></div>'
        '</div>')
    legend = [
        "맨 위 한 문장. 계산서를 다 읽지 않아도 왜 이 금액인지 안다",
        "손으로 따라갈 수 있는 순서와 숫자를 넣은 식. 다른 사람이 같은 값으로 다시 셈한다",
        "근거 칩은 출처별로 색이 다르다: 계약, 운영 기준, 부두 기준, 입력, 실적. 조항 번호가 칩 안에 있다",
        "추정이 든 줄은 그 줄에서 표시한다. 여기서는 작업시간이 과거 실적 평균이다",
        "금액을 사유별 구간으로 쪼갠다. 다툼은 총액보다 구간에서 난다",
        "공제는 전과 후를 같이, 정의가 확인 전인 규칙은 미확정으로 표시한다",
        "기준안과 이 안에서 이 배가 어떻게 달라졌는지 한 척 단위로 보인다",
    ]
    return frame("접안 계획 비교 › V06 계산 근거", head + '<div class="r">' + left + right + '</div>', legend,
                 "금액을 누르면 화면을 옮기지 않고 옆에서 열린다. 값은 데모 S05 실행의 계산서 그대로다.")


def screen4():
    back = '<div style="position:absolute;inset:0;padding:10px 12px;opacity:.28">' + gantt("1안") + gantt("기준안") + '</div>'
    risk = (
        f'<div class="h" style="margin-top:8px">{k(2)}남은 리스크 2건 · 펼쳐 본 것만 확인으로 센다</div>'
        '<div class="ln" style="align-items:flex-start"><span class="ck cy"></span><div><b>날씨 급변</b> <span class="p pg">펼쳐 봄 · 확인함</span>'
        '<div class="x m">F1(FIX) 접안 11/11 14:00이 강풍 구간(11/11 09:00 ~ 11/12 03:00) 안. 고정 일정 재확인 필요</div></div></div>'
        '<div class="ln" style="align-items:flex-start"><span class="ck"></span><div><b>현장 안전</b> <span class="p pa">아직 펼쳐 보지 않음</span>'
        '<div class="x m">야간 접안 · 이안 3건 (V04 00:56 이안, V01 01:10 이안, V05 02:30 접안)</div></div></div>')
    modal = (
        '<div style="position:relative;margin:26px auto;width:430px;background:#fff;border:1px solid #D5DBE5;border-radius:12px;padding:12px 14px">'
        f'<div style="display:flex;align-items:center;gap:6px"><b style="font-size:14px">1안을 확정합니다</b><span class="sp"></span>{k(1)}</div>'
        '<div class="r" style="margin-top:6px"><div class="tx" style="flex:1"><div class="x m">총 예상 체선료</div><b class="f">$87,489</b>'
        '<div class="x gn">기준안 대비 −$25,431 예상</div></div>'
        '<div class="tx" style="flex:1"><div class="x m">바뀐 선박 5척</div><b>V05 · V09 · V06</b><div class="x m">V04 · V03은 부두만</div></div>'
        '<div class="tx" style="flex:1"><div class="x m">계산 기준</div><b class="f">11/09 21:19</b><div class="x m">규칙 #1cd0b2</div></div></div>'
        + risk +
        f'<div class="h" style="margin-top:8px">{k(3)}선택 이유 (비워 둘 수 없음)</div>'
        '<div class="tx" style="min-height:38px">V05 긴급 출하분을 강풍 전에 붙인다. V06은 Laytime 여유가 커서 뒤로 보낸다.</div>'
        '<div style="display:flex;gap:4px;margin-top:4px;flex-wrap:wrap"><span class="p pk">금액</span><span class="p">현장 사정</span>'
        '<span class="p">안전</span><span class="p">관계</span><span class="p">기타</span></div>'
        f'<div style="display:flex;gap:8px;align-items:center;margin-top:8px">{k(4)}<span class="x">확정하는 사람 <b>스케줄러 A</b> (로그인한 계정)</span>'
        '<span class="sp"></span><span class="bt bo">취소</span><span class="bt">확정</span></div>'
        '<div class="x m" style="margin-top:6px">확정 뒤 입력이 바뀌면 이 기록은 그대로 두고 계획에 \'확정 후 입력 변경됨\'을 표시합니다</div>'
        '</div>')
    hist = (
        f'<div class="c" style="position:relative"><div class="h">{k(5)}이력 · 덧붙이기만 된다 (예시)</div>'
        '<div class="ln"><span class="f m">11/09 21:40</span><span><b>1안 확정</b> · 스케줄러 A</span><span class="sp"></span><span class="x m">실행 3068fa · 규칙 #1cd0b2</span></div>'
        '<div class="ln"><span class="f m">11/10 09:05</span><span><b>확정 취소</b> · 스케줄러 A</span><span class="sp"></span><span class="x m">사유: V09 ETA 변경 통보</span></div>'
        f'<div class="ln"><span class="f m">11/10 09:20</span><span><b>2안 확정</b> · 스케줄러 B {k(6)}</span><span class="sp"></span><span class="x m">1안이 아닌 안, 사유 유형: 현장 사정</span></div></div>')
    body = '<div style="position:relative;min-height:392px">' + back + modal + '</div>' + hist
    legend = [
        "누르는 순간 무엇을 확정하는지 다시 보인다: 금액, 바뀐 선박, 계산 기준",
        "리스크는 펼쳐 봐야 확인이 된다. 안 본 것은 안 봤다고 표시한다",
        "이유를 이 자리에서 받는다. 결정과 기록이 한 동작이다",
        "확정한 사람은 로그인한 계정에서 온다. 이름을 따로 적지 않는다",
        "이력은 고치지 못하고 취소와 다시 고른 것이 시간순으로 쌓인다",
        "1안이 아닌 안을 고른 경우와 그 사유 유형이 남는다",
    ]
    return frame("접안 계획 비교 › 확정", body, legend, "확정 창의 금액과 리스크는 데모 S05 실행 결과이고, 이력의 시각과 사람은 예시다.")


def imported():
    rows = ""
    for vid in ("V04", "V05", "V09"):
        v = vessel("기준안", vid)
        biz = {"EXPORT": "EX", "IMPORT": "IM"}.get(v["direction"], v["direction"])
        cells = "".join(f'<span class="f" style="flex:1">{v[key][5:].replace("-", "/")}</span>' for key in ("eta", "etb", "etu"))
        rows += f'<div class="ln x"><span class="sb" style="width:34px">{v["berth"]}</span>{cells}<span style="width:24px">{biz}</span></div>'
    return ('<div class="h" style="margin-top:8px">불러온 표 · 열 이름과 순서가 SEAGATE 조회 결과 그대로</div>'
            '<div class="ln x m"><span style="width:34px">Berth</span><span style="flex:1">ETA</span><span style="flex:1">ETB</span>'
            '<span style="flex:1">ETU</span><span style="width:24px">Biz</span></div>' + rows + '<div class="x m">… 외 8척</div>')


def screen5():
    start = (
        f'<div class="r">{k(1)}<div class="c on" style="text-align:center"><b>접안계획 불러오기</b><div class="x m">SEAGATE 조회 결과 그대로</div></div>'
        '<div class="c" style="text-align:center"><b>어제 시나리오 복제</b><div class="x m">바뀐 값만 고침</div></div>'
        '<div class="c" style="text-align:center;border-style:dashed"><b class="m">빈 양식</b><div class="x m">마지막 선택지</div></div></div>')
    issues = (
        f'<div class="c" style="flex:1"><div class="h">{k(2)}11척을 불러왔고 고칠 곳은 3곳 <span class="sp"></span>{k(5)}<span class="p pa">3개 남음</span></div>'
        '<div class="ln" style="align-items:flex-start"><span class="p pr">막힘</span><div><b>V02 일 체선료 $3,800</b>'
        '<div class="x m">같은 선종 평균의 1/10. 0이 하나 빠졌는지 확인하세요</div></div></div>'
        '<div class="ln" style="align-items:flex-start"><span class="p pa">주의</span><div><b>V09 Laytime 24h / 36h</b>'
        '<div class="x m">계약서 안에서 값이 두 번 다르게 나옴. 둘 중 고르세요</div></div></div>'
        '<div class="ln" style="align-items:flex-start"><span class="p pa">주의</span><div><b>V07 NOR 03/04 14:00</b>'
        '<div class="x m">일과 월의 순서가 모호함. 3월 4일인지 4월 3일인지</div></div></div>'
        '<div class="x m" style="margin-top:4px">나머지 8척은 문제없음 <span class="p">펼치기</span></div>'
        + imported() +
        f'<div class="h" style="margin-top:8px">{k(6)}이대로 계산하면 들어가는 가정</div>'
        '<div class="x">작업시간 = 과거 실적 평균 (선박 6척) · Direction과 Switching = 부두 기준값 · 호스분리 = 작업완료 + 최빈 소요</div></div>')
    doc = (
        '<div class="tx" style="font-size:11px;line-height:1.6;background:#FBFBF8">'
        '<b>CT-2611-06 (가상) · 3쪽</b><br>10. LAYTIME. <span class="mk">Thirty-six (36) running hours SHINC</span> shall be allowed …<br>'
        '11. DEMURRAGE. <span class="mk">USD 16,000 per day pro rata</span> …<br>'
        '9. NOTICE. Laytime shall commence <span style="background:#FFD9B0">six (6) hours after NOR</span> or on berthing …</div>')
    fields = (
        '<div class="ln"><span style="width:76px">Laytime</span><b class="f">36h SHINC</b><span class="sp"></span><span class="p pg">높음</span></div>'
        '<div class="ln"><span style="width:76px">일 체선료</span><b class="f">$16,000</b><span class="sp"></span><span class="p pg">높음</span></div>'
        '<div class="ln"><span style="width:76px">기상 공제</span><b class="f">1/2</b><span class="sp"></span><span class="p pg">높음</span></div>'
        '<div class="ln"><span style="width:76px">Laycan</span><b class="f">11/10 ~ 11/12</b><span class="sp"></span><span class="p pg">높음</span></div>'
        '<div class="ln" style="background:#FFF8EC"><span style="width:76px">NOR 뒤 대기</span><b class="f">6h</b><span class="sp"></span>'
        '<span class="p pa">확인 필요 · 근거 문장이 2곳</span></div>')
    extract = (
        f'<div class="c" style="flex:1.15"><div class="h">{k(3)}추출값 확인 · 원문과 나란히</div>{doc}'
        f'<div style="margin-top:6px">{fields}</div>'
        f'<div style="display:flex;gap:6px;align-items:center;margin-top:6px">{k(4)}<span class="bt">높음 4개 한 번에 확인</span>'
        '<span class="x m">확인한 값만 계산에 들어간다</span></div></div>')
    legend = [
        "빈 양식에서 시작하지 않는다. 불러오기와 복제가 먼저다",
        "불러온 뒤에는 고칠 곳만 위로. 왜 확인이 필요한지와 고칠 방법을 같이 말한다",
        "추출값과 원문을 나란히 놓는다. 근거 문장이 표시돼 있다",
        "신뢰도가 높은 값은 묶어서 한 번에 확인한다",
        "남은 확인 수가 늘 보인다. 끝이 보여야 끝까지 한다",
        "계산 전에 어떤 가정이 들어가는지 한 번 보인다",
    ]
    return frame("입력 › 불러오기와 확인", start + '<div class="r">' + issues + extract + '</div>', legend,
                 "계약 조건은 데모의 가상 계약서 CT-2611-06 값이다. 고칠 곳 세 건과 원문 발췌는 화면을 보이려고 만든 예시다.")


def screen6():
    steps = (
        f'<div style="display:flex;gap:6px;align-items:center">{k(4)}<div class="st">'
        '<span style="background:#E6F4EC;border-color:#B4DCC5;color:#0E6B3B">입력</span>'
        '<span style="background:#E6F4EC;border-color:#B4DCC5;color:#0E6B3B">계산</span>'
        '<span style="background:#0B1F33;color:#fff;border-color:#0B1F33">후보 비교</span>'
        '<span style="border-style:dashed;color:#8A5300;background:#FFF3DC;border-color:#F3D69A">리스크 · 다시 계산 필요</span>'
        '<span style="border-style:dashed;color:#8A5300;background:#FFF3DC;border-color:#F3D69A">보고서 · 다시 계산 필요</span><span>일정 확정</span></div></div>'
        '<div class="x m" style="margin-top:-4px">낡은 이유: V09 ETA 변경 뒤 리스크와 보고서를 다시 만들지 않음. 앞 단계로는 언제든 돌아갈 수 있다</div>')
    change = (
        f'<div class="c" style="flex:1"><div class="h">{k(1)}그 자리에서 바꾸기 <span class="sp"></span>{k(3)}<span class="p pv">연습판 · 원본은 그대로</span></div>'
        '<div style="display:flex;gap:4px;flex-wrap:wrap"><span class="p pk">이 배 +6시간</span><span class="p">이 배 −6시간</span>'
        '<span class="p">강풍 6시간 늦게</span><span class="p">강풍 예보 해제</span><span class="p">부두 사용 제한 추가</span></div>'
        f'<div class="h" style="margin-top:8px">{k(2)}바꾼 것</div>'
        '<div class="ln"><span class="sb">V09 ETA</span><span class="f">11/11 13:00 → 11/11 19:00</span><span class="sp"></span><span class="p">되돌리기</span></div>'
        '<div class="x m" style="margin-top:3px">여러 개를 걸어 두고 한 번에 다시 계산할 수 있다</div></div>')
    prog = (
        f'<div class="c" style="flex:1"><div class="h">{k(5)}다시 계산 · 기준안이 먼저 나온다</div>'
        '<div class="ln"><span class="p pg">끝</span><span>입력 검증 · 제약 정리</span><span class="sp"></span><span class="f m">0.1초</span></div>'
        '<div class="ln"><span class="p pg">끝</span><span>기준안과 선박별 체선료</span><span class="sp"></span><span class="f m">0.2초</span></div>'
        '<div class="ln"><span class="p pb">진행</span><span>후보 탐색</span><span class="sp"></span><span class="f m">4초째</span><span class="p">취소</span></div>'
        '<div class="ln dim"><span class="p">대기</span><span>리스크 점검 · 민감도</span></div>'
        '<div class="x m" style="margin-top:3px">그동안 이전 결과는 흐리게 남아 있다</div></div>')
    rows = [("기준안", "$112,919", "$107,169", "−$5,750", "4위 → 4위", ""), ("1안 · 확정안", "$87,489", "$87,489", "그대로", "1위 → 2위", "mk"),
            ("2안", "$91,235", "$85,485", "−$5,750", "2위 → 1위", "mk"), ("3안", "$92,300", "$92,300", "그대로", "3위 → 3위", ""),
            ("내 안 · V06을 #8에 고정", "$92,300", "$92,300", "그대로", "3안과 같은 배정", "")]
    tr = "".join(
        f'<div class="ln"><span style="width:150px" class="sb">{a}</span><span class="f m" style="width:66px;text-align:right">{b}</span>'
        f'<span class="f sb" style="width:66px;text-align:right">{c}</span><span class="f {"gn" if d.startswith("−") else "m"}" style="width:58px;text-align:right">{d}</span>'
        f'<span class="sp"></span><span class="x {cls}" style="padding:0 4px;border-radius:3px">{e}</span></div>' for a, b, c, d, e, cls in rows)
    result = (
        f'<div class="c"><div class="h">{k(6)}바꾸기 전과 후 · 달라진 것만 표시</div>'
        '<div class="x" style="padding:5px 8px;background:#F6F8FB;border-radius:6px;margin-bottom:4px"><b>V09 +6시간</b> · 1안은 그대로, 2안은 −$5,750. 순위가 바뀌어 2안이 가장 낮다</div>'
        '<div class="ln x m"><span style="width:150px"></span><span style="width:66px;text-align:right">전</span><span style="width:66px;text-align:right">후</span>'
        '<span style="width:58px;text-align:right">차이</span><span class="sp"></span><span>순위</span></div>' + tr +
        f'<div class="x" style="margin-top:6px;display:flex;gap:6px;align-items:center">{k(7)}<span class="p pa">확정안 다시 볼 것</span>'
        '<span>앞서 확정한 1안이 이 변경에서는 2위가 된다. 같았다면 \'확정안 그대로\'라고 알린다</span></div></div>')
    mine = (
        f'<div class="c"><div class="h">{k(8)}내 안 만들기 · 배를 끌어 옮기거나 고정한다</div>'
        '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap"><span class="b" style="position:static;background:#2F6FE0;padding:0 8px">V06</span>'
        '<span class="m">놓을 수 있는 곳</span><span class="p pg">#6</span><span class="p pg">#7</span><span class="p pg">#8 · 고정함</span>'
        '<span class="p pr" style="border-style:dashed">Buoy 불가 · 경유를 취급하지 않음, LOA 183m &lt; 최소 200m</span></div></div>')
    legend = [
        "비교 화면에서 값을 바로 고친다. 자주 하는 변경은 한 번에 건다",
        "무엇을 바꿨는지 늘 보이고 하나씩 되돌릴 수 있다",
        "시험 삼아 바꾼 값은 연습판에 있고 원본 계획에 섞이지 않는다",
        "단계 표시는 길만 보여 준다. 고치면 뒤 단계가 '다시 계산 필요'와 낡은 이유를 달고 남는다",
        "기준안이 먼저 뜨고 후보가 뒤따른다. 실제 단계 이름과 걸린 시간, 취소",
        "바꾸기 전과 후를 한 줄로 요약하고 달라진 숫자만 강조한다",
        "앞서 확정한 안이 아직 맞는지 알려 준다",
        "숙련자가 자기 안을 넣는다. 놓을 수 없는 자리는 이유와 함께 막는다",
    ]
    body = steps + '<div class="r">' + change + prog + '</div>' + result + mine
    return frame("접안 계획 비교 › 바꾸고 다시 보기", body, legend,
                 "전후 금액은 데모 S05의 민감도 계산(V09 ETA +6시간) 값이다. 진행 시간은 예시다.")


def screen7():
    sched = (
        f'<div class="c" style="flex:1.12"><div class="h">{k(1)}작업 지시자 · 무엇을 준비할까</div>'
        f'<div class="x" style="margin-bottom:4px"><span class="p pg">확정 1안</span> <span class="p pa">앞 계획(기준안)에서 5척 바뀜</span> {k(3)}</div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/10 10:30</span><span class="sb" style="width:34px">#7</span><span>V04 접안</span><span class="sp"></span><span class="p pa">바뀜</span></div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/10 13:00</span><span class="sb" style="width:34px">#8</span><span>V03 접안</span><span class="sp"></span><span class="p pa">바뀜</span></div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/10 15:35</span><span class="sb" style="width:34px">Buoy</span><span>V01 접안</span></div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/11 00:56</span><span class="sb" style="width:34px">#7</span><span>V04 이안</span></div>'
        f'<div class="x" style="padding:0 0 3px 80px;color:#8A5300">야간 이안. 인원과 예선 배치 확인 {k(2)}</div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/11 02:30</span><span class="sb" style="width:34px">#6</span><span>V05 접안</span><span class="sp"></span><span class="p pa">바뀜</span></div>'
        '<div class="x" style="padding:0 0 3px 80px;color:#8A5300">야간 접안. 긴급 출하분</div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/11 07:45</span><span class="sb" style="width:34px">#8</span><span>V03 이안</span></div>'
        '<div class="x" style="padding:0 0 3px 80px;color:#8A5300">강풍 제한 시작(09:00)까지 1.2시간</div>'
        '<div class="ln" style="background:#FFF8EC"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/11 09:00</span><span class="sb">강풍 제한 시작 · 11/12 03:00까지 전 부두 신규 접안 불가</span></div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/11 14:00</span><span class="sb" style="width:34px">#7</span><span>F1 접안 (FIX)</span></div>'
        '<div class="x" style="padding:0 0 3px 80px;color:#8A5300">강풍 구간 안. 고정 일정 재확인</div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/12 01:10</span><span class="sb" style="width:34px">Buoy</span><span>V01 이안</span></div>'
        '<div class="x" style="padding:0 0 3px 80px;color:#8A5300">야간 이안. 강풍 제한 끝(03:00)까지 1.8시간</div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/12 04:30</span><span class="sb" style="width:34px">#6</span><span>V09 접안</span><span class="sp"></span><span class="p pa">바뀜</span></div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/12 04:30</span><span class="sb" style="width:34px">#8</span><span>V07 접안</span></div>'
        '<div class="ln"><span class="f m" style="width:74px;flex:none;white-space:nowrap">11/12 08:00</span><span class="sb" style="width:34px">#7</span><span>V08 접안</span></div>'
        '<div class="x m" style="margin-top:3px">금액은 보이지 않는다 · 시간순 · CSV로 내려받기</div></div>')

    def pay(vid, amount, kind, split, extra=""):
        return (f'<div class="ln" style="align-items:flex-start"><span class="sb" style="width:30px">{vid}</span>'
                f'<div style="flex:1"><div style="display:flex;gap:5px;align-items:baseline"><b class="f" style="width:58px;text-align:right">{amount}</b>'
                f'<span class="p pb">{kind}</span>{extra}</div><div class="x m">{split}</div></div></div>')
    payer = (
        f'<div class="c" style="flex:1.25"><div class="h">{k(4)}체선 지불 부서 · 얼마가 왜 나오나</div>'
        '<div class="x" style="margin-bottom:4px"><span class="p pk">$10,000 이상 5척</span> <span class="p">전체 11척 · 합 $87,489</span></div>'
        + pay("V02", "$42,856", "용선계약", f"접안 후 작업 $33,356 · 야간 도선 $9,236 · 선행 선박 대기 $264 {k(5)}", '<span class="x rd f">시간당 +$1,583</span>')
        + pay("V06", "$12,189", "FOB", "접안 후 작업 $8,956 · 선행 선박 대기 $3,233", '<span class="x rd f">시간당 +$667</span>')
        + pay("V07", "$11,250", "FOB", "접안 후 작업 $11,250")
        + pay("V01", "$11,194", "CFR", "접안 후 작업 $11,194")
        + pay("V08", "$10,000", "CFR", "접안 후 작업 $10,000")
        + f'<div class="ln"><span class="sb" style="width:30px">6척</span><b class="f m" style="width:58px;text-align:right">$0</b>'
          f'<span class="x m">Laytime 안에 끝남 {k(6)}</span></div>'
        '<div class="x" style="margin-top:5px">점검할 곳 · 해석 대안 0 · 미확정 규칙 0 · 문서 충돌 0</div>'
        '<div class="tx" style="margin-top:8px"><div class="x m" style="margin-bottom:3px">V02를 누르면 · 정박종료 11/12 02:00 뒤 27.07h</div>'
        '<div style="display:flex;height:12px;border-radius:3px;overflow:hidden"><div style="width:0.62%;background:#E58A84"></div>'
        '<div style="width:21.55%;background:#8E7CC3"></div><div style="width:77.83%;background:#C13A32"></div></div>'
        '<div class="x" style="display:flex;gap:2px 8px;margin-top:3px;flex-wrap:wrap"><span><b style="color:#8E7CC3">■</b> 야간 도선 02:10 ~ 08:00 · 5.83h</span>'
        '<span><b class="rd">■</b> 접안 후 작업 08:00 ~ 11/13 05:04 · 21.07h</span></div>'
        '<div style="display:flex;gap:4px;margin-top:4px"><span class="p pb">계약 조항 보기</span><span class="p">운영 기준 · 야간 도선</span></div></div>'
        '<div class="tx" style="margin-top:6px;display:flex;gap:6px;align-items:center"><span class="x m" style="flex:1">스케줄러에게 의견 남기기 (조회만 하는 역할)</span>'
        '<span class="bt bo">남기기</span></div></div>')
    sch = (
        '<div class="c"><div style="display:flex;gap:6px;align-items:center;white-space:nowrap"><span class="sb">선박 스케줄러 · 어느 안으로 할까</span>'
        '<span class="p pg">1안 $87,489</span><span class="p">2안 $91,235</span><span class="p">3안 $92,300</span>'
        f'<span class="sp"></span><span class="x m">첫 화면은 그림 1</span>{k(7)}</div></div>')
    legend = [
        "역할마다 첫 화면이 다르다. 세 사람의 질문이 다르기 때문이다",
        "작업 지시자는 시간순 할 일로 본다. 주의할 점이 해당 줄에 붙어 있다",
        "계획이 바뀌면 '바뀜'이 표시된다. 어제 본 계획으로 준비하지 않게 한다",
        "지불 부서는 금액이 큰 순서로 본다. '크다'의 기준을 밝힌다",
        "금액을 사유별로 쪼개고 계약 유형과 시간당 늘어나는 금액을 같이 보인다",
        "0달러에도 이유를 적는다. 계산 안 됨과 구별된다",
        "역할이 달라도 같은 선박은 같은 금액과 시각을 본다 (V06 $12,189, 11/12 20:51)",
    ]
    return frame("역할별 첫 화면", sch + '<div class="r">' + sched + payer + '</div>', legend,
                 "일정과 금액은 데모 S05의 1안 결과다. 두 역할이 화면을 직접 쓰는지는 확인 전이고, 문서로만 받는다면 같은 구성이 보고서와 메일의 구성이 된다.")


SCREENS = [("screen-1-compare", "접안 계획 비교", screen1), ("screen-2-timeline", "부두 24곳 1주일 타임라인", screen2),
           ("screen-3-evidence", "계산 근거", screen3), ("screen-4-confirm", "확정 창과 이력", screen4),
           ("screen-5-input", "불러오기와 추출값 확인", screen5), ("screen-6-whatif", "바꾸고 다시 보기", screen6),
           ("screen-7-roles", "역할별 첫 화면", screen7)]


def render_png(html_path, png_path):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    "--window-size=720,1500", f"--screenshot={png_path}", html_path.as_uri()],
                   check=True, capture_output=True, timeout=120)
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return
    im = Image.open(png_path).convert("RGB")
    bbox = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    if bbox:
        pad = 24
        im.crop((max(bbox[0] - pad, 0), max(bbox[1] - pad, 0), min(bbox[2] + pad, im.width), min(bbox[3] + pad, im.height))).save(png_path)


def main():
    check_numbers()
    frag_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    for name, title, fn in SCREENS:
        frag = fn()
        page = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>' + title + '</title>'
                '<style>body{margin:0;padding:20px;background:#fff;width:680px}</style></head><body>' + frag + '</body></html>')
        html_path = HERE / f"{name}.html"
        html_path.write_text(page, encoding="utf-8")
        if frag_dir:
            frag_dir.mkdir(parents=True, exist_ok=True)
            (frag_dir / f"{name}.txt").write_text(frag, encoding="utf-8")
        render_png(html_path, HERE / f"{name}.png")
        print(name, len(frag), "자")


if __name__ == "__main__":
    main()
