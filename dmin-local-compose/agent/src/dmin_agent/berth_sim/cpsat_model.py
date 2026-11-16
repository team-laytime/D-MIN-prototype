"""CP-SAT 조합 모델: 접안 가능 시각표 + 비용표 → 체선료 합계가 가장 작은 (부두, 접안 시각) 배정, 상위 N순위.

변수 — 접안 가능한 (선박, 부두) 쌍 p마다
  use[p]    이 부두를 쓰는가 (0/1). 선박마다 정확히 하나
  start[p]  접안 시각 칸 (정수). 값은 시각표에서 1인 칸으로만 제한
            → 부두 적합성 · 과거 실적 · 도착 · 사용 가능 시각 · 야간 도선 · 부두 제약 · FIX 충돌은 여기서 이미 반영
  fee[p]    비용표[p][start]
            비용 곡선이 볼록(늦을수록 같거나 더 가파르게 증가)이면 하한 볼록 껍질의 직선 몇 개로
            'fee ≥ 각 직선'을 건다 (최소화하므로 fee = 직선들의 최대 = 비용표 값, 오차 $1 이내).
            볼록이 아닌 곡선만 Element(표 조회) 제약 — Element 2,880칸 표는 무거워서 최소한으로만 쓴다.

제약 — 다른 선박 배치에 따라 달라지는 조건
  같은 부두   부두마다 점유 구간 [ETB, ETU + Switching)이 겹치지 않음 (NoOverlap)        ①
  동일 화물   {#6,#7,#8} · {#1-1,#1-2,#2-7} 같은 화물 그룹끼리 작업 구간 [ETB, ETU−2h) 겹치지 않음  ③-1
  #4 동시    #4-1 · #4-2 작업 구간 겹치지 않음, 두 척 모두 GRT ≤ 3천이면 예외                 ③-2
  (구간 길이는 5분 칸 단위로 올림 → 실제보다 최대 5분 보수적)

목표 (앞이 항상 우선)
  1) 체선료 합계 최소  2) 같으면 부두 변경(실제 계획 대비) 최소  3) 같으면 일찍 접안 (불필요한 대기 없음)

상위 N순위
  1순위를 찾은 뒤 '앞 순위와 최소 MIN_DIFF척은 부두가 달라야 함' 제약을 더하고 다시 푼다. 이를 N번 반복.
  (1척만 달라도 되게 하면 체선료 0인 선박을 같은 비용의 옆 부두로 옮긴 사실상 같은 계획만 나온다)
  각 순위가 OPTIMAL이면 '앞 순위들과 충분히 다른 계획 중 최선'이 증명된 것.
"""

import math
import time as _time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from ortools.sat.python import cp_model

from .cost_table import CostRow
from .feasibility import FeasibilityTable
from .models import Vessel
from .shifting import switching
from .step3_berth_pair import SIMULTANEOUS_BERTH_PAIRS, SMALL_GRT
from .step3_cargo_group import ETU_TO_WORK_END, SAME_CARGO_BERTH_GROUPS
from .synth import SynthData

TIME_LIMIT_S = 30.0  # 순위 하나 찾는 데 쓰는 최대 시간
TOP_K = 5
MIN_DIFF = 3  # 다음 순위는 앞 순위 각각과 최소 이만큼의 선박이 다른 부두
MAX_GAP_ROUNDS = 20  # 빈 시간 대기 검사 → 조건 추가 → 다시 풀기 반복 한도
WORKERS = 8
HULL_TOLERANCE = 1  # 볼록 껍질이 비용표보다 이만큼(센트)까지 낮아도 직선 방식 사용


