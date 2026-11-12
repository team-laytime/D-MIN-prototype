"""접안 계획 수리계획법(MILP) 모델 — 울산 CLX, 멘토링 PPT 규칙. 설명은 docs/13-math-programming.md.

엔진(src/demurrage/engine)은 '순서를 정하면 시각이 따라 나오는' 탐색으로 푼다. 이 스크립트는 같은 문제를
식(변수·목적함수·제약)으로 써서 범용 솔버(HiGHS)에 넘기고, 나온 답을 엔진 계산식·독립 검증기로 다시 확인한다.
엔진에는 넣지 않는다 — numpy·scipy가 필요해서 엔진의 '표준 라이브러리만' 원칙과 따로 둔다.
솔버가 '최적'이라고 한 값도 그대로 믿지 않는다: 설정 두 가지로 풀어 비교하고(Model.solve), 답은 늘 엔진으로 다시 계산한다.

  집합   i 선박(이동 가능) · b 부두 · k 시간창(그 배가 그 부두에 댈 수 있는 구간, 규칙으로 미리 계산)
  변수   u[i,b,k] 시간창선택(0/1) · y[i,j] 앞뒤순서(0/1) · t[i] 접안시각 · P[i] 정박개시 · D[i] 체선시간
         t0[i] 기상없었다면접안 · W[i] 기상체선시간 · z[i] 접안전체선중(0/1) · c0[i,j] 가상순서(0/1)
         x[i,b] 선석배정 = Σ_k u[i,b,k] (변수가 아니라 u의 합)
  목적   min Σ_i 요율_i ÷ 24 × D[i]
  제약   (1) Σ_b Σ_k u[i,b,k] = 1                                   한 척은 시간창 하나
         (2) Σ 창시작·u ≤ t[i] ≤ Σ 창끝·u                            접안시각은 고른 창 안
         (3) t[j] ≥ t[i] + 이안까지_ib + Switching_b − M(3 − y[i,j] − x[i,b] − x[j,b])    같은 부두 겹침 금지
             t[i] ≥ t[j] + 이안까지_jb + Switching_b − M(2 + y[i,j] − x[i,b] − x[j,b])
         (4) t[j] ≥ t[i] + 배타구간_ib − M(3 − y[i,j] − x[i,b] − x[j,b'])                 동시 작업 금지(다른 부두)
             t[i] ≥ t[j] + 배타구간_jb' − M(2 + y[i,j] − x[i,b] − x[j,b'])
         (5) P[i] ≤ Σ_접안형 창끝·u + Σ_고정형 고정개시·u ,  P[i] ≤ t[i] + Σ_고정형 max(0, 고정개시 − 창시작)·u
             D[i] ≥ t[i] + Σ_b 호스분리까지_ib·x[i,b] − P[i] − 허용시간_i − 공제비율_i·W[i] ,  D[i] ≥ 0
         (6) W[i] ≤ t[i] − t0[i] ,  W[i] ≤ t[i] − P[i] − 허용시간_i + M(1 − z[i]) ,  W[i] ≤ M·z[i]
             t0[i]는 '기상 제한만 뺀 시간창' 안, t0[i] ≤ t[i], 같은 부두 앞 배 뒤, 동시 작업 금지 짝과 겹치지 않음
         (7) 최소 ≤ 기초 + 일별 증감 + Σ 물량·(그날까지 작업을 시작했는가) ≤ 용량          일말 재고

실행 (scipy가 있는 파이썬으로):
  python3 scripts/milp_berth_plan.py                    정답 2개 + 시나리오 20개를 엔진 상위 3개 후보와 비교
  python3 scripts/milp_berth_plan.py --walk GC-01       한 문제를 파라미터 → 변수 값 → 제약식 숫자 대입까지
  python3 scripts/milp_berth_plan.py --walk S05-storm-rush
  python3 scripts/milp_berth_plan.py --random 300       무작위 사례를 완전 탐색과 비교
  python3 scripts/milp_berth_plan.py --lp GC-01         솔버에 넣는 모델 전문(LP 형식)
"""
from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import milp_core  # noqa: E402
from milp_core import INF, Model  # noqa: E402

from demurrage.domain.money import demurrage_cents  # noqa: E402
from demurrage.domain.timeutil import DAY, day_start, fmt, fmt_iso, overlap, parse_ts  # noqa: E402
from demurrage.engine.build import build_context  # noqa: E402
from demurrage.engine import laytime as lt_mod  # noqa: E402
from demurrage.engine import optimizer as opt_mod  # noqa: E402
from demurrage.engine.etb import make_placement  # noqa: E402
from demurrage.engine.laytime import amount_cents, compute, daylight_applies, laytime_minutes, laytime_start, notice_min, weather_ratio  # noqa: E402
from demurrage.engine.optimizer import TopK, _signature, optimize  # noqa: E402
from demurrage.engine.schedule import decode, evaluate, initial_state  # noqa: E402
from demurrage.engine.validator import validate  # noqa: E402
from demurrage.rules.loader import DATA_DIR, load_rules  # noqa: E402
from demurrage.verify import build_case_scenario  # noqa: E402



# ----------------------------------------------------------------------------- 규칙 두 가지: 데모 엔진 그대로 / 멘토링 PPT 그대로

RULES = "ppt"            # "ppt": 멘토링 PPT 09~11쪽과 멘토 설명 그대로 · "engine": 데모 엔진(11-09 버전) 규칙 그대로
# 기상체선 시간을 세는 구간(PPT 11쪽은 "Demurrage Time −= 기상체선 시간 / 2"까지만 말한다 → 세 가지 해석을 둔다)
#   "start" = 정박개시 ~ 호스분리(사용시간) 안의 기상 제약 시간   — 멘토 설명("이 선박의 시간 안에 그 시간이 포함되어 있으면")에 가장 가깝다
#   "end"   = 정박종료 ~ 호스분리(체선 기간) 안의 기상 제약 시간
#   "wait"  = 정박개시 ~ 접안 사이, 곧 기상 제약 때문에 접안하지 못하고 기다린 시간
WEATHER_FROM = "start"
WEATHER_LABEL = {"start": ("정박개시", "호스분리"), "end": ("정박종료", "호스분리"), "wait": ("정박개시", "접안")}
PPT_EARLY_H, PPT_EARLY_DAYLIGHT_H, PPT_DAY_H = 6, 7, 7      # 조기 도착: Laycan From 06시(Daylight 선박은 07시) · Daylight: 당일/다음 날 07시


def weather_windows(ctx):
    """기상 악화 제약 시간 — 전 부두에 함께 걸린다(멘토 설명). (시작, 종료) 목록, 겹치면 합친다."""
    out = []
    for s0, e0 in sorted({(r.start, r.end) for r in ctx.restrictions if r.reason == "WEATHER"}):
        if out and s0 <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e0))
        else:
            out.append((s0, e0))
    return out


def ppt_regime(ctx, v):
    """PPT 09쪽(Daylight 미적용)·10쪽(적용)의 정박개시 규칙 → (갈림 시각, 고정개시, 이름).

    갈림 시각 전에 접안하면 정박개시 = ETB, 그 뒤에 접안하면 정박개시 = 고정개시. (None, None)이면 언제 대든 ETB(LayCan Miss).
    """
    c = v.contract
    etanr = c.nor_tender if c.nor_tender is not None else v.eta          # ETANR = NVL(NR_TENDER, ETA)
    daylight = daylight_applies(ctx, v)                                  # 원유선·석유제품선
    if etanr > c.laycan_to:
        return None, None, "LayCan Miss"
    if etanr < c.laycan_from:                                            # 조기 도착: From 전에 대면 Early Loading(ETB), 아니면 From 당일 06시/07시
        return c.laycan_from, day_start(c.laycan_from) + (PPT_EARLY_DAYLIGHT_H if daylight else PPT_EARLY_H) * 60, "조기 도착"
    if not daylight:
        cand = etanr + notice_min(ctx, v)                                # ETANR + 6h
        return cand, cand, "LayCan 안"
    rise, sset = ctx.sun.get(day_start(etanr))
    if rise < etanr < sset:
        cand = etanr + notice_min(ctx, v)
    elif etanr <= rise:
        cand = day_start(etanr) + PPT_DAY_H * 60                         # ETANR 날의 07시
    else:
        cand = day_start(etanr) + DAY + PPT_DAY_H * 60                   # ETANR 다음 날의 07시
    return cand, cand, "Daylight"


