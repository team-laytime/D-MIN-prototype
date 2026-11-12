#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""유스케이스 다이어그램 생성기 (표준 라이브러리만 사용).

하는 일
  1. 모델(액터 · 유스케이스 · 관계)을 4개 층에 놓는다.
       층 0 사람 액터 | 층 1 기본 유스케이스 | 층 2 포함·확장 유스케이스 | 층 3 외부 시스템 액터
  2. 층 안의 순서로 선 교차 수를 센다. (번호순 배치와 최종 배치를 비교)
  3. 좌표를 정하고, 실제 선분끼리 · 선분과 타원 · 선분과 글자가 겹치는지 검사한다.
  4. SVG를 쓴다. --png 를 주면 Chrome 헤드리스로 PNG도 뜬다.

실행
  python3 docs/requirements/usecase/make_usecase_diagram.py [--png]

모델을 고칠 때는 ACTORS · USECASES · ASSOC · INCLUDE · EXTEND 만 고치면 된다.
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────── 1. 모델 ───────────────────────────
# 액터: id → (이름 줄들, 종류, 놓는 쪽)
ACTORS = {
    "adm": (["기준 정보", "관리자"], "human", "L"),
    "sch": (["선박", "스케줄러"], "human", "L"),
    "pay": (["체선 지불 부서"], "human", "L"),
    "ops": (["입출항 작업", "지시자"], "human", "L"),
    "qa": (["검증 담당자"], "human", "L"),
    "portal": (["공공데이터", "포털 API"], "system", "R"),
    "llm": (["LLM API"], "system", "R"),
}

# 유스케이스: id → (이름, 종류, 꼬리표, 관련 FR)
#   종류: base(액터가 직접 시작) · inc(포함되는 것) · ext(확장하는 것)
USECASES = {
    "UC-01": ("기준 정보를 관리한다", "base", "", "FR-09·12"),
    "UC-02": ("공공데이터를 수집한다", "base", "Should", "FR-13"),
    "UC-03": ("과거 실적을 적재한다", "base", "Should", "FR-10"),
    "UC-04": ("계약 문서를 등록한다", "base", "", "FR-02·06·07"),
    "UC-05": ("시나리오를 입력한다", "base", "", "FR-01"),
    "UC-06": ("접안 후보를 생성한다", "base", "", "FR-08·14~25·27·41~43"),
    "UC-07": ("한 척 체선료를 계산한다", "base", "Should", "FR-38"),
    "UC-08": ("후보를 비교한다", "base", "", "FR-44·45"),
    "UC-09": ("남은 리스크를 점검한다", "base", "", "FR-47~50"),
    "UC-10": ("보고·메일 초안을 쓴다", "base", "", "FR-51~53"),
    "UC-11": ("후보를 확정한다", "base", "", "FR-54·55"),
    "UC-12": ("산출 근거를 조회한다", "base", "", "FR-39·40·46"),
    "UC-13": ("확정 계획을 확인한다", "base", "확인 필요", "과제 원문 2절"),
    "UC-14": ("검증을 일괄 실행한다", "base", "", "FR-56~59"),
    "UC-15": ("문서 필드를 추출한다", "inc", "", "FR-03·04·05"),
    "UC-16": ("예상 체선료를 계산한다", "inc", "", "FR-29~37"),
    "UC-17": ("조건을 바꿔 재계산한다", "ext", "Could", "FR-26·28"),
    "UC-18": ("SOF 실적을 추출한다", "ext", "Could", "FR-11"),
}

