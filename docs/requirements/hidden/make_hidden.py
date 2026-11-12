#!/usr/bin/env python3
"""items/*.txt → ../15-hidden-requirements.md, hidden-requirements.csv

실행: python3 docs/requirements/hidden/make_hidden.py
내용은 items/ 아래 글 파일에서 고친다. 한 줄 = 항목 하나.
  ## 코드 | 갈래 이름 | 왜 안 보였나(또는 페인 포인트)
  요구 | 이유 | 확인 방법 | 우선·때 | 관련
우선·때: M/S/C(Must·Should·Could) + 1/2/3(지금·시연·도입)
"""
import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_MD = HERE.parent / "15-hidden-requirements.md"
OUT_CSV = HERE / "hidden-requirements.csv"

PRIO = {"M": "Must", "S": "Should", "C": "Could"}
WHEN = {"1": "지금", "2": "시연", "3": "도입"}
FIGS = [
    ("그림 1", "ux/screen-1-compare.png", "접안 계획 비교 (스케줄러의 첫 화면)"),
    ("그림 2", "ux/screen-2-timeline.png", "부두 24곳 · 1주일 타임라인"),
    ("그림 3", "ux/screen-3-evidence.png", "금액을 누르면 열리는 계산 근거"),
    ("그림 4", "ux/screen-4-confirm.png", "확정 창과 이력"),
    ("그림 5", "ux/screen-5-input.png", "불러오기와 추출값 확인"),
    ("그림 6", "ux/screen-6-whatif.png", "바꾸고 바로 다시 보기"),
    ("그림 7", "ux/screen-7-roles.png", "역할마다 다른 첫 화면"),
]


def parse():
    groups, problems = [], []
    for path in sorted((HERE / "items").glob("*.txt")):
        for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            where = f"{path.name}:{no}"
            if line.startswith("## "):
                parts = [p.strip() for p in line[3:].split(" | ")]
                if len(parts) != 3:
                    problems.append(f"{where} 갈래 줄은 칸이 3개여야 한다")
                    continue
                groups.append({"code": parts[0], "name": parts[1], "why": parts[2], "items": []})
                continue
            parts = [p.strip() for p in line.split(" | ")]
            if len(parts) != 5:
                problems.append(f"{where} 칸이 {len(parts)}개다 (5개여야 한다)")
                continue
            req, why, check, code, rel = parts
            if not re.fullmatch(r"[MSC][123]", code):
                problems.append(f"{where} 우선·때 코드가 틀렸다: {code}")
                continue
            groups[-1]["items"].append(
                {"req": req, "why": why, "check": check, "prio": PRIO[code[0]], "when": WHEN[code[1]],
                 "rel": rel, "where": where}
            )
    return groups, problems


def check_refs(item, problems):
    if item["rel"] == "-":
        return
    for ref in item["rel"].split(", "):
        ok = False
        m = re.fullmatch(r"FR-(\d\d)", ref)
        if m and 1 <= int(m.group(1)) <= 60:
            ok = True
        m = re.fullmatch(r"NFR-(\d\d)", ref)
        if m and 1 <= int(m.group(1)) <= 22:
            ok = True
        if re.fullmatch(r"ADR-01[45]", ref) or re.fullmatch(r"그림 [1-7]", ref):
            ok = True
        m = re.fullmatch(r"11:NFR-(\d\d)", ref)
        if m and 13 <= int(m.group(1)) <= 84:
            ok = True
        m = re.fullmatch(r"11:FR-(\d\d)", ref)
        if m and 18 <= int(m.group(1)) <= 95:
            ok = True
        if not ok:
            problems.append(f"{item['where']} 관련 표기를 알 수 없다: {ref}")


