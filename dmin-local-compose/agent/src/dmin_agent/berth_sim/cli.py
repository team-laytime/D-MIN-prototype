"""run_stepN.py 공통: 샘플 로드 + 덮어쓰기 옵션 + 단계 전후 비교 출력."""

import argparse

from .models import Vessel
from .overrides import set_cargo, set_fix, set_spec
from .sample_loader import load_berth_plan, parse_time
from .shifting import normalize_berth
from .step3_berth_block import BerthBlock, BlockKind
from .step1_prev_fix import Step1Result, is_feasible

UNDETERMINED = "미판정"


def build_parser(doc: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="Sample data.xlsx")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--fix", action="append", default=[], metavar="VESSEL_ID=MM/DD HH:MM")
    ap.add_argument("--spec", action="append", default=[], metavar="VESSEL_ID=GRT,DRAFT")
    ap.add_argument("--cargo", action="append", default=[], metavar="VESSEL_ID=제품그룹")
    ap.add_argument(
        "--block", action="append", default=[], metavar="부두,부두|ALL=MM/DD HH:MM~MM/DD HH:MM[@기상|공사|설비]",
        help="사용자 설정 부두 제약. 종류 생략 시 ALL은 기상, 그 외는 공사",
    )
    ap.add_argument(
        "--typhoon", action="append", default=[], metavar="MM/DD HH:MM~MM/DD HH:MM",
        help="태풍이 오는 시간. 그 시간은 모든 부두 접안 불가 · 하역 중단 (여러 번 가능)",
    )
    ap.add_argument(
        "--typhoon-track", default=None, metavar="파일|폴더",
        help="태풍 경로 (기상청 태풍정보 형식 CSV · JSON · XML). 강풍반경 안에 드는 부두 · 시간만 접안 불가. "
             "생략하면 data/typhoon/ 폴더의 파일을 읽음",
    )
    ap.add_argument("--no-typhoon-track", action="store_true", help="data/typhoon/ 폴더의 태풍 경로를 쓰지 않음")
    ap.add_argument("--all", action="store_true", help="변경 없는 선박도 출력")
    return ap


def parse_typhoons(args: argparse.Namespace) -> list:
    from .weather import parse_periods

    return [p for text in args.typhoon for p in parse_periods(text, args.year)]


def load_track_arg(args: argparse.Namespace):
    """--typhoon-track 또는 data/typhoon/ 의 태풍 경로 (없으면 None)."""
    if getattr(args, "no_typhoon_track", False):
        return None
    from .typhoon import read_track, track_files

    return read_track(track_files(getattr(args, "typhoon_track", None)))


def apply_typhoons(data, typhoons: list, track=None):
    """가상 예보에 태풍(직접 입력한 시간 · 경로 파일)을 반영한 데이터."""
    if (not typhoons and track is None) or data.weather is None:
        return data
    from dataclasses import replace

    from .weather import with_track, with_typhoon

    return replace(data, weather=with_track(with_typhoon(data.weather, typhoons), track))


def load(args: argparse.Namespace) -> dict[str, list[Vessel]]:
    sequences, _ = load_berth_plan(args.data, args.year)
    for item in args.fix:
        vessel_id, when = item.split("=")
        set_fix(sequences, vessel_id, parse_time(when, args.year))
    for item in args.spec:
        vessel_id, values = item.split("=")
        grt, draft = (float(x) for x in values.split(","))
        set_spec(sequences, vessel_id, grt, draft)
    for item in args.cargo:
        vessel_id, group = item.split("=")
        set_cargo(sequences, vessel_id, group.strip())
    return sequences


def parse_blocks(args: argparse.Namespace) -> list[BerthBlock]:
    blocks = []
    for item in args.block:
        where, rest = item.split("=", 1)
        span, _, kind = rest.partition("@")
        start, end = (parse_time(t, args.year) for t in span.split("~"))
        berths = None if where.strip().upper() == "ALL" else frozenset(normalize_berth(b) for b in where.split(","))
        kind = BlockKind(kind.strip()) if kind else (BlockKind.WEATHER if berths is None else BlockKind.CONSTRUCTION)
        blocks.append(BerthBlock(start, end, kind, berths))
    return blocks


def print_diff(
    before: dict[str, list[Step1Result]],
    after: dict[str, list[Step1Result]],
    before_label: str,
    after_label: str,
    show_all: bool = False,
) -> None:
    fmt = "%m/%d %H:%M"
    undetermined: dict[str, int] = {}
    print(
        f"{'선박':<10}{'Biz':<5}{'GRT':>8}{'Draft':>7}  {'화물':<7}{'ETA':<13}"
        f"{before_label + ' ETB':<13}{after_label + ' ETB':<13}{after_label + ' ETU':<13}판정 / 근거"
    )
    for berth, rows in after.items():
        for b, r in zip(before[berth], rows):
            v = r.vessel
            notes = []
            for n in r.notes:
                if UNDETERMINED in n:
                    key = n.split(":")[0]
                    undetermined[key] = undetermined.get(key, 0) + 1
                else:
                    notes.append(n)
            changed = b.etb != r.etb or b.berthable != r.berthable
            if not (show_all or changed or notes):
                continue
            grt = f"{v.grt:,.0f}" if v.grt is not None else "-"
            draft = f"{v.draft:g}" if v.draft is not None else "-"
            print(
                f"{r.vessel_id:<10}{v.biz or '-':<5}{grt:>8}{draft:>7}  {v.cargo_group or '-':<7}{r.eta:{fmt}}  "
                f"{b.etb:{fmt}}  {r.etb:{fmt}}  {r.etu:{fmt}}  {r.reason}"
                + "".join(f"\n{'':<10}└ {n}" for n in notes)
            )
    print()
    for key, count in undetermined.items():
        print(f"{key}: {count}척")
    print(f"시나리오 실행 가능: {before_label} {is_feasible(before)} → {after_label} {is_feasible(after)}")