# 연관(실선): 액터 ─ 유스케이스
ASSOC = [
    ("adm", "UC-01"), ("adm", "UC-02"), ("adm", "UC-03"),
    ("sch", "UC-04"), ("sch", "UC-05"), ("sch", "UC-06"), ("sch", "UC-07"),
    ("sch", "UC-08"), ("sch", "UC-09"), ("sch", "UC-10"), ("sch", "UC-11"),
    ("sch", "UC-12"),
    ("pay", "UC-12"), ("ops", "UC-13"), ("qa", "UC-14"),
    ("portal", "UC-02"), ("llm", "UC-18"), ("llm", "UC-15"), ("llm", "UC-10"),
]
# 포함(점선 화살표): 기본 → 포함되는 것
INCLUDE = [("UC-04", "UC-15"), ("UC-06", "UC-16"), ("UC-07", "UC-16")]
# 확장(점선 화살표): 확장하는 것 → 기본
EXTEND = [("UC-17", "UC-06"), ("UC-18", "UC-03")]

# 구역(그림 안의 띠): 이름 → 기본 유스케이스들 (위에서 아래 순서)
ZONES = [
    ("준비", ["UC-01", "UC-02", "UC-03"]),
    ("입력", ["UC-04", "UC-05"]),
    ("계산", ["UC-06", "UC-07"]),
    ("비교 · 리스크 · 보고 · 확정", ["UC-08", "UC-09", "UC-10", "UC-11"]),
    ("열람", ["UC-12", "UC-13"]),
    ("검증", ["UC-14"]),
]
# 포함·확장 유스케이스를 어느 기본 유스케이스와 같은 줄에 둘지
SUB_ROW = {"UC-18": "UC-03", "UC-15": "UC-04", "UC-17": "UC-06", "UC-16": "UC-07"}

# ─────────────────────── 2. 층과 교차 수 ───────────────────────
BASE = [u for _, us in ZONES for u in us]
SUBS = [u for u in USECASES if USECASES[u][1] != "base"]
LEFT = [a for a, v in ACTORS.items() if v[2] == "L"]
RIGHT = [a for a, v in ACTORS.items() if v[2] == "R"]


def layered_edges():
    """이웃한 층 사이의 선 목록. 층 1 → 층 3으로 건너뛰는 선은 층 2에 자리표(dummy)를 둔다."""
    e01 = [(a, u) for a, u in ASSOC if a in LEFT]
    e12 = [(b, s) for b, s in INCLUDE] + [(b, s) for s, b in EXTEND]
    e23 = []
    dummies = []
    for a, u in ASSOC:
        if a in RIGHT:
            if u in SUBS:
                e23.append((u, a))
            else:  # 기본 유스케이스 ↔ 오른쪽 액터: 층 2를 건너뛴다
                d = f"·{u}"
                dummies.append(d)
                e12.append((u, d))
                e23.append((d, a))
    return e01, e12, e23, dummies


def count_cross(edges, order_a, order_b):
    pa = {n: i for i, n in enumerate(order_a)}
    pb = {n: i for i, n in enumerate(order_b)}
    c = 0
    for (a1, b1), (a2, b2) in combinations(edges, 2):
        if (pa[a1] - pa[a2]) * (pb[b1] - pb[b2]) < 0:
            c += 1
    return c


def total_cross(l0, l1, l2, l3):
    e01, e12, e23, _ = layered_edges()
    return (count_cross(e01, l0, l1), count_cross(e12, l1, l2), count_cross(e23, l2, l3))


