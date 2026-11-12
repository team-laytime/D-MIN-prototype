"""접안 계획 수리계획법 — 주제 설명 문서(과제 원문) 기준. 설명은 docs/13a-math-programming-brief.md.

과제 원문에 적힌 것만으로 세운 모델이다(멘토링 PPT의 세부 규칙은 milp_berth_plan.py).
  계산 근거    도착 일시 · 허용 시간 · 예상 작업 종료 시간 · 하루 체선료                        (원문 3절 기능 1)
  후보의 제약  부두별 접안 가능 제품 · 조석 · 일출·일몰 · 기상 + 한 부두에는 한 척              (원문 3절 기능 2)
  계약 규칙    허용 시간을 언제부터 세는지(통지시간), 기상으로 기다린 시간을 빼 주는지(공제비율)
               → 코드에 박지 않고 선박(계약)마다 값으로 읽는다                                   (원문 6절)
  검증         손계산 정답과 일치 · 도착 순서 기준안보다 줄인 금액 · 제약 위반 0                 (원문 3절 기능 5)

  변수   u[i,b,k] 시간창선택(0/1) · y[i,j] 앞뒤순서(0/1) · t[i] 접안시각 · P[i] 개시시각 · D[i] 체선시간
         O[i,w] 기상대기(기상 구간 w와 겹친 대기 시간) · β[i,w] 기상 스위치(0/1) · x[i,b] 선석배정 = Σ_k u[i,b,k]
  목적   min Σ_i 요율_i ÷ 24 × D[i]
  제약   (1) Σ_b Σ_k u[i,b,k] = 1                                    한 척은 시간창 하나(갈 수 없는 부두는 변수가 없다)
         (2) Σ 창시작·u ≤ t[i] ≤ Σ 창끝·u                             접안시각은 고른 창 안 — 조석·일출·일몰·기상·도착·앞 배
         (3) t[j] ≥ t[i] + 작업_i + 간격 − M(3 − y[i,j] − x[i,b] − x[j,b])   같은 부두에서 겹치지 않기
             t[i] ≥ t[j] + 작업_j + 간격 − M(2 + y[i,j] − x[i,b] − x[j,b])
         (4) P[i] ≤ t[i] ,  P[i] ≤ 도착_i + 통지시간_i                 개시시각 = 둘 중 이른 때
         (5) D[i] ≥ t[i] + 작업_i − P[i] − 허용시간_i − 공제비율_i × Σ_w O[i,w] ,  D[i] ≥ 0
         (6) O[i,w] ≤ 기상 구간 w ∩ [P[i], t[i]) 의 길이               개시 뒤 접안 전까지 기상으로 기다린 시간

실행 (scipy가 있는 파이썬으로):
  python3 scripts/milp_brief.py                  정답 SC-01, 가상 시나리오 BR-01, 무작위 사례를 완전 탐색·기준안과 비교
  python3 scripts/milp_brief.py --walk BR-01     파라미터 → 시간창 → 변수 값 → 제약식 숫자 대입
  python3 scripts/milp_brief.py --lp SC-01       솔버에 넣는 모델 전문(LP 형식)
"""
from __future__ import annotations

import argparse
import itertools
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import milp_core  # noqa: E402
from milp_core import INF, Model  # noqa: E402

DAY, H = 1440, 60


# ----------------------------------------------------------------------------- 입력 (분 단위 정수, 시각 0 = 첫날 00:00)

@dataclass(frozen=True)
class Vessel:
    name: str
    product: str                 # 제품 — 부두별 접안 가능 제품과 맞춘다
    arrive: int                  # 도착 일시(준비 완료 통지 시각)
    work: int                    # 접안 → 호스 분리(예상 작업 종료)까지
    laytime: int                 # 허용 시간
    rate: int                    # 하루 체선료(USD)
    notice: int = 6 * H          # 통지시간: '도착 + 통지시간'과 접안 중 이른 때부터 허용 시간을 센다 (계약)
    weather_ratio: float = 0.0   # 기상으로 기다린 시간을 빼 주는 비율 (계약: 0 = 안 뺌, 0.5 = 절반, 1 = 전부)
    draft: float = 0.0           # 흘수 — 부두의 조석 기준 이상이면 조석 시간창에서만 접안
    daylight_only: bool = False  # 일출~일몰에만 접안하는 배


