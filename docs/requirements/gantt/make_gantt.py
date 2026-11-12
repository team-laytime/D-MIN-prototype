#!/usr/bin/env python3
"""간트 생성기 — tasks.csv + gantt.config.json 에서 gantt.html, gantt.md, tasks.resolved.csv,
starter.md, starter.csv 를 만든다.

사용법
  python3 make_gantt.py            파일 5개를 다시 만든다
  python3 make_gantt.py --check    검사만 한다 (파일을 쓰지 않는다)

시작용 표
  gantt.config.json 의 starter(작업 ID 목록)에 든 작업만 골라 starter.md·starter.csv 와
  gantt.html 의 '시작용' 보기로 만든다. 날짜·선행·담당은 tasks.csv 에서 그대로 가져오므로
  따로 고칠 곳이 없다.

날짜 규칙
  start_date·end_date 가 있으면 그 날짜를 쓴다.
  없으면 project_start ~ deadline 구간을 100%로 보고 start_pct·end_pct(%)로 환산한다.
  마감일이 바뀌면 gantt.config.json 의 deadline 만 고치면 전체가 같은 비율로 늘거나 준다.

표준 라이브러리만 쓴다.
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "gantt.config.json"
TASKS = HERE / "tasks.csv"
OUT_HTML = HERE / "gantt.html"
OUT_MD = HERE / "gantt.md"
OUT_CSV = HERE / "tasks.resolved.csv"
OUT_STARTER_MD = HERE / "starter.md"
OUT_STARTER_CSV = HERE / "starter.csv"

TYPES = {"task", "gate"}
BRANCHES = {"공통", "A", "B"}
STATUSES = {"todo", "active", "done"}
YN = {"Y", "N"}
GATE_LANE = "G"
WEEKDAY = "월화수목금토일"
STATUS_KO = {"todo": "예정", "active": "진행 중", "done": "완료"}
LONG_DAYS = 7  # 이보다 길면 시작용 표에서 '1주 초과'로 알린다


def half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def iso(s: str):
    return date.fromisoformat(s) if s else None


def md(d: date) -> str:
    return f"{d.month}/{d.day}({WEEKDAY[d.weekday()]})"


def split(s: str) -> list[str]:
    return [x.strip() for x in s.split(";") if x.strip()]


def load():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    with open(TASKS, encoding="utf-8-sig", newline="") as f:
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
    return cfg, rows


def resolve(cfg, rows):
    errors: list[str] = []
    warnings: list[str] = []
    start, end = iso(cfg["project_start"]), iso(cfg["deadline"])
    if not (start and end and end > start):
        return [], ["project_start 와 deadline 이 올바르지 않습니다 (deadline 이 더 늦어야 합니다)"], [], None
    total = (end - start).days
    lane_ids = {lane["id"] for lane in cfg["lanes"]}
    seen: set[str] = set()
    out: list[dict] = []

    def to_day(pct: str) -> int:
        v = float(pct)
        if not 0 <= v <= 100:
            raise ValueError(f"{pct} 는 0~100 이어야 합니다")
        return half_up(total * v / 100.0)

    for n, r in enumerate(rows, start=2):
        rid = r.get("id", "")
        where = f"tasks.csv {n}행 ({rid or '?'})"
        if not rid:
            errors.append(f"{where}: id 가 비었습니다")
            continue
        if rid in seen:
            errors.append(f"{where}: id 가 중복됩니다")
        seen.add(rid)
        if r["type"] not in TYPES:
            errors.append(f"{where}: type 은 task 또는 gate 여야 합니다")
        if r["branch"] not in BRANCHES:
            errors.append(f"{where}: branch 는 공통/A/B 중 하나여야 합니다")
        if r["status"] not in STATUSES:
            errors.append(f"{where}: status 는 todo/active/done 중 하나여야 합니다")
        for k in ("dep_on_answer", "conditional", "critical"):
            if r[k] not in YN:
                errors.append(f"{where}: {k} 는 Y 또는 N 이어야 합니다")
        if r["type"] == "gate" and r["lane"] != GATE_LANE:
            errors.append(f"{where}: gate 의 lane 은 {GATE_LANE} 여야 합니다")
        if r["type"] == "task" and r["lane"] not in lane_ids:
            errors.append(f"{where}: lane {r['lane']} 이(가) gantt.config.json 에 없습니다")
        try:
            sd, ed = iso(r["start_date"]), iso(r["end_date"])
            if r["status"] == "done":
                if not sd:
                    raise ValueError("done 항목은 start_date 가 필요합니다")
                s, e = sd, ed or sd
            elif r["type"] == "gate":
                if not sd and r["start_pct"] == "":
                    raise ValueError("gate 는 start_pct 또는 start_date 가 필요합니다")
                s = sd or start + timedelta(days=to_day(r["start_pct"]))
                e = s
            else:
                if not sd and r["start_pct"] == "":
                    raise ValueError("start_pct 또는 start_date 가 필요합니다")
                if not ed and r["end_pct"] == "":
                    raise ValueError("end_pct 또는 end_date 가 필요합니다")
                s = sd or start + timedelta(days=to_day(r["start_pct"]))
                e = ed or start + timedelta(days=to_day(r["end_pct"]))
                if e <= s:
                    warnings.append(f"{where}: 끝이 시작보다 늦지 않아 1일로 보정했습니다")
                    e = s + timedelta(days=1)
        except ValueError as ex:
            errors.append(f"{where}: {ex}")
            continue
        r = dict(r)
        r["_s"], r["_e"] = s, e
        out.append(r)

    by_id = {r["id"]: r for r in out}
    for r in out:
        if r["status"] == "done":
            continue
        for d in split(r["depends"]):
            p = by_id.get(d)
            if not p:
                errors.append(f"{r['id']}: depends 의 {d} 가 tasks.csv 에 없습니다")
            elif p["status"] != "done" and r["_s"] < p["_e"]:
                warnings.append(
                    f"{r['id']} 은(는) 선행 {d} 가 끝나기 전({md(p['_e'])})에 시작합니다 ({md(r['_s'])})"
                )
    return out, errors, warnings, (start, end, total)


def lane_order(cfg):
    order = {GATE_LANE: -1}
    for i, lane in enumerate(cfg["lanes"]):
        order[lane["id"]] = i
    return order


def lane_names(cfg):
    names = {lane["id"]: lane["name"] for lane in cfg["lanes"]}
    names[GATE_LANE] = "게이트"
    return names


def sort_key(cfg):
    order = lane_order(cfg)
    return lambda r: (order.get(r["lane"], 99), r["_s"], r["id"])


def write_csv(cfg, out, start):
    names = lane_names(cfg)
    cols = ["id", "lane", "lane_name", "name", "type", "start", "end", "days", "week", "depends",
            "branch", "dep_on_answer", "conditional", "critical", "status", "owner", "req", "note"]
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in sorted(out, key=sort_key(cfg)):
            week = "완료" if r["status"] == "done" else f"W{(r['_s'] - start).days // 7 + 1}"
            w.writerow([r["id"], r["lane"], names[r["lane"]], r["name"], r["type"], r["_s"].isoformat(),
                        r["_e"].isoformat(), (r["_e"] - r["_s"]).days, week, r["depends"], r["branch"],
                        r["dep_on_answer"], r["conditional"], r["critical"], r["status"], r["owner"],
                        r["req"], r["note"]])


def mm_clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[:;#,\"'\[\]%]", " ", s)).strip()


def mm_id(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def mermaid(cfg, out):
    lines = ["gantt", f"    title {mm_clean(cfg['title'])}", "    dateFormat YYYY-MM-DD", "    axisFormat %m/%d",
             "    section 게이트"]
    for g in sorted((r for r in out if r["type"] == "gate"), key=lambda r: r["_s"]):
        lines.append(f"    {mm_clean(g['name'])} :milestone, {mm_id(g['id'])}, {g['_s'].isoformat()}, 0d")
    for lane in cfg["lanes"]:
        ts = [r for r in out if r["type"] == "task" and r["lane"] == lane["id"] and r["status"] != "done"]
        if not ts:
            continue
        lines.append(f"    section {mm_clean(lane['name'])}")
        for r in sorted(ts, key=lambda r: (r["_s"], r["id"])):
            tags = (["active"] if r["status"] == "active" else []) + (["crit"] if r["critical"] == "Y" else [])
            days = max(1, (r["_e"] - r["_s"]).days)
            label = mm_clean(f"{r['id']} {r['name']}") + (" (조건부)" if r["conditional"] == "Y" else "")
            meta = ", ".join(tags + [mm_id(r["id"]), r["_s"].isoformat(), f"{days}d"])
            lines.append(f"    {label} :{meta}")
    return "\n".join(lines)


def write_md(cfg, out, start, end, total, warnings):
    names = lane_names(cfg)
    todo = [r for r in out if r["status"] != "done" and r["type"] == "task"]
    gates = sorted((r for r in out if r["type"] == "gate"), key=lambda r: r["_s"])
    done = sorted((r for r in out if r["status"] == "done"), key=lambda r: (r["_s"], r["id"]))
    p: list[str] = []
    p.append(f"# {cfg['title']}\n")
    p.append("> 이 파일은 `make_gantt.py`가 `tasks.csv`와 `gantt.config.json`에서 **자동 생성**한다. "
             "직접 고치지 말고 원본을 고친 뒤 `python3 make_gantt.py`를 다시 실행한다.\n")
    p.append(f"- 기간: **{md(start)} {start.year} ~ {md(end)} {end.year}** ({total}일, {cfg['deadline_status']})")
    p.append(f"- 날짜 규칙: `start_pct`·`end_pct`는 이 기간을 100%로 본 비율이고, `start_date`·`end_date`가 있으면 그것이 우선한다.")
    p.append(f"- {cfg.get('owner_note', '')}")
    p.append(f"- 차트(상호작용): [`gantt.html`](gantt.html) — 브라우저로 연다. 분기(A/B) 버튼으로 안 고른 쪽 레인을 접어 볼 수 있다.")
    p.append(f"- 표 데이터: [`tasks.csv`](tasks.csv)(원본), [`tasks.resolved.csv`](tasks.resolved.csv)(날짜가 풀린 사본 — Excel·Google Sheets·Notion으로 가져갈 때)")
    p.append("- 처음 보는 사람용 요약: [`starter.md`](starter.md)(핵심 작업만), 시트로 가져갈 때는 [`starter.csv`](starter.csv). 차트에서는 '시작용' 보기 버튼.")
    p.append("- 요구 ID(INT-, CLK- …)는 [`../03-prd-v0.md`](../03-prd-v0.md), 시나리오 ID(S-)는 [`../04-scenarios.md`](../04-scenarios.md)에 있다.\n")
    p.append("## 1. 간트 (Mermaid)\n")
    p.append("GitHub·Obsidian·VS Code 미리보기에서는 아래 블록이 그림으로 보인다. 안 보이면 내용을 <https://mermaid.live/> 에 붙여 넣는다. "
             "`crit`(붉은 막대)은 임계 경로, `active`는 진행 중이다.\n")
    p.append("```mermaid\n" + mermaid(cfg, out) + "\n```\n")
    p.append("## 2. 게이트\n")
    p.append("| 게이트 | 날짜 | 주 | 의미 | 선행 |\n|---|---|---|---|---|")
    for g in gates:
        p.append(f"| {g['name']} | {md(g['_s'])} | W{(g['_s'] - start).days // 7 + 1} | {g['note'] or '—'} | {g['depends'] or '—'} |")
    p.append("\n## 3. 작업\n")
    for lane in cfg["lanes"]:
        ts = sorted((r for r in todo if r["lane"] == lane["id"]), key=lambda r: (r["_s"], r["id"]))
        if not ts:
            continue
        p.append(f"### {lane['name']}\n")
        p.append("| ID | 작업 | 시작 | 끝 | 선행 | 분기 | 요구 | 담당 | 비고 |\n|---|---|---|---|---|---|---|---|---|")
        for r in ts:
            flags = []
            if r["dep_on_answer"] == "Y":
                flags.append("멘토 답에 달림")
            if r["conditional"] == "Y":
                flags.append("조건부")
            if r["critical"] == "Y":
                flags.append("임계 경로")
            if r["status"] == "active":
                flags.append("진행 중")
            note = " · ".join(flags + ([r["note"]] if r["note"] else []))
            p.append(f"| {r['id']} | {r['name']} | {md(r['_s'])} | {md(r['_e'])} | {r['depends'].replace(';', ', ') or '—'} | "
                     f"{r['branch']} | {r['req'].replace(';', ', ') or '—'} | {r['owner'].replace(';', ', ') or '미정'} | {note or '—'} |")
        p.append("")
    p.append("## 4. 이미 끝난 것 (타임라인 밖)\n")
    p.append("| ID | 레인 | 내용 | 날짜 | 비고 |\n|---|---|---|---|---|")
    for r in done:
        p.append(f"| {r['id']} | {names[r['lane']]} | {r['name']} | {md(r['_s'])} | {r['note'] or '—'} |")
    p.append("\n## 5. 고치는 법\n")
    p.append("1. 마감이 확정되면 `gantt.config.json`의 `deadline`을 고치고 `deadline_status`를 \"확정\"으로 바꾼다. 모든 막대가 같은 비율로 늘거나 준다.")
    p.append("2. 작업은 `tasks.csv`에서 고친다. 날짜가 확정된 작업은 `start_date`·`end_date`(YYYY-MM-DD)를 적는다.")
    p.append("3. 코어(A/B)가 정해지면 안 고른 분기의 작업을 `tasks.csv`에서 지우거나 `branch`는 그대로 두고 Won't로 `note`에 적는다.")
    p.append("4. 시작용 요약에 넣을 작업은 `gantt.config.json`의 `starter`(작업 ID 목록)로 고른다. 코어가 B로 바뀌면 T-502·T-503을 T-602·T-603으로 바꾼다.")
    p.append("5. `python3 make_gantt.py`를 실행한다. `--check`만 주면 검사만 한다.")
    if warnings:
        p.append("\n## 6. 생성기 경고\n")
        p.extend(f"- {w}" for w in warnings)
    OUT_MD.write_text("\n".join(p) + "\n", encoding="utf-8")


def starter_rows(cfg, out):
    """config 의 starter(작업 ID 목록)를 시작일 순서의 행으로 풀어 (행, 오류) 를 돌려준다."""
    by_id = {r["id"]: r for r in out}
    rows: list[dict] = []
    errors: list[str] = []
    for tid in cfg.get("starter", []):
        r = by_id.get(tid)
        if r is None:
            errors.append(f"gantt.config.json starter: {tid} 이(가) tasks.csv 에 없습니다")
        elif r["type"] != "task" or r["status"] == "done":
            errors.append(f"gantt.config.json starter: {tid} 은(는) 남은 작업이 아닙니다 (게이트는 자동으로 붙고 완료 항목은 넣지 않습니다)")
        elif any(x["id"] == tid for x in rows):
            errors.append(f"gantt.config.json starter: {tid} 이(가) 두 번 적혀 있습니다")
        else:
            rows.append(r)
    rows.sort(key=lambda r: (r["_s"], r["_e"], r["id"]))
    return rows, errors


def starter_table(cfg, out, rows):
    """시작용 표의 각 행을 사전으로 만든다 (md·csv 공용). 날짜·선행·담당은 tasks.csv 에서 그대로 가져온다."""
    gates = [r for r in out if r["type"] == "gate"]
    no = {r["id"]: i for i, r in enumerate(rows, start=1)}
    table = []
    for i, r in enumerate(rows, start=1):
        days = (r["_e"] - r["_s"]).days
        table.append({
            "no": i, "id": r["id"], "name": r["name"], "start": r["_s"], "end": r["_e"], "days": days,
            "after": [str(no[d]) if d in no else f"{d}(목록 밖)" for d in split(r["depends"])],
            "owner": r["owner"].replace(";", "·") or "미정", "status": STATUS_KO[r["status"]],
            "marks": [f"{g['name']} ({g['_s'].month}/{g['_s'].day})" for g in gates if r["id"] in split(g["depends"])],
            "crit": r["critical"] == "Y", "long": days > LONG_DAYS, "branch": r["branch"], "note": r["note"],
        })
    return table


def write_starter_csv(table):
    cols = ["번호", "할 일(결과물)", "시작", "끝", "기간(일)", "먼저 끝나야 할 일(번호)", "담당(역할)", "담당(이름)",
            "상태", "이정표", "핵심 경로", "1주 초과", "분기", "원본 ID", "비고"]
    with open(OUT_STARTER_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for t in table:
            w.writerow([t["no"], t["name"], t["start"].isoformat(), t["end"].isoformat(), t["days"],
                        ", ".join(t["after"]), t["owner"], "", t["status"], " / ".join(t["marks"]),
                        "예" if t["crit"] else "", "예" if t["long"] else "", t["branch"], t["id"], t["note"]])


def write_starter_md(cfg, table, out, start, end, total):
    team = cfg.get("team") or {}
    n_all = len([r for r in out if r["type"] == "task" and r["status"] != "done"])
    gates = sorted((r for r in out if r["type"] == "gate"), key=lambda r: r["_s"])
    p: list[str] = []
    p.append("# 시작용 간트 표 — 우리 팀\n")
    p.append("> 이 파일은 `make_gantt.py`가 `tasks.csv`·`gantt.config.json`에서 **자동 생성**한다. 직접 고치지 말고 "
             "원본을 고친 뒤 `python3 make_gantt.py`를 다시 실행한다. 여기에 담을 작업은 `gantt.config.json`의 `starter`로 고른다.\n")
    p.append("- [`../00-start-here.md`](../00-start-here.md) §3의 시작용 표를 우리 일정으로 채운 것이다.")
    p.append(f"- 기간: **{md(start)} ~ {md(end)}** ({total}일). 마감일은 **{cfg['deadline_status']}** 이다. 알게 되면 `deadline`만 고친다.")
    if team:
        p.append(f"- 팀: **{team.get('size', '미정')}** ({team.get('status', '')}). {team.get('note', '')}")
    p.append(f"- 전체 일정 {n_all}개 작업 중 핵심 {len(table)}개만 골랐다. 전부 보려면 [`gantt.md`](gantt.md), "
             "차트는 [`gantt.html`](gantt.html)(처음에 '시작용' 보기)이다.\n")
    p.append(f"## 시작일({start.month}/{start.day})에 시작하는 일\n")
    for t in (t for t in table if t["start"] == start):
        p.append(f"- **{t['no']}번** {t['name']} ({t['days']}일, {t['owner']})" + (" — 핵심 경로" if t["crit"] else ""))
    p.append("\n## 표\n")
    p.append("| # | 할 일 (결과물) | 시작 | 끝 | 기간 | 먼저 끝나야 할 일 | 담당(역할) | 담당(이름) | 상태 | 표시 |")
    p.append("|---|---|---|---|---|---|---|---|---|---|")
    for t in table:
        flags = []
        if t["crit"]:
            flags.append("핵심 경로")
        flags += [f"◆ {m}" for m in t["marks"]]
        if t["branch"] != "공통":
            flags.append(f"{t['branch']} 코어 전용")
        if t["long"]:
            flags.append(f"1주 초과 ({t['days']}일)")
        if t["note"]:
            flags.append(t["note"].split(" · ")[0])
        p.append(f"| {t['no']} | {t['name']} | {md(t['start'])} | {md(t['end'])} | {t['days']}일 | "
                 f"{', '.join(t['after']) or '—'} | {t['owner']} | | {t['status']} | {' · '.join(flags) or '—'} |")
    p.append("\n**읽는 법**: 핵심 경로 = 이 줄이 밀리면 마감까지 통째로 밀린다 · ◆ = 결정하는 날 · "
             "A 코어 전용 = 코어가 B로 바뀌면 내용이 바뀐다 · 1주 초과 = 착수 전에 반으로 쪼갠다 · "
             "'먼저 끝나야 할 일'의 숫자는 이 표의 # 번호다.\n")
    p.append("## 결정하는 날 ◆\n")
    p.append("| 날짜 | 이정표 | 뜻 |\n|---|---|---|")
    for g in gates:
        p.append(f"| {md(g['_s'])} | {g['name']} | {g['note'] or '—'} |")
    longs = [t for t in table if t["long"]]
    if longs:
        p.append("\n## 1주를 넘는 줄\n")
        p.append("좋은 간트의 조건(\"막대 하나가 1주를 넘지 않는다\")에 걸리는 줄이다. 일을 시작할 때 반으로 쪼개 두 줄로 만든다 [추천].\n")
        for t in longs:
            p.append(f"- {t['no']}번 {t['name']} ({t['days']}일)")
    p.append("\n## 쓰는 법\n")
    p.append("1. [`starter.csv`](starter.csv)를 Google Sheets나 Excel로 가져온다 (파일 → 가져오기). 한글이 깨지면 인코딩을 UTF-8로 고른다.")
    p.append("2. `담당(이름)` 칸에 사람 이름을 적는다. 한 줄에 한 명이다.")
    p.append("3. 일을 시작하면 `상태`를 \"진행 중\", 끝나면 \"완료\"로 바꾼다. 매주 월요일 5분, 이 표를 같이 본다.")
    p.append("4. 시트로 옮긴 순간부터 시트가 팀의 일정이다. 저장소의 `tasks.csv`와 시트 중 **하나만 원본**으로 정한다. "
             "저장소를 원본으로 쓰면 `tasks.csv`를 고치고 다시 생성한다.")
    OUT_STARTER_MD.write_text("\n".join(p) + "\n", encoding="utf-8")


def payload(cfg, out, start, total):
    names = lane_names(cfg)

    def day(pct):
        return (start + timedelta(days=half_up(total * float(pct) / 100.0))).isoformat()

    def rec(r):
        return {
            "id": r["id"], "lane": r["lane"], "lane_name": names[r["lane"]], "name": r["name"], "type": r["type"],
            "start": r["_s"].isoformat(), "end": r["_e"].isoformat(), "depends": split(r["depends"]),
            "branch": r["branch"], "dep": r["dep_on_answer"] == "Y", "cond": r["conditional"] == "Y",
            "crit": r["critical"] == "Y", "status": r["status"], "owner": r["owner"].replace(";", ", "),
            "req": split(r["req"]), "note": r["note"],
        }

    keys = ("title", "subtitle", "project_start", "deadline", "deadline_status", "today", "owner_note")
    return {
        "config": {k: cfg.get(k) for k in keys},
        "lanes": cfg["lanes"],
        "phases": [{"name": p["name"], "from": day(p["from_pct"]), "to": day(p["to_pct"])} for p in cfg["phases"]],
        "tasks": [rec(r) for r in sorted(out, key=sort_key(cfg)) if r["type"] == "task" and r["status"] != "done"],
        "gates": [rec(r) for r in out if r["type"] == "gate"],
        "done": [rec(r) for r in sorted(out, key=lambda r: (r["_s"], r["id"])) if r["status"] == "done"],
        "starter": cfg.get("starter", []),
        "generated": date.today().isoformat(),
    }


def write_html(cfg, out, start, total):
    data = json.dumps(payload(cfg, out, start, total), ensure_ascii=False).replace("</", "<\\/")
    OUT_HTML.write_text(HTML.replace("__TITLE__", cfg["title"]).replace("__DATA__", data), encoding="utf-8")


HTML = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#fff;--fg:#1f2328;--muted:#656d76;--line:#d8dee4;--panel:#f6f8fa;--card:#fff;--teal:#0f766e;--teal-bg:#d1f5ec;--purple:#6d28d9;--purple-bg:#ece6fd;--gate:#57606a;--today:#d1242f;--crit:#c2410c;--ok:#1a7f37}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8b949e;--line:#30363d;--panel:#161b22;--card:#0d1117;--teal:#3dd5c0;--teal-bg:#12423d;--purple:#b197fc;--purple-bg:#2f2557;--gate:#9da7b3;--today:#ff7b72;--crit:#ffa657;--ok:#3fb950}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",system-ui,sans-serif}
header,main,footer{max-width:1240px;margin:0 auto;padding:0 20px}
h1{font-size:22px;margin:24px 0 4px;font-weight:600}
h2{font-size:16px;font-weight:600;margin:28px 0 10px}
.sub{color:var(--muted);margin:0 0 12px}
.banner{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--crit);padding:8px 12px;border-radius:6px;margin:8px 0 12px;font-size:13px}
.ctl{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin:8px 0 12px;font-size:13px}
.ctl button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);padding:4px 12px;cursor:pointer}
.seg{display:inline-flex}
.seg button:first-child{border-radius:6px 0 0 6px}.seg button:last-child{border-radius:0 6px 6px 0}.seg button+button{border-left:0}
.seg button.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
#bPrint{border-radius:6px}
.chart{border:1px solid var(--line);border-radius:8px;background:var(--card);overflow:hidden}
svg text{font-family:inherit}
.lh{fill:var(--panel)}.ll{font-size:13px;font-weight:600;fill:var(--fg)}.ln{font-weight:400;fill:var(--muted);font-size:12px}
.tl{font-size:12px;fill:var(--fg)}.tid{fill:var(--muted);font-family:ui-monospace,Menlo,monospace;font-size:11px}
.dt{font-size:11px;fill:var(--muted)}.grid{stroke:var(--line);stroke-width:1}.rowline{stroke:var(--line);stroke-width:.5;opacity:.7}
.gl{stroke:var(--gate);stroke-width:1;stroke-dasharray:4 4;opacity:.7}
.today{stroke:var(--today);stroke-width:1.6}.todaytxt{fill:var(--today);font-size:11px;font-weight:600}
.ph{fill:var(--panel);stroke:var(--line)}.pht{font-size:12px;fill:var(--fg)}.wk{font-size:11px;fill:var(--muted)}
.gd{fill:var(--gate);stroke:var(--card);stroke-width:1.5}.gd.k{fill:var(--crit)}
.gt{font-size:12px;font-weight:600;fill:var(--fg)}.gn{font-size:11px;fill:var(--muted)}
.bar{stroke-width:1.2}.bar.t{fill:var(--teal-bg);stroke:var(--teal)}.bar.p{fill:var(--purple-bg);stroke:var(--purple)}
.bar.c{stroke-dasharray:5 3}.bar.k{stroke:var(--crit);stroke-width:2.2}.act{fill:var(--ok)}
.dep{fill:none;stroke:var(--muted);stroke-width:1;opacity:.5}.dep.k{stroke:var(--crit);opacity:.9;stroke-width:1.4}
.mk{fill:var(--muted)}.mkk{fill:var(--crit)}
.task{cursor:default}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;margin:10px 0 0;font-size:12.5px;color:var(--muted)}
.sw{display:inline-block;width:22px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:6px;border:1.2px solid}
.sw.t{background:var(--teal-bg);border-color:var(--teal)}.sw.p{background:var(--purple-bg);border-color:var(--purple)}
.sw.c{border-style:dashed}.sw.k{border:2.2px solid var(--crit);background:var(--panel)}
.dia{display:inline-block;width:9px;height:9px;background:var(--gate);transform:rotate(45deg);margin:0 9px 0 4px}
.tdot{display:inline-block;width:16px;border-top:2px solid var(--today);margin-right:6px;vertical-align:4px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:8px}
.card{border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:var(--panel);font-size:13px}
.card b{color:var(--ok);margin-right:4px}.card .meta{color:var(--muted);font-size:12px}
details{margin-top:24px}summary{cursor:pointer;font-size:16px;font-weight:600}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:10px}
th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:var(--panel)}td.id{font-family:ui-monospace,Menlo,monospace;color:var(--muted);white-space:nowrap}
#tip{position:fixed;z-index:10;display:none;max-width:380px;background:var(--fg);color:var(--bg);padding:8px 10px;border-radius:6px;font-size:12.5px;line-height:1.5;pointer-events:none;box-shadow:0 2px 10px rgba(0,0,0,.3)}
footer{padding-bottom:40px}
@media print{.ctl,#tip{display:none}body{font-size:11px}@page{size:A3 landscape;margin:10mm}}
</style>
</head>
<body>
<header>
<h1 id="ttl"></h1>
<p class="sub" id="sub"></p>
<div class="banner" id="ban"></div>
<div class="ctl">
<span id="lblV">범위</span>
<span class="seg" id="segV"><button class="on" data-view="starter" id="bvS">시작용</button><button data-view="all" id="bvA">전체</button></span>
<span>분기 보기</span>
<span class="seg"><button class="on" data-br="both">A·B 둘 다</button><button data-br="A">A 코어</button><button data-br="B">B 코어</button></span>
<label><input type="checkbox" id="cCond" checked> 조건부 작업</label>
<label><input type="checkbox" id="cDeps" checked> 의존선</label>
<button id="bPrint">인쇄</button>
</div>
</header>
<main>
<div class="chart" id="host"></div>
<div class="legend">
<span><i class="sw t"></i>답과 무관, 지금 가능</span>
<span><i class="sw p"></i>멘토 답에 달림</span>
<span><i class="sw t c"></i>조건부(자료를 받을 때만)</span>
<span><i class="sw k"></i>임계 경로</span>
<span><i class="dia"></i>게이트</span>
<span><i class="tdot"></i>오늘</span>
</div>
<h2>이미 끝난 것 <span class="sub" id="doneN"></span></h2>
<div class="cards" id="done"></div>
<details><summary>작업 표 (날짜 포함)</summary><div id="table"></div></details>
</main>
<footer><p class="sub" id="foot"></p></footer>
<div id="tip"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
var DATA=JSON.parse(document.getElementById('data').textContent);
var cfg=DATA.config,lanes=DATA.lanes,phases=DATA.phases,ONE=86400000,WD=['일','월','화','수','목','금','토'];
function parse(s){var p=s.split('-').map(Number);return new Date(p[0],p[1]-1,p[2]);}
function addDays(d,n){return new Date(d.getFullYear(),d.getMonth(),d.getDate()+n);}
var start=parse(cfg.project_start),end=parse(cfg.deadline),total=Math.round((end-start)/ONE);
function dayOf(d){return Math.round((d-start)/ONE);}
function fmt(d){return (d.getMonth()+1)+'/'+d.getDate();}
function fmtW(d){return fmt(d)+'('+WD[d.getDay()]+')';}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function strW(s,px){var w=0;for(var i=0;i<s.length;i++){w+=s.charCodeAt(i)>=0x1100?px*1.05:px*0.56;}return w;}
function clip(s,max,px){if(strW(s,px)<=max)return s;var o='';for(var i=0;i<s.length;i++){if(strW(o+s[i]+'…',px)>max)break;o+=s[i];}return o+'…';}
var tasks=DATA.tasks.map(function(t){t._s=dayOf(parse(t.start));t._e=dayOf(parse(t.end));return t;});
var gates=DATA.gates.map(function(g){g._d=dayOf(parse(g.start));return g;}).sort(function(a,b){return a._d-b._d;});
var byId={};tasks.forEach(function(t){byId[t.id]=t;});gates.forEach(function(g){byId[g.id]=g;});
var STARTER=DATA.starter||[];
var state={branch:'both',cond:true,deps:true,view:STARTER.length?'starter':'all'};
function visible(t){if(state.view==='starter'&&STARTER.indexOf(t.id)<0)return false;if(state.branch==='A'&&t.branch==='B')return false;if(state.branch==='B'&&t.branch==='A')return false;if(!state.cond&&t.cond)return false;return true;}

function render(){
var W=1180,LEFT=360,RIGHT=28,HEAD=114,ROW=28,LH=28,CW=W-LEFT-RIGHT;
function X(d){return LEFT+CW*d/total;}
var rows=[];
lanes.forEach(function(ln){
var ts=tasks.filter(function(t){return t.lane===ln.id&&visible(t);}).sort(function(a,b){return a._s-b._s||(a.id<b.id?-1:1);});
if(!ts.length)return;
rows.push({k:'lane',ln:ln,n:ts.length});
ts.forEach(function(t){rows.push({k:'task',t:t});});
});
var y=HEAD;rows.forEach(function(r){r.y=y;y+=(r.k==='lane'?LH:ROW);});
var H=y+26,B=[],pos={};
rows.forEach(function(r){if(r.k==='task')pos[r.t.id]=r;});
B.push('<svg viewBox="0 0 '+W+' '+H+'" width="100%" role="img" aria-label="'+esc(cfg.title)+' 간트 차트"><title>'+esc(cfg.title)+'</title>');
B.push('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="mk" d="M1 1L9 5L1 9z"/></marker><marker id="ahk" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="mkk" d="M1 1L9 5L1 9z"/></marker></defs>');
phases.forEach(function(p){var x0=X(dayOf(parse(p.from))),x1=X(dayOf(parse(p.to)));
B.push('<rect class="ph" x="'+(x0+1)+'" y="8" width="'+Math.max(x1-x0-2,2)+'" height="22" rx="4"/>');
B.push('<text class="pht" x="'+((x0+x1)/2)+'" y="23" text-anchor="middle">'+esc(p.name)+'</text>');});
for(var d=0;d<=total;d+=7){var gx=X(d);
B.push('<line class="grid" x1="'+gx+'" x2="'+gx+'" y1="36" y2="'+(H-14)+'"/>');
var wl='W'+(d/7+1)+' '+fmt(addDays(start,d));
if(gx+4+strW(wl,11)<W-4)B.push('<text class="wk" x="'+(gx+4)+'" y="50">'+wl+'</text>');}
gates.forEach(function(g){var gx=X(g._d);B.push('<line class="gl" x1="'+gx+'" x2="'+gx+'" y1="64" y2="'+(H-14)+'"/>');});
rows.forEach(function(r){
if(r.k==='lane'){B.push('<rect class="lh" x="0" y="'+r.y+'" width="'+W+'" height="'+LH+'"/>');
B.push('<text class="ll" x="12" y="'+(r.y+LH/2+4.5)+'">'+esc(r.ln.name)+' <tspan class="ln">'+r.n+'개</tspan></text>');}
else{B.push('<line class="rowline" x1="0" x2="'+W+'" y1="'+(r.y+ROW)+'" y2="'+(r.y+ROW)+'"/>');}});
if(state.deps){rows.forEach(function(r){if(r.k!=='task')return;var t=r.t;t.depends.forEach(function(pid){var pr=pos[pid];if(!pr)return;
var p=pr.t,x1=X(p._e),y1=pr.y+ROW/2,x2=X(t._s),y2=r.y+ROW/2,k=p.crit&&t.crit,path;
if(x2>=x1+14){var xm=x1+7;path='M'+x1+' '+y1+' H'+xm+' V'+y2+' H'+(x2-1);}
else{path='M'+x1+' '+(y1+8)+' L'+(x2+2)+' '+(y2-9);}
B.push('<path class="dep'+(k?' k':'')+'" d="'+path+'" marker-end="url(#'+(k?'ahk':'ah')+')"/>');});});}
rows.forEach(function(r){if(r.k!=='task')return;var t=r.t,x0=X(t._s),x1=X(t._e),w=Math.max(x1-x0,6);
var cls='bar '+(t.dep?'p':'t')+(t.cond?' c':'')+(t.crit?' k':'');
B.push('<g class="task" data-id="'+esc(t.id)+'"><rect x="0" y="'+r.y+'" width="'+W+'" height="'+ROW+'" fill="transparent"/>');
B.push('<text class="tl" x="12" y="'+(r.y+ROW/2+4)+'"><tspan class="tid">'+esc(t.id)+'</tspan><tspan dx="8">'+esc(clip(t.name,LEFT-24-50,12))+'</tspan></text>');
B.push('<rect class="'+cls+'" x="'+x0+'" y="'+(r.y+5)+'" width="'+w+'" height="'+(ROW-10)+'" rx="4"/>');
if(t.status==='active')B.push('<circle class="act" cx="'+(x0+8)+'" cy="'+(r.y+ROW/2)+'" r="3.5"/>');
var dl=fmt(parse(t.start))+'–'+fmt(parse(t.end));
if(x1+8+strW(dl,11)>W-6)B.push('<text class="dt" x="'+(x0-6)+'" y="'+(r.y+ROW/2+4)+'" text-anchor="end">'+dl+'</text>');
else B.push('<text class="dt" x="'+(x1+6)+'" y="'+(r.y+ROW/2+4)+'">'+dl+'</text>');
B.push('</g>');});
gates.forEach(function(g,i){var gx=X(g._d),gy=80;
B.push('<g class="task" data-id="'+esc(g.id)+'"><path class="gd'+(g.crit?' k':'')+'" d="M'+(gx-8)+' '+gy+' L'+gx+' '+(gy-8)+' L'+(gx+8)+' '+gy+' L'+gx+' '+(gy+8)+'Z"/>');
var nx=gates[i+1],avail=(nx?X(nx._d):W)-gx-20;
if(gx+16+strW(g.name,12)>W-4){B.push('<text class="gt" x="'+Math.min(gx+8,W-6)+'" y="'+(gy+22)+'" text-anchor="end">'+esc(g.name)+'</text>');}
else{B.push('<text class="gt" x="'+(gx+14)+'" y="'+(gy+4)+'">'+esc(g.name)+'</text>');
var nt=(g.note||'').split(' · ')[0];
if(nt)B.push('<text class="gn" x="'+(gx+14)+'" y="'+(gy+20)+'">'+esc(clip(nt,avail,11))+'</text>');}
B.push('</g>');});
var td=cfg.today?parse(cfg.today):new Date();td=new Date(td.getFullYear(),td.getMonth(),td.getDate());
var tdd=dayOf(td);
if(tdd>=0&&tdd<=total){var tx=X(tdd);B.push('<line class="today" x1="'+tx+'" x2="'+tx+'" y1="60" y2="'+(H-14)+'"/><text class="todaytxt" x="'+(tx+4)+'" y="108">오늘 '+fmt(td)+'</text>');}
B.push('</svg>');
document.getElementById('host').innerHTML=B.join('');
}

var tip=document.getElementById('tip'),host=document.getElementById('host');
var ST={todo:'예정',active:'진행 중',done:'완료'};
function tipHtml(id){var t=byId[id];if(!t)return '';var s=parse(t.start),e=parse(t.end);
var h='<b>'+esc(t.id)+' '+esc(t.name)+'</b><br>'+fmtW(s)+(t.type==='gate'?'':' → '+fmtW(e)+' ('+(dayOf(e)-dayOf(s))+'일)')+' · W'+(Math.floor(dayOf(s)/7)+1);
var m=[];if(t.depends.length)m.push('선행 '+t.depends.join(', '));m.push('분기 '+t.branch);m.push('담당 '+(t.owner||'미정'));if(t.type!=='gate')m.push('상태 '+ST[t.status]);
h+='<br>'+esc(m.join(' · '));
if(t.req.length)h+='<br>요구 '+esc(t.req.join(', '));
if(t.note)h+='<br>'+esc(t.note);
var f=[];if(t.dep)f.push('멘토 답에 달림');if(t.cond)f.push('조건부');if(t.crit)f.push('임계 경로');
if(f.length)h+='<br><i>'+esc(f.join(' · '))+'</i>';return h;}
host.addEventListener('mousemove',function(e){var g=e.target.closest?e.target.closest('[data-id]'):null;
if(!g){tip.style.display='none';return;}
tip.innerHTML=tipHtml(g.getAttribute('data-id'));tip.style.display='block';
var x=e.clientX+14,y=e.clientY+14;if(x+390>window.innerWidth)x=e.clientX-390;if(y+tip.offsetHeight>window.innerHeight)y=e.clientY-tip.offsetHeight-8;
tip.style.left=Math.max(x,4)+'px';tip.style.top=Math.max(y,4)+'px';});
host.addEventListener('mouseleave',function(){tip.style.display='none';});

document.getElementById('ttl').textContent=cfg.title;
document.getElementById('sub').textContent=cfg.subtitle||'';
var assumed=(cfg.deadline_status||'').indexOf('가정')>=0;
document.getElementById('ban').innerHTML=(assumed?'<b>날짜는 가정입니다.</b> ':'')+'시작 '+fmtW(start)+' · 마감 '+fmtW(end)+' ('+esc(cfg.deadline_status||'')+'). 막대 위치는 남은 기간 대비 비율에서 환산했습니다. '+esc(cfg.owner_note||'');
document.getElementById('doneN').textContent='('+DATA.done.length+'건, 타임라인 밖)';
document.getElementById('done').innerHTML=DATA.done.map(function(d){var s=parse(d.start);
return '<div class="card"><b>✓</b>'+esc(d.name)+'<div class="meta">'+esc(d.lane_name)+' · '+fmt(s)+(d.req.length?' · '+esc(d.req.join(', ')):'')+(d.note?' · '+esc(d.note):'')+'</div></div>';}).join('');
var rowsT=gates.concat(tasks);
document.getElementById('table').innerHTML='<table><thead><tr><th>ID</th><th>레인</th><th>작업</th><th>시작</th><th>끝</th><th>주</th><th>선행</th><th>분기</th><th>담당</th><th>요구</th><th>상태</th></tr></thead><tbody>'+
rowsT.map(function(t){var s=parse(t.start),e=parse(t.end);
return '<tr><td class="id">'+esc(t.id)+'</td><td>'+esc(t.lane_name)+'</td><td>'+esc(t.name)+'</td><td>'+fmtW(s)+'</td><td>'+(t.type==='gate'?'—':fmtW(e))+'</td><td>W'+(Math.floor(dayOf(s)/7)+1)+'</td><td>'+esc(t.depends.join(', ')||'—')+'</td><td>'+esc(t.branch)+'</td><td>'+esc(t.owner||'미정')+'</td><td>'+esc(t.req.join(', ')||'—')+'</td><td>'+(t.type==='gate'?'게이트':ST[t.status])+'</td></tr>';}).join('')+'</tbody></table>';
document.getElementById('foot').textContent='생성: '+DATA.generated+' · 원본: tasks.csv, gantt.config.json · 다시 만들기: python3 make_gantt.py';
Array.prototype.forEach.call(document.querySelectorAll('.seg button'),function(b){b.addEventListener('click',function(){
if(b.hasAttribute('data-br'))state.branch=b.getAttribute('data-br');
if(b.hasAttribute('data-view'))state.view=b.getAttribute('data-view');
Array.prototype.forEach.call(b.parentNode.querySelectorAll('button'),function(x){x.classList.toggle('on',x===b);});render();});});
var segV=document.getElementById('segV'),lblV=document.getElementById('lblV');
if(!STARTER.length){segV.style.display='none';lblV.style.display='none';}
else{document.getElementById('bvS').textContent='시작용 '+STARTER.length+'개';document.getElementById('bvA').textContent='전체 '+tasks.length+'개';}
document.getElementById('cCond').addEventListener('change',function(e){state.cond=e.target.checked;render();});
document.getElementById('cDeps').addEventListener('change',function(e){state.deps=e.target.checked;render();});
document.getElementById('bPrint').addEventListener('click',function(){window.print();});
render();
})();
</script>
</body>
</html>
'''


def main(argv) -> int:
    check_only = "--check" in argv
    cfg, rows = load()
    out, errors, warnings, span = resolve(cfg, rows)
    srows, serrors = starter_rows(cfg, out) if span else ([], [])
    errors = errors + serrors
    for w in warnings:
        print("경고:", w)
    for e in errors:
        print("오류:", e)
    if errors or span is None:
        print(f"검사 실패: 오류 {len(errors)}건")
        return 1
    start, end, total = span
    todo = [r for r in out if r["status"] != "done" and r["type"] == "task"]
    gates = [r for r in out if r["type"] == "gate"]
    done = [r for r in out if r["status"] == "done"]
    print(f"검사 통과: 작업 {len(todo)} · 게이트 {len(gates)} · 완료 {len(done)} · 시작용 {len(srows)} · 경고 {len(warnings)} "
          f"· 기간 {start}~{end} ({total}일)")
    if check_only:
        return 0
    write_csv(cfg, out, start)
    write_md(cfg, out, start, end, total, warnings)
    write_html(cfg, out, start, total)
    made = [OUT_HTML, OUT_MD, OUT_CSV]
    if srows:
        table = starter_table(cfg, out, srows)
        write_starter_md(cfg, table, out, start, end, total)
        write_starter_csv(table)
        made += [OUT_STARTER_MD, OUT_STARTER_CSV]
    print("만든 파일:", ", ".join(p.name for p in made))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
