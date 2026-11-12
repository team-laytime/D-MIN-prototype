"""입력 변화 민감도 (FR-43): ETA ±6시간, 기상 예보 변경 시 후보 순위가 바뀌는가.

방법: 후보마다 '부두별 순서'를 그대로 두고(=그 계획을 확정했다고 가정) 입력만 바꿔 다시 계산한다.
다시 최적화하지 않는 이유 — 담당자가 묻는 것은 "이 안을 골랐는데 ETA가 6시간 늦으면?"이기 때문이다.
"""
from __future__ import annotations

import copy

from ..domain.timeutil import fmt_iso, parse_ts
from .build import build_context
from .schedule import replay

SHIFT_H = 6


def _shift_ts(s: str, hours: int) -> str:
    return fmt_iso(parse_ts(s) + hours * 60)


def perturbations(doc: dict, movable: list):
    out = []
    for vid in movable:
        for h in (SHIFT_H, -SHIFT_H):
            d = copy.deepcopy(doc)
            for v in d["vessels"]:
                if v["id"] == vid:
                    v["eta"] = _shift_ts(v["eta"], h)
                    if v.get("nor_tender"):
                        v["nor_tender"] = _shift_ts(v["nor_tender"], h)
            if parse_ts([v for v in d["vessels"] if v["id"] == vid][0]["eta"]) < parse_ts(d["horizon"]["start"]) - 24 * 60:
                continue
            out.append({"id": f"ETA:{vid}:{'+' if h > 0 else ''}{h}h", "kind": "ETA", "vessel": vid, "hours": h,
                        "label": f"{vid} ETA {'+' if h > 0 else ''}{h}시간", "doc": d})
    segs = (doc.get("weather_forecast") or {}).get("segments") or []
    if segs:
        for name, label, fn in (
            ("WX:+6h", "강풍 구간 6시간 늦게", lambda s: {**s, "from": _shift_ts(s["from"], SHIFT_H), "to": _shift_ts(s["to"], SHIFT_H)}),
            ("WX:-6h", "강풍 구간 6시간 일찍", lambda s: {**s, "from": _shift_ts(s["from"], -SHIFT_H), "to": _shift_ts(s["to"], -SHIFT_H)}),
            ("WX:long", "강풍 6시간 더 길게", lambda s: {**s, "to": _shift_ts(s["to"], SHIFT_H)}),
            ("WX:none", "강풍 예보 해제", lambda s: {**s, "wind_ms": min(s.get("wind_ms", 0), 10)}),
        ):
            d = copy.deepcopy(doc)
            strong = [s for s in segs if s.get("wind_ms", 0) >= 15]
            d["weather_forecast"]["segments"] = [fn(s) if s in strong else s for s in segs]
            out.append({"id": name, "kind": "WEATHER", "label": label, "doc": d})
    return out


def analyze(doc: dict, rules, plans: dict, data_dir=None) -> dict:
    """plans: {후보 이름: 계획}. 결과: 바뀐 입력마다 후보별 총액과 순위, 순위가 바뀐 후보 표시."""
    base_ctx, _ = build_context(doc, rules, data_dir=data_dir)
    base_tot = {name: replay(base_ctx, plan, name).total_cents for name, plan in plans.items()}
    base_rank = {n: i + 1 for i, (n, _) in enumerate(sorted(base_tot.items(), key=lambda kv: (kv[1], kv[0])))}
    rows = []
    flagged = {n: [] for n in plans}
    for pt in perturbations(doc, list(base_ctx.movable)):
        ctx, issues = build_context(pt["doc"], rules, data_dir=data_dir)
        if ctx is None:
            continue
        tot, infeasible = {}, {}
        for name, plan in plans.items():
            s = replay(ctx, plan, name)
            tot[name] = s.total_cents
            if s.infeasible:
                infeasible[name] = [b.detail for b in s.infeasible]
        rank = {n: i + 1 for i, (n, _) in enumerate(sorted(tot.items(), key=lambda kv: (kv[1], kv[0])))}
        changed = [n for n in plans if rank[n] != base_rank[n]]
        for n in changed:
            flagged[n].append({"input": pt["label"], "rank_from": base_rank[n], "rank_to": rank[n]})
        rows.append({"id": pt["id"], "kind": pt["kind"], "label": pt["label"],
                     "totals_usd": {n: tot[n] / 100 for n in plans},
                     "delta_usd": {n: (tot[n] - base_tot[n]) / 100 for n in plans},
                     "ranks": rank, "rank_changed": changed, "infeasible": infeasible})
    return {"base_totals_usd": {n: v / 100 for n, v in base_tot.items()}, "base_ranks": base_rank,
            "rows": rows, "flagged": flagged, "shift_hours": SHIFT_H}