def lower_hull(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """(칸, 비용) 점들의 아래쪽 볼록 껍질 (칸 오름차순)."""
    h: list[tuple[int, int]] = []
    for pt in points:
        while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (pt[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (pt[0] - h[-2][0]) <= 0:
            h.pop()
        h.append(pt)
    return h


def _hull_gap(hull: list[tuple[int, int]], points: list[tuple[int, int]]) -> float:
    """껍질이 비용표보다 낮게 잡는 최대 금액 (볼록이면 0~반올림 오차)."""
    if len(hull) == 1:
        return max(f - hull[0][1] for _, f in points)
    segs = list(zip(hull, hull[1:]))
    return max(f - max(f1 + (f2 - f1) * (t - t1) / (t2 - t1) for (t1, f1), (t2, f2) in segs) for t, f in points)


def _ceil_slots(td: timedelta, step: timedelta) -> int:
    return max(1, math.ceil(td / step))


@dataclass(frozen=True)
class Assignment:
    vessel_id: str
    berth: str
    slot: int
    etb: datetime
    fee: int


@dataclass(frozen=True)
class SolveResult:
    rank: int
    status: str
    total_fee: int | None
    best_bound: float | None  # 체선료 하한 (이 순위 탐색 범위 안에서)
    wall_s: float
    assignments: dict[str, Assignment]
    moves: int  # 실제 계획 대비 부두 변경 선박 수
    n_pairs: int
    n_constraints: dict[str, int] = field(default_factory=dict)
    tier: int = 0  # 체선료 구간 번호 (1부터)
    alt: int = 0  # 구간 안 순번 (0 = 대표)
    diff_rep: int = 0  # 구간 대표와 부두가 다른 선박 수
    model_fee: int | None = None  # 모델 안의 체선료 합 (센트, 구간 경계 비교용)
    waits: int | None = None  # 불필요한 대기 검사 위반 선박 수 (0이어야 함)

    @property
    def gap(self) -> float | None:
        if self.total_fee is None or self.best_bound is None or self.total_fee == 0:
            return None
        return max(0.0, (self.total_fee - self.best_bound) / self.total_fee)

    def plan(self, sequences: dict[str, list[Vessel]]) -> dict[str, list[Vessel]]:
        """배정 결과를 부두별 접안 순서로 (규칙 엔진 재평가용)."""
        vessels = {v.vessel_id: v for s in sequences.values() for v in s}
        out: dict[str, list[Vessel]] = {}
        for a in sorted(self.assignments.values(), key=lambda a: (a.slot, a.vessel_id)):
            out.setdefault(a.berth, []).append(replace(vessels[a.vessel_id], berth=a.berth))
        return out


FEE_TOL = 3  # 구간 직선과 비용표의 허용 차이 (센트, 반올림 오차)


def segments(slots: list[int], etu: dict[int, int], fee: dict[int, int], tol: int = FEE_TOL) -> list[tuple]:
    """접안 칸을 'ETU와 체선료가 둘 다 직선'인 연속 구간으로 나눈다 → [(a, b, etu_a, etu 기울기 0/1, fee_a, fee_b)].

    ETU 기울기: 평소 1 (늦게 접안하면 그만큼 늦게 끝남), 하역 중단 중 접안하면 0 (중단이 끝나야 시작하므로 같은 시각에 끝남).
    중단 구간 직전에 끝나던 작업이 중단에 걸리면 ETU가 중단 길이만큼 뛴다 → 구간을 나눈다.
    """
    out, k, n = [], 0, len(slots)
    while k < n:
        a = b = k
        while b + 1 < n and slots[b + 1] == slots[b] + 1:
            de = etu[slots[b + 1]] - etu[slots[b]]
            if de not in (0, 1):
                break
            if b > a:
                if de != etu[slots[a + 1]] - etu[slots[a]]:
                    break
                if abs((fee[slots[b + 1]] - fee[slots[b]]) - (fee[slots[b]] - fee[slots[b - 1]])) > tol:
                    break
            b += 1
        out += _split_until_linear(slots[a:b + 1], etu, fee, tol)
        k = b + 1
    return out


def _split_until_linear(run: list[int], etu, fee, tol) -> list[tuple]:
    a, b = run[0], run[-1]
    if a == b:
        return [(a, a, etu[a], 0, fee[a], fee[a])]
    worst = max(run, key=lambda t: abs(fee[t] - (fee[a] + (fee[b] - fee[a]) * (t - a) / (b - a))))
    if abs(fee[worst] - (fee[a] + (fee[b] - fee[a]) * (worst - a) / (b - a))) <= tol:
        return [(a, b, etu[a], etu[run[1]] - etu[a], fee[a], fee[b])]
    i = run.index(worst)
    i = max(1, min(i, len(run) - 1))
    return _split_until_linear(run[:i], etu, fee, tol) + _split_until_linear(run[i:], etu, fee, tol)


class BerthModel:
    """모델을 한 번 만들고, 조건(가정)을 바꿔 가며 다시 푼다.

    기상 하역 중단 때문에 ETU(→ 부두 점유 · 작업 구간)와 체선료가 접안 시각에 따라 달라진다.
    선박·부두 쌍마다 비용표의 칸별 ETU · 체선료를 'ETU와 체선료가 둘 다 직선인 구간'으로 나눠 정확히 넣는다:
      구간 z 선택 → a ≤ start ≤ b, ETU = etu_a + 기울기·(start − a), 체선료 = 직선 ± 3센트.
    (stays 인자는 예전 호환용으로 받기만 한다)
    """

    def __init__(
        self, table: FeasibilityTable, costs: dict[tuple[str, str], CostRow], data: SynthData,
        stays: dict[tuple[str, str], timedelta] | None, home: dict[str, str], no_wait: bool = True,
        tanks=None,
    ):
        self.table, self.costs = table, costs
        m = self.m = cp_model.CpModel()
        n = table.n_slots
        step_min = int(table.step.total_seconds() // 60)
        self.slot_h = int(timedelta(hours=1) / table.step)
        self.work_back = math.ceil(ETU_TO_WORK_END / table.step)  # 작업완료 = ETU − 2h
        pairs = self.pairs = list(costs)
        vessels = sorted({p[0] for p in pairs})
        self.use, self.start, self.etu, self.windows, self.sw = {}, {}, {}, {}, {}
        self.etu_at: dict[tuple[str, str], dict[int, int]] = {}
        self.dmax_occ, self.dmax_work = {}, {}
        occ, work = {}, {}
        fee_terms, start_terms, move_terms = [], [], []
        counts = self.counts = {"선박당 1부두": 0, "같은 부두": 0, "동일 화물": 0, "#4 동시 접안": 0, "ETU·체선료 구간": 0}

        for p in pairs:
            vid, b = p
            c = costs[p]
            slots = c.feasible_slots()
            windows, s0 = [], slots[0]
            for prev, cur in zip(slots, slots[1:] + [None]):
                if cur != prev + 1:
                    windows.append([s0, prev])
                    s0 = cur
            self.windows[p] = windows
            etu_at = self.etu_at[p] = {i: math.ceil(c.etu[i] / step_min) for i in slots}
            fee_at = {i: c.fee_c[i] for i in slots}
            sw = self.sw[p] = math.ceil(switching(b) / table.step)
            self.dmax_occ[p] = max(etu_at[i] + sw - i for i in slots)
            self.dmax_work[p] = max(etu_at[i] - self.work_back - i for i in slots)

            use = self.use[p] = m.new_bool_var(f"use[{vid},{b}]")
            start = self.start[p] = m.new_int_var_from_domain(cp_model.Domain.from_intervals(windows), f"start[{vid},{b}]")
            etu = self.etu[p] = m.new_int_var(min(etu_at.values()), max(etu_at.values()), f"etu[{vid},{b}]")
            top = max(fee_at.values()) + FEE_TOL
            fee = m.new_int_var(0, top, f"fee[{vid},{b}]")  # 센트
            m.add(fee == 0).only_enforce_if(~use)
            zs = []
            for a, bb, e_a, de, f_a, f_b in segments(slots, etu_at, fee_at):
                z = m.new_bool_var(f"seg[{vid},{b},{a}]")
                m.add(start >= a).only_enforce_if(z)
                m.add(start <= bb).only_enforce_if(z)
                m.add(etu == e_a + de * (start - a)).only_enforce_if(z)
                if a == bb:
                    m.add(fee == f_a).only_enforce_if(z)
                else:  # fee ≈ f_a + (f_b − f_a)/(b − a)·(start − a)  (양변 × (b − a) → 정수 계수)
                    m.add((bb - a) * fee >= (f_b - f_a) * (start - a) + (f_a - FEE_TOL) * (bb - a)).only_enforce_if(z)
                    m.add((bb - a) * fee <= (f_b - f_a) * (start - a) + (f_a + FEE_TOL) * (bb - a)).only_enforce_if(z)
                zs.append(z)
            m.add(sum(zs) == use)
            counts["ETU·체선료 구간"] += len(zs)
            fee_terms.append(fee)

            used_start = m.new_int_var(0, n, f"ustart[{vid},{b}]")
            m.add(used_start == start).only_enforce_if(use)
            m.add(used_start == 0).only_enforce_if(~use)
            start_terms.append(used_start)
            if b != home.get(vid):
                move_terms.append(use)

            # 부두 점유 [ETB, ETU + Switching) · 작업 구간 [ETB, ETU − 2h) — 길이가 접안 시각에 따라 다름
            occ_size = m.new_int_var(1, self.dmax_occ[p], f"occsize[{vid},{b}]")
            m.add(occ_size == etu + sw - start).only_enforce_if(use)
            occ[p] = m.new_optional_interval_var(start, occ_size, etu + sw, use, f"occ[{vid},{b}]")
            work_size = m.new_int_var(1, max(1, self.dmax_work[p]), f"worksize[{vid},{b}]")
            m.add(work_size == etu - self.work_back - start).only_enforce_if(use)
            work[p] = m.new_optional_interval_var(start, work_size, etu - self.work_back, use, f"work[{vid},{b}]")

        for vid in vessels:
            m.add_exactly_one(self.use[p] for p in pairs if p[0] == vid)
            counts["선박당 1부두"] += 1
        for b in {p[1] for p in pairs}:
            ivs = [occ[p] for p in pairs if p[1] == b]
            if len(ivs) > 1:
                m.add_no_overlap(ivs)
                counts["같은 부두"] += 1
        cargo = {vid: data.profiles[vid].cargo_group for vid in vessels}
        for group in SAME_CARGO_BERTH_GROUPS:
            by_cargo: dict[str, list] = {}
            for p in pairs:
                if p[1] in group:
                    by_cargo.setdefault(cargo[p[0]], []).append(work[p])
            for ivs in by_cargo.values():
                if len(ivs) > 1:
                    m.add_no_overlap(ivs)
                    counts["동일 화물"] += 1
        small = self.small = {vid: data.profiles[vid].grt <= SMALL_GRT for vid in vessels}
        self.cargo = cargo
        for group in SIMULTANEOUS_BERTH_PAIRS:
            members = [p for p in pairs if p[1] in group]
            for i, p in enumerate(members):
                for q in members[i + 1:]:
                    if p[0] != q[0] and p[1] != q[1] and not (small[p[0]] and small[q[0]]):
                        m.add_no_overlap([work[p], work[q]])
                        counts["#4 동시 접안"] += 1

        # 사전식 목표: 체선료 ≫ 부두 변경 ≫ 접안 시각 합
        self.fee_sum, self.move_sum, self.start_sum = sum(fee_terms), sum(move_terms), sum(start_terms)
        self.w_move = n * len(vessels) + 1
        self.w_fee = self.w_move * (len(vessels) + 1)
        self.n_vessels = len(vessels)
        self.home = home
        counts["대기 금지"] = 0
        if no_wait:
            self._add_no_wait()
        if tanks is not None:
            self._add_tanks(tanks)
        self.objective_cheapest()

    # ── 구간 끝 (칸 단위) ──
    def end_at(self, p, t: int, kind: str) -> int:
        """p를 t에 접안했을 때 kind 구간의 끝 칸 (occ = ETU + Switching, work = ETU − 2h)."""
        e = self.etu_at[p][t]
        return e + self.sw[p] if kind == "occ" else e - self.work_back

    def end_expr(self, q, kind: str):
        return self.etu[q] + self.sw[q] if kind == "occ" else self.etu[q] - self.work_back

    def _add_tanks(self, ts) -> None:
        """탱크 재고 안전 범위 (Reservoir 제약). 수위 = 시작 재고 대비 변화량 (Reservoir는 0에서 시작).

        선박 하역·선적은 실제로는 작업 시간 동안 (기상 중단 때는 멈추며) 조금씩이지만,
        범위를 넘기 쉬운 쪽으로 한꺼번에 일어난다고 본다:
          상한 검사  반입은 작업시작에 전량 · 반출은 작업완료에 전량
          하한 검사  반입은 작업완료에 전량 · 반출은 작업시작에 전량
        공정 처리·생산도 상한 검사에선 증가를 시간 초, 감소를 시간 끝에 (하한은 반대) 둔다.
        → 이 제약을 통과한 계획은 실제 시간대별 재고(tanks.simulate)로도 범위를 지킨다.
        """
        m, slot_h = self.m, self.slot_h
        self.counts["탱크"] = 0
        for tank in ts.tanks.values():
            vids = {f.vessel_id for f in ts.flows.values() if f.tank == tank.name}
            hi_t, hi_c, hi_a, lo_t, lo_c, lo_a = [], [], [], [], [], []
            for k in range(ts.hours):  # 공정 처리 · 생산: 시간마다 일정량 (누적 반올림으로 오차 없이)
                c = round(tank.rate_per_h * (k + 1)) - round(tank.rate_per_h * k)
                if c == 0:
                    continue
                early, late = k * slot_h, (k + 1) * slot_h
                hi_t.append(early if c > 0 else late); hi_c.append(c); hi_a.append(True)
                lo_t.append(late if c > 0 else early); lo_c.append(c); lo_a.append(True)
            for p in self.pairs:
                if p[0] not in vids:
                    continue
                f = ts.flows[p[0]]
                ws, wf = self.start[p] + slot_h, self.etu[p] - self.work_back  # 작업시작 ETB+1h · 작업완료 ETU−2h
                change = f.sign * f.qty
                hi_t.append(ws if f.sign > 0 else wf); hi_c.append(change); hi_a.append(self.use[p])
                lo_t.append(wf if f.sign > 0 else ws); lo_c.append(change); lo_a.append(self.use[p])
            big = tank.capacity + sum(abs(c) for c in hi_c)
            m.add_reservoir_constraint_with_active(hi_t, hi_c, hi_a, -big, tank.hi - tank.initial)
            m.add_reservoir_constraint_with_active(lo_t, lo_c, lo_a, tank.lo - tank.initial, big)
            self.counts["탱크"] += 1

    def _rivals(self, p: tuple[str, str]) -> list[tuple[tuple[str, str], str]]:
        """p를 막을 수 있는 다른 선박 쌍 q와 겹침을 보는 구간 종류 (occ = 같은 부두 점유, work = 작업 구간)."""
        out = []
        vid, b = p
        for q in self.pairs:
            if q[0] == vid:
                continue
            if q[1] == b:
                out.append((q, "occ"))
            elif any(b in g and q[1] in g for g in SAME_CARGO_BERTH_GROUPS) and self.cargo[q[0]] == self.cargo[vid]:
                out.append((q, "work"))  # 동일 화물 그룹
            elif any(b in g and q[1] in g for g in SIMULTANEOUS_BERTH_PAIRS) and not (self.small[vid] and self.small[q[0]]):
                out.append((q, "work"))  # #4 동시 접안
        return out

    def _add_no_wait(self) -> None:
        """불필요한 대기 금지: 접안한 선박은 (가장 이른 칸) 이거나 (바로 앞 가능 칸으로 당기면 다른 선박과 충돌).

        '바로 앞 가능 칸' = 같은 접안 가능 구간 안이면 한 칸 앞, 구간 첫 칸이면(야간 도선 등으로 끊긴 뒤)
        앞 구간의 마지막 칸. p 쪽 구간 길이는 가장 긴 경우로 본다(느슨) — 정확한 검사는 빈 시간 검사(gap_waits)가 한다.
        """
        m = self.m
        for p in self.pairs:
            wins, start, use = self.windows[p], self.start[p], self.use[p]
            first = m.new_bool_var(f"first[{p}]")
            m.add(start == wins[0][0]).only_enforce_if(first)
            m.add(start >= wins[0][0] + 1).only_enforce_if(~first)
            rivals = self._rivals_cached(p)
            if not rivals:
                m.add_implication(use, first)  # 막을 선박이 없으면 가장 이른 칸
                self.counts["대기 금지"] += 1
                continue
            prev = m.new_int_var(wins[0][0], wins[-1][1], f"prev[{p}]")
            at_win = []
            for (a, _), (_, b_prev) in zip(wins[1:], wins[:-1]):  # 각 구간 첫 칸 → 앞 구간 마지막 칸
                z = m.new_bool_var(f"winstart[{p},{a}]")
                m.add(start == a).only_enforce_if(z)
                m.add(start != a).only_enforce_if(~z)
                m.add(prev == b_prev).only_enforce_if(z)
                at_win.append(z)
            inner = m.new_bool_var(f"inner[{p}]")  # 구간 중간: 한 칸 앞
            m.add_bool_and([~first] + [~z for z in at_win]).only_enforce_if(inner)
            m.add_bool_or([first] + at_win).only_enforce_if(~inner)
            m.add(prev == start - 1).only_enforce_if(inner)

            blocks = []
            for q, kind in rivals:
                dp = self.dmax_occ[p] if kind == "occ" else self.dmax_work[p]
                ov = m.new_bool_var(f"block[{p},{q}]")
                m.add_implication(ov, self.use[q])
                m.add(self.start[q] <= prev + dp - 1).only_enforce_if(ov)  # prev에 두면 겹침
                m.add(prev <= self.end_expr(q, kind) - 1).only_enforce_if(ov)
                blocks.append(ov)
            m.add_bool_or(blocks).only_enforce_if([use, ~first])
            self.counts["대기 금지"] += 1

    def objective_cheapest(self) -> None:
        """체선료 ≫ 부두 변경 ≫ 접안 시각."""
        self.m.minimize(self.fee_sum * self.w_fee + self.move_sum * self.w_move + self.start_sum)

    def objective_most_different(self, rep: SolveResult) -> None:
        """대표와 부두가 다른 선박 수 최대 ≫ 체선료 작게 ≫ 일찍 접안 (빈 시간을 두고 기다리는 배치를 줄인다)."""
        same = sum(self.use[(a.vessel_id, a.berth)] for a in rep.assignments.values())
        w_fee = self.w_move  # 접안 시각 합의 최대보다 큼
        max_fee = sum(max(self.costs[p].fee_c[i] for i in self.windows_slots(p)) + FEE_TOL for p in self.pairs)
        self.m.minimize(same * (max_fee + 1) * w_fee + self.fee_sum * w_fee + self.start_sum)

    def windows_slots(self, p):
        return self.costs[p].feasible_slots()

    def when(self, constraint_builder) -> cp_model.IntVar:
        """조건부 제약: 반환한 리터럴을 가정(assumption)으로 켤 때만 적용."""
        lit = self.m.new_bool_var("cond")
        constraint_builder(self.m).only_enforce_if(lit)
        return lit

    def differ_at_least(self, res: SolveResult, k: int) -> cp_model.IntVar:
        same = [self.use[(a.vessel_id, a.berth)] for a in res.assignments.values()]
        return self.when(lambda m: m.add(sum(same) <= len(same) - k))

    def hint(self, plan: dict[str, tuple[str, datetime]]) -> None:
        self.m.clear_hints()
        for p in self.pairs:
            hb, hetb = plan.get(p[0], (None, None))
            self.m.add_hint(self.use[p], p[1] == hb)
            if p[1] == hb:
                self.m.add_hint(self.start[p], min(self.table.n_slots - 1, -(-(hetb - self.table.start) // self.table.step)))

    def exclude(self, res: SolveResult, min_diff: int = MIN_DIFF) -> None:
        """이 부두 배정과 min_diff척 미만으로만 다른 계획을 금지한다."""
        chosen = [self.use[(a.vessel_id, a.berth)] for a in res.assignments.values()]
        self.m.add(sum(chosen) <= len(chosen) - min_diff)

    def solve_once(self, rank: int, time_limit_s: float = TIME_LIMIT_S, workers: int = WORKERS,
                   assume: list | None = None, **meta) -> SolveResult:
        """풀기 → 빈 시간을 두고 기다린 선박 검사 → 있으면 '그 시각엔 막는 선박이 있어야 늦출 수 있다' 조건 추가 → 다시.

        추가하는 조건은 현장 기준(빈 시간이 있으면 먼저 넣는다)에서 항상 참이라 모델에 영구로 남겨 다른 풀이에도 쓴다.
        마지막 결과는 이 검사를 반드시 통과한다 (MAX_GAP_ROUNDS 안에 못 끝내면 waits > 0으로 표시).
        """
        wall = 0.0
        res = None
        for _ in range(MAX_GAP_ROUNDS):
            res = self._solve_raw(rank, time_limit_s, workers, assume, **meta)
            wall += res.wall_s
            if not res.assignments:
                break
            gaps = self.gap_waits(res)
            if not gaps:
                break
            for p, t in gaps:
                self._add_gap_cut(p, t)
            self.hint({a.vessel_id: (a.berth, a.etb) for a in res.assignments.values()})
        waits = len(self.gap_waits(res)) if res and res.assignments else None
        return replace(res, wall_s=wall, waits=waits)

    def _solve_raw(self, rank, time_limit_s, workers, assume, **meta) -> SolveResult:
        self.m.clear_assumptions()
        if assume:
            self.m.add_assumptions(assume)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_s
        solver.parameters.num_workers = workers
        t0 = _time.perf_counter()
        status = solver.solve(self.m)
        wall = _time.perf_counter() - t0
        assignments = {}
        fee_val = bound = model_fee = None
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            model_fee = int(solver.value(self.fee_sum))
            for p in self.pairs:
                if solver.value(self.use[p]):
                    s = solver.value(self.start[p])
                    assignments[p[0]] = Assignment(p[0], p[1], s, self.table.time(s), round(self.costs[p].fee_c[s] / 100))
            fee_val = round(sum(self.costs[(a.vessel_id, a.berth)].fee_c[a.slot] for a in assignments.values()) / 100)
            bound = math.floor(solver.best_objective_bound / self.w_fee / 100) if meta.get("alt", 0) == 0 else None
        moves = sum(1 for a in assignments.values() if a.berth != self.home.get(a.vessel_id))
        return SolveResult(rank, solver.status_name(status), fee_val, bound, wall, assignments, moves,
                           len(self.pairs), dict(self.counts), model_fee=model_fee, **meta)

    def gap_waits(self, res: SolveResult) -> list[tuple[tuple[str, str], int]]:
        """다른 선박을 그대로 둔 채 더 이른 접안 가능 칸에 넣어도 아무와도 안 겹치는 선박 → (쌍, 그 칸).
        구간 길이는 그 칸에 접안했을 때의 실제 값(기상 중단 반영)."""
        placed = {(a.vessel_id, a.berth): a.slot for a in res.assignments.values()}
        out = []
        for p, s in placed.items():
            rivals = [(placed[q], self.end_at(q, placed[q], kind), kind) for q, kind in self._rivals_cached(p) if q in placed]
            for t in self.costs[p].feasible_slots():
                if t >= s:
                    break
                if not any(qs < self.end_at(p, t, kind) and t < qe for qs, qe, kind in rivals):
                    out.append((p, t))
                    break
        return out

    def wait_violations(self, res: SolveResult) -> list[str]:
        return [f"{p[0]} #{p[1]}: {self.table.time(t):%m/%d %H:%M}에 들어갈 수 있는데 "
                f"{self.table.time(res.assignments[p[0]].slot):%m/%d %H:%M}까지 대기" for p, t in self.gap_waits(res)]

    def _rivals_cached(self, p):
        if not hasattr(self, "_rival_cache"):
            self._rival_cache = {}
        if p not in self._rival_cache:
            self._rival_cache[p] = self._rivals(p)
        return self._rival_cache[p]

    def _add_gap_cut(self, p: tuple[str, str], t: int) -> None:
        """p가 t보다 늦게 접안하려면, p를 t에 두었을 때 겹치는 선박이 반드시 있어야 한다."""
        m = self.m
        late = m.new_bool_var(f"late[{p},{t}]")
        m.add(self.start[p] >= t + 1).only_enforce_if(late)
        m.add(self.start[p] <= t).only_enforce_if(~late)
        blocks = []
        for q, kind in self._rivals_cached(p):
            z = m.new_bool_var(f"gapblock[{p},{q},{t}]")
            m.add_implication(z, self.use[q])
            m.add(self.start[q] <= self.end_at(p, t, kind) - 1).only_enforce_if(z)
            m.add(t <= self.end_expr(q, kind) - 1).only_enforce_if(z)
            blocks.append(z)
        if blocks:
            m.add_bool_or(blocks).only_enforce_if([self.use[p], late])
        else:
            m.add_implication(self.use[p], ~late)
        self.counts["빈 시간 대기 금지"] = self.counts.get("빈 시간 대기 금지", 0) + 1


def solve_top_k(
    table: FeasibilityTable, costs: dict[tuple[str, str], CostRow], data: SynthData,
    stays: dict[tuple[str, str], timedelta], home: dict[str, str], hint: dict[str, tuple[str, datetime]] | None = None,
    k: int = TOP_K, time_limit_s: float = TIME_LIMIT_S, on_result: Callable[[SolveResult], None] | None = None,
    min_diff: int = MIN_DIFF,
) -> list[SolveResult]:
    model = BerthModel(table, costs, data, stays, home)
    if hint:
        model.hint(hint)
    out: list[SolveResult] = []
    for rank in range(1, k + 1):
        res = model.solve_once(rank, time_limit_s)
        if not res.assignments:
            break
        out.append(res)
        if on_result:
            on_result(res)
        model.exclude(res, min_diff)
        model.hint({a.vessel_id: (a.berth, a.etb) for a in res.assignments.values()})
    return out


TIERS = 1  # 1구간(최적해 + 같은 구간 대안)만 사용
PER_TIER = 3
BAND = 500  # 대안 허용 범위($): 대안은 최적해 체선료 + 이 금액 미만 (구간을 여러 개 풀 때는 구간 간격)


def solve_tiers(
    table: FeasibilityTable, costs: dict[tuple[str, str], CostRow], data: SynthData,
    stays: dict[tuple[str, str], timedelta], home: dict[str, str], hint: dict[str, tuple[str, datetime]] | None = None,
    tiers: int = TIERS, per_tier: int = PER_TIER, band: float = BAND, time_limit_s: float = TIME_LIMIT_S,
    min_diff: int = MIN_DIFF, on_result: Callable[[SolveResult], None] | None = None, tanks=None,
) -> list[SolveResult]:
    """체선료 구간 Top N, 구간마다 대표 1개 + 대표와 부두가 많이 다른 순으로 대안 (최대 per_tier개). 모두 CP-SAT.

    모든 풀이에 '불필요한 대기 금지'가 들어 있어, 금액 조건을 맞추려고 선박을 일부러 늦추는 계획은 나오지 않는다.
    구간 t 대표: 체선료 ≥ (구간 t−1 대표 + band) 중 최선 (체선료 ≫ 부두 변경 ≫ 접안 시각)
    구간 t 대안: 체선료 < 대표 + band 이면서 대표 · 앞 대안과 각각 min_diff척 이상 다른 계획 중
                 대표와 부두가 다른 선박이 가장 많은 것 → 많이 바뀌는 순으로 나온다
    시간 제한으로 대표가 최적 증명을 못 해 대안이 더 싸게 나오면, 구간에서 가장 싼 계획을 대표로 다시 정한다.
    """
    band_c = int(round(band * 100))
    model = BerthModel(table, costs, data, stays, home, tanks=tanks)
    if hint:
        model.hint(hint)
    out: list[SolveResult] = []
    floor_lit, rank = None, 0
    for t in range(1, tiers + 1):
        model.objective_cheapest()
        rank += 1
        rep = model.solve_once(rank, time_limit_s, assume=[floor_lit] if floor_lit is not None else None, tier=t, alt=0)
        if not rep.assignments:
            break
        out.append(rep)
        if on_result:
            on_result(rep)

        cap = model.when(lambda m, f=rep.model_fee: m.add(model.fee_sum <= f + band_c - 1))
        tier_lits = ([floor_lit] if floor_lit is not None else []) + [cap, model.differ_at_least(rep, min_diff)]
        model.objective_most_different(rep)
        for j in range(1, per_tier):
            rank += 1
            alt = model.solve_once(rank, time_limit_s, assume=tier_lits, tier=t, alt=j)
            if not alt.assignments:
                rank -= 1
                break
            alt = replace(alt, diff_rep=_berth_diff(alt, rep))
            out.append(alt)
            if on_result:
                on_result(alt)
            tier_lits.append(model.differ_at_least(alt, min_diff))
        floor_lit = model.when(lambda m, f=rep.model_fee: m.add(model.fee_sum >= f + band_c))
        model.hint({a.vessel_id: (a.berth, a.etb) for a in rep.assignments.values()})
    return _reselect_reps(out)


def _berth_diff(a: SolveResult, b: SolveResult) -> int:
    return sum(1 for v, x in a.assignments.items() if b.assignments[v].berth != x.berth)


def _reselect_reps(results: list[SolveResult]) -> list[SolveResult]:
    """구간마다 가장 싼 계획(같으면 부두 변경 적은 것)을 대표로, 나머지는 대표와 다른 척수가 많은 순."""
    out = []
    for t in sorted({r.tier for r in results}):
        group = [r for r in results if r.tier == t]
        rep = min(group, key=lambda r: (r.model_fee, r.moves, r.alt))
        alts = sorted((r for r in group if r is not rep), key=lambda r: -_berth_diff(r, rep))
        out.append(replace(rep, alt=0, diff_rep=0))
        out += [replace(r, alt=j, diff_rep=_berth_diff(r, rep)) for j, r in enumerate(alts, 1)]
    return out


def solve(table, costs, data, stays, hint=None, time_limit_s: float = TIME_LIMIT_S, home: dict[str, str] | None = None) -> SolveResult:
    """1순위만."""
    model = BerthModel(table, costs, data, stays, home or {})
    if hint:
        model.hint(hint)
    return model.solve_once(1, time_limit_s)


def stays_for(table: FeasibilityTable, costs: dict[tuple[str, str], CostRow]) -> dict[tuple[str, str], timedelta]:
    return {(r.vessel_id, r.berth): r.stay for r in table.rows if (r.vessel_id, r.berth) in costs}


def hint_from(outcomes) -> dict[str, tuple[str, datetime]]:
    """규칙 엔진 결과(ScenarioResult.outcomes)를 시작 힌트로."""
    return {o.vessel.vessel_id: (o.vessel.berth, o.etb) for o in outcomes}


def home_from(sequences: dict[str, list[Vessel]]) -> dict[str, str]:
    return {v.vessel_id: b for b, seq in sequences.items() for v in seq}
