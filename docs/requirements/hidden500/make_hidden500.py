"""숨은 비기능 요구 250 + 페인 포인트 기반 화면 특징 250 생성기.

원본: items_*.txt (한 줄 = 항목 하나)
만드는 것:
  ../15-hidden-nfr-ux-500.md   글 문서 (분류별 표)
  hidden500.csv                UTF-8 BOM, 엑셀·구글 시트용
  fig-1-map.svg                500개 한 장 지도
  fig-2-pain.svg               페인 포인트별 항목 수
실행:
  python3 docs/requirements/hidden500/make_hidden500.py          # 생성 + 검사
  python3 docs/requirements/hidden500/make_hidden500.py --png    # + fig-*.svg → PNG (Chrome 헤드리스)
"""
import csv
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from svgkit import (AMBER, BG, CARD, INK, INK2, INK3, INK4, LINE, Svg, tw)  # noqa: E402

HERE = Path(__file__).parent
DOC = HERE.parent / "15-hidden-nfr-ux-500.md"
CSV = HERE / "hidden500.csv"

PRI = {"M": "Must", "S": "Should", "C": "Could"}

PAINS = {
    "P01": ("따질 조건이 많다", "과제 원문 1절"),
    "P02": ("순서를 바꾸면 하나하나 셈한다", "과제 원문 1절"),
    "P03": ("판단 이유가 남지 않는다", "과제 원문 1절 · 멘토링(숙련자 감에 의존)"),
    "P04": ("큰 비용과 분쟁으로 이어진다", "과제 원문 1절 · 멘토링(9월 약 180억 원)"),
    "P05": ("도착 일시·예보가 바뀐다", "과제 원문 6절"),
    "P06": ("역할마다 하는 일이 다르다", "과제 원문 2절"),
    "P07": ("계약마다 규칙이 다르다", "과제 원문 6절"),
    "P08": ("같은 데이터를 다시 옮겨 적는다", "추정 · 사내 연동은 범위 밖(원문 6절)"),
    "P09": ("문서에서 값을 읽어야 한다", "요구사항서 11/10 (C/P·NOR 필수)"),
    "P10": ("계산·AI 결과를 그대로 믿기 어렵다", "과제 원문 FAQ(의사결정 보조)"),
    "P11": ("시연·운영이 끊기면 안 된다", "평가 안내(최종평가 ②)"),
    "P12": ("여럿이 짧은 기간에 바꾼다", "팀 6명 · 10/30~12/17"),
}

# 11/20 중간점검 전에 먼저 볼 20개 (비기능 10 + 화면 10)
PICKS = [
    "HN-001", "HN-002", "HN-021", "HN-022", "HN-042", "HN-071", "HN-091", "HN-093", "HN-121", "HN-176",
    "UX-016", "UX-036", "UX-053", "UX-081", "UX-102", "UX-161", "UX-162", "UX-191", "UX-206", "UX-221",
]

