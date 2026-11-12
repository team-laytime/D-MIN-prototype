"""명령줄: 케이스 JSON → 계산서.

    python3 -m laytime                      # cases/ 전체 요약표
    python3 -m laytime cases/TC-03.json     # 계산서(Markdown)
    python3 -m laytime cases/TC-03.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .engine import compute_statement
from .model import CaseError, load_case
from .render import render_markdown, render_summary

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m laytime", description="CLOCK 레이타임 계산서")
    p.add_argument("cases", nargs="*", help="케이스 JSON 경로(없으면 cases/ 전체 요약)")
    p.add_argument("--json", action="store_true", help="06 LAYTIME_STATEMENT 형식 JSON으로 출력")
    args = p.parse_args(argv)
    paths = [Path(c) for c in args.cases] or sorted(CASES_DIR.glob("*.json"), key=lambda p: p.stem)
    try:
        statements = [compute_statement(load_case(path)) for path in paths]
    except CaseError as e:
        print(f"입력 오류: {e}", file=sys.stderr)
        return 2
    if args.json:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        docs = [dict(st.to_dict(), computed_at=now) for st in statements]
        print(json.dumps(docs[0] if len(docs) == 1 else docs, ensure_ascii=False, indent=2))
    elif args.cases:
        print("\n---\n\n".join(render_markdown(st) for st in statements), end="")
    else:
        print(render_summary(statements), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