def barycenter_sweep(l0, l1, l2, l3, rounds=12):
    """층별 무게중심 정렬(이웃 위치의 평균 순으로 줄 세우기)을 되풀이하고,
    이웃한 둘을 맞바꿔 교차가 줄면 바꾼다. (층 그래프 그리기의 표준 휴리스틱)
    돌려주는 것: 마지막 층 순서, 회차별 교차 수 기록."""
    e01, e12, e23, _ = layered_edges()
    layers = [list(l0), list(l1), list(l2), list(l3)]
    nbr = {}
    for k, edges in enumerate((e01, e12, e23)):
        for a, b in edges:
            nbr.setdefault(a, []).append((k + 1, b))
            nbr.setdefault(b, []).append((k, a))

    def npos(k):
        n = len(layers[k])
        return {x: (i / (n - 1) if n > 1 else 0.5) for i, x in enumerate(layers[k])}

    def total():
        return sum(total_cross(*layers))

    log = [total()]
    for _ in range(rounds):
        for k in (1, 2, 3, 2, 1, 0):
            pos = [npos(j) for j in range(4)]
            cur = pos[k]
            key = {}
            for n in layers[k]:
                vs = [pos[j][m] for j, m in nbr.get(n, [])]
                key[n] = sum(vs) / len(vs) if vs else cur[n]
            layers[k] = sorted(layers[k], key=lambda n: (key[n], cur[n]))
        improved = True
        while improved:  # 이웃 맞바꾸기
            improved = False
            for k in range(4):
                for i in range(len(layers[k]) - 1):
                    before = total()
                    layers[k][i], layers[k][i + 1] = layers[k][i + 1], layers[k][i]
                    if total() < before:
                        improved = True
                    else:
                        layers[k][i], layers[k][i + 1] = layers[k][i + 1], layers[k][i]
        log.append(total())
        if log[-1] == 0 or log[-1] == log[-2]:
            break
    return layers, log


def fr_first(u):
    """번호순 배치용: 관련 FR 가운데 가장 작은 번호 (없으면 맨 뒤)."""
    import re
    nums = [int(x) for x in re.findall(r"\d+", USECASES[u][3])] if USECASES[u][3].startswith("FR") else []
    return min(nums) if nums else 999


def final_orders():
    _, _, _, dummies = layered_edges()
    row = {u: i for i, u in enumerate(BASE)}
    l2 = sorted(SUBS + dummies, key=lambda n: row[SUB_ROW[n]] if n in SUB_ROW else row[n[1:]])
    return ["adm", "sch", "pay", "ops", "qa"], BASE, l2, ["portal", "llm"]


def naive_orders():
    _, _, _, dummies = layered_edges()
    l0 = ["sch", "ops", "pay", "adm", "qa"]  # 과제 원문에 나온 순서 + 덧붙인 역할
    l1 = sorted(BASE, key=fr_first)
    l2 = sorted(SUBS, key=fr_first) + sorted(dummies, key=lambda d: fr_first(d[1:]))
    return l0, l1, l2, ["llm", "portal"]


# ─────────────────────────── 3. 좌표 ───────────────────────────
W = 680
XL, XR = 42, 644            # 액터 중심 x
BX0, BX1 = 92, 588          # 시스템 경계
C1, C2 = 270, 494           # 유스케이스 열 중심
RX, RY = 78, 20
PITCH, ZGAP = 52, 14
ROW0 = 146
BAND = (PITCH + ZGAP) / 2   # 구역 띠가 타원 중심에서 위아래로 차지하는 높이

FONT = "Pretendard,'Apple SD Gothic Neo','Noto Sans KR','Malgun Gothic',sans-serif"
INK, GRAY, LINE = "#0E1726", "#667085", "#475467"
COL = {
    "base": ("#EEF4FF", "#2F6FED"),
    "inc": ("#F3F0FF", "#6E56CF"),
    "ext": ("#FFF4E8", "#E8590C"),
}
INC_INK, EXT_INK = "#5B45B8", "#C2410C"


def layout():
    y = {}
    cur = ROW0
    zone_span = []
    for zi, (name, ucs) in enumerate(ZONES):
        if zi:
            cur += ZGAP
        top = cur
        for u in ucs:
            y[u] = cur
            cur += PITCH
        zone_span.append((name, top - BAND, cur - PITCH + BAND, top))
    pos = {u: (C1, y[u]) for u in BASE}
    for s, b in SUB_ROW.items():
        pos[s] = (C2, y[b])
    act = {}
    for a in LEFT:
        ys = [pos[u][1] for x, u in ASSOC if x == a]
        act[a] = (XL, round(sum(ys) / len(ys)))
    act["portal"] = (XR, pos["UC-02"][1])
    act["llm"] = (XR, round((pos["UC-18"][1] + pos["UC-15"][1]) / 2))
    bottom = max(v[1] for v in pos.values()) + BAND
    return pos, act, zone_span, bottom


