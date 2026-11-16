"""전체 워크플로우 다이어그램(HTML) 생성.

실제 데이터 → 가상 데이터 → 검증 → ETB 산정 ①②③ → ETB 이후 계산 → 체선료를 한 장에 그린다.
- 박스마다 실행 결과 수치(이번 실행 기준)를 표시한다.
- 박스 제목·경로를 누르면 VS Code에서 해당 함수 줄이 열린다 (vscode://file/경로:줄).
- 박스 안의 고정값(시각·시간·톤수·부두 묶음 등)은 그 값이 정의된 상수 줄로 따로 연결된다.
"""

import ast
import html
import inspect
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from types import ModuleType

from .after_etb import (
    pipeline, s1_work_start, s2_work_finish, s3_etu, s4_hose_off, s5_etanr, s6_daylight,
    s7_laytime_start_no_daylight, s8_laytime_start_daylight, s9_laytime_end, s10_weather_hours,
    s11_demurrage_time, s12_demurrage_fee,
)
from . import berth_fit, master_data, sample_loader, scenario, shifting, step1_prev_fix, step2_night_pilot, sun, synth
from . import berth_availability, dummy_data, optimizer, typhoon, validate, vessel_specs, weather
from . import step3_berth_block, step3_berth_pair, step3_cargo_group
from .scenario import ScenarioResult
from .validate import Check, _branch_kind

E = html.escape


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class K:
    """다이어그램 속 고정값 하나와 그 값이 정의된 코드 줄."""

    text: str
    href: str
    where: str  # 상대경로:줄


def _at(path: Path, line: int) -> tuple[str, str]:
    # macOS: vscode://file/Users/... · Windows: vscode://file/C:/...
    return f"vscode://file/{path.as_posix().lstrip('/')}:{line}", f"{path.relative_to(ROOT).as_posix()}:{line}"


def kf(obj: Callable | type, text: str = "") -> K:
    """함수/클래스 정의 줄."""
    obj = inspect.unwrap(obj)  # lru_cache 등으로 감싼 함수도 원래 정의 줄로
    path = Path(inspect.getsourcefile(obj)).resolve()
    return K(text, *_at(path, inspect.getsourcelines(obj)[1]))