PICK_SHORT = {
    "HN-001": ("모든 결과·보고서·메일에 기준 시각", "오전 숫자가 오후에도 그대로 나간다 (원문 6절)"),
    "HN-002": ("입력이 바뀌면 '입력 바뀜' 표시", "화면 숫자가 낡은 줄 모른다"),
    "HN-021": ("문서 시각은 원문 표기 + KST 변환값", "NOR·SOF에 LT와 UTC가 섞인다 (도메인 함정 9)"),
    "HN-022": ("시간대 없는 시각은 '확인 필요'로 막기", "9시간 오차 = 하루 3만 달러 배에서 1만 달러 넘게"),
    "HN-042": ("총액 옆에 ETA ±6h 범위", "지불 부서는 '크게 날 가능성'을 본다 (원문 2절)"),
    "HN-071": ("후보마다 확정 계획 대비 바뀐 배 수", "바뀐 배 수 = 다시 연락할 곳 수 [추정]"),
    "HN-091": ("역할별 계정으로 로그인", "세 역할이 있는데 NFR 22개에 로그인·권한이 없다"),
    "HN-093": ("확정 기록에 계정 ID", "FR-54 기록 항목에 '누가'가 없다"),
    "HN-121": ("확정 기록·당시 버전은 보존 기간 동안 삭제 불가", "다툼은 몇 주~몇 달 뒤에 온다 (도메인 함정 8)"),
    "HN-176": ("사람이 정한 순서 하나는 1초 안에 평가", "'이 변경이 돈으로 얼마인가'를 그 자리에서 (원문 1절)"),
    "UX-016": ("SEAGATE·엑셀 표를 붙여넣으면 열 자동 맞춤", "연동이 범위 밖이라 사람이 옮겨 적는다"),
    "UX-036": ("원문 옆에서 추출값 확인", "미확인 값이 하나라도 있으면 계산이 막힌다 (FR-06)"),
    "UX-053": ("강풍·공사 제한을 빗금 띠로", "기상은 '부두 제약 시간'으로 넣는다 (멘토링 12쪽)"),
    "UX-081": ("배를 끌면 1초 안에 금액 차이", "순서를 바꾸면 하나하나 셈한다 (원문 1절)"),
    "UX-102": ("'바뀐 배만' 비교가 기본", "후보 3개 × 배 12척을 머리로 대조하지 않게"),
    "UX-161": ("확정 창에 근거 문장을 미리 채움", "왜 그 순서인지 남지 않는다 (원문 1절)"),
    "UX-162": ("확정 이유는 태그로 고르기", "빈칸 서술은 한 단어로 채워지기 쉽다 [추정]"),
    "UX-191": ("작업 지시자: 확정본 할 일 목록", "계획과 주의점을 보고 준비한다 (원문 2절)"),
    "UX-206": ("지불 부서: 예상 체선료 큰 순 목록", "크게 날 가능성을 점검한다 (원문 2절)"),
    "UX-221": ("입력이 바뀌면 '결과 낡음' 띠", "낡은 숫자를 보내는 실수를 막는다"),
}

EXPECT = {"N": 250, "U": 250}


def parse():
    cats = []          # (code, name, part)
    items = []         # dict
    seen = set()
    errors = []
    for f in sorted(HERE.glob("items_*.txt")):
        cur = None
        for ln, raw in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                code, name = line[1:].split(" ", 1)
                cur = (code, name.strip())
                cats.append((code, name.strip(), code[0]))
                continue
            parts = [p.strip() for p in line.split("|")]
            where = f"{f.name}:{ln}"
            if cur is None:
                errors.append(f"{where} 분류 없이 항목이 나옴")
                continue
            if len(parts) != 6:
                errors.append(f"{where} 칸 수 {len(parts)} (6이어야 함)")
                continue
            text, why, check, pri, pain, rel = parts
            if pri not in PRI:
                errors.append(f"{where} 우선순위 '{pri}'")
            if pain not in PAINS:
                errors.append(f"{where} 페인 코드 '{pain}'")
            key = re.sub(r"\s+", "", text)
            if key in seen:
                errors.append(f"{where} 같은 문장이 이미 있음: {text}")
            seen.add(key)
            for label, val in (("요구사항", text), ("이유", why), ("수용기준", check)):
                if not val:
                    errors.append(f"{where} {label} 비어 있음")
            items.append(dict(cat=cur[0], cat_name=cur[1], part=cur[0][0], text=text, why=why,
                              check=check, pri=pri, pain=pain, rel=rel))
    # ID 붙이기
    n = {"N": 0, "U": 0}
    for it in items:
        n[it["part"]] += 1
        it["id"] = f"{'HN' if it['part'] == 'N' else 'UX'}-{n[it['part']]:03d}"
    for part, want in EXPECT.items():
        if n[part] != want:
            errors.append(f"{part} 부분 항목 수 {n[part]} (기대 {want})")
    ids = {it["id"] for it in items}
    for p in PICKS:
        if p not in ids:
            errors.append(f"먼저 볼 항목 {p} 없음")
    return cats, items, errors


def md_cell(s):
    return s.replace("|", "/").replace("\n", " ")