def ell_point(c, toward):
    """타원 중심 c에서 toward 쪽으로 나갈 때 둘레와 만나는 점."""
    dx, dy = toward[0] - c[0], toward[1] - c[1]
    t = 1 / math.sqrt((dx / RX) ** 2 + (dy / RY) ** 2)
    return (c[0] + dx * t, c[1] + dy * t)


def ell_at(c, deg):
    r = math.radians(deg)
    return (c[0] + RX * math.cos(r), c[1] - RY * math.sin(r))


def sys_box(a, act):
    cx, cy = act[a]
    h = 26 + 12 * len(ACTORS[a][0])
    return (cx - 32, cy - h / 2, 64, h)


def build_lines(pos, act):
    """모든 관계 선을 선분 목록으로. (종류, 점들, 끝 노드 두 개)"""
    out = []
    for a, u in ASSOC:
        c = pos[u]
        if a in LEFT:
            p0 = (act[a][0] + 12, act[a][1])
            # 한 타원에 선이 둘 붙으면(UC-12) 위에서 오는 선은 둘레를 조금 올려 붙인다
            shared = sum(1 for x, v in ASSOC if v == u and x in LEFT) > 1
            p1 = ell_at(c, 157) if (shared and act[a][1] < c[1] - 4) else (c[0] - RX, c[1])
            out.append(("assoc", [p0, p1], (a, u)))
        else:
            bx, by, bw, bh = sys_box(a, act)
            if u in SUBS:
                off = -7 if c[1] < act[a][1] else 7
                out.append(("assoc", [(bx, act[a][1] + off), (c[0] + RX, c[1])], (a, u)))
            elif abs(c[1] - act[a][1]) < 1:  # 같은 줄: 빈 칸을 지나는 수평선
                out.append(("assoc", [(c[0] + RX, c[1]), (bx, c[1])], (a, u)))
            else:  # 멀리 있는 줄: 경계 밖으로 내려와 꺾는다
                out.append(("elbow", [(act[a][0], by + bh), (act[a][0], c[1]), (c[0] + RX, c[1])], (a, u)))
    for b, s in INCLUDE:
        cb, cs = pos[b], pos[s]
        if abs(cb[1] - cs[1]) < 1:
            pts = [(cb[0] + RX, cb[1]), (cs[0] - RX, cs[1])]
        else:
            pts = [ell_point(cb, cs), ell_point(cs, cb)]
        out.append(("include", pts, (b, s)))
    for s, b in EXTEND:
        cb, cs = pos[b], pos[s]
        out.append(("extend", [(cs[0] - RX, cs[1]), (cb[0] + RX, cb[1])], (s, b)))
    return out


# ─────────────────────── 4. 겹침 검사 ───────────────────────
def segs_of(line):
    pts = line[1]
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def seg_cross(s1, s2, eps=1e-6):
    (a, b), (c, d) = s1, s2
    for p in (a, b):
        for q in (c, d):
            if math.hypot(p[0] - q[0], p[1] - q[1]) < 0.75:
                return False  # 끝점을 같이 쓰는 선(같은 액터에서 나온 선)은 교차가 아니다
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    return (o1 * o2 < -eps) and (o3 * o4 < -eps)


def seg_hits_ellipse(seg, c, grow=1.0):
    (a, b) = seg
    ax, ay = (a[0] - c[0]) / (RX * grow), (a[1] - c[1]) / (RY * grow)
    bx, by = (b[0] - c[0]) / (RX * grow), (b[1] - c[1]) / (RY * grow)
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, -(ax * dx + ay * dy) / L2))
    px, py = ax + t * dx, ay + t * dy
    return px * px + py * py < 1 - 1e-9


def seg_hits_rect(seg, r, pad=0.0):
    (a, b) = seg
    x0, y0, x1, y1 = r[0] - pad, r[1] - pad, r[0] + r[2] + pad, r[1] + r[3] + pad
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    return t0 < t1 - 1e-9