@dataclass(frozen=True)
class Berth:
    name: str
    products: tuple              # 접안 가능 제품
    free_at: int = -10 ** 9      # 현재 접안 중인 선박이 부두를 비우는 시각
    tide_draft: float = None     # 이 흘수 이상인 배는 조석 시간창에서만
    tide_windows: tuple = ()     # ((시작, 끝), …)


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    vessels: tuple
    berths: tuple
    end: int                     # 계획 기간 끝(이 뒤로는 접안하지 않는다)
    sun: tuple = ()              # 날마다 (일출, 일몰) — 그날 00:00부터 지난 분
    weather: tuple = ()          # 기상 악화 구간 ((시작, 끝), …) — 그동안 모든 부두 접안 불가
    gap_out: int = H             # 호스 분리 → 부두 비움
    gap_in: int = H              # 부두 비움 → 다음 배 접안 완료

    @property
    def gap(self):
        return self.gap_out + self.gap_in


def hm(m):
    """분 → 'D2 01:00' (D1 = 첫날)."""
    return f"D{m // DAY + 1} {m % DAY // 60:02d}:{m % 60:02d}"


def hh(m):
    h = m / 60
    return f"{h:.2f}".rstrip("0").rstrip(".") + "h"


def usd(x):
    return f"{x:,.2f}"


SUN_ULSAN_NOV = ((413, 1041), (414, 1040), (415, 1039), (416, 1039), (417, 1038), (418, 1037), (419, 1037))   # 11/10~ 계산값(NOAA 식) [가정]


def sc01():
    """손계산 정답 SC-01 (docs/requirements/09-first-steps.md 3-3절): 두 척·한 부두, 제약 없음 → 도착 순서 52,000 / Y 먼저 6,000."""
    return Scenario("SC-01", "두 척·한 부두 (손계산 정답)",
                    (Vessel("X", "화학", 2 * H, 16 * H, 24 * H, 48000), Vessel("Y", "화학", 4 * H, 10 * H, 12 * H, 96000)),
                    (Berth("부두", ("화학",), free_at=6 * H),), end=6 * DAY)


def br01():
    """가상 시나리오 BR-01: 부두 3곳·선박 7척, 원문의 제약 네 가지(접안 가능 제품·조석·일출·일몰·기상)가 모두 걸린다."""
    d = DAY
    vessels = (
        Vessel("V1", "원유", 4 * H, 30 * H, 36 * H, 52000, weather_ratio=0.5, draft=20.5, daylight_only=True),
        Vessel("V2", "원유", 14 * H, 22 * H, 36 * H, 38000, weather_ratio=0.5, draft=17.0, daylight_only=True),
        Vessel("V3", "경유", 7 * H, 14 * H, 24 * H, 22000, weather_ratio=0.5),
        Vessel("V4", "휘발유", 9 * H, 16 * H, 24 * H, 28000, weather_ratio=0.5),
        Vessel("V5", "경유", d + 1 * H, 12 * H, 12 * H, 36000),
        Vessel("V6", "경유", 22 * H, 14 * H, 36 * H, 16000, weather_ratio=0.5),
        Vessel("V7", "화학", d + 6 * H, 10 * H, 18 * H, 18000, weather_ratio=0.5),
    )
    berths = (
        Berth("1부두", ("경유", "휘발유"), free_at=15 * H),
        Berth("2부두", ("경유", "화학")),
        Berth("부이", ("원유",), tide_draft=20.0,
              tide_windows=((3 * H + 10, 7 * H + 10), (15 * H + 35, 19 * H + 35), (d + 4 * H, d + 8 * H), (d + 16 * H + 25, d + 20 * H + 25),
                            (2 * d + 4 * H + 50, 2 * d + 8 * H + 50), (2 * d + 17 * H + 15, 2 * d + 21 * H + 15),
                            (3 * d + 5 * H + 40, 3 * d + 9 * H + 40), (3 * d + 18 * H + 5, 3 * d + 22 * H + 5))),
    )
    return Scenario("BR-01", "부두 3곳·선박 7척, 강풍 예보가 있는 날 (가상)", vessels, berths, end=6 * DAY,
                    sun=SUN_ULSAN_NOV, weather=((d + 9 * H, 2 * d + 3 * H),))


SCENARIOS = {"SC-01": sc01, "BR-01": br01}


# ----------------------------------------------------------------------------- 규칙 (모델과 따로 쓴다 — 검산용)