def ppt_laytime_start(ctx, v, etb):
    """엔진의 laytime_start 자리에 끼우는 PPT 그대로의 정박개시. 돌려주는 모양은 엔진과 같다."""
    c = v.contract
    etanr = c.nor_tender if c.nor_tender is not None else v.eta
    steps = {"ETANR": etanr, "ETANR_rule": "LAY-01", "laycan_from": c.laycan_from, "laycan_to": c.laycan_to}
    split, cfix, name = ppt_regime(ctx, v)
    if split is None:
        return etb, "LAY-03", "LayCan Miss → ETB", steps
    if name == "조기 도착":
        if etb < split:
            return etb, "LAY-02", "Early Loading → ETB", steps
        return cfix, "LAY-04", f"조기 도착 → LayCan From 당일 {fmt(cfix)[6:]}", steps
    rule = "LAY-06" if name == "Daylight" else "LAY-05"
    if etb < cfix:
        return etb, rule, f"{fmt(cfix)}보다 ETB가 이름 → ETB", steps
    return cfix, rule, f"{name} → {fmt(cfix)}", steps


def ppt_weather_minutes(ctx, start, end, etb, hose_off):
    """기상체선 시간: 기상 악화 제약 시간 중 WEATHER_FROM이 정한 구간에 든 시간."""
    a, b = {"start": (start, hose_off), "end": (end, hose_off), "wait": (start, etb)}[WEATHER_FROM]
    return sum(overlap(s0, e0, a, b) for s0, e0 in weather_windows(ctx))


def _ppt_money(ctx, v, start, lay_min, etb, hose_off, etb_nowx):
    from fractions import Fraction
    end = start + lay_min
    dt_raw = hose_off - end
    wx_min = ppt_weather_minutes(ctx, start, end, etb, hose_off) if dt_raw > 0 else 0
    deduction = Fraction(wx_min) * weather_ratio(ctx, v)
    dt = max(Fraction(0), Fraction(dt_raw) - deduction)
    return end, dt_raw, wx_min, deduction, dt, demurrage_cents(dt, v.contract.rate_usd_day)


def _ppt_lower_bound(ctx, v, bid, t):
    """ETB가 t 이후일 때 체선료 하한(엔진 분기한정용). 기상 공제는 '기상 시간 전부'를 최대치로 잡는다."""
    from fractions import Fraction
    wp = ctx.work[(v.id, bid)]
    lay_min = laytime_minutes(ctx, v)[0]
    wtotal = sum(e0 - s0 for s0, e0 in weather_windows(ctx))

    def g(tt):
        dt = Fraction(tt + wp.etb_to_hose - ppt_laytime_start(ctx, v, tt)[0] - lay_min) - Fraction(wtotal) * weather_ratio(ctx, v)
        return demurrage_cents(dt, v.contract.rate_usd_day) if dt > 0 else 0
    best = g(t)
    c = v.contract
    etanr = c.nor_tender if c.nor_tender is not None else v.eta
    if etanr < c.laycan_from and t < c.laycan_from:
        best = min(best, g(c.laycan_from))
    return best


def use_rules(rules, weather_from="start"):
    """이 프로세스에서 쓸 규칙을 정한다. "ppt"면 엔진의 정박개시·기상 공제·하한 함수를 PPT 그대로의 것으로 바꿔 끼운다."""
    global RULES, WEATHER_FROM
    RULES, WEATHER_FROM = rules, weather_from
    if rules == "ppt":
        lt_mod.laytime_start = ppt_laytime_start
        lt_mod._money = _ppt_money
        lt_mod.lower_bound_cents = _ppt_lower_bound
        opt_mod.lower_bound_cents = _ppt_lower_bound


def ppt_doc(doc):
    """PPT 기준으로 볼 때 쓰지 않는 입력을 뺀다: 조석 시간창(12쪽 '고려하지 않음')과 출하 마감(팀이 더한 규칙)."""
    d = copy.deepcopy(doc)
    d.pop("tide_windows", None)
    for v in d.get("vessels", []):
        v.pop("deadline", None)
    return d


def ppt_patch(extra=None):
    """PPT 기준 규칙 표 고치기: 조석 기준 흘수를 없앤다(조석을 보지 않음)."""
    terminal = json.loads((DATA_DIR / "master" / "terminal_ulsan_clx.v1.json").read_text(encoding="utf-8"))
    patch = {f"terminal.berths.{n}.tide_draft_threshold": None for n, b in enumerate(terminal["berths"]) if b.get("tide_draft_threshold") is not None}
    patch.update(extra or {})
    return patch


# ----------------------------------------------------------------------------- 시간창 (규칙 → 파라미터)

def complement(forbidden, lo, hi):
    """정수 분 [lo, hi]에서 반열린 금지 구간 [s, e)들을 뺀 닫힌 구간 목록."""
    iv = sorted((max(s, lo), min(e, hi + 1)) for s, e in forbidden if e > lo and s <= hi)
    out, cur = [], lo
    for s, e in iv:
        if s > cur:
            out.append((cur, s - 1))
        cur = max(cur, e)
    if cur <= hi:
        out.append((cur, hi))
    return out


def split_at(windows, points):
    for p in sorted(set(points)):
        nxt = []
        for lo, hi in windows:
            if lo < p <= hi:
                nxt += [(lo, p - 1), (p, hi)]
            else:
                nxt.append((lo, hi))
        windows = nxt
    return windows


def static_windows(ctx, base, vid, bid, with_weather=True):
    """(선박, 부두)의 접안 가능 시간창. 다른 '이동 가능' 선박과 상관없이 정해지는 규칙을 모두 뺀 나머지다.

    각 규칙이 '이 구간에는 접안 못 함'을 하나씩 내놓고, 그 구간들을 뺀 것이 시간창이다(엔진 etb._search의 밀어내기와 같은 집합).
    """
    v, b, wp = ctx.vessels[vid], ctx.berths[bid], ctx.work[(vid, bid)]
    lo = v.eta + b.direction                                             # ETB-01 ETA + Direction 전에는 불가
    hi = ctx.limit_end if v.deadline is None else min(ctx.limit_end, v.deadline)   # ETB-11 출하 마감
    g = wp.etb_to_etu
    ex = g - ctx.rules.release_min
    fb = []
    pob = ctx.last_pob.get(vid)
    if pob is not None:                                                  # ETB-03 Last POB 뒤 도착 → 다음 08:00
        lo = max(lo, pob[0])
    if v.grt >= ctx.dawn_grt:                                            # ETB-04 GRT 3만↑ 새벽 02~08시
        d = day_start(lo) - DAY
        while d <= hi:
            fb.append((d + ctx.dawn_from, d + ctx.dawn_to))
            d += DAY
    for r in ctx.restr_by_berth[bid]:                                    # ETB-07 정비·강풍·사용자 제한 → 종료 + Direction
        if r.reason == "WEATHER" and not with_weather:
            continue
        fb.append((r.start, r.end + b.direction))
    if ctx.requires_tide(v, bid):                                        # ETB-08 조석 시간창 밖
        cur = -10 ** 12
        for s, e in sorted(ctx.tide.get(bid, [])):
            fb.append((cur, s))
            cur = e + 1
        fb.append((cur, 10 ** 12))
    for k in base.pl.values():                                           # FIX·작업 중 선박(움직이지 않음)
        if k.berth == bid:                                               # ETB-01·02 같은 부두: 그 배 앞에 끼지도, 겹치지도 못함
            fb.append((k.etb - g - b.switching, k.etu + b.switching))
        elif ctx.conflict_rule(v, bid, ctx.vessels[k.vid], k.berth) is not None:   # ETB-05·06 다른 부두 동시 작업 금지
            fb.append((k.etb - ex + 1, k.excl_end))
    return complement(fb, lo, hi)


