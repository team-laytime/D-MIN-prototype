"""계산 문맥 — 시나리오 하나를 계산하기 전에 한 번만 구해 두는 값들.

- 부두별 사용 제한(사용자 입력 + 풍속 예보에서 만든 기상 제한)
- 선박별 배정 가능 부두(FR-07·08)와 (선박, 부두)별 작업 소요(FR-22·23)
- 선박별 Last POB 해제 시각(ETB-03, ETA 기준이라 미리 정해진다)
- 동시 접안 제한이 걸리는 (부두, 부두) 짝 (ETB-05·06)
"""
from __future__ import annotations

from ..data.providers import SunTable, weather_restrictions
from ..domain.timeutil import DAY, HOUR, day_start, fmt
from .eligibility import eligible_berths
from .worktime import WorkModel


class Ctx:
    def __init__(self, sc, rules, work_model: WorkModel, sun: SunTable):
        self.sc = sc
        self.rules = rules
        self.sun = sun
        self.work_model = work_model
        self.vessels = {v.id: v for v in sc.vessels}
        self.movable = [v.id for v in sc.vessels if v.movable]
        self.immovable = [v.id for v in sc.vessels if v.immovable]
        self.berths = rules.berths
        self.berth_order = list(rules.berth_order)
        self.wx_restrictions = weather_restrictions(sc.weather_segments, rules.berths, rules.wind_limits)
        self.restrictions = list(sc.restrictions) + self.wx_restrictions
        self.restr_by_berth = {
            bid: sorted([r for r in self.restrictions if r.covers(bid)], key=lambda r: (r.start, r.end, r.id))
            for bid in self.berths}
        self.has_weather = {bid: any(r.reason == "WEATHER" for r in rs) for bid, rs in self.restr_by_berth.items()}
        self.tide = sc.tide_windows
        self.limit_end = sc.horizon_end + 3 * DAY  # 이 뒤로 밀리면 '기간 안 접안 불가'
        self.laytime_cache = {}

        self.eligible, self.excluded = {}, {}
        self.work = {}
        for v in sc.vessels:
            if v.status == "COMPLETED":
                continue
            if v.immovable:
                wp = work_model.plan(v, v.fixed_berth)
                if wp is not None:
                    self.work[(v.id, v.fixed_berth)] = wp
                continue
            ok, excluded = eligible_berths(v, rules.berths, self.berth_order, active=sc.active_berths)
            kept = []
            for bid in ok:
                wp = work_model.plan(v, bid)
                if wp is None:
                    excluded[bid] = [{"rule_id": "WRK-02", "item": "작업시간", "message": f"{bid} 작업시간 추정 불가(과거 실적 없음)"}]
                    continue
                self.work[(v.id, bid)] = wp
                kept.append(bid)
            self.eligible[v.id] = kept
            self.excluded[v.id] = excluded

        self.combo_of = {}
        for combo in rules.combos:
            for b in combo:
                self.combo_of.setdefault(b, []).append(combo)
        self.pair_of = {}
        for pair, exempt in rules.pairs:
            for b in pair:
                self.pair_of.setdefault(b, []).append((pair, exempt))

        self.last_pob = {vid: self._last_pob_release(v) for vid, v in self.vessels.items()}
        dw = rules.night["dawn_window"]
        self.dawn_from = int(dw["from_hour"]) * HOUR
        self.dawn_to = int(dw["to_hour"]) * HOUR
        self.dawn_release = int(dw["release_hour"]) * HOUR
        self.dawn_grt = int(dw["grt_min"])

    # ---------- 규칙 보조 ----------
    def _match(self, cond: dict, v) -> bool:
        if "grt_min" in cond and v.grt < cond["grt_min"]:
            return False
        if "grt_max" in cond and v.grt > cond["grt_max"]:
            return False
        if "direction" in cond and v.direction != cond["direction"]:
            return False
        if "draft_min" in cond and v.draft < cond["draft_min"]:
            return False
        return True

    def _last_pob_release(self, v):
        """ETB-03: 대상 선박의 ETA가 [Last POB, 다음 날 08:00) 안이면 (해제 시각, Last POB, 설명)."""
        cfg = self.rules.night["last_pob"]
        if not any(self._match(c, v) for c in cfg["subject_any"]):
            return None
        offset_h = None
        for o in cfg["offsets"]:
            if "grt_max" in o and v.grt <= o["grt_max"]:
                offset_h = o["sunset_minus_h"]
                break
            if "grt_min_exclusive" in o and v.grt > o["grt_min_exclusive"]:
                offset_h = o["sunset_minus_h"]
                break
        if offset_h is None:
            return None
        off = int(round(float(offset_h) * 60))
        rel_h = int(cfg["release_hour"]) * HOUR
        d_eta = day_start(v.eta)
        for d0 in (d_eta, d_eta - DAY):
            lp = self.sun.sunset(d0) - off
            rel = d0 + DAY + rel_h
            if lp <= v.eta < rel:
                return rel, lp, f"ETA {fmt(v.eta)} ≥ Last POB {fmt(lp)}(일몰 − {offset_h}h) → 다음 날 08:00"
        return None

    def conflict_rule(self, vj, bj: str, vk, bk: str):
        """두 선박이 동시에 작업하면 안 되는지. 규칙 ID 또는 None."""
        if bj == bk:
            return None
        for combo in self.combo_of.get(bj, ()):
            if bk in combo and vj.cargo_group == vk.cargo_group:
                return "ETB-05"
        for pair, exempt in self.pair_of.get(bj, ()):
            if bk in pair and not (vj.grt <= exempt and vk.grt <= exempt):
                return "ETB-06"
        return None

    def requires_tide(self, v, bid: str) -> bool:
        b = self.berths[bid]
        return b.tide_draft_threshold is not None and v.draft >= float(b.tide_draft_threshold)