def write_doc(cats, items):
    by_cat = defaultdict(list)
    for it in items:
        by_cat[it["cat"]].append(it)
    pc = Counter((it["part"], it["pri"]) for it in items)
    pain_cnt = Counter((it["pain"], it["part"]) for it in items)
    guess = sum("[추정]" in it["why"] for it in items)
    byid = {it["id"]: it for it in items}

    L = []
    a = L.append
    a("# 숨은 비기능 요구 250 + 페인 포인트 기반 화면 특징 250")
    a("")
    a("- 작성: 2026-11-11 · 상태: **제안 (팀 확인 전)**")
    a("- 기준: 팀 요구사항서 **실시간 탭 3절** (FR-01~60 · NFR-01~22). 여기 항목은 그 목록에 없거나, 있어도 약하게 적힌 것이다. '관련' 칸이 기존 번호를 가리킨다")
    a("- 원본은 `hidden500/items_*.txt` 한 곳이다 (한 줄 = 항목 하나). `hidden500/make_hidden500.py`가 이 문서, `hidden500/hidden500.csv`, 그림 1~3을 만들고, `hidden500/make_mockups.py`가 화면 목업 4~6을 만든다(그림 0은 앞 답변의 스케줄러 목업을 옮긴 것). 이 문서를 직접 고치지 말고 원본을 고친 뒤 다시 만든다")
    a(f"- 표기: 이유 칸의 괄호는 근거 문서, **[추정]** 은 현업 확인 전 추정이다 ({guess}개). 현업 확인을 거친 항목은 아직 없다")
    a("")
    a("## 한눈에")
    a("")
    a("| 구분 | 개수 | Must | Should | Could |")
    a("|---|---:|---:|---:|---:|")
    for part, name in (("N", "숨은 비기능 요구 (HN)"), ("U", "화면 특징 (UX)")):
        a(f"| {name} | {sum(1 for it in items if it['part'] == part)} | {pc[(part, 'M')]} | {pc[(part, 'S')]} | {pc[(part, 'C')]} |")
    a(f"| 합계 | {len(items)} | {pc[('N','M')] + pc[('U','M')]} | {pc[('N','S')] + pc[('U','S')]} | {pc[('N','C')] + pc[('U','C')]} |")
    a("")
    a("그림 (같은 폴더 `hidden500/`)")
    a("")
    a("- `fig-1-map.png` — 500개 한 장 지도. 칸 하나가 항목 하나, 진한 색이 Must, 흰 점이 '먼저 볼 20개'")
    a("- `fig-2-pain.png` — 페인 포인트 12개에서 각각 몇 개가 나왔나")
    a("- `fig-3-picks.png` — 먼저 볼 20개 (짧은 제목과 이유)")
    a("- `fig-0-ui-scheduler.png` · `fig-4-ui-instructor.png` · `fig-5-ui-payment.png` · `fig-6-ui-input.png` — 스케줄러 비교 · 작업 지시자 · 지불 부서 · 입력과 문서 확인 화면 목업. 4~6의 번호 설명에 UX ID가 붙어 있다")
    a("")
    a("## 왜 '숨어' 있었나")
    a("")
    a("지금 NFR 22개는 대부분 **계산 한 번**이 맞는지(결정성 · 재현성 · 추적성 · 시각·금액 처리)를 지킨다. 숨은 요구는 계산 한 번의 바깥에서 나온다.")
    a("")
    a("1. 판이 하루에도 바뀐다 — 도착 일시와 예보가 바뀌고(원문 6절), 결과는 금방 낡는다")
    a("2. 세 역할이 같은 판을 본다 — 스케줄러 · 작업 지시자 · 지불 부서가 보는 것과 할 수 있는 일이 다르다(원문 2절)")
    a("3. 숫자가 나중에 돈 다툼의 증거가 된다 — 기록 보존, 해석 차이, 표시 정밀도")
    a("4. 입력이 문서와 다른 시스템에서 온다 — 시간대 · 날짜 순서 · 단위, 다시 옮겨 적기")
    a("5. 시연과 운영이 평가 대상이다 — 최종평가 ②가 클라우드 기반의 안정적인 배포·시연을 본다")
    a("")
    a("## 먼저 볼 20개 (11/20 중간점검 전 추천)")
    a("")
    a("비용이 작고, 빠지면 데모나 질문에서 바로 드러나는 것부터 골랐다.")
    a("")
    a("| ID | 항목 | 이유 | 우선 |")
    a("|---|---|---|---|")
    for p in PICKS:
        it = byid[p]
        a(f"| {p} | {md_cell(it['text'])} | {md_cell(it['why'])} | {PRI[it['pri']]} |")
    a("")
    a("## 페인 포인트 12개")
    a("")
    a("| 코드 | 페인 포인트 | 근거 | 비기능 | 화면 | 합 |")
    a("|---|---|---|---:|---:|---:|")
    for code, (label, src) in PAINS.items():
        hn, ux = pain_cnt[(code, "N")], pain_cnt[(code, "U")]
        a(f"| {code} | {label} | {src} | {hn} | {ux} | {hn + ux} |")
    a("")
    a("## 분류")
    a("")
    a("| 코드 | 분류 | 개수 | ID | Must |")
    a("|---|---|---:|---|---:|")
    for code, name, part in cats:
        its = by_cat[code]
        a(f"| {code} | {name} | {len(its)} | {its[0]['id']}~{its[-1]['id'][-3:]} | {sum(i['pri'] == 'M' for i in its)} |")
    a("")
    for part, title, col in (("N", "A. 숨은 비기능 요구 250", ("요구사항", "수용기준")),
                             ("U", "B. 페인 포인트 기반 화면 특징 250", ("화면 특징", "확인 방법"))):
        a(f"## {title}")
        a("")
        for code, name, p in cats:
            if p != part:
                continue
            its = by_cat[code]
            a(f"### {code} {name} ({len(its)}) — {its[0]['id']}~{its[-1]['id'][-3:]}")
            a("")
            a(f"| ID | {col[0]} | 이유 | {col[1]} | 우선 | 페인 | 관련 |")
            a("|---|---|---|---|---|---|---|")
            for it in its:
                a(f"| {it['id']} | {md_cell(it['text'])} | {md_cell(it['why'])} | {md_cell(it['check'])} | "
                  f"{PRI[it['pri']]} | {it['pain']} | {md_cell(it['rel'])} |")
            a("")
    a("## 이 목록을 쓰는 법")
    a("")
    a("- **요구사항서에 옮길 때**: `hidden500/hidden500.csv`를 구글 시트나 엑셀로 열어 '먼저 볼 것'과 Must만 거른 뒤 옮긴다. 요구사항서 번호(NFR-23~)는 팀이 붙인다")
    a("- **화면 기획에 쓸 때**: UX 항목은 화면 단위(U02 입력 · U04 타임라인 · U06 비교 · U12 작업 지시자 · U13 지불 부서 …)로 묶여 있다. 목업 그림의 번호가 UX ID를 가리킨다")
    a("- **고칠 때**: `items_*.txt`의 줄을 고치거나 더하고 `python3 docs/requirements/hidden500/make_hidden500.py --png`를 다시 돌린다. 생성기가 칸 수 · 우선순위 · 페인 코드 · 같은 문장을 검사한다")
    a("- **확인할 것**: [추정] 항목은 멘토에게 '실제로 이렇게 일하나요?'를 물어 지우거나 고친다. 특히 판이 하루에 몇 번 바뀌는지, 작업 지시자와 지불 부서가 화면을 직접 쓰는지, 확정 기록을 얼마나 보관하는지")
    a("")
    DOC.write_text("\n".join(L), encoding="utf-8")