@dataclass
class Built:
    m: Model
    ctx: object
    base: object                 # 고정(FIX·작업 중) 선박만 놓인 상태
    T0: int                      # 모델의 시각 0 (분, 자정)
    mov: list
    elig: dict
    par: dict                    # (i, b) → 파라미터
    win: dict                    # (i, b) → [(창시작, 창끝, 종류 T|C, 고정개시, 작업시작일)]
    win0: dict                   # 기상 제한만 뺀 시간창
    lay: dict                    # i → (정박개시 규칙 설명용) (갈림 시각, 고정개시)
    u: dict
    u0: dict
    t: dict
    t0: dict
    y: dict
    P: dict
    D: dict
    W: dict
    z: dict
    c0: dict
    const_cents: int             # 고정 선박의 체선료(어느 후보에서나 같다)
    rules: str = "engine"
    O: dict = None               # (i, 기상 구간 번호) → 겹친 시간 변수 (PPT 기준)
    wxw: list = None             # 기상 악화 제약 시간 목록 (PPT 기준)


def build(ctx) -> Built:
    """시나리오 문맥 → MILP. 파라미터(시간창·소요·요율)는 엔진의 규칙 표와 함수에서 읽는다."""
    ppt = RULES == "ppt"
    wxw = weather_windows(ctx) if ppt else []
    base = initial_state(ctx)
    mov = list(ctx.movable)
    V = ctx.vessels
    rel = ctx.rules.release_min
    elig = {i: list(ctx.eligible[i]) for i in mov}
    inv_groups = ctx.sc.inventory
    m = Model()

    # 시각 0: 모든 시각이 0 이상이 되게 옮긴다(자정 정렬은 그대로)
    marks = [ctx.sc.horizon_start]
    for v in ctx.sc.vessels:
        marks += [v.eta, v.contract.laycan_from]
        if v.contract.nor_tender is not None:
            marks.append(v.contract.nor_tender)
        if v.fixed_etb is not None:
            marks.append(v.fixed_etb)
    T0 = day_start(min(marks)) - DAY
    far = ctx.limit_end + 30 * DAY

    par, win, win0, lay, wx = {}, {}, {}, {}, {}
    for i in mov:
        v = V[i]
        L = laytime_minutes(ctx, v)[0]
        rho = float(weather_ratio(ctx, v))
        if ppt:                                        # PPT 09·10쪽 그대로
            split, cfix, rule = ppt_regime(ctx, v)
        else:
            # 정박개시 규칙(LAY-02~06)을 엔진 함수에 '아주 늦은 접안'을 넣어 읽어 온다 → 갈림 시각과 고정 정박개시
            start, rule, _, _ = laytime_start(ctx, v, far)
            if rule == "LAY-03":                       # Laycan Miss: 언제 대든 정박개시 = 접안
                split, cfix = None, None
            elif rule == "LAY-04":                     # 조기 도착: Laycan From 전에 대면 접안, 그 뒤면 From 당일 06:00
                split, cfix = v.contract.laycan_from, start
            else:                                      # Laycan 안: min(ETANR + 6h(또는 Daylight 시각), 접안)
                split, cfix = start, start
        lay[i] = (split, cfix, rule)
        wx[i] = (not ppt) and rho > 0 and any(ctx.has_weather[b] for b in elig[i])   # '기상 없었다면' 일정은 엔진 규칙에서만 쓴다
        for b in elig[i]:
            wp, bb = ctx.work[(i, b)], ctx.berths[b]
            par[i, b] = dict(lb0=v.eta + bb.direction, g=wp.etb_to_etu, q=wp.etb_to_hose, ex=wp.etb_to_etu - rel,
                             delay=wp.start_delay, sw=bb.switching, L=L, rho=rho, rate=v.contract.rate_usd_day)
            ws = static_windows(ctx, base, i, b, True)
            days = []
            if v.cargo_group in inv_groups:                 # 재고를 일 단위로 세려면 창이 작업시작일을 넘지 않게 자른다
                d = day_start(v.eta + bb.direction + wp.start_delay)
                while d <= ctx.limit_end + wp.start_delay + DAY:
                    days.append(d - wp.start_delay)
                    d += DAY
            out = []
            for lo, hi in split_at(ws, days + ([split] if split is not None else [])):
                typ, c = ("T", None) if (split is None or hi < split) else ("C", cfix)
                out.append((lo, hi, typ, c, day_start(lo + wp.start_delay)))
            win[i, b] = out
            w0 = split_at(static_windows(ctx, base, i, b, False), days) if wx[i] else []
            win0[i, b] = [(lo, hi, day_start(lo + wp.start_delay)) for lo, hi in w0]
        elig[i] = [b for b in elig[i] if win[i, b]]
        if not elig[i]:
            raise RuntimeError(f"{i}: 접안 가능 시간창이 없음")

    tlo = {i: min(w[0] for b in elig[i] for w in win[i, b]) for i in mov}
    thi = {i: max(w[1] for b in elig[i] for w in win[i, b]) for i in mov}
    tlo0 = {i: min([tlo[i]] + [w[0] for b in elig[i] for w in win0[i, b]]) for i in mov}
    pmax = {i: max((w[1] if w[2] == "T" else max(w[3], w[1])) for b in elig[i] for w in win[i, b]) for i in mov}

    u, u0, t, t0, P, D, W, z = {}, {}, {}, {}, {}, {}, {}, {}
    for i in mov:
        for b in elig[i]:
            for k in range(len(win[i, b])):
                u[i, b, k] = m.binary(f"u[{i},{b},{k + 1}]")
        t[i] = m.time(f"t[{i}]", tlo[i] - T0, thi[i] - T0)
        P[i] = m.time(f"P[{i}]", 0, pmax[i] - T0)
        D[i] = m.time(f"D[{i}]", 0, INF, cost=V[i].contract.rate_usd_day / 1440)
        if wx[i]:
            t0[i] = m.time(f"t0[{i}]", tlo0[i] - T0, thi[i] - T0)
            W[i] = m.time(f"W[{i}]", 0, thi[i] - tlo0[i])
            z[i] = m.binary(f"z[{i}]")
            for b in elig[i]:
                for k in range(len(win0[i, b])):
                    u0[i, b, k] = m.binary(f"u0[{i},{b},{k + 1}]")

    O, beta = {}, {}
    if ppt:                      # 기상체선 시간: 선박마다, 기상 구간마다 '겹친 시간' 변수와 스위치
        for i in mov:
            if par[i, elig[i][0]]["rho"] > 0:
                for n, (s0, e0) in enumerate(wxw):
                    O[i, n] = m.time(f"O[{i},{n + 1}]", 0, e0 - s0)
                    beta[i, n] = m.binary(f"b[{i},{n + 1}]")

    def x(i, b, a=1.0):          # 선석 배정 x[i,b] = Σ_k u[i,b,k]
        return [(u[i, b, k], a) for k in range(len(win[i, b]))]

    # (1) 한 척은 시간창 하나 · (2) 접안 시각은 고른 창 안
    for i in mov:
        allw = [(b, k, w) for b in elig[i] for k, w in enumerate(win[i, b])]
        m.add([(u[i, b, k], 1) for b, k, _ in allw], 1, 1, f"C1[{i}]")
        m.add([(t[i], 1)] + [(u[i, b, k], -(w[0] - T0)) for b, k, w in allw], lo=0, name=f"C2a[{i}]")
        m.add([(t[i], 1)] + [(u[i, b, k], -(w[1] - T0)) for b, k, w in allw], hi=0, name=f"C2b[{i}]")

    # (3) 같은 부두 겹침 금지 · (4) 다른 부두 동시 작업 금지 — 두 척마다 앞뒤순서 y 하나
    y, c0 = {}, {}
    for i, j in itertools.combinations(mov, 2):
        vi, vj = V[i], V[j]
        same = [b for b in elig[i] if b in elig[j]]
        cross = [(b, b2) for b in elig[i] for b2 in elig[j] if b != b2 and ctx.conflict_rule(vi, b, vj, b2) is not None]
        if not same and not cross:
            continue
        yv = y[i, j] = m.binary(f"y[{i}<{j}]")
        Mij, Mji = max(0, thi[i] - tlo0[j]) + milp_core.M_PAD, max(0, thi[j] - tlo0[i]) + milp_core.M_PAD
        if cross and wx[i]:
            c0[i, j] = m.binary(f"c0[{i}|{j}]")      # j가 실제로 앞일 때: '기상 없었다면'의 i가 j 앞에 통째로 들어가는가
        if cross and wx[j]:
            c0[j, i] = m.binary(f"c0[{j}|{i}]")
        for b in same:
            di, dj = par[i, b]["g"] + par[i, b]["sw"], par[j, b]["g"] + par[j, b]["sw"]
            M1, M2 = Mij + di, Mji + dj
            m.add([(t[j], 1), (t[i], -1), (yv, -M1)] + x(i, b, -M1) + x(j, b, -M1), lo=di - 3 * M1, name=f"C3a[{i}<{j}|{b}]")
            m.add([(t[i], 1), (t[j], -1), (yv, M2)] + x(i, b, -M2) + x(j, b, -M2), lo=dj - 2 * M2, name=f"C3b[{j}<{i}|{b}]")
            if wx[j]:           # i가 앞이면 '기상 없었다면'의 j도 i 뒤
                m.add([(t0[j], 1), (t[i], -1), (yv, -M1)] + x(i, b, -M1) + x(j, b, -M1), lo=di - 3 * M1, name=f"C6f[{i}<{j}|{b}]")
            if wx[i]:
                m.add([(t0[i], 1), (t[j], -1), (yv, M2)] + x(i, b, -M2) + x(j, b, -M2), lo=dj - 2 * M2, name=f"C6f[{j}<{i}|{b}]")
        for b, b2 in cross:
            di, dj = par[i, b]["ex"], par[j, b2]["ex"]
            M1, M2 = Mij + di, Mji + dj
            m.add([(t[j], 1), (t[i], -1), (yv, -M1)] + x(i, b, -M1) + x(j, b2, -M1), lo=di - 3 * M1, name=f"C4a[{i}<{j}|{b}/{b2}]")
            m.add([(t[i], 1), (t[j], -1), (yv, M2)] + x(i, b, -M2) + x(j, b2, -M2), lo=dj - 2 * M2, name=f"C4b[{j}<{i}|{b2}/{b}]")
            if wx[j]:           # 실제로 i가 앞(y = 1): 가상의 j는 i의 배타 구간 뒤(c0 = 0)이거나 통째로 i 앞(c0 = 1)
                cv, Mb = c0[j, i], max(0, thi[j] - tlo[i]) + dj + milp_core.M_PAD
                m.add([(t0[j], 1), (t[i], -1), (yv, -M1), (cv, M1)] + x(i, b, -M1) + x(j, b2, -M1), lo=di - 3 * M1, name=f"C6g[{i}<{j}|{b}/{b2}]")
                m.add([(t[i], 1), (t0[j], -1), (yv, -Mb), (cv, -Mb)] + x(i, b, -Mb) + x(j, b2, -Mb), lo=dj - 4 * Mb, name=f"C6h[{i}<{j}|{b}/{b2}]")
            if wx[i]:           # 실제로 j가 앞(y = 0)
                cv, Mb = c0[i, j], max(0, thi[i] - tlo[j]) + di + milp_core.M_PAD
                m.add([(t0[i], 1), (t[j], -1), (yv, M2), (cv, M2)] + x(i, b, -M2) + x(j, b2, -M2), lo=dj - 2 * M2, name=f"C6g[{j}<{i}|{b2}/{b}]")
                m.add([(t[j], 1), (t0[i], -1), (yv, Mb), (cv, -Mb)] + x(i, b, -Mb) + x(j, b2, -Mb), lo=di - 3 * Mb, name=f"C6h[{j}<{i}|{b2}/{b}]")

    # (5) 정박개시 · 체선 시간
    for i in mov:
        ca, cb = [(P[i], 1)], [(P[i], 1), (t[i], -1)]
        for b in elig[i]:
            for k, (lo, hi, typ, c, _) in enumerate(win[i, b]):
                ca.append((u[i, b, k], -((hi if typ == "T" else c) - T0)))
                if typ == "C" and c > lo:
                    cb.append((u[i, b, k], -(c - lo)))
        m.add(ca, hi=0, name=f"C5a[{i}]")
        m.add(cb, hi=0, name=f"C5b[{i}]")
        p0 = par[i, elig[i][0]]
        co = [(D[i], 1), (t[i], -1), (P[i], 1)]
        for b in elig[i]:
            co += x(i, b, -par[i, b]["q"])
        if i in W:
            co.append((W[i], p0["rho"]))
        co += [(O[i, n], p0["rho"]) for n in range(len(wxw)) if (i, n) in O]
        m.add(co, lo=-p0["L"], name=f"C5c[{i}]")

    # (6-PPT) 기상체선 시간 = 기상 악화 제약 시간 ∩ [정박개시(또는 정박종료), 호스분리]
    for (i, n), ov in O.items():
        s0, e0 = wxw[n]
        L = par[i, elig[i][0]]["L"]
        shift = L if WEATHER_FROM == "end" else 0                    # 세기 시작하는 곳: 정박개시 P 또는 정박종료 P + L
        hose = [(t[i], 1)]                                           # 세기 끝나는 곳: 접안 t 또는 호스분리 t + Σ q·x
        if WEATHER_FROM != "wait":
            hose += [c for b in elig[i] for c in x(i, b, par[i, b]["q"])]
        bv = beta[i, n]
        m.add([(ov, 1), (bv, -(e0 - s0))], hi=0, name=f"C6k[{i}|{n + 1}]")                     # 스위치가 꺼지면 0
        M1 = max(0, s0 - tlo[i]) + milp_core.M_PAD
        m.add([(ov, 1), (bv, M1)] + [(j, -a) for j, a in hose], hi=-(s0 - T0) + M1, name=f"C6l[{i}|{n + 1}]")       # ≤ 호스분리 − 기상시작
        M2 = max(0, pmax[i] + shift - e0) + milp_core.M_PAD
        m.add([(ov, 1), (bv, M2), (P[i], 1)], hi=(e0 - T0) - shift + M2, name=f"C6m[{i}|{n + 1}]")                 # ≤ 기상종료 − 세기 시작
        M3 = max(0, pmax[i] + shift - tlo[i]) + milp_core.M_PAD
        m.add([(ov, 1), (bv, M3), (P[i], 1)] + [(j, -a) for j, a in hose], hi=-shift + M3, name=f"C6n[{i}|{n + 1}]")   # ≤ 호스분리 − 세기 시작

    # (6) 기상 공제 — '기상이 없었다면'의 접안 시각 t0와 실제 t 사이 중 체선 기간에 든 시간
    for i in W:
        L = par[i, elig[i][0]]["L"]
        all0 = [(b, k, w) for b in elig[i] for k, w in enumerate(win0[i, b])]
        for b in elig[i]:
            m.add([(u0[i, b, k], 1) for k in range(len(win0[i, b]))] + x(i, b, -1), 0, 0, f"C6a[{i}|{b}]")
        m.add([(t0[i], 1)] + [(u0[i, b, k], -(w[0] - T0)) for b, k, w in all0], lo=0, name=f"C6b[{i}]")
        m.add([(t0[i], 1)] + [(u0[i, b, k], -(w[1] - T0)) for b, k, w in all0], hi=0, name=f"C6c[{i}]")
        m.add([(t0[i], 1), (t[i], -1)], hi=0, name=f"C6d[{i}]")
        m.add([(W[i], 1), (t[i], -1), (t0[i], 1)], hi=0, name=f"C6e[{i}]")
        Mw = max(0, pmax[i] - tlo[i]) + L + milp_core.M_PAD
        m.add([(W[i], 1), (t[i], -1), (P[i], 1), (z[i], Mw)], hi=Mw - L, name=f"C6i[{i}]")
        m.add([(W[i], 1), (z[i], -(thi[i] - tlo0[i]))], hi=0, name=f"C6j[{i}]")

    # (7) 재고 — 작업시작일 기준 일말 재고(ETB-09). 수입은 용량, 수출은 최소 재고. 첫 배가 오기 전 날은 검사하지 않는다(검증기와 같게).
    h0, h1 = day_start(ctx.sc.horizon_start), day_start(ctx.sc.horizon_end)

    def began(i, d, since=-INF):          # 실제 일정: d일까지 작업을 시작했는가 (= 그날까지의 시간창을 골랐는가)
        return [(u[i, b, k], 1) for b in elig[i] for k, w in enumerate(win[i, b]) if since <= w[4] <= d]

    def began0(i, d, since=-INF):         # '기상 없었다면'의 일정
        return [(u0[i, b, k], 1) for b in elig[i] for k, w in enumerate(win0[i, b]) if since <= w[2] <= d]

    for gname, inv in inv_groups.items():
        movers = [i for i in mov if V[i].cargo_group == gname]
        if not movers:
            continue
        fixed = [(day_start(p.work_start), V[p.vid]) for p in base.pl.values() if V[p.vid].cargo_group == gname]
        unit = 1.0 / max(V[i].qty for i in movers)          # 행 스케일: 물량 계수를 1 근처로
        for direction, bound in (("IMPORT", "cap"), ("EXPORT", "min")):
            mine = [i for i in movers if V[i].direction == direction]
            fixed_days = [d for d, v in fixed if v.direction == direction]
            if not mine and not fixed_days:
                continue
            sign = 1 if bound == "cap" else -1            # 용량은 위쪽 한계, 최소 재고는 아래쪽 한계
            d, n = h0, 0
            while d <= h1:
                n += 1
                const = inv.opening + n * inv.daily_net + sum((v.qty if v.direction == "IMPORT" else -v.qty) for dd, v in fixed if h0 <= dd <= d)
                signed = {i: (V[i].qty if V[i].direction == "IMPORT" else -V[i].qty) for i in movers}
                lvl = [(var, signed[i] * a) for i in movers for var, a in began(i, d, h0)]
                limit = (inv.capacity if bound == "cap" else inv.minimum) - const
                # 가장 나쁜 경우에도 한계를 못 넘으면 이 날의 식은 필요 없다. 넘을 수 있으면 그 차이만큼만 '큰 수'로 쓴다.
                worst = sum(max(0.0, sign * signed[i]) for i in movers if began(i, d, h0) or (i in t0 and began0(i, d, h0)))
                big = worst - sign * limit
                tag = f"{gname}|{fmt(d)[:5]}"
                d += DAY
                if big <= 1e-9:
                    continue

                def row(terms, switch, name, lvl=lvl, limit=limit, big=big):
                    """재고 식 한 줄. switch(0/1 식)가 1일 때만 검사한다(0이면 큰 수로 풀린다)."""
                    coefs = lvl + terms + [(var, sign * big * a) for var, a in switch]
                    if bound == "cap":
                        m.add(coefs, hi=limit + (big if switch else 0), name=name, scale=unit)
                    else:
                        m.add(coefs, lo=limit - (big if switch else 0), name=name, scale=unit)
                dd0 = d - DAY
                if any(x <= dd0 for x in fixed_days):       # 고정 선박이 이미 시작했으면 늘 검사
                    row([], [], f"C7{bound}[{tag}]")
                elif mine:                                  # 그 방향 배가 하나라도 시작한 날부터 검사
                    f = m.var(f"f[{bound},{tag}]", 0, 1)
                    for i in mine:
                        m.add([(f, 1)] + [(var, -a) for var, a in began(i, dd0)], lo=0, name=f"C7f[{i}|{tag}]")
                    row([], [(f, 1)], f"C7{bound}[{tag}]")
                for i in mine:                              # '기상 없었다면'의 작업시작일도 재고가 맞아야 한다(엔진의 가상 탐색과 같게)
                    if i in t0:
                        shift = [(var, signed[i] * a) for var, a in began0(i, dd0, h0)] + [(var, -signed[i] * a) for var, a in began(i, dd0, h0)]
                        row(shift, began0(i, dd0), f"C7g[{i}|{tag}]")

    const_cents = sum(amount_cents(ctx, V[vid], p) for vid, p in base.pl.items())
    return Built(m, ctx, base, T0, mov, elig, par, win, win0, lay, u, u0, t, t0, y, P, D, W, z, c0, const_cents, RULES, O, wxw)