def k(module: ModuleType, name: str, text: str, key: str | None = None) -> K:
    """모듈 상수 정의 줄. key를 주면 dict 상수의 그 항목 줄."""
    path = Path(inspect.getsourcefile(module)).resolve()
    for st in ast.parse(path.read_text(encoding="utf-8")).body:
        targets = st.targets if isinstance(st, ast.Assign) else [st.target] if isinstance(st, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            line = st.lineno
            if key is not None:
                line = next(x.lineno for x in st.value.keys if isinstance(x, ast.Constant) and x.value == key)
            return K(text, *_at(path, line))
    raise KeyError(f"{module.__name__}.{name}")


def kt(module: ModuleType, needle: str, text: str, exact: bool = False) -> K:
    """상수로 빼지 않은 코드 속 숫자: needle이 들어 있는(exact면 그 내용뿐인) 첫 코드 줄."""
    path = Path(inspect.getsourcefile(module)).resolve()
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if (line.strip() == needle) if exact else (needle in line):
            return K(text, *_at(path, i))
    raise KeyError(f"{module.__name__}: {needle}")


def hrs(td: timedelta) -> str:
    h = td.total_seconds() / 3600
    return f"{h:g}h" if h >= 1 else f"{td.total_seconds() / 60:g}분"


def clk(t: time) -> str:
    return f"{t:%H}시"


def ton(x: float) -> str:
    return f"{x / 10_000:g}만" if x >= 10_000 else f"{x / 1_000:g}천"


def pct(module: ModuleType, name: str) -> K:
    return k(module, name, f"{getattr(module, name):.0%}")


def rng_(module: ModuleType, name: str) -> K:
    lo, hi = getattr(module, name)
    return k(module, name, f"{lo:g}~{hi:g}")


def groups(gs: Iterable[frozenset[str]]) -> str:
    return " · ".join("{" + ", ".join(f"#{b}" for b in sorted(g)) + "}" for g in gs)


Line = str | K | tuple[str | K, ...]


def _line(x: Line) -> str:
    parts = x if isinstance(x, tuple) else (x,)
    return "".join(
        E(p) if isinstance(p, str) else f"<a class='k' href='{p.href}' title='{E(p.where)}'>{E(p.text)}</a>"
        for p in parts
    )


def node(kind: str, title: str, obj, lines: Iterable[Line] = (), stats: Iterable[str] = (), wide: bool = False) -> str:
    ref = obj if isinstance(obj, K) else kf(obj)
    body = "".join(f"<div class='f'>{_line(x)}</div>" for x in lines)
    chips = "".join(f"<span class='chip'>{E(s)}</span>" for s in stats)
    kind_label = {"real": "실제 데이터", "synth": "가상 데이터", "rule": "장표 규칙", "check": "검증",
                  "link": "연결", "out": "결과"}[kind]
    return (
        f"<div class='node {kind}{' wide' if wide else ''}'>"
        f"<span class='kind'>{kind_label}</span><h4><a href='{ref.href}' title='VS Code에서 열기'>{E(title)}</a></h4>{body}"
        f"{f'<div class=chips>{chips}</div>' if chips else ''}"
        f"<a class='src' href='{ref.href}'>{E(ref.where)} ↗</a></div>"
    )


def arrow(direction: str = "down", label: str = "") -> str:
    return f"<div class='arrow {direction}'>{f'<span>{E(label)}</span>' if label else ''}</div>"


def row(*parts: str, cls: str = "") -> str:
    return f"<div class='row {cls}'>{''.join(parts)}</div>"


def stage(no: str, title: str, sub: str, inner: str) -> str:
    return (f"<section class='stage'><header><span class='no'>{no}</span><div><h2>{E(title)}</h2>"
            f"<p>{E(sub)}</p></div></header>{inner}</section>")


def _note_count(res: ScenarioResult, prefix: str) -> int:
    return sum(1 for o in res.outcomes if any(n.startswith(prefix) for n in o.etb_notes))


def _fmt_money(x: float) -> str:
    return f"${x:,.0f}"


def _checks_html(checks: list[Check]) -> str:
    out = []
    for c in checks:
        mark = {True: "pass", False: "fail", None: "info"}[c.passed]
        icon = {True: "✓", False: "✕", None: "i"}[c.passed]
        items = "".join(f"<li>{E(x)}</li>" for x in c.items)
        detail = f"<details><summary>{len(c.items)}건 보기</summary><ul>{items}</ul></details>" if items else ""
        out.append(f"<div class='ck {mark}'><b>{icon}</b><span class='code'>{c.code}</span>"
                   f"<span class='t'>{E(c.title)}</span><span class='d'>{E(c.detail)}</span>{detail}</div>")
    return "".join(out)


def _table(base: ScenarioResult, rules: ScenarioResult, options: dict[str, list[str]]) -> str:
    b = base.by_id()
    rows = []
    for o in rules.outcomes:
        v, p, a = o.vessel, o.profile, o.after
        bo = b[v.vessel_id]
        diff = (o.etb - bo.etb).total_seconds() / 3600
        notes = "<br>".join(E(n) for n in o.etb_notes) or "<span class='mut'>—</span>"
        lay = E(_branch_kind(a.laytime_start.reason)) if a else E(o.alert or "")
        rows.append(
            f"<tr><td class='id'>{E(v.vessel_id)}</td><td>{E(v.biz or '')}</td><td>{E(p.vessel_type)}<br>"
            f"<span class='mut'>{E(p.cargo_group)}</span></td>"
            f"<td>{E(p.ship_class)}<br><span class='mut'>DWT {p.dwt:,.0f} · GRT {p.grt:,.0f}<br>"
            f"LOA {p.loa:g} · PBL {p.pbl:g} · Draft {p.draft:g}</span></td>"
            f"<td>{' · '.join(('<b>#' + E(b) + '</b>') if b == v.berth else '#' + E(b) for b in options[v.vessel_id])}</td>"
            f"<td>{v.eta:%m/%d %H:%M}</td><td>{bo.etb:%m/%d %H:%M}</td><td>{o.etb:%m/%d %H:%M}"
            f"<br><span class='mut'>{diff:+g}h · {E(o.rule or '')}</span></td><td class='note'>{notes}</td>"
            f"<td>{lay}</td><td class='n'>{_fmt_money(bo.fee)}</td><td class='n'>{_fmt_money(o.fee)}</td></tr>"
        )
    return (
        "<div class='tablewrap'><table><thead><tr><th>선박</th><th>Biz</th><th>선종 / 화물</th><th>선박 제원</th><th>접안 가능 부두</th>"
        "<th>ETA</th><th>실제 ETB</th><th>규칙 ETB</th><th>ETB 조정 근거</th><th>정박개시 분기(규칙)</th>"
        "<th>체선료 실제</th><th>체선료 규칙</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def build_html(
    master: master_data.MasterData, data: synth.SynthData, base: ScenarioResult, rules: ScenarioResult,
    checks_a: list[Check], checks_b: list[Check], source: str, options: dict[str, list[str]],
    opt: "optimizer.OptimizeResult",
) -> str:
    n = len(rules.outcomes)
    ok = [o.after for o in rules.outcomes if o.after]
    rule_count = Counter(o.rule for o in rules.outcomes)
    basis = Counter(a.rate.basis for a in ok)
    daylight = sum(1 for a in ok if a.daylight)
    crude_half = sum(1 for o in rules.outcomes if o.profile.vessel_type == "원유선" and not o.profile.cfr)
    branches = Counter(_branch_kind(a.laytime_start.reason) for a in ok)
    dem_pos = sum(1 for a in ok if a.demurrage_fee > 0)
    nr = sum(1 for o in rules.outcomes if o.profile.nr_tender)
    a_pass = sum(1 for c in checks_a if c.passed)
    plan_n = sum(1 for _ in base.outcomes)

    def branch_stats(keys: tuple[str, ...]) -> list[str]:
        return [f"{k} {c}척" for k, c in branches.most_common() if k.split(" → ")[0] in keys]

    data_stage = (
        row(
            node("real", "접안계획 예시", sample_loader.load_berth_plan,
                 ["부두 · ETA · ETB · ETU · Biz", "같은 선박의 화물 라인은 한 척으로 합침", "부두 안 순서 = 실제 ETB 순"],
                 [f"{plan_n}척", f"{len({o.vessel.berth for o in base.outcomes})}개 부두"]),
            node("real", "부두 제원 · 접안 가능 제품 · 선박 제원", master_data.load_master,
                 ["부두별 Max DWT · Draft · LOA · Min PBL", "부두 → 제품 그룹 → 선종", "DWT 구간별 평균 GRT · LOA · PBL · 일 체선료"],
                 [f"부두 {len(master.berths)}", f"DWT 구간 {len(master.buckets)}"]),
            node("synth", "가상 선박 · 계약 데이터", synth.synthesize,
                 [("저장: data/dummy/ — ", kf(dummy_data.export, "past_shipments.csv · current_shipments.csv")),
                  "선박 제원: 아래 탱커 등급 생성기 · 화물: 부두 접안 가능 제품 중",
                  ("QTY 역산 (실제 ETU 재현) · 적재율 ", rng_(synth, "LOAD_FACTOR")),
                  ("과거 Shipment: 자체 기록 ", pct(synth, "OWN_HISTORY_P"), " · Rate 편차 ", rng_(synth, "HISTORY_RATE_NOISE")),
                  ("LayCan: 창 안 ", pct(synth, "LAYCAN_IN_P"), " · 조기 ", pct(synth, "LAYCAN_EARLY_P"),
                   " · 창 ", k(synth, "LAYCAN_WINDOW_DAYS", f"{synth.LAYCAN_WINDOW_DAYS}일")),
                  ("N/R ", pct(synth, "NR_TENDER_P"), " = ETA + ", k(synth, "NR_DELAY_H", "/".join(f"{h:g}" for h in synth.NR_DELAY_H) + "h")),
                  ("LayTime ×", rng_(synth, "LAYTIME_FACTOR"), " (원유 ×", rng_(synth, "LAYTIME_FACTOR_CRUDE"), ") ",
                   k(synth, "LAYTIME_ROUND_H", f"{synth.LAYTIME_ROUND_H}h"), " 올림"),
                  ("일 체선료 = 구간 평균 ×", rng_(synth, "DEMURRAGE_RATE_NOISE"), " · CFR ", pct(synth, "CFR_P"))],
                 [f"seed {data.seed}", f"과거 Shipment {len(data.history)}건"]),
            node("check", "검증", validate.validate_synthetic,
                 ["가상 데이터가 부두 제원 · 제품과 맞는가", "실제 ETB를 넣으면 실제 ETU가 나오는가",
                  "규칙이 실제 계획을 얼마나 재현하는가"],
                 [f"A 검증 {a_pass}/{len(checks_a)} 통과", f"① 일치 {checks_b[0].detail}"]),
            cls="four",
        )
        + arrow()
        + row(
            node("synth", "가상 선박 제원 (탱커 위주)", vessel_specs.generate,
                 [("등급: ", k(vessel_specs, "SHIP_CLASSES", "소형 ~ VLCC · LPG선")),
                  ("치수 = 「선박 제원 Sample」 구간 평균 × ", kf(vessel_specs.dimensions, "(DWT/구간 중앙)^(1/3)")),
                  ("편차 ×", rng_(vessel_specs, "DIM_NOISE"), " · Draft ×", rng_(vessel_specs, "DRAFT_LOAD"),
                   " · 최대 ", k(vessel_specs, "MAX_TRIES", f"{vessel_specs.MAX_TRIES}회"), " 재시도"),
                  ("가스 화물 → LPG선: ", k(vessel_specs, "GAS_CARGO", " · ".join(sorted(vessel_specs.GAS_CARGO)))),
                  ("PBL = 'epeo' 열 · 이상 구간 제외: ", k(vessel_specs, "OUTLIER_BUCKETS", "17만~22만")),
                  "배정 부두 적합성을 통과할 때까지 다시 뽑음"],
                 [f"{c} {n_}척" for c, n_ in Counter(p.ship_class for p in data.profiles.values()).most_common()]),
            arrow("right"),
            node("rule", "부두 적합성 필터", berth_fit.misfit_reasons,
                 [("DWT ", kt(berth_fit, "ship.dwt > spec.max_dwt", "≤ Max"), " · Buoy ",
                   kt(berth_fit, "ship.dwt < spec.min_dwt", "≥ Min"), " ", k(master_data, "BERTH_SUPPLEMENT", "80,000")),
                  ("LOA ", kt(berth_fit, "ship.loa < spec.min_loa", "≥ Min"), " · ", kt(berth_fit, "ship.loa > spec.max_loa", "≤ Max")),
                  ("PBL ", kt(berth_fit, "ship.pbl < spec.min_pbl", "≥ Min PBL")),
                  ("Draft ", kt(berth_fit, "ship.draft > spec.max_draft", "≤ Max"), " (수입·수출 모두)"),
                  ("제품 ", kt(berth_fit, "ship.cargo_group not in allowed_cargo", "∈ 부두 접안 가능 제품")),
                  "'-' 또는 빈 칸은 비교 안 함 · Depth는 Max Draft에 반영"],
                 [f"실제 배정 부두 적합 {checks_a[0].detail}",
                  f"옮길 수 있는 선박 {sum(1 for b in options.values() if len(b) > 1)}/{len(options)}척"]),
            cls="flow",
        )
        + "<div class='checks'><div><h5>A. 가상 데이터 검증</h5>" + _checks_html(checks_a) + "</div>"
        + "<div><h5>B. 실제 접안계획 대비 (정보)</h5>" + _checks_html(checks_b) + "</div></div>"
    )

    st2, st3 = step2_night_pilot, step3_cargo_group
    s7, s8 = s7_laytime_start_no_daylight, s8_laytime_start_daylight
    SW = k(shifting, "SHIFTING_HOURS", "Switching")
    DR = k(shifting, "SHIFTING_HOURS", "Direction")
    ETU2 = k(st3, "ETU_TO_WORK_END", "ETU − " + hrs(st3.ETU_TO_WORK_END))
    START = k(s1_work_start, "ETB_TO_START", "+ " + hrs(s1_work_start.ETB_TO_START))
    TO_ETU = k(s3_etu, "FINISH_TO_ETU", "+ " + hrs(s3_etu.FINISH_TO_ETU))
    SIX = k(s7, "NOTICE_TIME", "+ " + hrs(s7.NOTICE_TIME))
    shifting_rows = [
        (k(shifting, "SHIFTING_HOURS", f"{name:<7}", key=name), f" Switching {sw:g}h · Direction {dr:g}h")
        for name, (sw, dr) in shifting.SHIFTING_HOURS.items()
    ]

    etb_stage = (
        row(
            node("link", "부두 점유시간 = ETB 이후 계산식", scenario.occupancy,
                 [("stay = (ETB ", START, ") + QTY / 평균 Rate ", TO_ETU, " − ETB"),
                  "입력값 대신 3단계 계산식(작업시작·작업완료·ETU)으로 연결"],
                 [f"{n}척 계산"]),
            node("rule", "Shifting 소요시간 표 (장표 07쪽)", k(shifting, "SHIFTING_HOURS", ""),
                 [*shifting_rows, ("부두 → 표 행: ", kf(shifting.shifting_group, "shifting_group"))]),
            cls="two",
        )
        + arrow()
        + row(
            node("rule", "① 이전 선박 · FIX", step1_prev_fix._candidate,
                 [("ETA + ", DR, " ≤ 직전 ETU + ", SW), ("  YES → ETB = 직전 ETU + ", SW),
                  ("  NO  → ETB = ETA + ", DR)],
                 [f"Direction {rule_count.get('DIRECTION', 0)}척", f"Switching {rule_count.get('SWITCHING', 0)}척"]),
            node("rule", "② 야간 도선 제한", st2.make_night_pilot_adjuster,
                 [("GRT ≥ ", k(st2, "GRT_ALWAYS", ton(st2.GRT_ALWAYS)), " OR (≥ ", k(st2, "GRT_MIN", ton(st2.GRT_MIN)),
                   " · 수입 · Draft ≥ ", k(st2, "DRAFT_MIN", f"{st2.DRAFT_MIN:g}"), ")"),
                  ("Last POB = ", kf(sun.ulsan_sunset, "일몰"), " − ", k(st2, "POB_BEFORE_SUNSET_SMALL", hrs(st2.POB_BEFORE_SUNSET_SMALL)),
                   " (≤", k(st2, "GRT_POB_2H", ton(st2.GRT_POB_2H)), ") / − ", k(st2, "POB_BEFORE_SUNSET_LARGE", hrs(st2.POB_BEFORE_SUNSET_LARGE))),
                  ("ETA ≥ Last POB 또는 ETB ∈ [", k(st2, "NIGHT_START", clk(st2.NIGHT_START)), ", ",
                   k(st2, "RELEASE", clk(st2.RELEASE)), ")"),
                  ("→ ETB = 다가오는 ", k(st2, "RELEASE", clk(st2.RELEASE)))],
                 [f"{_note_count(rules, '야간 도선 제한')}척 조정"]),
            node("rule", "③-1 동일 화물 그룹", st3.make_cargo_group_adjuster,
                 [k(st3, "SAME_CARGO_BERTH_GROUPS", groups(st3.SAME_CARGO_BERTH_GROUPS)),
                  "같은 화물 그룹 작업 구간 겹침", ("→ ETB = 중복 선박 ", ETU2)],
                 [f"{_note_count(rules, '동일 화물 그룹(')}척 조정"]),
            node("rule", "③-2 부두 동시 접안", step3_berth_pair.make_berth_pair_adjuster,
                 [(k(step3_berth_pair, "SIMULTANEOUS_BERTH_PAIRS", groups(step3_berth_pair.SIMULTANEOUS_BERTH_PAIRS)),
                   " 동시 접안 불가"),
                  ("두 척 모두 GRT ≤ ", k(step3_berth_pair, "SMALL_GRT", ton(step3_berth_pair.SMALL_GRT)), "이면 예외"),
                  ("→ ETB = 중복 선박 ", ETU2)],
                 [f"{_note_count(rules, '부두 동시') + _note_count(rules, 'GRT 없음')}척 조정"]),
            node("rule", "③-3 사용자 설정 부두 제약", step3_berth_block.make_berth_block_adjuster,
                 [(kf(step3_berth_block.BlockKind, "기상 · 공사 · 설비"), " (기상=전체, 그 외=부두별)"),
                  ("→ ETB = 제약 종료 + ", DR)],
                 [f"{_note_count(rules, '부두 제약(')}척 조정", "이번 실행: 입력 없음"]),
            cls="five",
        )
        + arrow()
        + row(
            node("rule", "부두 사용 가능 시각 (데이터 범위)", berth_availability.make_availability_adjuster,
                 [(kf(berth_availability.availability_from_plan, "부두별 첫 실제 ETB"), " 이전엔 점유 정보 없음"),
                  "→ ETB = max(후보 ETB, 사용 가능 시각)", "장표 규칙 아님 · 조회 기간 밖 선박 대비"],
                 [f"{_note_count(opt.baseline, '부두 사용 가능')}척 조정 (최적화 전)"]),
            arrow("right"),
            node("rule", "AND · 고정점 반복", step1_prev_fix._apply_adjusters,
                 ["②③ 조정기를 ETB가 안 바뀔 때까지 반복", "모든 제약을 동시에 만족하는 가장 이른 ETB"],
                 [f"조정된 선박 {sum(1 for o in rules.outcomes if o.etb_notes)}척"]),
            arrow("right"),
            node("rule", "다음 FIX 선박 충돌 판정", step1_prev_fix.schedule,
                 [("FIX ETB ≤ 예상 ETU + ", SW, " → 접안불가"), "부두 간 제약 때문에 전체 부두를 시간순으로 확정"],
                 [f"접안불가 {sum(1 for o in rules.outcomes if not o.berthable)}척"]),
            cls="flow",
        )
    )

    after_stage = (
        row(
            node("rule", "작업시작", s1_work_start.work_start,
                 ["ETB 有? / 부두 지정? (없으면 Alert)", ("예상시작 없으면 ETB ", START)], [f"{len(ok)}척"]),
            arrow("right"),
            node("rule", "평균 Rate · 작업완료", s2_work_finish.average_rate,
                 [(kf(s2_work_finish.find_past, "선박코드+자재코드+부두 → 없으면 부두+자재코드"),),
                  ("작업완료 = 시작 + QTY / ", kf(s2_work_finish.average_rate, "평균 Rate")),
                  ("작업 중 기상중단 1회 → 호스 분리 ", k(s2_work_finish, "HOSE_DISCONNECT", hrs(s2_work_finish.HOSE_DISCONNECT)),
                   " + 재연결·준비 ", k(s2_work_finish, "HOSE_RECONNECT", hrs(s2_work_finish.HOSE_RECONNECT))),
                  "작업 시작 전부터 중단 중이면 호스 추가시간 없음 · 겹친 중단은 1회"],
                 [f"{kk} {c}척" for kk, c in basis.most_common()]),
            arrow("right"),
            node("rule", "예상 이안 ETU", s3_etu.etu, [("ETU = 작업완료 ", TO_ETU), "→ ETB 산정의 부두 점유시간"]),
            arrow("right"),
            node("rule", "호스분리", s4_hose_off.hose_off,
                 [("호스분리 = 작업완료 + ", k(s4_hose_off, "FINISH_TO_HOSE_OFF", hrs(s4_hose_off.FINISH_TO_HOSE_OFF))),
                  "(최빈 Term 박스는 삭제됨)"]),
            cls="flow",
        )
        + arrow()
        + row(
            node("rule", "ETANR", s5_etanr.etanr,
                 ["ETANR = NVL(NR_TENDER, ETA)", "둘 다 없으면 Alert"], [f"N/R 사용 {nr}척", f"ETA 사용 {n - nr}척"]),
            arrow("right"),
            node("rule", "Day Light 적용?", s6_daylight.is_daylight,
                 [("적용: ", k(s6_daylight, "DAYLIGHT_APPLIED", " · ".join(sorted(s6_daylight.DAYLIGHT_APPLIED)))),
                  ("미적용: ", k(s6_daylight, "DAYLIGHT_NOT_APPLIED", " · ".join(sorted(s6_daylight.DAYLIGHT_NOT_APPLIED))))],
                 [f"적용 {daylight}척", f"미적용 {len(ok) - daylight}척"]),
            arrow("right"),
            f"<div class='stack'>"
            + node("rule", "정박개시 · Daylight 미적용", s7.laytime_start_no_daylight,
                   [(kf(s7.laycan_branch, "Early Loading / LayCan Miss"), " → ETB"),
                    ("ETANR < From → From의 ", k(s7, "LAYCAN_FROM_HOUR", clk(s7.LAYCAN_FROM_HOUR))),
                    ("그 외 → ETANR ", SIX, " (", kf(s7.cap_at_etb, "ETB가 더 이르면 ETB"), ")")],
                   branch_stats(("Early Loading", "LayCan Miss", "LayCan From 시각", "LayCan 내 +6h")))
            + node("rule", "정박개시 · Daylight 적용", s8.laytime_start_daylight,
                   [("LayCan 분기 동일 (From의 ", k(s8, "LAYCAN_FROM_HOUR", clk(s8.LAYCAN_FROM_HOUR)), ")"),
                    (kf(sun.ulsan_sunrise, "일출"), " < ETANR < ", kf(sun.ulsan_sunset, "일몰"), " → ETANR ", SIX),
                    ("≤ 일출 → 당일 ", k(s8, "MORNING", clk(s8.MORNING)), " · ≥ 일몰 → 다음날 ", k(s8, "MORNING", clk(s8.MORNING)))],
                   branch_stats(("일출~일몰 +6h", "일출 전 07시", "일몰 후 다음날 07시")))
            + "</div>",
            arrow("right"),
            node("rule", "정박종료", s9_laytime_end.laytime_end,
                 ["LayTime 없으면 Alert",
                  (k(pipeline, "CRUDE_VESSEL_TYPE", "원유"), " && CFR False → + ", kt(s9_laytime_end, "laytime / 2", "LayTime / 2")),
                  ("그 외 → + ", kt(s9_laytime_end, "return laytime_start + laytime", "LayTime", exact=True))],
                 [f"절반 적용 {crude_half}척"]),
            cls="flow",
        )
        + arrow()
        + row(
            node("rule", "기상체선 시간", s10_weather_hours.weather_hours,
                 [("#1~2·GAS: 하역중단 ≥ ", k(weather, "THRESHOLDS", "18 m/s", key="#1~2·GAS"),
                   " · 접안불가 ≥ ", k(weather, "THRESHOLDS", "20 m/s", key="#1~2·GAS")),
                  ("#3~7계열: 하역중단 ≥ ", k(weather, "THRESHOLDS", "14 m/s", key="#3~7"),
                   " · 접안불가 ≥ ", k(weather, "THRESHOLDS", "21 m/s", key="#3~7")),
                  "심한 뇌우·대기 정체 → 하역중단",
                  ("태풍 → 접안불가: ", kf(weather.with_typhoon, "직접 입력 시간 = 전 부두"), " · ",
                   kf(typhoon.berth_periods, "경로 파일 = 부두별 "), k(typhoon, "RADIUS_FIELD", "강풍반경"), " 안 (",
                   k(typhoon, "STEP", "1시간"), " 보간, ", k(typhoon, "SK_PORT", "부두 좌표"), ")"),
                  (kf(step3_berth_block.BlockKind, "사용자 기상 제약"), " ∩ [정박종료, 호스분리] → 기상체선")],
                 ["예보는 ETU 지연·접안불가에 반영", "기상체선 50%는 사용자 제약만"]),
            arrow("right"),
            node("rule", "Demurrage Time", s11_demurrage_time.demurrage_time,
                 [("호스분리 − 정박종료 − 기상체선 ", kt(s11_demurrage_time, "weather / 2", "/ 2")),
                  ("음수면 ", kt(s11_demurrage_time, "max(timedelta()", "0"), " (조출료 미반영)")],
                 [f"체선 발생 {dem_pos}척"]),
            arrow("right"),
            node("rule", "체선료", s12_demurrage_fee.demurrage_fee,
                 [("Demurrage Time × 일 체선료 ", kt(s12_demurrage_fee, "rate_per_day / 24", "/ 24")),
                  ("시나리오 합계 = ", kf(s12_demurrage_fee.scenario_total, "Σ 선박별"))],
                 [_fmt_money(rules.total_fee)]),
            cls="flow",
        )
    )

    opt_base, best = opt.baseline, opt.best
    b0 = opt_base.by_id()
    moved = [o for o in best.outcomes if o.vessel.berth != b0[o.vessel.vessel_id].vessel.berth]
    n_movable = sum(1 for bs in opt.candidates.berths.values() if len(bs) > 1)
    n_excl = sum(len(x) for x in opt.candidates.excluded.values())
    MW = optimizer.MOVE_WEIGHTS

    opt_stage = (
        row(
            node("rule", "후보 부두 = 부두 적합성 ∩ 과거 실적", optimizer.candidate_berths,
                 [(kf(berth_fit.allowed_berths, "부두 적합성 필터"), " 통과 (DWT·LOA·PBL·Draft·제품)"),
                  ("∩ ", kf(s2_work_finish.find_past, "과거 Shipment"), " 있음 (없으면 평균 Rate 산출 불가)"),
                  "FIX 선박은 현재 부두 고정"],
                 [f"옮길 수 있는 선박 {n_movable}/{n}척", f"실적 없어 제외 {n_excl}건"]),
            arrow("right"),
            node("rule", "이웃 계획 만들기", optimizer.neighbor,
                 [("SWAP ", k(optimizer, "MOVE_WEIGHTS", f"{MW['SWAP']:.0%}", key="SWAP"), " 같은 부두 두 선박 순서 교환"),
                  ("REINSERT ", k(optimizer, "MOVE_WEIGHTS", f"{MW['REINSERT']:.0%}", key="REINSERT"), " 같은 부두 안 순번 이동"),
                  ("RELOCATE ", k(optimizer, "MOVE_WEIGHTS", f"{MW['RELOCATE']:.0%}", key="RELOCATE"), " 후보 부두로 이동 (ETA 순 자리)")]),
            arrow("right"),
            node("rule", "평가", optimizer.cost,
                 [("ETB 산정 ①②③ → ETB 이후 → ", kf(scenario.evaluate_rules, "체선료 합계")),
                  ("+ 접안불가·Alert 1척당 ", k(optimizer, "INFEASIBLE_PENALTY", _fmt_money(optimizer.INFEASIBLE_PENALTY))),
                  ("+ ", kf(berth_availability.make_availability_adjuster, "부두 사용 가능 시각"), " 제약")]),
            arrow("right"),
            node("rule", "담금질 탐색", optimizer.optimize,
                 [("반복 ", k(optimizer, "ITERATIONS", f"{opt.iterations:,}회"), " · seed ", k(optimizer, "SEED", str(opt.seed))),
                  ("온도 ", k(optimizer, "T_START", _fmt_money(optimizer.T_START)), " → ", k(optimizer, "T_END", _fmt_money(optimizer.T_END))),
                  "나빠져도 exp(−증가액/온도) 확률로 채택"],
                 [f"개선 채택 {len(opt.accepted_moves)}회"]),
            cls="flow",
        )
        + _trace_svg(opt.trace)
    )

    cut = opt_base.total_fee - best.total_fee
    result_stage = (
        row(
            node("out", "실제 계획 ETB 그대로", scenario.evaluate_fixed_etb,
                 ["실제 접안계획의 ETB로 ETB 이후 계산만 수행", "(실제 계획엔 규칙 밖 대기·동시 접안 포함)"],
                 [_fmt_money(base.total_fee)]),
            node("out", "최적화 전 — 실제 배정 · 규칙 ETB", scenario.evaluate_rules,
                 ["실제 부두 배정 · 순서 그대로, ETB만 ①②③로", "최적화 효과의 기준선"],
                 [_fmt_money(opt_base.total_fee), "접안불가 " + str(sum(1 for o in opt_base.outcomes if not o.berthable)) + "척"]),
            node("out", "최적화 후", optimizer.optimize,
                 [f"부두 변경 {len(moved)}척 · 모든 선박 부두 적합성 통과", "같은 규칙(①②③ + 사용 가능 시각)으로 평가"],
                 [_fmt_money(best.total_fee), f"기준선 대비 −{_fmt_money(cut)} ({cut / opt_base.total_fee:.0%})" if opt_base.total_fee else "",
                  "접안불가 " + str(sum(1 for o in best.outcomes if not o.berthable)) + "척"]),
            cls="three",
        )
        + "<p class='caveat'>체선료 금액은 가상 계약 데이터(LayCan · LayTime · 일 체선료)로 계산한 값이라 절대값에는 의미가 없다. "
        "같은 데이터·같은 규칙에서 '최적화 전'과 '최적화 후'를 비교하는 용도다. '실제 계획'은 규칙 밖 대기(B3)와 "
        "같은 부두 동시 접안(B2)이 있어 비교 기준으로 쓰지 않는다. 부두 변경 수를 제한하는 조건은 아직 없다.</p>"
        + "<details class='tbl' open><summary>최적화로 바뀐 선박 " + str(len(moved)) + "척 (부두 변경) · 체선료가 바뀐 선박 포함</summary>"
        + _changes_table(opt) + "</details>"
        + "<details class='tbl'><summary>선박별 결과 (최적화 전 규칙 ETB 기준)</summary>" + _table(base, opt_base, options) + "</details>"
    )

    return PAGE.format(
        generated=f"{datetime.now():%Y-%m-%d %H:%M}", source=E(source), seed=data.seed,
        body=stage("1", "데이터", "실제 데이터를 읽고, 없는 값은 가상으로 만들고, 검증한다", data_stage)
        + arrow()
        + stage("2", "ETB 산정 — 모든 제약의 동시 충족", "장표 06~08쪽", etb_stage)
        + arrow()
        + stage("3", "ETB 산정 이후 계산식", "장표 09~11쪽", after_stage)
        + arrow()
        + stage("4", "최적화 — 부두 배정 · 접안 순서", "부두 적합성 필터를 통과한 부두 안에서만 옮긴다", opt_stage)
        + arrow()
        + stage("5", "결과", "최적화 전후 비교", result_stage),
    )


def _trace_svg(trace) -> str:
    w, h, pad = 1000, 140, 8
    its = [t[0] for t in trace]
    vals = [t[2] for t in trace]
    cur = [t[1] for t in trace]
    hi, lo = max(cur + vals), min(cur + vals)
    span = (hi - lo) or 1

    def pts(series):
        return " ".join(f"{pad + (w - 2 * pad) * i / max(its[-1], 1):.1f},{pad + (h - 2 * pad) * (1 - (v - lo) / span):.1f}"
                        for i, v in zip(its, series))

    return (
        "<div class='trace'><div class='trace-h'><b>탐색 경과</b><span><i class='lg cur'></i>현재 계획 비용"
        "<i class='lg best'></i>최고 기록</span><span class='mut'>"
        f"{_fmt_money(vals[0])} → {_fmt_money(vals[-1])}</span></div>"
        f"<svg viewBox='0 0 {w} {h}' preserveAspectRatio='none' role='img' aria-label='반복에 따른 체선료 합계'>"
        f"<polyline class='cur' points='{pts(cur)}'/><polyline class='best' points='{pts(vals)}'/></svg></div>"
    )


def _changes_table(opt) -> str:
    b0 = opt.baseline.by_id()
    pos0 = {v.vessel_id: i + 1 for seq in _plan_of(opt.baseline).values() for i, v in enumerate(seq)}
    pos1 = {v.vessel_id: i + 1 for seq in opt.best_plan.values() for i, v in enumerate(seq)}
    rows = []
    for o in sorted(opt.best.outcomes, key=lambda o: o.fee - b0[o.vessel.vessel_id].fee):
        a = b0[o.vessel.vessel_id]
        if o.vessel.berth == a.vessel.berth and abs(o.fee - a.fee) < 1 and o.etb == a.etb:
            continue
        cands = " · ".join(("<b>#" + E(b) + "</b>") if b == o.vessel.berth else "#" + E(b)
                           for b in opt.candidates.berths[o.vessel.vessel_id])
        berth = (f"#{E(a.vessel.berth)} → <b>#{E(o.vessel.berth)}</b>" if o.vessel.berth != a.vessel.berth
                 else f"#{E(a.vessel.berth)}")
        d = o.fee - a.fee
        notes = "<br>".join(E(n) for n in o.etb_notes) or "<span class='mut'>—</span>"
        rows.append(
            f"<tr><td class='id'>{E(o.vessel.vessel_id)}</td><td>{E(o.profile.ship_class)}<br>"
            f"<span class='mut'>{E(o.profile.cargo_group)} · DWT {o.profile.dwt:,.0f}</span></td>"
            f"<td>{berth}<br><span class='mut'>{pos0[o.vessel.vessel_id]}번 → {pos1[o.vessel.vessel_id]}번</span></td>"
            f"<td class='note'>{cands}</td><td>{o.vessel.eta:%m/%d %H:%M}</td>"
            f"<td>{a.etb:%m/%d %H:%M}<br><b>{o.etb:%m/%d %H:%M}</b></td><td class='note'>{notes}</td>"
            f"<td class='n'>{_fmt_money(a.fee)}<br><b>{_fmt_money(o.fee)}</b></td>"
            f"<td class='n {'down' if d < 0 else 'up' if d > 0 else ''}'>{'−' if d < 0 else '+'}{_fmt_money(abs(d))}</td></tr>"
        )
    return (
        "<div class='tablewrap'><table><thead><tr><th>선박</th><th>등급 / 화물</th><th>부두 · 순번</th><th>후보 부두</th>"
        "<th>ETA</th><th>ETB 전 / 후</th><th>ETB 조정 근거(후)</th><th>체선료 전 / 후</th><th>차이</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>"
    )


def _plan_of(res: ScenarioResult) -> dict[str, list]:
    plan: dict[str, list] = {}
    for o in sorted(res.outcomes, key=lambda o: o.etb):
        plan.setdefault(o.vessel.berth, []).append(o.vessel)
    return plan



PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>체선료 계산 워크플로우</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#16202c;--mut:#667085;--line:#d0d5dd;--real:#1d5fd1;--real-bg:#eaf1fd;
--synth:#b25e09;--synth-bg:#fdf3e7;--rule:#344054;--rule-bg:#ffffff;--check:#137a48;--check-bg:#e8f6ee;
--link:#6b3fc4;--link-bg:#f2edfc;--out:#16202c;--out-bg:#eef0f3;--fail:#c4320a}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#0f141a;--card:#161d25;--ink:#e6eaf0;--mut:#93a0b0;
--line:#2c3743;--real:#7aa7f5;--real-bg:#15233a;--synth:#f0a85a;--synth-bg:#2b1f12;--rule:#c9d2dc;--rule-bg:#161d25;
--check:#5fd39a;--check-bg:#11281d;--link:#b69af0;--link-bg:#221a35;--out:#e6eaf0;--out-bg:#1d2630;--fail:#ff8a65}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,"Apple SD Gothic Neo","Pretendard","Noto Sans KR",sans-serif}}
main{{max-width:1320px;margin:0 auto;padding:28px 16px 64px}}
h1{{font-size:24px;margin:0 0 4px}}.lead{{color:var(--mut);margin:0 0 14px}}
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px}}.legend span{{font-size:12px;padding:3px 10px;border-radius:999px;border:1px solid var(--line);background:var(--card)}}
.legend i{{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px;vertical-align:middle}}
.stage{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.stage>header{{display:flex;gap:12px;align-items:center;margin-bottom:14px}}.stage h2{{font-size:17px;margin:0}}.stage header p{{margin:0;color:var(--mut);font-size:12.5px}}
.no{{width:28px;height:28px;border-radius:8px;background:var(--ink);color:var(--bg);display:grid;place-items:center;font-weight:700;flex:none}}
.row{{display:grid;gap:12px}}.row.one{{grid-template-columns:minmax(0,560px);justify-content:center}}
.row.two{{grid-template-columns:repeat(2,minmax(0,1fr))}}.row.three{{grid-template-columns:repeat(3,minmax(0,1fr))}}
.trace{{margin-top:14px;border:1px solid var(--line);border-radius:10px;padding:10px 12px}}.trace-h{{display:flex;gap:16px;flex-wrap:wrap;align-items:center;font-size:12.5px;margin-bottom:6px}}
.trace svg{{width:100%;height:140px;display:block}}.trace polyline{{fill:none;stroke-width:2;vector-effect:non-scaling-stroke}}
.trace polyline.cur{{stroke:var(--line)}}.trace polyline.best{{stroke:var(--real)}}.lg{{display:inline-block;width:14px;height:3px;margin:0 5px 2px 10px;vertical-align:middle}}
.lg.cur{{background:var(--line)}}.lg.best{{background:var(--real)}}td.down{{color:var(--check)}}td.up{{color:var(--fail)}}.row.four{{grid-template-columns:repeat(4,minmax(0,1fr))}}
.row.five{{grid-template-columns:repeat(5,minmax(0,1fr))}}
.row.flow{{display:flex;align-items:stretch;gap:0}}.row.flow>.node,.row.flow>.stack{{flex:1 1 0;min-width:0}}
.stack{{display:flex;flex-direction:column;gap:10px}}
.node{{display:flex;flex-direction:column;gap:3px;text-decoration:none;color:inherit;border:1px solid var(--line);border-left:4px solid var(--rule);
border-radius:10px;padding:10px 12px;background:var(--rule-bg);transition:transform .12s,box-shadow .12s}}
.node:hover{{transform:translateY(-1px);box-shadow:0 4px 14px rgba(16,24,40,.12)}}
.node h4{{margin:0 0 2px;font-size:14px}}.node .kind{{font-size:10.5px;font-weight:600;letter-spacing:.02em;color:var(--rule)}}
.node .f{{font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mut);white-space:pre-wrap}}
.node .src{{margin-top:auto;padding-top:6px;font:11px ui-monospace,Menlo,monospace;color:var(--mut);overflow-wrap:anywhere}}
.node h4 a{{color:inherit;text-decoration:none}}.node h4 a:hover{{text-decoration:underline}}a.src{{text-decoration:none;align-self:flex-start}}
a.k{{color:var(--real);font-weight:600;text-decoration:underline dotted;text-underline-offset:2px;white-space:pre-wrap}}a.k:hover{{text-decoration-style:solid;background:var(--real-bg)}}
.node a.src:hover{{color:var(--ink);text-decoration:underline}}
.chips{{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}}.chip{{font-size:11.5px;padding:1px 8px;border-radius:999px;background:var(--bg);border:1px solid var(--line);font-variant-numeric:tabular-nums}}
.node.real{{border-left-color:var(--real);background:var(--real-bg)}}.node.real .kind{{color:var(--real)}}
.node.synth{{border-left-color:var(--synth);background:var(--synth-bg)}}.node.synth .kind{{color:var(--synth)}}
.node.check{{border-left-color:var(--check);background:var(--check-bg)}}.node.check .kind{{color:var(--check)}}
.node.link{{border-left-color:var(--link);background:var(--link-bg)}}.node.link .kind{{color:var(--link)}}
.node.out{{border-left-color:var(--out);background:var(--out-bg)}}.node.out .chip:first-child{{font-size:15px;font-weight:700}}
.arrow{{position:relative;display:flex;align-items:center;justify-content:center;color:var(--mut)}}
.arrow.down{{height:26px}}.arrow.down::before{{content:"";width:2px;height:100%;background:var(--line)}}
.arrow.down::after{{content:"";position:absolute;bottom:0;border:6px solid transparent;border-top-color:var(--line);border-bottom:0}}
.arrow.right{{flex:0 0 22px}}.arrow.right::before{{content:"";height:2px;width:100%;background:var(--line)}}
.arrow.right::after{{content:"";position:absolute;right:0;border:6px solid transparent;border-left-color:var(--line);border-right:0}}
.checks{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px}}.checks h5{{margin:0 0 6px;font-size:12.5px;color:var(--mut)}}
.ck{{display:grid;grid-template-columns:20px 30px max-content 1fr;gap:6px;align-items:baseline;padding:5px 0;border-bottom:1px dashed var(--line);font-size:12.5px}}
.ck .d{{text-align:right}}.ck b{{width:18px;height:18px;border-radius:50%;display:grid;place-items:center;font-size:11px;color:#fff;background:var(--mut)}}
.ck.pass b{{background:var(--check)}}.ck.fail b{{background:var(--fail)}}.ck .code{{font:11px ui-monospace,Menlo,monospace;color:var(--mut)}}
.ck .d{{font-variant-numeric:tabular-nums;color:var(--mut)}}.ck details{{grid-column:3/-1}}.ck summary{{cursor:pointer;color:var(--mut);font-size:12px}}
.ck ul{{margin:4px 0;padding-left:18px;color:var(--mut);font-size:12px}}
.caveat{{font-size:12.5px;color:var(--mut);margin:12px 0}}
details.tbl summary{{cursor:pointer;font-weight:600;margin:6px 0}}.tablewrap{{overflow-x:auto;border:1px solid var(--line);border-radius:10px}}
table{{border-collapse:collapse;width:100%;font-size:12px;min-width:1100px}}th,td{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{position:sticky;top:0;background:var(--out-bg);font-weight:600;white-space:nowrap}}td.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
td.id{{font-family:ui-monospace,Menlo,monospace;white-space:nowrap}}td.note{{max-width:300px;color:var(--mut)}}.mut{{color:var(--mut)}}
footer{{color:var(--mut);font-size:12px;margin-top:18px}}
@media (max-width:1000px){{.row.five,.row.four{{grid-template-columns:repeat(2,minmax(0,1fr))}}.row.flow{{flex-direction:column}}
.arrow.right{{flex-basis:22px;height:22px}}.arrow.right::before{{width:2px;height:100%}}.arrow.right::after{{right:auto;bottom:0;border:6px solid transparent;border-top-color:var(--line);border-bottom:0}}
.checks{{grid-template-columns:1fr}}}}
@media (max-width:560px){{.row.five,.row.four,.row.three,.row.two{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>체선료 계산 워크플로우</h1>
<p class="lead">실제 접안계획에서 출발해 ETB 산정과 체선료까지 이어지는 전체 흐름. 박스 제목을 누르면 함수가, <a class="k">파란 점선 값</a>을 누르면 그 값이 정의된 줄이 VS Code에서 열린다.</p>
<div class="legend"><span><i style="background:var(--real)"></i>실제 데이터</span><span><i style="background:var(--synth)"></i>가상 데이터</span>
<span><i style="background:var(--check)"></i>검증</span><span><i style="background:var(--link)"></i>연결</span><span><i style="background:var(--rule)"></i>장표 규칙</span>
<span><i style="background:var(--out)"></i>결과</span></div>
{body}
<footer>생성 {generated} · 데이터 {source} · 가상 데이터 seed {seed} · 칩의 숫자는 이번 실행 결과</footer>
</main></body></html>
"""