def write_csv(items):
    with CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ID", "구분", "분류 코드", "분류", "요구사항·화면 특징", "이유", "수용기준·확인 방법",
                    "우선순위", "페인 코드", "페인 포인트", "관련", "먼저 볼 것"])
        for it in items:
            w.writerow([it["id"], "비기능" if it["part"] == "N" else "화면 특징", it["cat"], it["cat_name"],
                        it["text"], it["why"], it["check"], PRI[it["pri"]], it["pain"], PAINS[it["pain"]][0],
                        it["rel"], "Y" if it["id"] in PICKS else ""])


RAMP = {
    "N": {"M": "#1F4FBF", "S": "#7398E6", "C": "#CAD7F3"},
    "U": {"M": "#0B7A6E", "S": "#4FB5A6", "C": "#C0E6DF"},
}


def fig_map(cats, items):
    by_cat = defaultdict(list)
    for it in items:
        by_cat[it["cat"]].append(it)
    W = 680
    ROW = 17
    nN = sum(1 for c in cats if c[2] == "N")
    nU = sum(1 for c in cats if c[2] == "U")
    y0 = 92
    cardA_h = 48 + nN * ROW + 10
    cardB_h = 48 + nU * ROW + 10
    H = int(y0 + cardA_h + 14 + cardB_h + 46)
    s = Svg(W, H, "숨은 비기능 요구 250개와 화면 특징 250개의 한 장 지도",
            "분류 31개마다 항목을 칸 하나로 그렸다. 진한 색이 Must, 중간이 Should, 옅은 색이 Could이고 흰 점은 먼저 볼 20개다.")
    s.header("500개 한 장 지도", "칸 하나 = 항목 하나 · 진한 칸부터 Must · Should · Could · 흰 점 = 먼저 볼 20개")
    # 범례
    lx = 24
    for part, lab in (("N", "숨은 비기능"), ("U", "화면 특징")):
        for p in "MSC":
            s.rect(lx, 70, 10, 10, fill=RAMP[part][p], rx=2)
            lx += 13
        s.text(lx + 2, 79, lab, 11, 500, INK2)
        lx += tw(lab, 11) + 18
    s.circle(lx + 5, 75, 2.6, "#FFFFFF", INK3, 1)
    s.text(lx + 13, 79, "먼저 볼 20개", 11, 500, INK2)

    y = y0
    for part, title in (("N", "숨은 비기능 요구 250 · HN-001~250"), ("U", "페인 포인트 기반 화면 특징 250 · UX-001~250")):
        rows = [c for c in cats if c[2] == part]
        ch = 48 + len(rows) * ROW + 10
        s.card(16, y, W - 32, ch)
        its_all = [it for it in items if it["part"] == part]
        cnt = Counter(it["pri"] for it in its_all)
        s.text(32, y + 24, title, 13, 700)
        summ = f"Must {cnt['M']} · Should {cnt['S']} · Could {cnt['C']}"
        s.text(W - 32, y + 24, summ, 11.5, 600, INK3, "end")
        s.line(32, y + 36, W - 32, y + 36, "#EEF1F5")
        ry = y + 48
        for code, name, _ in rows:
            its = by_cat[code]
            s.text(32, ry + 9.5, code, 11, 600, INK4)
            s.text(64, ry + 9.5, name, 12, 500, INK)
            s.text(262, ry + 9.5, str(len(its)), 11.5, 700, INK2, "end")
            order = sorted(its, key=lambda i: ("MSC".index(i["pri"]), i["id"] not in PICKS, i["id"]))
            cx = 272
            for it in order:
                s.rect(cx, ry, 9.4, 9.4, fill=RAMP[part][it["pri"]], rx=2)
                if it["id"] in PICKS:
                    s.circle(cx + 4.7, ry + 4.7, 2.2, "#FFFFFF")
                cx += 11.6
            ry += ROW
        y += ch + 14
    s.text(24, H - 20, "칸은 분류 안에서 우선순위 순서로 놓았다. 항목 문장은 15-hidden-nfr-ux-500.md와 hidden500.csv에 있다", 11, 400, INK3)
    (HERE / "fig-1-map.svg").write_text(s.render(), encoding="utf-8")