# ----------------------------------------------------------------------------- 풀기·엔진으로 다시 확인

@dataclass
class Sol:
    status: str
    obj_cents: float             # MILP 목적함수 + 고정 선박 금액 (센트)
    rows: dict                   # i → 선박별 값
    order: list                  # [(i, b)] 접안 시각 순
    seconds: float
    xs: object
    reprice_cents: int = None    # MILP 일정을 엔진 계산식(laytime.compute)으로 다시 계산한 합계
    violations: list = None      # 독립 검증기(validator)가 찾은 제약 위반
    decoded_cents: int = None    # 같은 순서를 엔진 디코더(가장 이른 시각)로 붙였을 때 합계
    decoded_ok: bool = None
    holds: list = None           # 디코더보다 일부러 늦게 댄 선박 [(i, MILP 접안, 디코더 접안)]
    decoded: object = None
    agree: bool = True           # 솔버 설정 두 가지의 최적값이 같았는가

    def signature(self):
        per = {}
        for i, b in self.order:
            per.setdefault(b, []).append(i)
        return tuple(sorted((b, tuple(vs)) for b, vs in per.items()))


def solve(B: Built, cuts=(), time_limit=120.0):
    """1단계: 총 체선료 최소. 2단계: 같은 부두·같은 순서·같은 금액 안에서 가장 이른 시각(보고용 일정)."""
    m, T0 = B.m, B.T0
    t_begin = time.perf_counter()
    res = m.solve(extra=cuts, time_limit=time_limit)
    if res.x is None:
        return None
    status = "최적" if res.status == 0 else "제한시간(최선)"
    star, xs = res.fun, res.x
    fix = {B.y[k]: round(xs[B.y[k]]) for k in B.y}
    for i in B.mov:
        for b in B.elig[i]:
            ks = range(len(B.win[i, b]))
            if not any(xs[B.u[i, b, k]] > 0.5 for k in ks):
                fix.update({B.u[i, b, k]: 0 for k in ks})
    c2 = np.zeros(len(m.names))
    for i in B.mov:
        c2[B.t[i]] = 1.0
        if i in B.t0:
            c2[B.t0[i]] = 1e-3
    rate = {B.D[i]: B.ctx.vessels[i].contract.rate_usd_day / 1440 for i in B.mov}
    res2 = m.solve(cost=c2, extra=list(cuts) + [(rate, -INF, star + max(1e-6, 1e-9 * abs(star)), "COST", 1.0)], fix=fix, time_limit=time_limit)
    if res2.x is not None and res2.status == 0:
        xs = res2.x
    rows = {}
    for i in B.mov:
        (b, k), = [(b, k) for b in B.elig[i] for k in range(len(B.win[i, b])) if xs[B.u[i, b, k]] > 0.5]
        rows[i] = dict(berth=b, k=k, t=int(round(xs[B.t[i]])) + T0,
                       t0=(int(round(xs[B.t0[i]])) + T0) if i in B.t0 else None)
    order = [(i, rows[i]["berth"]) for i in sorted(B.mov, key=lambda i: (rows[i]["t"], i))]
    sol = Sol(status, star * 100 + B.const_cents, rows, order, time.perf_counter() - t_begin, xs, agree=res.agree)
    _check_with_engine(B, sol)
    return sol