def bigrams(s):
    s = re.sub(r"[\s'\"(),.·:~]", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def near_duplicates(items, limit=0.5):
    grams = [bigrams(i["req"]) for i in items]
    pairs = []
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            inter = len(grams[a] & grams[b])
            if not inter:
                continue
            score = inter / len(grams[a] | grams[b])
            if score >= limit:
                pairs.append((score, items[a], items[b]))
    return sorted(pairs, key=lambda p: -p[0])


def rel_text(rel):
    if rel == "-":
        return ""
    out = []
    for ref in rel.split(", "):
        out.append("11번 문서 " + ref[3:] if ref.startswith("11:") else ref)
    return ", ".join(out)


def main():
    groups, problems = parse()
    items = []
    counters = {"N": 0, "U": 0}
    for g in groups:
        kind = g["code"][0]
        g["kind"] = "비기능" if kind == "N" else "UI/UX"
        for it in g["items"]:
            counters[kind] += 1
            it["id"] = f"{kind}-{counters[kind]:03d}"
            it["group"] = g
            check_refs(it, problems)
            items.append(it)
    seen = {}
    for it in items:
        if it["req"] in seen:
            problems.append(f"{it['where']} 같은 요구가 또 있다: {seen[it['req']]}")
        seen[it["req"]] = it["where"]
    if problems:
        print("\n".join(problems))
        sys.exit(1)

    n_total, u_total = counters["N"], counters["U"]
    total = n_total + u_total

    def count(rows, key, value):
        return sum(1 for r in rows if r[key] == value)

    md = []
    md.append(f"# 드러나지 않은 요구 후보 {total}개 — 비기능 {n_total} · UI/UX {u_total}")
    md.append("")
    md.append("- 작성: 2026-11-11 · 상태: **후보 목록 (팀 검토 전)**. 넣을지 말지는 팀이 정한다")
    md.append("- 기준: 팀 구글 문서 '[판교_2반_1조] 프로젝트정의 요구사항서'의 **실시간 탭 3절** (FR-01~60, NFR-01~22, 2026-11-11에 다시 읽음). 비기능(N) 항목은 그 목록에 없는 것만 적었다")
    md.append("- 뽑은 근거: 과제 원문([`official-brief.md`](official-brief.md)), 캔버스, 멘토 샘플 데이터(부두 24곳, 1주일 접안계획 54건), 평가 안내 자료(2026-11-06), 결정 기록 ADR-014 · 015(`demo/docs/adr/README.md`), 기능명세서([`14`](14-functional-spec.md))")
    md.append("- 현업 사용자에게 직접 확인한 것은 아니다. 페인 포인트는 과제 원문 1절과 캔버스 문장에서 가져왔고, U9(입력 부담)는 추정이다")
    md.append("- 표로 옮길 때는 [`hidden/hidden-requirements.csv`](hidden/hidden-requirements.csv)를 쓴다 (엑셀 · 구글 시트용, 한글 안 깨짐)")
    md.append("")
    md.append("## 읽는 법")
    md.append("")
    md.append("- **N-** 은 비기능 요구 후보, **U-** 는 페인 포인트에서 나온 UI/UX 특징이다. 번호는 임시다")
    md.append("- U 항목에는 요구사항서에 이미 있는 기능(FR-44 · 45 · 46 등)을 화면에서 어떻게 보일지로 풀어 쓴 것도 있다. 관련 칸의 FR이 그 기능이다")
    md.append("- 줄 모양: **ID** 요구. — 왜: 이유 · 확인: 확인 방법 `우선순위 · 때 · 관련`")
    md.append("- **때**: `지금` 구현하면서 반영 · `시연` 발표 전까지 갖춤 · `도입` 실제 현업 도입 때 필요 (지금은 설계에서 막지 않거나 발표에서 한계로 밝힌다)")
    md.append("- **관련**의 FR · NFR은 실시간 탭 번호, '11번 문서'는 [`11`](11-requirements-extraction.md)의 옛 후보 번호(겹치는 것), '그림'은 아래 화면 그림 번호다")
    md.append("- 요구사항서에 넣는다면 새 번호를 늘리기보다 관련 칸의 기존 항목 수용기준에 한 줄 덧붙이는 쪽을 권한다. 번호를 이미 한 번 다시 매겼고 유스케이스 · 기능명세서 · WBS가 그 번호를 쓴다")
    md.append("")
    md.append("## 한눈에")
    md.append("")
    md.append("| | 전체 | 지금 | 시연 | 도입 | Must | Should | Could |")
    md.append("|---|---|---|---|---|---|---|---|")
    for label, rows in (("비기능 (N)", [i for i in items if i["id"][0] == "N"]),
                        ("UI/UX (U)", [i for i in items if i["id"][0] == "U"]), ("합계", items)):
        md.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            label, len(rows), count(rows, "when", "지금"), count(rows, "when", "시연"), count(rows, "when", "도입"),
            count(rows, "prio", "Must"), count(rows, "prio", "Should"), count(rows, "prio", "Could")))
    md.append("")
    md.append("| 갈래 | 개수 | 번호 | 왜 안 보였나 · 페인 포인트 |")
    md.append("|---|---|---|---|")
    for g in groups:
        md.append("| {} {} | {} | {} ~ {} | {} |".format(
            g["code"], g["name"], len(g["items"]), g["items"][0]["id"], g["items"][-1]["id"], g["why"]))
    md.append("")
    md.append("## 화면 그림")
    md.append("")
    md.append("U 항목의 관련 칸에 적힌 그림이다. 금액과 시각은 데모 S05 실행(`demo/out/3068fa86f727`)의 계산값이고 가상 데이터다. 원본은 `ux/make_screens.py`.")
    md.append("")
    for no, path, title in FIGS:
        md.append(f"- **{no}** {title} — [`{path}`]({path})")
    md.append("")
    musts = [i for i in items if i["prio"] == "Must"]
    md.append(f"## 먼저 볼 것 — Must {len(musts)}개")
    md.append("")
    for it in musts:
        md.append(f"- **{it['id']}** {it['req']} `{it['when']}`")
    md.append("")
    md.append("---")
    md.append("")
    for g in groups:
        md.append(f"## {g['code']} {g['name']} ({len(g['items'])})")
        md.append("")
        md.append(("페인 포인트와 방향: " if g["kind"] == "UI/UX" else "왜 안 보였나: ") + g["why"])
        md.append("")
        for it in g["items"]:
            tags = " · ".join(x for x in (it["prio"], it["when"], rel_text(it["rel"])) if x)
            md.append(f"- **{it['id']}** {it['req']}. — 왜: {it['why']} · 확인: {it['check']} `{tags}`")
        md.append("")
    md.append("## 다시 만들기")
    md.append("")
    md.append("```bash")
    md.append("python3 docs/requirements/hidden/make_hidden.py")
    md.append("```")
    md.append("")
    md.append("내용은 `hidden/items/*.txt`에서 고친다 (한 줄에 항목 하나). 이 파일과 CSV는 생성물이다.")
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["ID", "구분", "갈래", "요구사항", "우선순위", "수용기준(확인 방법)", "이유", "때", "관련"])
        for it in items:
            g = it["group"]
            w.writerow([it["id"], g["kind"], f"{g['code']} {g['name']}", it["req"], it["prio"], it["check"],
                        it["why"], it["when"], rel_text(it["rel"])])

    print(f"항목 {total}개 (비기능 {n_total}, UI/UX {u_total}), 갈래 {len(groups)}개")
    for g in groups:
        print(f"  {g['code']} {g['name']}: {len(g['items'])}")
    print("때:", {w: count(items, 'when', w) for w in WHEN.values()}, "우선순위:", {p: count(items, 'prio', p) for p in PRIO.values()})
    pairs = near_duplicates(items)
    print(f"비슷한 요구 쌍 {len(pairs)}개 (글자 2개 묶음이 절반 이상 겹침)")
    for score, a, b in pairs[:40]:
        print(f"  {score:.2f} {a['id']} {a['req'][:44]} / {b['id']} {b['req'][:44]}")
    print("→", OUT_MD.relative_to(HERE.parent.parent.parent), "·", OUT_CSV.relative_to(HERE.parent.parent.parent))


if __name__ == "__main__":
    main()
