"""계산서를 Markdown으로 그린다(04 §0 템플릿 + 구간 원장 + 쟁점·대안)."""
from __future__ import annotations

from . import rules
from .engine import EFFECT_LABEL, PHASE_LABEL, Statement
from .fmt import fmt_dt, fmt_hours, fmt_rows, fmt_usd


def _esc(text: str | None) -> str:
    return (text or "").replace("|", "\\|")


def render_markdown(st: Statement) -> str:
    base = st.base_date
    F = lambda dt: fmt_dt(dt, base)  # noqa: E731
    out = [f"# 레이타임 계산서 — {st.call_id} {st.title}".rstrip(), ""]
    out.append(f"- 계약: {st.form} / {st.layer} · 허용 {fmt_hours(st.allowed_hours)} · 요율 USD {st.rate_usd_day:,.0f}/일")
    if base:
        out.append(f"- 시각: D1 = {base.isoformat()} (KST, 가상 날짜) · 엔진 {st.version} · 룰 {st.rules_version}")
    out.append(f"- 결과: 체선 {fmt_hours(st.demurrage_hours)} · **{fmt_usd(st.amount_usd)}**"
               + (f" · 여유 {fmt_hours(st.margin_hours)}" if st.margin_hours is not None else ""))
    out += ["", "| 항목 | 값 | 룰 ID | SOF 행 | 비고 |", "|---|---|---|---|---|"]
    for ln in st.lines:
        rows = fmt_rows(ln.sof_rows) if ln.sof_rows else f"— ({ln.source})" if ln.source else "—"
        out.append(f"| {_esc(ln.label)} | {_esc(ln.value)} | {', '.join(ln.rule_ids)} | {_esc(rows)} | {_esc(ln.note)} |")

    out += ["", "## 구간 원장", "", "| 구간 | 시간 | 상태 | 단계 | 효과 | 룰 ID | SOF 행 |", "|---|---|---|---|---|---|---|"]
    for e in st.ledger:
        out.append(f"| {F(e.from_ts)} ~ {F(e.to_ts)} | {fmt_hours(e.hours)} | {e.label} | {PHASE_LABEL[e.phase]} | "
                   f"{EFFECT_LABEL[e.effect]} | {', '.join(e.rule_ids)} | {fmt_rows(e.sof_rows)} |")

    out += ["", "## 쟁점·경고", ""]
    if not st.issues:
        out.append("없음")
    for n, i in enumerate(st.issues, 1):
        ref = f" {i.dispute_ref}" if i.dispute_ref else ""
        out.append(f"{n}. **[{i.level}]{ref}** {i.title}")
        out.append(f"   - {i.detail}")
        out.append(f"   - 룰: {', '.join(i.rule_ids)} · SOF 행: {fmt_rows(i.sof_rows)}")
        if i.alternative:
            a = i.alternative
            out.append(f"   - 대안 — {a.title}: 개시 {F(a.laytime_start_at)}, 체선 {fmt_hours(a.demurrage_hours)}"
                       f"(반액 {fmt_hours(a.half_rate_hours)}), {fmt_usd(a.amount_usd)} (차이 {a.delta_usd:+,.2f})")

    used = sorted({r for ln in st.lines for r in ln.rule_ids} | {r for e in st.ledger for r in e.rule_ids}
                  | {r for i in st.issues for r in i.rule_ids})
    out += ["", "## 쓰인 룰", "", "| 룰 ID | 상태 | 내용 | 출처 |", "|---|---|---|---|"]
    for rid in used:
        r = rules.rule(rid)
        out.append(f"| {rid} | {r.tag} | {_esc(r.title)} | {_esc(r.source)} |")
    return "\n".join(out) + "\n"


def render_summary(statements: list[Statement]) -> str:
    out = ["| 케이스 | 개시 | 체선 개시 | 사용 | 허용 | 체선 (전액/반액) | 금액 | 쟁점·경고 |",
           "|---|---|---|---|---|---|---|---|"]
    for st in statements:
        F = lambda dt: fmt_dt(dt, st.base_date)  # noqa: E731
        flags = ", ".join(f"{i.code}" + (f"→{fmt_usd(i.alternative.amount_usd)}" if i.alternative else "")
                          for i in st.issues) or "—"
        out.append(f"| {st.call_id} | {F(st.laytime_start_at)} | {F(st.demurrage_start_at)} | {fmt_hours(st.used_hours)} | "
                   f"{fmt_hours(st.allowed_hours)} | {fmt_hours(st.demurrage_hours)} ({fmt_hours(st.full_rate_hours)}/"
                   f"{fmt_hours(st.half_rate_hours)}) | {fmt_usd(st.amount_usd)} | {flags} |")
    return "\n".join(out) + "\n"