def _check_with_engine(B: Built, sol: Sol):
    """① MILP 일정 그대로 엔진 계산식·독립 검증기에 넣는다  ② 같은 순서를 엔진 디코더로 다시 붙여 본다."""
    ctx = B.ctx
    st = B.base.copy()
    for i, b in sol.order:
        r, v = sol.rows[i], ctx.vessels[i]
        p = make_placement(ctx, v, b, r["t"], "MOVABLE", [], v.eta + ctx.berths[b].direction)
        p.etb_nowx = r["t0"] if r["t0"] is not None else p.etb
        st.add(p)
        r["p"] = p
    calcs = {vid: compute(ctx, ctx.vessels[vid], p) for vid, p in st.pl.items()}
    sol.reprice_cents = sum(c["amount_cents"] for c in calcs.values())
    sol.violations = validate(ctx, st.pl)
    for i in B.mov:
        sol.rows[i]["calc"] = calcs[i]
    st2, bad = decode(ctx, sol.order)
    sol.decoded = evaluate(ctx, st2, sol.order, "MILP 순서", bad)
    sol.decoded_cents = sol.decoded.total_cents
    sol.decoded_ok = not bad and not validate(ctx, st2.pl)
    sol.holds = [(i, sol.rows[i]["t"], st2.pl[i].etb) for i, _ in sol.order if i in st2.pl and st2.pl[i].etb != sol.rows[i]["t"]]