def fig_pain(items):
    cnt = Counter((it["pain"], it["part"]) for it in items)
    rows = sorted(PAINS, key=lambda p: -(cnt[(p, "N")] + cnt[(p, "U")]))
    W = 680
    RH = 40
    top = 100
    H = top + len(rows) * RH + 50
    s = Svg(W, H, "페인 포인트별 항목 수", "페인 포인트 12개마다 숨은 비기능 요구와 화면 특징이 몇 개씩 나왔는지 막대로 보인다.")
    s.header("어떤 페인에서 몇 개가 나왔나", "막대 = 그 페인 때문에 생긴 항목 수 · 파랑 = 숨은 비기능 · 청록 = 화면 특징")
    mx = max(cnt[(p, "N")] + cnt[(p, "U")] for p in rows)
    BX, BW = 300, 230
    s.card(16, 72, W - 32, H - 72 - 34)
    s.rect(BX, 84, 10, 10, fill=RAMP["N"]["M"], rx=2)
    s.text(BX + 15, 93, "숨은 비기능", 11, 500, INK2)
    s.rect(BX + 92, 84, 10, 10, fill=RAMP["U"]["M"], rx=2)
    s.text(BX + 107, 93, "화면 특징", 11, 500, INK2)
    y = top
    for i, p in enumerate(rows):
        label, src = PAINS[p]
        hn, ux = cnt[(p, "N")], cnt[(p, "U")]
        if i:
            s.line(32, y - 4, W - 32, y - 4, "#F0F2F5")
        pw = s.pill(32, y + 3, p, 10.5, INK3, "#EEF1F5", h=17, padx=5, weight=600)
        s.text(32 + pw + 7, y + 15.5, label, 12.5, 700)
        s.text(32, y + 32, src, 11, 400, INK3)
        w1 = BW * hn / mx
        w2 = BW * ux / mx
        s.rect(BX, y + 6, w1, 14, fill=RAMP["N"]["M"], rx=3)
        s.rect(BX + w1 + (1 if hn else 0), y + 6, w2, 14, fill=RAMP["U"]["M"], rx=3)
        end = BX + w1 + w2 + 8
        s.text(end, y + 17.5, str(hn + ux), 13, 700, INK)
        s.text(end + tw(str(hn + ux), 13) + 6, y + 17.5, f"비기능 {hn} · 화면 {ux}", 11, 400, INK3)
        y += RH
    s.text(24, H - 14, "근거 문서가 같은 페인도 항목은 겹치지 않게 하나의 페인에만 셌다", 11, 400, INK3)
    (HERE / "fig-2-pain.svg").write_text(s.render(), encoding="utf-8")


