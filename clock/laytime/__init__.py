"""CLOCK — 레이타임·체선료 계산 엔진 (결정론, 표준 라이브러리만).

    from laytime import load_case, compute_statement
    st = compute_statement(load_case("cases/TC-03.json"))
    st.amount_usd, st.demurrage_hours, st.issues
"""
from .engine import (ENGINE_VERSION, LEVEL_EVIDENCE, LEVEL_INFO, LEVEL_REVIEW, LEVEL_WARNING, AltCalc, Issue, Line,
                     Policy, Statement, compute_statement)
from .model import Case, CaseError, case_from_dict, load_case
from .render import render_markdown, render_summary

__all__ = [
    "ENGINE_VERSION", "LEVEL_EVIDENCE", "LEVEL_INFO", "LEVEL_REVIEW", "LEVEL_WARNING", "AltCalc", "Case", "CaseError",
    "Issue", "Line", "Policy", "Statement", "case_from_dict", "compute_statement", "load_case", "render_markdown",
    "render_summary",
]