def nogood(B: Built, sol: Sol):
    """'이 부두별 순서는 빼고' 제약 한 줄 — 배정이 하나라도 다르거나, 이웃한 두 척의 앞뒤가 하나라도 바뀌어야 한다."""
    coefs, n, const = {}, 0, 0

    def put(j, a):
        coefs[j] = coefs.get(j, 0) + a
    per = {}
    for i, b in sol.order:
        for k in range(len(B.win[i, b])):
            put(B.u[i, b, k], 1)
        n += 1
        per.setdefault(b, []).append(i)
    for seq in per.values():
        for a, c in zip(seq, seq[1:]):
            if (a, c) in B.y:
                put(B.y[a, c], 1)
            else:
                put(B.y[c, a], -1)
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


# ----------------------------------------------------------------------------- 문제 읽기

def rules_for(patch=None):
    return load_rules(patch=ppt_patch(patch) if RULES == "ppt" else patch)


def ctx_from_doc(doc, patch=None, rules=None):
    ctx, issues = build_context(ppt_doc(doc) if RULES == "ppt" else doc, rules or rules_for(patch))
    if ctx is None:
        raise SystemExit(f"입력 오류: {[i.as_dict() for i in issues if i.level == 'ERROR']}")
    return ctx


def golden_cases():
    for path in sorted((DATA_DIR / "golden").glob("GC-*.json")):
        gc = json.loads(path.read_text(encoding="utf-8"))
        for case in gc.get("cases", []):
            if "optimizer" in case.get("expect", {}):
                yield gc["id"], build_case_scenario(gc, case), case.get("rules_patch"), case["expect"]["optimizer"]


def scenario_docs():
    for path in sorted((DATA_DIR / "scenarios").rglob("*.json")):
        yield json.loads(path.read_text(encoding="utf-8"))


def find_problem(pid):
    for gid, doc, patch, _ in golden_cases():
        if gid == pid:
            return doc, patch
    for doc in scenario_docs():
        if doc["id"] == pid:
            return doc, None
    raise SystemExit(f"{pid} 를 찾지 못함 (정답 GC-01·GC-12 또는 시나리오 ID)")


# ----------------------------------------------------------------------------- 출력

def usd(cents):
    return f"{cents / 100:,.2f}"


def hh(minutes):
    h = minutes / 60
    return f"{h:.2f}".rstrip("0").rstrip(".") + "h"


def compare_all(time_limit):
    """정답 2개 + 시나리오 20개: MILP 상위 3개를 엔진 탐색(분기한정, 6척 이하는 완전 탐색도)과 비교한다."""
    title = "멘토링 PPT 규칙(조석·마감 제외)" if RULES == "ppt" else "데모 엔진 규칙"
    print(f"[{title}] MILP 상위 3개 후보 vs 엔진 탐색 상위 3개 후보 — 금액은 USD")
    print(f"{'문제':<20}{'선박':>4}{'변수':>6}{'0/1':>5}{'제약':>6}  {'엔진 1·2·3안':<38}{'MILP 1·2·3안(엔진 계산식으로 다시 계산)':<40}{'위반':>4}{'초':>7}  결과")
    n = same = cheaper = worse = 0
    rows = []
    problems = [(gid, doc, patch) for gid, doc, patch, _ in golden_cases()] + [(d["id"], d, None) for d in scenario_docs()]
    for pid, doc, patch in problems:
        ctx = ctx_from_doc(doc, patch)
        res = optimize(ctx, k=3, time_limit_s=30)
        eng = [c.total_cents for c in res.candidates]
        proven = res.proven_optimal
        if len(ctx.movable) <= 5:                       # 작은 문제는 완전 탐색으로 한 번 더
            eng = sorted(canonical_top(ctx, 3)[0].values())
            proven = True
        B = build(ctx)
        t0 = time.perf_counter()
        sols = top_k(B, 3, time_limit)
        el = time.perf_counter() - t0
        mine = [s.reprice_cents for s in sols]
        viol = sum(len(s.violations) for s in sols)
        clean = viol == 0 and all(s.status == "최적" for s in sols) and all(abs(s.obj_cents - s.reprice_cents) <= len(B.mov) for s in sols)
        holds = sorted({i for s in sols for i, _, _ in s.holds})
        if clean and mine == eng and not holds:
            verdict = "일치"
            same += 1
        elif clean and len(mine) >= len(eng) and all(a <= b for a, b in zip(mine, eng)):
            verdict = "MILP가 같거나 더 쌈" + (f" (늦춰 댄 배: {', '.join(holds)})" if holds else "") + ("" if proven else " · 엔진은 제한시간 최선")
            cheaper += 1
        else:
            verdict = "다름 ←"
            worse += 1
        n += 1
        rows.append(dict(id=pid, n=len(B.mov), vars=len(B.m.names), bins=sum(B.m.integ), rows=len(B.m.rows), eng=eng, mine=mine,
                         viol=viol, sec=round(el, 1), verdict=verdict, holds=holds, disagree=B.m.disagreements))
        print(f"{pid:<20}{len(B.mov):>4}{len(B.m.names):>6}{sum(B.m.integ):>5}{len(B.m.rows):>6}  "
              f"{' / '.join(usd(e) for e in eng):<38}{' / '.join(usd(e) for e in mine):<40}{viol:>4}{el:>7.1f}  {verdict}")
    print(f"\n{n}문제: 엔진과 금액·접안 시각이 같음 {same} · MILP가 같거나 더 쌈 {cheaper} · 다름 {worse} | 후보 {sum(len(r['mine']) for r in rows)}개, 검증기 위반 {sum(r['viol'] for r in rows)}건, "
          f"솔버 두 설정이 엇갈린 문제 {sum(1 for r in rows if r['disagree'])}")
    return rows


