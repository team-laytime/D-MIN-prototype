"""계산 결과를 화면·보고서·API가 같이 쓰는 JSON 모양으로 바꾼다."""
from __future__ import annotations

from ..domain.model import VESSEL_TYPE_KO
from ..domain.money import fmt_usd
from ..domain.timeutil import fmt, fmt_iso
from ..engine.laytime import calc_sheet, evidence_rows, serialize


def schedule_view(ctx, sch, baseline=None) -> dict:
    vessels = []
    base_calcs = baseline.calcs if baseline is not None else {}
    for vid, c in sorted(sch.calcs.items(), key=lambda kv: (ctx.berth_order.index(kv[1]["berth"]), kv[1]["etb"])):
        v = ctx.vessels[vid]
        row = serialize(c)
        row.update({
            "name": v.name, "vessel_type": v.vessel_type, "vessel_type_ko": VESSEL_TYPE_KO.get(v.vessel_type, v.vessel_type),
            "cargo_group": v.cargo_group, "direction": v.direction,
            "grt": v.grt, "status": v.status, "priority": v.priority,
            "contract_type": v.contract.type, "laytime_h": float(v.contract.laytime_h),
            "evidence": evidence_rows(ctx, c),
            "sheet": calc_sheet(ctx, v, sch.state.pl[vid], c),
            "contract_id": v.contract.id,
            "rule_names": [ctx.rules.rule_name(r) for r in c["rule_ids"]],
            "eligible_berths": ctx.eligible.get(vid, [c["berth"]]),
            "excluded_berths": {b: [x["message"] for x in r] for b, r in ctx.excluded.get(vid, {}).items() if b in ctx.sc.active_berths},
        })
        if vid in base_calcs:
            bc = base_calcs[vid]
            row["baseline"] = {"berth": bc["berth"], "etb": fmt_iso(bc["etb"]), "amount_usd": bc["amount_cents"] / 100}
            row["delta_usd"] = (c["amount_cents"] - bc["amount_cents"]) / 100
            row["changed"] = (bc["berth"] != c["berth"]) or (bc["etb"] != c["etb"])
        vessels.append(row)
    statuses = sorted({s for c in sch.calcs.values() for s in c["statuses"]})
    total = sch.total_cents
    out = {
        "label": sch.label,
        "total_cents": total,
        "total_usd": total / 100,
        "total_display": fmt_usd(total),
        "signature": [[b, list(vs)] for b, vs in sch.signature()],
        "plan": [list(x) for x in sch.plan],
        "complete": sch.complete,
        "violations": sch.violations,
        "infeasible": [{"vessel": b.vid, "berth": b.berth, "reason": b.reason, "rule_id": b.rule_id, "detail": b.detail} for b in sch.infeasible],
        "vessels": vessels,
        "statuses": statuses or ["확정 규칙만 사용"],
        "meta": dict(sch.meta),
    }
    if baseline is not None and baseline.complete:
        sav = baseline.total_cents - total
        out["savings_cents"] = sav
        out["savings_usd"] = sav / 100
        out["savings_display"] = fmt_usd(sav)
        out["savings_pct"] = round(sav / baseline.total_cents * 100, 1) if baseline.total_cents else 0.0
        out["changed_vessels"] = [r["vessel_id"] for r in vessels if r.get("changed")]
        # 선박별 증감의 합 = 절감액(FR-38 수용기준 '차이 0')
        out["delta_sum_cents"] = sum(round(r.get("delta_usd", 0) * 100) for r in vessels)
    return out


def restriction_view(ctx) -> list:
    return [{"id": r.id, "berths": list(r.berths), "start": fmt_iso(r.start), "end": fmt_iso(r.end), "reason": r.reason,
             "note": r.note, "source": r.source} for r in sorted(ctx.restrictions, key=lambda r: (r.start, r.id))]


def schedule_rows(view: dict) -> list:
    """보고서·메일·CSV용 선박별 일정 행."""
    rows = []
    for r in view["vessels"]:
        rows.append({
            "선박": r["vessel_id"], "선종": r["vessel_type"], "부두": r["berth"], "ETA": fmt_short(r["eta"]),
            "ETB": fmt_short(r["etb"]), "작업": f"{fmt_short(r['work_start'])}~{fmt_short(r['work_end'])}",
            "호스분리": fmt_short(r["hose_off"]), "ETU": fmt_short(r["etu"]), "정박종료": fmt_short(r["laytime_end"]),
            "체선(h)": f"{r['demurrage_hours']:.2f}".rstrip("0").rstrip("."), "체선료": fmt_usd(r["amount_cents"]),
            "고정": {"FIX": "FIX", "WORKING": "작업 중"}.get(r["kind"], ""),
        })
    return rows


def fmt_short(iso: str) -> str:
    """'2026-11-10 07:00' → '11/10 07:00'."""
    if not iso:
        return "-"
    return f"{iso[5:7]}/{iso[8:10]} {iso[11:16]}"