def fig_picks(items):
    byid = {it["id"]: it for it in items}
    W, RH = 680, 40
    top = 72
    nN = sum(1 for p in PICKS if p.startswith("HN"))
    nU = len(PICKS) - nN
    H = top + (46 + nN * RH + 8) + 14 + (46 + nU * RH + 8) + 40
    s = Svg(W, H, "먼저 볼 20개", "중간점검 전에 요구사항서에 먼저 넣을 숨은 비기능 요구 10개와 화면 특징 10개를 짧은 제목과 이유로 보인다.")
    s.header("먼저 볼 20개", "11/20 중간점검 전 추천 · 넣기 쉽고, 빠지면 데모나 질문에서 바로 드러나는 것")
    y = top
    for part, title in (("HN", "숨은 비기능 요구 10"), ("UX", "화면 특징 10")):
        ids = [p for p in PICKS if p.startswith(part)]
        ch = 46 + len(ids) * RH + 8
        s.card(16, y, W - 32, ch)
        col = RAMP["N" if part == "HN" else "U"]
        s.rect(32, y + 15, 10, 10, fill=col["M"], rx=2)
        s.text(48, y + 24, title, 13, 700)
        s.line(32, y + 36, W - 32, y + 36, "#EEF1F5")
        ry = y + 46
        for i, p in enumerate(ids):
            it = byid[p]
            head, why = PICK_SHORT[p]
            if i:
                s.line(32, ry - 4, W - 32, ry - 4, "#F3F4F7")
            pw = s.pill(32, ry + 1, p, 10.5, "#FFFFFF", col["M"], h=17, padx=6, weight=700)
            s.text(32 + pw + 8, ry + 14, head, 12.5, 700)
            s.text(32 + pw + 8, ry + 30, why, 11, 400, INK3)
            tag = PRI[it["pri"]]
            tw_ = tw(tag, 10.5) + 12
            s.pill(W - 32 - tw_ - 44, ry + 1, tag, 10.5, INK2, "#EEF1F5", h=17, padx=6)
            s.pill(W - 32 - 38, ry + 1, it["pain"], 10.5, INK3, "#FFFFFF", stroke="#E2E7EE", h=17, padx=5)
            ry += RH
        y += ch + 14
    s.text(24, H - 16, "오른쪽 칩 = 우선순위 · 페인 코드. 전체 문장과 수용기준은 15-hidden-nfr-ux-500.md", 11, 400, INK3)
    (HERE / "fig-3-picks.svg").write_text(s.render(), encoding="utf-8")


def render_png():
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    for svg in sorted(HERE.glob("fig-*.svg")):
        body = svg.read_text(encoding="utf-8")
        m = re.search(r'height="(\d+)"', body)
        h = int(m.group(1)) if m else 1000
        html = HERE / f".{svg.stem}.html"
        html.write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#fff}</style>' + body,
                        encoding="utf-8")
        png = svg.with_suffix(".png")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=2", f"--window-size=680,{h}",
                        f"--screenshot={png}", html.as_uri()], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        html.unlink()
        print("png", png.name)


def main():
    cats, items, errors = parse()
    if errors:
        print("문제", len(errors))
        for e in errors:
            print(" -", e)
        sys.exit(1)
    write_doc(cats, items)
    write_csv(items)
    fig_map(cats, items)
    fig_pain(items)
    fig_picks(items)
    pc = Counter((it["part"], it["pri"]) for it in items)
    print(f"항목 {len(items)} · 분류 {len(cats)} · 문제 0")
    for part in "NU":
        print(part, {PRI[p]: pc[(part, p)] for p in "MSC"})
    if "--png" in sys.argv:
        render_png()


if __name__ == "__main__":
    main()