def walk(pid, time_limit, k=3):
    """한 문제를 파라미터 → 시간창 → 해의 변수 값 → 제약식 숫자 대입까지 따라간다."""
    doc, patch = find_problem(pid)
    ctx = ctx_from_doc(doc, patch)
    B = build(ctx)
    V, T0 = ctx.vessels, B.T0
    origin = day_start(ctx.sc.horizon_start)
    print(f"[규칙: {'멘토링 PPT 그대로 (조석·마감 제외)' if RULES == 'ppt' else '데모 엔진'}]")
    for n, (s0, e0) in enumerate(B.wxw or [], 1):
        print(f"   기상 악화 제약 시간 {n}: {fmt(s0)} ~ {fmt(e0)} (전 부두, 종료 + Direction까지 접안 불가)")

    def H(tm):              # 기준일 00:00부터 지난 시간(h)
        return f"{(tm - origin) / 60:.2f}".rstrip("0").rstrip(".")
    print(f"== {pid} — 이동 가능 {len(B.mov)}척, 변수 {len(B.m.names)}개(0/1 {sum(B.m.integ)}개), 제약 {len(B.m.rows)}개")
    print(f"   시각은 'MM/DD HH:mm', 괄호 안은 {fmt(origin)}부터 지난 시간(h)\n")
    print("① 파라미터 (주어지는 값)")
    for vid, p in B.base.pl.items():
        print(f"   [고정] {vid} {p.berth}: 접안 {fmt(p.etb)} · 이안 {fmt(p.etu)} → 다음 배는 이안 + Switching 뒤부터")
    for i in B.mov:
        v, (split, cfix, rule) = V[i], B.lay[i]
        c = v.contract
        etanr = c.nor_tender if c.nor_tender is not None else v.eta
        print(f"   {i}: ETA {fmt(v.eta)}({H(v.eta)}) · ETANR {fmt(etanr)} · Laycan {fmt(c.laycan_from)}~{fmt(c.laycan_to)} · "
              f"허용시간 {hh(B.par[i, B.elig[i][0]]['L'])} · 요율 ${c.rate_usd_day:,}/일(시간당 ${c.rate_usd_day / 24:,.0f})")
        for b in B.elig[i]:
            p = B.par[i, b]
            print(f"      부두 {b}: Direction 뒤 가장 이른 접안 {fmt(p['lb0'])} · 접안→호스분리 {hh(p['q'])} · 접안→이안 {hh(p['g'])} · "
                  f"Switching {hh(p['sw'])} · 배타구간 {hh(p['ex'])}")
            for n, (lo, hi, typ, cc, _) in enumerate(B.win[i, b], 1):
                kind = "정박개시 = 접안시각" if typ == "T" else f"정박개시 = {fmt(cc)}({H(cc)}) 고정"
                print(f"         시간창 {n}: {fmt(lo)}({H(lo)}) ~ {fmt(hi)}({H(hi)})   {kind}")
    sols = top_k(B, k, time_limit)
    for rank, s in enumerate(sols, 1):
        print(f"\n② {rank}안 — MILP 목적함수 ${usd(s.obj_cents)} · 엔진 계산식으로 다시 ${usd(s.reprice_cents)} · "
              f"같은 순서를 엔진 디코더로 ${usd(s.decoded_cents)} · 검증기 위반 {len(s.violations)}건 · {s.status} {s.seconds:.2f}초")
        print("   부두별 순서: " + " | ".join(f"{b}: {' → '.join(vs)}" for b, vs in s.signature()))
        for i, b in s.order:
            r, c = s.rows[i], s.rows[i]["calc"]
            lo, hi, typ, cc, _ = B.win[i, b][r["k"]]
            line = (f"   {i}: 선석배정 x[{i},{b}] = 1 · 시간창선택 u[{i},{b},{r['k'] + 1}] = 1 · 접안시각 t = {fmt(r['t'])}({H(r['t'])}) · "
                    f"호스분리 {fmt(c['hose_off'])}({H(c['hose_off'])}) · 정박개시 P = {fmt(c['laytime_start'])}({H(c['laytime_start'])}) · "
                    f"정박종료 {fmt(c['laytime_end'])}({H(c['laytime_end'])})")
            if r["t0"] is not None and r["t0"] != r["t"]:
                line += f" · 기상없었다면접안 t0 = {fmt(r['t0'])} · 기상체선시간 W = {hh(c['weather_minutes'])}"
            line += f" · 체선시간 D = {hh(float(c['demurrage_minutes']))} → ${usd(c['amount_cents'])}"
            print(line)
        for (i, j), yv in B.y.items():
            val = round(s.xs[yv])
            print(f"   앞뒤순서 y[{i}<{j}] = {val}  ({i if val else j} 먼저)")
        for i, tm, te in s.holds:
            print(f"   ※ {i}: 가장 이른 가능 시각 {fmt(te)}보다 늦은 {fmt(tm)}에 접안 — 기다리는 쪽이 총 체선료가 낮다")
        if rank == 1:
            _explain(B, s, origin)
    return sols


def _explain(B: Built, s: Sol, origin):
    """1안의 값을 제약식에 넣어 본다. 숫자마다 이름을 붙이고, 등호인 식(그 배의 접안 시각을 정한 식)을 표시한다."""
    ctx, V = B.ctx, B.ctx.vessels

    def H(tm):
        return f"{(tm - origin) / 60:.2f}".rstrip("0").rstrip(".")

    def num(minutes):
        return hh(minutes)[:-1]
    print("\n③ 1안의 값을 제약식에 대입 — '← 등호'가 그 배의 접안 시각을 정한 식")
    for i, b in s.order:
        r = s.rows[i]
        lo, hi = B.win[i, b][r["k"]][:2]
        print(f"   (2) {i}: 창시작 {fmt(lo)} ≤ 접안시각 {fmt(r['t'])} ≤ 창끝 {fmt(hi)}{'  ← 등호(창이 열리자마자 접안)' if r['t'] == lo else ''}")
    for (i, j), yv in B.y.items():
        a, c = (i, j) if round(s.xs[yv]) else (j, i)          # a가 먼저
        ba, bc, ta, tc = s.rows[a]["berth"], s.rows[c]["berth"], s.rows[a]["t"], s.rows[c]["t"]
        pa = B.par[a, ba]
        if ba == bc:
            need, what, no = ta + pa["g"] + pa["sw"], f"이안까지 {hh(pa['g'])} + Switching {hh(pa['sw'])}", "(3)"
        elif ctx.conflict_rule(V[a], ba, V[c], bc) is not None:
            need, what, no = ta + pa["ex"], f"배타구간 {hh(pa['ex'])}", "(4)"
        else:
            print(f"   (3)(4) {i}·{j}: 부두가 다르고({s.rows[i]['berth']}·{s.rows[j]['berth']}) 동시 작업 금지 짝도 아님 → 식이 꺼짐")
            continue
        print(f"   {no} {c}({bc}) 접안시각 {fmt(tc)} ≥ {a}({ba}) 접안시각 {fmt(ta)} + {what} = {fmt(need)}"
              f"{'  ← 등호' if tc == need else f'  (여유 {hh(tc - need)})'}")
    for i, b in s.order:
        r, c, p = s.rows[i], s.rows[i]["calc"], B.par[i, b]
        typ = B.win[i, b][r["k"]][2]
        rate = V[i].contract.rate_usd_day
        line = (f"   (5) {i}: {'접안형 창 → 정박개시 = 접안시각' if typ == 'T' else '고정형 창 → 정박개시 = 고정개시'} {fmt(c['laytime_start'])} · "
                f"체선시간 = max(0, 접안시각 {H(r['t'])} + 호스분리까지 {num(p['q'])} − 정박개시 {H(c['laytime_start'])} − 허용시간 {num(p['L'])}")
        if c["weather_minutes"]:
            line += f" − 공제비율 {p['rho']:g} × 기상체선시간 {num(c['weather_minutes'])}"
        print(line + f") = {hh(float(c['demurrage_minutes']))} → × 시간당 ${rate / 24:,.0f} = ${usd(c['amount_cents'])}")
    for i, b in s.order:
        c = s.rows[i]["calc"]
        if B.rules == "ppt" and c["weather_minutes"]:
            a = c["laytime_end"] if WEATHER_FROM == "end" else c["laytime_start"]
            z = s.rows[i]["t"] if WEATHER_FROM == "wait" else c["hose_off"]
            la, lz = WEATHER_LABEL[WEATHER_FROM]
            print(f"   (6) {i}: 기상체선시간 = 기상 악화 제약 시간 중 [{la} {fmt(a)}, {lz} {fmt(z)}]에 든 시간"
                  f" = {hh(c['weather_minutes'])} → 그 {B.par[i, b]['rho']:g}배를 체선시간에서 뺌")
    for i, b in s.order:
        r, c = s.rows[i], s.rows[i]["calc"]
        if r["t0"] is not None and r["t0"] != r["t"]:
            print(f"   (6) {i}: 기상없었다면접안 {fmt(r['t0'])} → 기상체선시간 = max(0, 접안시각 {fmt(r['t'])} − max(기상없었다면접안 {fmt(r['t0'])}, "
                  f"정박종료 {fmt(c['laytime_end'])})) = {hh(c['weather_minutes'])}")
    h0, h1 = day_start(ctx.sc.horizon_start), day_start(ctx.sc.horizon_end)
    placed = dict(B.base.pl)
    placed.update({i: s.rows[i]["p"] for i in B.mov})
    for gname, inv in ctx.sc.inventory.items():
        if not any(V[i].cargo_group == gname for i in B.mov):
            continue
        level, d, parts = inv.opening, h0, []
        while d <= h1:
            level += inv.daily_net + sum((V[v].qty if V[v].direction == "IMPORT" else -V[v].qty)
                                         for v, p in placed.items() if V[v].cargo_group == gname and day_start(p.work_start) == d)
            parts.append(f"{fmt(d)[:5]} {level:,.0f}")
            d += DAY
        print(f"   (7) {gname} 일말 재고(최소 {inv.minimum:,.0f} ~ 용량 {inv.capacity:,.0f}): " + " · ".join(parts))