def text_w(s, size, bold=False):
    """글자 폭 어림값(px). 한글 0.93em · 영문/숫자 0.56em · 공백 0.26em."""
    w = 0.0
    for ch in s:
        if ch == " ":
            w += 0.26
        elif ord(ch) > 0x2E7F:
            w += 0.93
        elif ch in "·«»":
            w += 0.5
        else:
            w += 0.58 if bold else 0.55
    return w * size


def check(pos, act, lines, labels):
    problems = []
    segs = [(i, s) for i, ln in enumerate(lines) for s in segs_of(ln)]
    for (i, s1), (j, s2) in combinations(segs, 2):
        if i != j and seg_cross(s1, s2):
            problems.append(f"선 교차: {lines[i][2]} × {lines[j][2]}")
    for i, s in segs:
        ends = lines[i][2]
        for u, c in pos.items():
            if u not in ends and seg_hits_ellipse(s, c, grow=1.04):
                problems.append(f"선이 타원을 지남: {ends} → {u}")
        for a in ACTORS:
            if a in ends:
                continue
            r = sys_box(a, act) if ACTORS[a][1] == "system" else (act[a][0] - 30, act[a][1] - 18, 60, 52)
            if seg_hits_rect(s, r, pad=2):
                problems.append(f"선이 액터를 지남: {ends} → {a}")
        for name, r, owner in labels:
            if owner == i:
                continue
            if seg_hits_rect(s, r, pad=1.5):
                problems.append(f"선이 글자를 지남: {ends} → '{name}'")
    for (n1, r1, o1), (n2, r2, o2) in combinations(labels, 2):
        if o1 is not None and o1 == o2:
            continue  # 한 이름표의 두 줄
        if (r1[0] < r2[0] + r2[2] + 1 and r2[0] < r1[0] + r1[2] + 1
                and r1[1] < r2[1] + r2[3] + 1 and r2[1] < r1[1] + r1[3] + 1):
            problems.append(f"글자끼리 겹침: '{n1}' · '{n2}'")
    for name, r, _ in labels:
        for u, c in pos.items():
            # 타원을 단위원으로 펴서, 글자 상자에서 중심에 가장 가까운 점이 원 안인지 본다
            x0, x1 = (r[0] - c[0]) / RX, (r[0] + r[2] - c[0]) / RX
            y0, y1 = (r[1] - c[1]) / RY, (r[1] + r[3] - c[1]) / RY
            px, py = min(max(0, x0), x1), min(max(0, y0), y1)
            if px * px + py * py < 1:
                problems.append(f"글자가 타원에 겹침: '{name}' · {u}")
    for (u, c1), (v, c2) in combinations(pos.items(), 2):
        if abs(c1[0] - c2[0]) < 2 * RX + 8 and abs(c1[1] - c2[1]) < 2 * RY + 6:
            problems.append(f"타원 겹침: {u} · {v}")
    for u, c in pos.items():
        w = text_w(USECASES[u][0], 11.5, bold=True)
        if w > 2 * RX * 0.86:
            problems.append(f"이름이 타원보다 김: {u} ({w:.0f}px)")
    return problems