def allowed(sc: Scenario, v: Vessel, b: Berth, t: int):
    """배 v가 부두 b에 시각 t에 접안해도 되는가. 안 되면 (False, 그 이유가 풀리는 가장 이른 시각, 이유)."""
    if v.product not in b.products:
        return False, None, "접안 가능 제품"
    if t < v.arrive:
        return False, v.arrive, "도착 전"
    if t < b.free_at + sc.gap_in:
        return False, b.free_at + sc.gap_in, "앞 배"
    for s, e in sc.weather:
        if s <= t < e:
            return False, e, "기상"
    if v.daylight_only:
        rise, sset = sc.sun[min(t // DAY, len(sc.sun) - 1)]
        m = t % DAY
        if m < rise:
            return False, t - m + rise, "일출·일몰"
        if m > sset:
            nxt = sc.sun[min(t // DAY + 1, len(sc.sun) - 1)][0]
            return False, t - m + DAY + nxt, "일출·일몰"
    if b.tide_draft is not None and v.draft >= b.tide_draft:
        if not any(s <= t <= e for s, e in b.tide_windows):
            later = [s for s, e in b.tide_windows if s > t]
            return False, (later[0] if later else None), "조석"
    return True, t, ""


def earliest(sc: Scenario, v: Vessel, b: Berth, ready: int):
    """ready 이후 접안할 수 있는 가장 이른 시각(밀어내기). 없으면 None."""
    t = max(ready, v.arrive)
    for _ in range(1000):
        ok, nxt, _why = allowed(sc, v, b, t)
        if ok:
            return t if t <= sc.end else None
        if nxt is None or nxt > sc.end:
            return None
        t = nxt
    return None


def price(sc: Scenario, v: Vessel, t: int):
    """접안시각 t일 때 (개시, 정박종료, 호스 분리, 기상대기, 체선시간(분), 체선료(USD))."""
    start = min(v.arrive + v.notice, t)
    end = start + v.laytime
    hose = t + v.work
    wait = sum(max(0, min(e, t) - max(s, start)) for s, e in sc.weather)
    dem = max(0.0, hose - end - v.weather_ratio * wait)
    return start, end, hose, wait, dem, dem * v.rate / 1440


def decode(sc: Scenario, orders: dict):
    """부두별 순서 {부두 이름: [배, …]} → 가장 이르게 붙인 일정 {배 이름: (부두, 접안시각)}. 불가면 None."""
    bmap = {b.name: b for b in sc.berths}
    out = {}
    for bname, seq in orders.items():
        b, ready = bmap[bname], -10 ** 9
        for v in seq:
            t = earliest(sc, v, b, ready)
            if t is None:
                return None
            out[v.name] = (bname, t)
            ready = t + v.work + sc.gap
    return out


def total(sc: Scenario, sched: dict):
    vmap = {v.name: v for v in sc.vessels}
    return sum(price(sc, vmap[n], t)[5] for n, (_, t) in sched.items())


def check(sc: Scenario, sched: dict):
    """독립 검산: 일정이 제약을 어긴 곳의 목록(빈 목록이면 위반 0)."""
    vmap, bmap = {v.name: v for v in sc.vessels}, {b.name: b for b in sc.berths}
    bad = [f"{v.name} 미배정" for v in sc.vessels if v.name not in sched]
    for n, (bname, t) in sched.items():
        ok, _nxt, why = allowed(sc, vmap[n], bmap[bname], t)
        if not ok:
            bad.append(f"{n}: {bname} {hm(t)} — {why}")
        if t > sc.end:
            bad.append(f"{n}: 계획 기간 밖")
    for bname in bmap:
        seq = sorted((t, n) for n, (bn, t) in sched.items() if bn == bname)
        for (t1, n1), (t2, n2) in zip(seq, seq[1:]):
            if t2 < t1 + vmap[n1].work + sc.gap:
                bad.append(f"{bname}: {n1}과 {n2}가 겹침")
    return bad


def signature(sched: dict):
    per = {}
    for n, (b, t) in sorted(sched.items(), key=lambda kv: (kv[1][1], kv[0])):
        per.setdefault(b, []).append(n)
    return tuple(sorted((b, tuple(ns)) for b, ns in per.items()))


def brute_force(sc: Scenario, k=3):
    """완전 탐색: 부두 배정 × 부두별 순서를 전부. 접안이 늦어질수록 체선료가 줄지 않으므로 가장 이르게 붙인 일정이 그 순서의 최선이다."""
    best = {}
    choices = [[b for b in sc.berths if v.product in b.products] for v in sc.vessels]
    for assign in itertools.product(*choices):
        groups = {}
        for v, b in zip(sc.vessels, assign):
            groups.setdefault(b.name, []).append(v)
        per = []
        for bname, grp in groups.items():
            opts = []
            for perm in itertools.permutations(grp):
                sched = decode(sc, {bname: perm})
                if sched is not None:
                    opts.append((total(sc, sched), sched))
            per.append(sorted(opts, key=lambda o: o[0])[:k * 4])
        if any(not o for o in per):
            continue
        for combo in itertools.product(*per):
            sched = {}
            for _c, sub in combo:
                sched.update(sub)
            cost = sum(c for c, _ in combo)
            sig = signature(sched)
            if sig not in best or cost < best[sig][0] - 1e-9:
                best[sig] = (cost, sched)
    return sorted(best.values(), key=lambda o: o[0])[:k]


def fcfs(sc: Scenario):
    """기준안: 도착 순서대로, 가장 빨리 댈 수 있는 부두에(동률이면 부두 표 순서)."""
    ready = {b.name: -10 ** 9 for b in sc.berths}
    sched = {}
    for v in sorted(sc.vessels, key=lambda v: (v.arrive, v.name)):
        opts = [(t, n, b) for n, b in enumerate(sc.berths) if v.product in b.products
                for t in [earliest(sc, v, b, ready[b.name])] if t is not None]
        if not opts:
            return None
        t, _n, b = min(opts)
        sched[v.name] = (b.name, t)
        ready[b.name] = t + v.work + sc.gap
    return sched


# ----------------------------------------------------------------------------- 시간창과 모델

def windows(sc: Scenario, v: Vessel, b: Berth):
    """배 v가 부두 b에 접안할 수 있는 시간창(닫힌 정수 구간 목록). 규칙마다 금지 구간을 내고 그 나머지를 남긴다."""
    if v.product not in b.products:
        return []
    lo, hi = max(v.arrive, b.free_at + sc.gap_in), sc.end
    fb = list(sc.weather)                                               # 기상: 그동안 접안 불가
    if v.daylight_only:                                                 # 일출·일몰: 일몰 뒤 ~ 다음 일출 전
        for d in range(-1, hi // DAY + 2):
            sset = sc.sun[max(0, min(d, len(sc.sun) - 1))][1]
            rise = sc.sun[max(0, min(d + 1, len(sc.sun) - 1))][0]
            fb.append((d * DAY + sset + 1, (d + 1) * DAY + rise))
    if b.tide_draft is not None and v.draft >= b.tide_draft:            # 조석: 시간창 밖
        cur = -10 ** 9
        for s, e in sorted(b.tide_windows):
            fb.append((cur, s))
            cur = e + 1
        fb.append((cur, 10 ** 9))
    iv = sorted((max(s, lo), min(e, hi + 1)) for s, e in fb if e > lo and s <= hi)
    out, cur = [], lo
    for s, e in iv:
        if s > cur:
            out.append((cur, s - 1))
        cur = max(cur, e)
    if cur <= hi:
        out.append((cur, hi))
    return out


@dataclass
class Built:
    m: Model
    sc: Scenario
    win: dict
    u: dict
    y: dict
    t: dict
    P: dict
    D: dict
    O: dict


def build(sc: Scenario) -> Built:
    m = Model()
    V, B = {v.name: v for v in sc.vessels}, {b.name: b for b in sc.berths}
    win = {(i, b): windows(sc, V[i], B[b]) for i in V for b in B}
    elig = {i: [b for b in B if win[i, b]] for i in V}
    for i in V:
        if not elig[i]:
            raise RuntimeError(f"{i}: 댈 수 있는 부두·시간창이 없음")
    tlo = {i: min(w[0] for b in elig[i] for w in win[i, b]) for i in V}
    thi = {i: max(w[1] for b in elig[i] for w in win[i, b]) for i in V}
    pad = milp_core.M_PAD
    u, y, t, P, D, O, beta = {}, {}, {}, {}, {}, {}, {}
    for i, v in V.items():
        for b in elig[i]:
            for k in range(len(win[i, b])):
                u[i, b, k] = m.binary(f"u[{i},{b},{k + 1}]")
        t[i] = m.time(f"t[{i}]", tlo[i], thi[i])
        P[i] = m.time(f"P[{i}]", 0, v.arrive + v.notice)                 # (4) P ≤ 도착 + 통지시간
        D[i] = m.time(f"D[{i}]", 0, INF, cost=v.rate / 1440)
        if v.weather_ratio > 0:
            for n, (s, e) in enumerate(sc.weather):
                O[i, n] = m.time(f"O[{i},{n + 1}]", 0, e - s)
                beta[i, n] = m.binary(f"b[{i},{n + 1}]")

    def x(i, b, a=1.0):
        return [(u[i, b, k], a) for k in range(len(win[i, b]))]

    for i, v in V.items():
        allw = [(b, k, w) for b in elig[i] for k, w in enumerate(win[i, b])]
        m.add([(u[i, b, k], 1) for b, k, _ in allw], 1, 1, f"C1[{i}]")                                        # (1)
        m.add([(t[i], 1)] + [(u[i, b, k], -w[0]) for b, k, w in allw], lo=0, name=f"C2a[{i}]")                 # (2)
        m.add([(t[i], 1)] + [(u[i, b, k], -w[1]) for b, k, w in allw], hi=0, name=f"C2b[{i}]")
        m.add([(P[i], 1), (t[i], -1)], hi=0, name=f"C4[{i}]")                                                  # (4) P ≤ t
        m.add([(D[i], 1), (t[i], -1), (P[i], 1)] + [(O[i, n], v.weather_ratio) for n in range(len(sc.weather)) if (i, n) in O],
              lo=v.work - v.laytime, name=f"C5[{i}]")                                                          # (5)
        for n, (s, e) in enumerate(sc.weather):                                                                # (6)
            if (i, n) not in O:
                continue
            ov, bv = O[i, n], beta[i, n]
            m.add([(ov, 1), (bv, -(e - s))], hi=0, name=f"C6a[{i}|{n + 1}]")
            M1 = max(0, s - tlo[i]) + pad
            m.add([(ov, 1), (t[i], -1), (bv, M1)], hi=-s + M1, name=f"C6b[{i}|{n + 1}]")                       # O ≤ t − 기상시작
            M2 = max(0, v.arrive + v.notice - e) + pad
            m.add([(ov, 1), (P[i], 1), (bv, M2)], hi=e + M2, name=f"C6c[{i}|{n + 1}]")                         # O ≤ 기상종료 − P
    for i, j in itertools.combinations(list(V), 2):                                                            # (3)
        same = [b for b in elig[i] if b in elig[j]]
        if not same:
            continue
        yv = y[i, j] = m.binary(f"y[{i}<{j}]")
        di, dj = V[i].work + sc.gap, V[j].work + sc.gap
        M1, M2 = max(0, thi[i] - tlo[j]) + di + pad, max(0, thi[j] - tlo[i]) + dj + pad
        for b in same:
            m.add([(t[j], 1), (t[i], -1), (yv, -M1)] + x(i, b, -M1) + x(j, b, -M1), lo=di - 3 * M1, name=f"C3a[{i}<{j}|{b}]")
            m.add([(t[i], 1), (t[j], -1), (yv, M2)] + x(i, b, -M2) + x(j, b, -M2), lo=dj - 2 * M2, name=f"C3b[{j}<{i}|{b}]")
    return Built(m, sc, win, u, y, t, P, D, O)


@dataclass
class Sol:
    status: str
    obj: float                   # MILP 목적함수(USD)
    sched: dict                  # {배: (부두, 접안시각)}
    xs: object
    seconds: float
    agree: bool

    def repriced(self, sc):      # 규칙 함수로 다시 계산한 합계
        return total(sc, self.sched)


def solve(B: Built, cuts=(), time_limit=120.0):
    """1단계: 총 체선료 최소. 2단계: 같은 배정·순서·금액 안에서 가장 이른 시각."""
    m, sc = B.m, B.sc
    t0 = time.perf_counter()
    res = m.solve(extra=cuts, time_limit=time_limit)
    if res.x is None:
        return None
    star, xs = res.fun, res.x
    fix = {B.y[k]: round(xs[B.y[k]]) for k in B.y}
    for (i, b), ws in B.win.items():
        if ws and not any(xs[B.u[i, b, k]] > 0.5 for k in range(len(ws))):
            fix.update({B.u[i, b, k]: 0 for k in range(len(ws))})
    c2 = np.zeros(len(m.names))
    for i in B.t:
        c2[B.t[i]] = 1.0
    rate = {B.D[v.name]: v.rate / 1440 for v in sc.vessels}
    res2 = m.solve(cost=c2, extra=list(cuts) + [(rate, -INF, star + max(1e-6, 1e-9 * abs(star)), "COST", 1.0)], fix=fix, time_limit=time_limit)
    if res2.x is not None and res2.status == 0:
        xs = res2.x
    sched = {}
    for v in sc.vessels:
        (b,) = [b for (i, b), ws in B.win.items() if i == v.name and ws and any(xs[B.u[i, b, k]] > 0.5 for k in range(len(ws)))]
        sched[v.name] = (b, int(round(xs[B.t[v.name]])))
    return Sol("최적" if res.status == 0 else "제한시간(최선)", star, sched, xs, time.perf_counter() - t0, res.agree)


def nogood(B: Built, sol: Sol):
    """'이 배정·순서는 빼고' 한 줄."""
    coefs, n, const = {}, 0, 0
    for i, (b, _t) in sol.sched.items():
        for k in range(len(B.win[i, b])):
            coefs[B.u[i, b, k]] = 1
        n += 1
    for _b, seq in signature(sol.sched):
        for a, c in zip(seq, seq[1:]):
            if (a, c) in B.y:
                coefs[B.y[a, c]] = coefs.get(B.y[a, c], 0) + 1
            else:
                coefs[B.y[c, a]] = coefs.get(B.y[c, a], 0) - 1
                const += 1
            n += 1
    return (coefs, -INF, n - 1 - const, "NOGOOD", 1.0)


def top_k(B: Built, k=3, time_limit=120.0):
    cuts, sols = [], []
    for _ in range(k):
        s = solve(B, cuts, time_limit)
        if s is None:
            break
        sols.append(s)
        cuts.append(nogood(B, s))
    return sols


# ----------------------------------------------------------------------------- 출력

def compare(sc: Scenario, k=3, time_limit=120.0, quiet=False):
    """MILP 상위 k개 vs 완전 탐색 상위 k개, 기준안, 제약 위반."""
    B = build(sc)
    t0 = time.perf_counter()
    sols = top_k(B, k, time_limit)
    el = time.perf_counter() - t0
    bf = brute_force(sc, k)
    base = fcfs(sc)
    mine = [round(s.repriced(sc), 2) for s in sols]
    ref = [round(c, 2) for c, _ in bf]
    viol = sum(len(check(sc, s.sched)) for s in sols)
    exact = all(abs(s.obj - s.repriced(sc)) < 0.01 for s in sols)
    ok = mine == ref and viol == 0 and exact and all(s.status == "최적" for s in sols)
    row = dict(id=sc.name, n=len(sc.vessels), berths=len(sc.berths), vars=len(B.m.names), bins=sum(B.m.integ), rows=len(B.m.rows),
               base=None if base is None else round(total(sc, base), 2), mine=mine, ref=ref, viol=viol, ok=ok, sec=round(el, 2),
               disagree=B.m.disagreements)
    if not quiet:
        saved = "" if base is None else f" · 기준안 대비 −{usd(row['base'] - mine[0])}"
        print(f"{sc.name:<8}{row['n']:>3}척 {row['berths']}부두  변수 {row['vars']:>3}(0/1 {row['bins']:>3}) 제약 {row['rows']:>3}  "
              f"기준안 {usd(row['base']) if base else '성립 안 함':>11}  MILP {' / '.join(usd(c) for c in mine):<34} 완전 탐색 {' / '.join(usd(c) for c in ref):<34}"
              f" 위반 {viol} {'일치' if ok else '다름 ←'}{saved}")
    return row, B, sols


def walk(name, time_limit=120.0):
    sc = SCENARIOS[name]()
    vmap, bmap = {v.name: v for v in sc.vessels}, {b.name: b for b in sc.berths}
    row, B, sols = compare(sc, 3, time_limit, quiet=True)
    print(f"== {sc.name} — {sc.title}: 변수 {row['vars']}개(0/1 {row['bins']}개), 제약 {row['rows']}줄. 시각은 'D1 07:00'(D1 = 첫날)\n")
    print("① 파라미터 (주어지는 값)")
    for b in sc.berths:
        extra = (f" · {hm(b.free_at)}에 앞 배가 비움" if b.free_at > -10 ** 8 else "") + (f" · 흘수 {b.tide_draft:g} m 이상은 조석 시간창에서만" if b.tide_draft else "")
        print(f"   부두 {b.name}: 접안 가능 제품 {', '.join(b.products)}{extra}")
    for s, e in sc.weather:
        print(f"   기상 악화 {hm(s)} ~ {hm(e)}: 그동안 접안 불가")
    print(f"   간격: 호스 분리 → 부두 비움 {hh(sc.gap_out)}, 부두 비움 → 다음 배 접안 {hh(sc.gap_in)}")
    for v in sc.vessels:
        tags = [f"흘수 {v.draft:g} m" if v.draft else "", "일출~일몰에만 접안" if v.daylight_only else "",
                f"기상 대기 {v.weather_ratio:g}배 공제" if v.weather_ratio else "기상 공제 없음"]
        print(f"   {v.name}({v.product}): 도착 {hm(v.arrive)} · 작업 {hh(v.work)} · 허용시간 {hh(v.laytime)} · 하루 ${v.rate:,}(시간당 ${v.rate / 24:,.0f}) · "
              f"통지시간 {hh(v.notice)} → 개시 기준 {hm(v.arrive + v.notice)} · {' · '.join(t for t in tags if t)}")
        for b in sc.berths:
            ws = B.win[v.name, b.name]
            if ws:
                print(f"      {b.name}의 시간창: " + " | ".join(f"{k + 1}) {hm(lo)}~{hm(hi)}" for k, (lo, hi) in enumerate(ws[:6])) + (" | …" if len(ws) > 6 else ""))
    base = fcfs(sc)
    if base:
        print(f"\n② 기준안(도착 순서): 합계 ${usd(total(sc, base))} — " + " | ".join(f"{b}: {' → '.join(ns)}" for b, ns in signature(base)))
    for rank, s in enumerate(sols, 1):
        print(f"\n③ {rank}안 — MILP 목적함수 ${usd(s.obj)} · 규칙 함수로 다시 ${usd(s.repriced(sc))} · 위반 {len(check(sc, s.sched))}건 · {s.status} {s.seconds:.2f}초")
        print("   부두별 순서: " + " | ".join(f"{b}: {' → '.join(ns)}" for b, ns in signature(s.sched)))
        for n, (bname, t) in sorted(s.sched.items(), key=lambda kv: (kv[1][1], kv[0])):
            v = vmap[n]
            start, end, hose, wait, dem, cost = price(sc, v, t)
            k = next(k for k, (lo, hi) in enumerate(B.win[n, bname]) if lo <= t <= hi)
            line = (f"   {n}: x[{n},{bname}] = 1 · u[{n},{bname},{k + 1}] = 1 · 접안시각 t = {hm(t)} · 개시 P = {hm(start)} · 정박종료 {hm(end)} · 호스 분리 {hm(hose)}")
            if wait:
                line += f" · 기상대기 O = {hh(wait)}"
            print(line + f" · 체선시간 D = {hh(dem)} → ${usd(cost)}")
        if rank == 1:
            print("   제약식에 대입:")
            for (i, j), yv in B.y.items():
                a, c = (i, j) if round(s.xs[yv]) else (j, i)
                (ba, ta), (bc, tc) = s.sched[a], s.sched[c]
                if ba == bc:
                    need = ta + vmap[a].work + sc.gap
                    print(f"     (3) {c} 접안시각 {hm(tc)} ≥ {a} 접안시각 {hm(ta)} + 작업 {hh(vmap[a].work)} + 간격 {hh(sc.gap)} = {hm(need)}"
                          f"{'  ← 등호' if tc == need else f'  (여유 {hh(tc - need)})'}")
            for n, (bname, t) in sorted(s.sched.items(), key=lambda kv: (kv[1][1], kv[0])):
                v = vmap[n]
                start, end, hose, wait, dem, cost = price(sc, v, t)
                lo, hi = next(w for w in B.win[n, bname] if w[0] <= t <= w[1])
                why = allowed(sc, v, bmap[bname], t - 1)[2] if t - 1 >= 0 else ""
                print(f"     (2) {n}: 창시작 {hm(lo)} ≤ 접안시각 {hm(t)} ≤ 창끝 {hm(hi)}" + (f"  ← 등호(바로 앞은 '{why}' 때문에 불가)" if t == lo and why else ""))
                extra = f" − {v.weather_ratio:g} × 기상대기 {hh(wait)[:-1]}" if wait and v.weather_ratio else ""
                print(f"     (4)(5) {n}: 개시 = min(도착 + 통지시간 {hm(v.arrive + v.notice)}, 접안 {hm(t)}) = {hm(start)} · "
                      f"체선시간 = max(0, 접안 {t / 60:g} + 작업 {hh(v.work)[:-1]} − 개시 {start / 60:g} − 허용시간 {hh(v.laytime)[:-1]}{extra}) = {hh(dem)}"
                      f" → × 시간당 ${v.rate / 24:,.0f} = ${usd(cost)}")
    print(f"\n④ 완전 탐색(배정 × 순서 전부): " + " / ".join(usd(c) for c, _ in brute_force(sc, 3)) + f" → MILP와 {'같다' if row['ok'] else '다르다'}")


def random_scenario(rng, n):
    """무작위 가상 사례: 부두 2~3곳, 조석·일출·일몰·기상이 섞인다."""
    d = DAY
    prods = ["경유", "휘발유", "화학"]
    berths = [Berth("1부두", ("경유", "휘발유"), free_at=rng.choice([-10 ** 9, 6 * H, 15 * H])), Berth("2부두", ("경유", "화학"))]
    if rng.random() < 0.6:
        berths.append(Berth("3부두", ("휘발유", "화학", "경유"), tide_draft=12.0,
                            tide_windows=tuple((k * d // 2 + 3 * H, k * d // 2 + 8 * H) for k in range(12))))
    weather = ((rng.randint(6, 40) * H, 0),) if rng.random() < 0.6 else ()
    weather = tuple((s, s + rng.choice([6, 10, 14]) * H) for s, _ in weather)
    vessels = []
    for i in range(n):
        vessels.append(Vessel(f"R{i}", rng.choice(prods), rng.randint(0, 40) * H + rng.choice([0, 30]), rng.choice([6, 8, 10, 14, 18]) * H,
                              rng.choice([6, 12, 18, 24, 36]) * H, rng.choice([12000, 24000, 36000, 48000]),
                              notice=rng.choice([0, 6 * H]), weather_ratio=rng.choice([0.0, 0.5, 1.0]),
                              draft=rng.choice([8.0, 11.0, 13.0]), daylight_only=rng.random() < 0.3))
    return Scenario("rand", "무작위", tuple(vessels), tuple(berths), end=7 * DAY, sun=SUN_ULSAN_NOV, weather=weather)


def main():
    ap = argparse.ArgumentParser(description="접안 계획 MILP — 주제 설명 문서 기준")
    ap.add_argument("--walk", metavar="ID", choices=sorted(SCENARIOS), help="한 문제를 파라미터·시간창·변수·제약식 숫자까지")
    ap.add_argument("--lp", metavar="ID", choices=sorted(SCENARIOS), help="솔버에 넣는 모델 전문(LP 형식)")
    ap.add_argument("--random", type=int, default=200, metavar="N", help="무작위 사례 수(기본 200)")
    ap.add_argument("--seed", type=int, default=20261110)
    a = ap.parse_args()
    if a.lp:
        B = build(SCENARIOS[a.lp]())
        print(B.m.to_lp(f"{a.lp} — 접안 계획 MILP, 주제 설명 문서 기준 (솔버에 넣는 그대로: 시각 단위는 시간, 시각 0 = 첫날 00:00, 큰 수 M에는 하루 여유 포함)\n"
                        "u 시간창선택 · y 앞뒤순서 · t 접안시각 · P 개시시각 · D 체선시간 · O 기상대기 · b 기상 스위치"))
        return 0
    if a.walk:
        walk(a.walk)
        return 0
    print("[주제 설명 문서 기준] MILP 상위 3개 vs 완전 탐색 상위 3개 — 금액은 USD")
    ok = True
    for name in SCENARIOS:
        row, _B, _s = compare(SCENARIOS[name]())
        ok &= row["ok"]
    rng = random.Random(a.seed)
    same = bad = saved = feasible_base = dis = 0
    for _ in range(a.random):
        sc = random_scenario(rng, rng.choice([2, 3, 4, 5]))
        try:
            row, _B, _s = compare(sc, quiet=True)
        except RuntimeError:
            continue
        same += row["ok"]
        bad += not row["ok"]
        dis += row["disagree"] > 0
        if row["base"] is not None and row["mine"]:
            feasible_base += 1
            saved += row["mine"][0] < row["base"] - 0.005
            ok &= row["mine"][0] <= row["base"] + 0.005
    print(f"무작위 {same + bad}사례(시드 {a.seed}): 상위 3개 금액이 완전 탐색과 같고 위반 0 — {same} · 다름 {bad} | "
          f"기준안이 성립한 {feasible_base}사례 중 MILP가 더 싼 것 {saved}, 더 비싼 것 0이어야 함 · 솔버 두 설정이 엇갈린 사례 {dis}")
    return 0 if ok and bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