def canonical_top(ctx, k=3):
    """엔진 완전 탐색(순서 n! × 부두 조합)의 상위 k개 — 금액은 '접안 시각 순서로 다시 붙였을 때'의 값으로 센다.

    엔진의 기상 체선 시간은 '그 배를 붙일 때 이미 놓여 있던 배'에 따라 정해져서, 같은 일정이어도 계획 목록의 순서가 다르면
    금액이 달라질 수 있다. 비교 기준을 하나로 맞추려고 접안 시각 순서로 다시 붙인다.
    돌려주는 것: ({부두별 순서: 금액} 중 낮은 k개, 엔진 그대로 셌을 때의 금액 목록)
    """
    base, V = initial_state(ctx), ctx.vessels
    top, raw_top = TopK(k), TopK(k)
    for perm in itertools.permutations(ctx.movable):
        for berths in itertools.product(*[ctx.eligible[v] for v in perm]):
            plan = list(zip(perm, berths))
            st, bad = decode(ctx, plan, base=base)
            if bad or validate(ctx, st.pl):
                continue
            raw = sum(amount_cents(ctx, V[v], p) for v, p in st.pl.items())
            order = sorted(plan, key=lambda vb: (st.pl[vb[0]].etb, vb[0]))
            st2, bad2 = decode(ctx, order, base=base)
            same = not bad2 and all(st2.pl[v].etb == st.pl[v].etb for v, _ in plan)
            cost = sum(amount_cents(ctx, V[v], p) for v, p in st2.pl.items()) if same else raw
            sig = _signature(st)
            top.offer(cost, sig, order)
            raw_top.offer(raw, sig, plan)
    return {sig: c for c, sig, _ in top.items}, [c for c, _, _ in raw_top.items]


def top_with_holds(doc, rules, k=3):
    """완전 탐색에 '조기 도착 선박을 Laycan From까지 일부러 기다리게 하기'를 선택지로 더했을 때의 상위 k개 금액(센트).

    기다리게 하려면 ETA를 'Laycan From − Direction'으로 늦추고 NOR 제출 시각에 원래 ETA를 넣는다(ETANR은 그대로).
    """
    early = [n for n, v in enumerate(doc["vessels"]) if parse_ts(v["eta"]) < parse_ts(v["contract"]["laycan_from"])]
    direction = {rules.berths[b].direction for b in doc["berths"]}
    if len(direction) != 1:
        return None
    best = {}
    for mask in itertools.product((0, 1), repeat=len(early)):
        d = copy.deepcopy(doc)
        for flag, n in zip(mask, early):
            if flag:
                v = d["vessels"][n]
                v["nor_tender"] = v["eta"]
                v["eta"] = fmt_iso(parse_ts(v["contract"]["laycan_from"]) - min(direction))
        ctx, _ = build_context(d, rules)
        if ctx is None:
            continue
        for sig, c in canonical_top(ctx, k)[0].items():
            if sig not in best or c < best[sig]:
                best[sig] = c
    return sorted(best.values())[:k]


def random_compare(n, seed, time_limit):
    """엔진 테스트(tests/test_optimizer.py)와 같은 무작위 사례 생성기로 MILP와 완전 탐색을 비교한다."""
    sys.path.insert(0, str(DEMO))
    try:
        from tests.test_optimizer import _random_case
    except ImportError as exc:      # pytest가 없으면 테스트 모듈을 못 읽는다
        raise SystemExit(f"무작위 비교에는 pytest가 필요함: {exc}")
    rules = rules_for()
    rng = random.Random(seed)
    checked = same = held = path_dep = disagree = 0
    others = []
    for idx in range(n):
        doc = _random_case(rng, rng.choice([2, 3, 4, 5]))
        if RULES == "ppt":
            doc = ppt_doc(doc)
        ctx, _ = build_context(doc, rules)
        if ctx is None:
            continue
        top, raw = canonical_top(ctx, 3)
        eng = sorted(top.values())
        B = build(ctx)
        sols = top_k(B, 3, time_limit)
        mine = [s.reprice_cents for s in sols]
        checked += 1
        path_dep += eng != raw
        disagree += B.m.disagreements > 0
        note = None
        if any(s.violations for s in sols) or any(s.status != "최적" for s in sols):
            note = "제약 위반 또는 최적 증명 실패"
        elif mine == eng:
            same += 1
        elif mine == top_with_holds(doc, rules, 3):
            held += 1
        else:
            note = "기다리기를 넣어도 다름"
        if note:
            others.append((idx, note, [usd(c) for c in eng], [usd(c) for c in mine],
                           [[(i, fmt(a), fmt(b)) for i, a, b in s.holds] for s in sols]))
    print(f"무작위 {checked}사례(시드 {seed}): 완전 탐색과 상위 3개 금액이 같음 {same} · 'Laycan From까지 기다리기'를 넣은 완전 탐색과 같음 {held}"
          f" · 그 밖 {len(others)} | 참고: 엔진 금액이 계획 순서에 따라 달라진 사례 {path_dep} · 솔버 두 설정이 엇갈린 사례 {disagree}")
    for o in others[:12]:
        print("   ", o)
    return checked, same, held, others


def main():
    ap = argparse.ArgumentParser(description="접안 계획 MILP — 엔진과 비교")
    ap.add_argument("--rules", choices=("ppt", "engine"), default="ppt",
                    help="ppt = 멘토링 PPT 그대로(정박개시 06·07시, 기상 공제는 제약 시간과 겹친 만큼, 조석·마감 제외) · engine = 데모 엔진 규칙 그대로")
    ap.add_argument("--weather-from", choices=("start", "end", "wait"), default="start",
                    help="PPT 기준에서 기상체선 시간을 세는 구간: start = 정박개시~호스분리 · end = 정박종료~호스분리 · wait = 정박개시~접안(기다린 시간)")
    ap.add_argument("--walk", metavar="ID", help="한 문제를 파라미터·변수·제약식 숫자까지 (예: GC-01, S05-storm-rush)")
    ap.add_argument("--lp", metavar="ID", help="솔버에 넣는 모델 전문(LP 형식)을 표준 출력으로")
    ap.add_argument("--random", type=int, metavar="N", help="무작위 사례 N개를 완전 탐색과 비교")
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--time-limit", type=float, default=300.0)
    ap.add_argument("--json", metavar="FILE", help="비교 결과를 JSON으로 저장")
    a = ap.parse_args()
    use_rules(a.rules, a.weather_from)
    if a.lp:
        doc, patch = find_problem(a.lp)
        B = build(ctx_from_doc(doc, patch))
        print(B.m.to_lp(f"{a.lp} — 접안 계획 MILP (솔버에 넣는 그대로: 시각 단위는 시간, 시각 0 = {fmt(B.T0)}, 큰 수 M에는 하루 여유 포함)\n"
                        "u 시간창선택 · y 앞뒤순서 · t 접안시각 · P 정박개시 · D 체선시간 · O 기상체선시간(구간별) · b 기상 스위치"))
        return 0
    if a.walk:
        walk(a.walk, a.time_limit)
        return 0
    if a.random:
        return 0 if not random_compare(a.random, a.seed, a.time_limit)[3] else 1
    rows = compare_all(a.time_limit)
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if not any(r["verdict"].startswith("다름") for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