# ─────────────────────────── 5. SVG ───────────────────────────
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def T(x, y, s, size=11, weight=400, fill=INK, anchor="start", extra=""):
    return (f'<text x="{x:g}" y="{y:g}" font-family="{FONT}" font-size="{size:g}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def stick(cx, cy, s=1.0, stroke="#344054"):
    k = lambda v: f"{v:g}"
    return (f'<g fill="none" stroke="{stroke}" stroke-width="1.5" stroke-linecap="round">'
            f'<circle cx="{k(cx)}" cy="{k(cy - 12 * s)}" r="{k(5 * s)}" fill="#FFFFFF"/>'
            f'<path d="M{k(cx)} {k(cy - 7 * s)} V{k(cy + 4 * s)} M{k(cx - 9 * s)} {k(cy - 3 * s)} H{k(cx + 9 * s)} '
            f'M{k(cx)} {k(cy + 4 * s)} L{k(cx - 7 * s)} {k(cy + 13 * s)} M{k(cx)} {k(cy + 4 * s)} L{k(cx + 7 * s)} {k(cy + 13 * s)}"/></g>')


def oval(cx, cy, kind, rx=RX, ry=RY):
    f, s = COL[kind]
    return f'<ellipse cx="{cx:g}" cy="{cy:g}" rx="{rx:g}" ry="{ry:g}" fill="{f}" stroke="{s}" stroke-width="1.3"/>'


def P(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def render(pos, act, zones, bottom, lines):
    o = []
    labels = []  # (글자, 상자, 그 글자가 붙은 선 번호) — 겹침 검사용
    by1 = bottom + 12
    leg_y = by1 + 14
    H = leg_y + 84 + 14 + 30 + 14
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:g}" viewBox="0 0 {W} {H:g}" role="img">')
    o.append('<title>유스케이스 다이어그램 — 체선료 최적화 Agent(척화비)</title>')
    o.append('<desc>왼쪽에 사람 액터 다섯(기준 정보 관리자, 선박 스케줄러, 체선 지불 부서, 입출항 작업 지시자, 검증 담당자), '
             '오른쪽에 외부 시스템 액터 둘(공공데이터포털 API, LLM API)이 있고, 시스템 경계 안 왼쪽 열에 액터가 직접 시작하는 '
             '유스케이스 14개, 오른쪽 열에 포함·확장 유스케이스 4개가 있다. 선은 서로 교차하지 않는다.</desc>')
    o.append('<defs>'
             '<marker id="ai" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">'
             f'<path d="M1.5 1 L9 5 L1.5 9" fill="none" stroke="{COL["inc"][1]}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>'
             '<marker id="ae" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">'
             f'<path d="M1.5 1 L9 5 L1.5 9" fill="none" stroke="{COL["ext"][1]}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>'
             '</defs>')
    o.append(f'<rect x="0" y="0" width="{W}" height="{H:g}" rx="14" fill="#F6F8FB"/>')

    # 머리글
    o.append(T(24, 37, "유스케이스 다이어그램", 17, 700))
    o.append(T(24, 56, "체선료 최적화 Agent(척화비) · 요구사항서 v1.0(FR 60 · NFR 22) 기준 · 액터 7 · 유스케이스 18 · 선 교차 0", 11, 400, GRAY))
    o.append('<rect x="566" y="22" width="90" height="22" rx="11" fill="#FFF4DF"/>')
    o.append(T(611, 37, "제안 · 팀 확인 전", 11, 600, "#B26A00", "middle"))

    # 시스템 경계와 구역 띠
    by0 = 76
    o.append(f'<rect x="{BX0}" y="{by0}" width="{BX1 - BX0}" height="{by1 - by0:g}" rx="10" fill="#FFFFFF" stroke="#98A2B3" stroke-width="1.3"/>')
    for i, (name, y0, y1, top) in enumerate(zones):
        if i % 2 == 0:
            o.append(f'<rect x="{BX0 + 1}" y="{y0:g}" width="{BX1 - BX0 - 2}" height="{y1 - y0:g}" fill="#F7F9FC"/>')
        o.append(T(C1 - RX + 5, top - 27, name, 9, 700, "#98A2B3", extra=' letter-spacing="0.3"'))
        labels.append((name, (C1 - RX + 5, top - 36, text_w(name, 9, True) + 4, 11), None))
    o.append(T(BX0 + 14, by0 + 22, "체선료 최적화 Agent (척화비)", 12, 700))
    o.append(T(BX1 - 14, by0 + 22, "시스템 경계", 9.5, 500, "#98A2B3", "end"))

    # 선: 연관 → 포함·확장 순서로 그린다 (타원보다 먼저 그려 끝이 깔끔하게)
    for i, (kind, pts, ends) in enumerate(lines):
        if kind == "assoc":
            (x0, y0), (x1, y1) = pts
            o.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{LINE}" stroke-width="1.15" stroke-linecap="round"/>')
        elif kind == "elbow":
            (x0, y0), (x1, y1), (x2, y2) = pts
            r = 9
            o.append(f'<path d="M{x0:.1f} {y0:.1f} L{x1:.1f} {y1 - r:.1f} Q{x1:.1f} {y1:.1f} {x1 - r:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" '
                     f'fill="none" stroke="{LINE}" stroke-width="1.15" stroke-linecap="round"/>')
        else:
            (x0, y0), (x1, y1) = pts
            col, mk, ink, word = ((COL["inc"][1], "ai", INC_INK, "«include»") if kind == "include"
                                  else (COL["ext"][1], "ae", EXT_INK, "«extend»"))
            d = math.hypot(x1 - x0, y1 - y0)
            ex, ey = x1 - (x1 - x0) / d * 1.5, y1 - (y1 - y0) / d * 1.5
            o.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{col}" stroke-width="1.3" '
                     f'stroke-dasharray="4.5 3" stroke-linecap="round" marker-end="url(#{mk})"/>')
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            tw = text_w(word, 9, True)
            if abs(y1 - y0) < 1:
                lx, ly = mx, my - 6
            else:  # 비스듬한 선: 글자를 선 위 오른쪽에 두고, 글자 왼쪽 아래 모서리를 선에서 5px 띄운다
                lx = mx + 16
                slope = (y1 - y0) / (x1 - x0)
                ly = y0 + slope * (lx - tw / 2 - x0) - 5
            o.append(T(lx, ly, word, 9, 600, ink, "middle", ' font-style="italic"'))
            labels.append((word, (lx - tw / 2, ly - 8, tw, 10), i))

    # 유스케이스
    for u, (cx, cy) in pos.items():
        name, kind, tag, _ = USECASES[u]
        o.append(oval(cx, cy, kind))
        idline = u if not tag else f"{u} · {tag}"
        idfill = "#B42318" if tag == "확인 필요" else GRAY
        o.append(T(cx, cy - 5.5, idline, 8.5, 600, idfill, "middle"))
        o.append(T(cx, cy + 8.5, name, 11.5, 600, INK, "middle"))

    # 액터
    for a, (cx, cy) in act.items():
        names, kind, side = ACTORS[a]
        if kind == "human":
            o.append(stick(cx, cy))
            for k, nm in enumerate(names):
                o.append(T(cx, cy + 25 + 11.5 * k, nm, 10.5, 600, INK, "middle"))
                tw = text_w(nm, 10.5, True)
                labels.append((nm, (cx - tw / 2, cy + 25 + 11.5 * k - 9, tw, 11), f"actor:{a}"))
        else:
            x, y, w, h = sys_box(a, act)
            o.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="5" fill="#FFFFFF" stroke="#344054" stroke-width="1.3"/>')
            o.append(T(cx, y + 13, "«actor»", 8.5, 500, GRAY, "middle"))
            for k, nm in enumerate(names):
                o.append(T(cx, y + 26 + 12 * k, nm, 10.5, 600, INK, "middle"))

    # 범례
    o.append(f'<rect x="24" y="{leg_y:g}" width="632" height="84" rx="10" fill="#FFFFFF" stroke="#E2E7EE" stroke-width="1"/>')
    cells = [
        ("actor", "액터 (사람)", "시스템 밖에서 쓰는 역할"),
        ("sys", "액터 (외부 시스템)", "시스템이 부르는 바깥 서비스"),
        ("uc", "유스케이스", "액터가 얻는 결과 하나"),
        ("assoc", "연관 · 실선", "액터가 그 일에 참여한다"),
        ("inc", "«include» 포함", "기본 → 포함 · 항상 같이 실행"),
        ("ext", "«extend» 확장", "확장 → 기본 · 조건이 맞을 때만"),
    ]
    for i, (ic, t1, t2) in enumerate(cells):
        gx = 40 + (i % 3) * 206
        gy = leg_y + 24 + (i // 3) * 38
        if ic == "actor":
            o.append(stick(gx + 20, gy + 0.5, 0.72))
        elif ic == "sys":
            o.append(f'<rect x="{gx + 2}" y="{gy - 10}" width="36" height="20" rx="4" fill="#FFFFFF" stroke="#344054" stroke-width="1.2"/>')
            o.append(T(gx + 20, gy + 3, "«actor»", 7.5, 500, GRAY, "middle"))
        elif ic == "uc":
            o.append(oval(gx + 20, gy, "base", 19, 9.5))
        elif ic == "assoc":
            o.append(f'<line x1="{gx + 2}" y1="{gy}" x2="{gx + 38}" y2="{gy}" stroke="{LINE}" stroke-width="1.3" stroke-linecap="round"/>')
        else:
            col, mk = (COL["inc"][1], "ai") if ic == "inc" else (COL["ext"][1], "ae")
            o.append(f'<line x1="{gx + 2}" y1="{gy}" x2="{gx + 36.5}" y2="{gy}" stroke="{col}" stroke-width="1.3" '
                     f'stroke-dasharray="4.5 3" stroke-linecap="round" marker-end="url(#{mk})"/>')
        o.append(T(gx + 50, gy - 2.5, t1, 10.5, 700))
        o.append(T(gx + 50, gy + 10.5, t2, 9.5, 400, GRAY))

    fy = leg_y + 84 + 18
    o.append(T(28, fy, "타원의 위아래 순서는 실행 순서가 아니다. 순서와 조건은 유스케이스 시나리오에 적는다.", 9.5, 400, GRAY))
    o.append(T(28, fy + 14, "FR-60(업무 단계 안내)과 NFR 22개는 타원으로 그리지 않고 시나리오의 사전조건 · 특별 요구사항에 적는다.", 9.5, 400, GRAY))
    o.append("</svg>")
    return "\n".join(o), labels, H


# ─────────────────────────── 6. 실행 ───────────────────────────
def main():
    names = {**{a: "".join(v[0]) for a, v in ACTORS.items()}, **{u: u for u in USECASES}}
    nv = naive_orders()
    fn = final_orders()
    c_nv, c_fn = total_cross(*nv), total_cross(*fn)
    swept, log = barycenter_sweep(*nv)
    print("층별 선 교차 수  (층0–1, 층1–2, 층2–3) = 합계")
    print(f"  번호순 배치      {c_nv} = {sum(c_nv)}")
    print(f"  무게중심 정렬    회차별 합계 {log}")
    print(f"  최종 배치        {c_fn} = {sum(c_fn)}")
    print("  무게중심 정렬 뒤 층 1 순서:", " ".join(swept[1]))

    pos, act, zones, bottom = layout()
    lines = build_lines(pos, act)
    svg, labels, H = render(pos, act, zones, bottom, lines)
    problems = check(pos, act, lines, labels)
    n_assoc = len(ASSOC)
    print(f"그림: 액터 {len(ACTORS)} · 유스케이스 {len(USECASES)} · 연관 {n_assoc} · include {len(INCLUDE)} · extend {len(EXTEND)} · 크기 {W}×{H:g}")
    print(f"좌표 검사: 문제 {len(problems)}건")
    for p in problems:
        print("  -", p)

    out = os.path.join(HERE, "usecase-diagram.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg + "\n")
    print("저장:", os.path.relpath(out))

    if "--png" in sys.argv:
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if not os.path.exists(chrome):
            chrome = shutil.which("google-chrome") or shutil.which("chromium") or ""
        if not chrome:
            print("PNG: Chrome을 찾지 못해 건너뜀")
        else:
            png = os.path.join(HERE, "usecase-diagram.png")
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--force-device-scale-factor=2", f"--window-size={W},{int(H)}",
                            f"--screenshot={png}", "file://" + out],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("저장:", os.path.relpath(png))
    return 1 if (problems or sum(c_fn)) else 0


if __name__ == "__main__":
    sys.exit(main())
