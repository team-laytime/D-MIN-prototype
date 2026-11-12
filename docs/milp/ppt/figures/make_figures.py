"""그림 4장 — SVG를 만들고 Chrome(headless)으로 PNG까지 뽑는다.

    python3 docs/milp/ppt/figures/make_figures.py

    formula-map   PPT 장 → 계산식 P1~P23 → 솔버 입력(Ω·F·C·q) → 본체 식 (1)~(8)
    infra-flow    수리계획법이 Spring Boot · Python 서비스 · DB · S3와 주고받는 것
    sample-gantt  샘플 주간: 현행 계획 vs 1안 (대형 부두)
    ppt-pages     PPT 13장 한눈 보기 (장마다 어느 식으로 갔는지)
"""
from __future__ import annotations

import html
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONT = "Pretendard,'Apple SD Gothic Neo','Noto Sans KR','Malgun Gothic',sans-serif"
INK, SUB, MUTED, LINE, BG, CARD = "#0E1726", "#344054", "#667085", "#E2E7EE", "#F6F8FB", "#FFFFFF"
BLUE, TEAL, PURPLE, ORANGE, RED, AMBER = "#1B5FD9", "#0B8B7B", "#5B4BC4", "#D9620B", "#C8102E", "#B26A00"
TINT = {BLUE: "#EAF1FE", TEAL: "#E3F4F1", PURPLE: "#EFEDFB", ORANGE: "#FDEEE3", RED: "#FCE8EB", AMBER: "#FFF4DF", MUTED: "#EEF2F7"}


def esc(s):
    return html.escape(str(s), quote=True)


def tw(s, size):
    """글자 폭 어림 (Pretendard): 한글 1.0em, 그 밖 0.56em"""
    w = 0.0
    for ch in str(s):
        w += size * (0.98 if ord(ch) > 0x2E80 else (0.33 if ch in " .,:;·|()[]'" else 0.58))
    return w


class Svg:
    def __init__(self, w, h, title, desc=""):
        self.w, self.h = w, h
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">',
                      f"<title>{esc(title)}</title><desc>{esc(desc)}</desc>",
                      '<defs>' + "".join(
                          f'<marker id="m{n}" viewBox="0 0 10 10" refX="8.2" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">'
                          f'<path d="M1 1.2 L9 5 L1 8.8 Z" fill="{c}"/></marker>' for n, c in (("k", INK), ("g", MUTED), ("o", ORANGE), ("b", BLUE), ("t", TEAL), ("p", PURPLE))) + "</defs>",
                      f'<rect x="0" y="0" width="{w}" height="{h}" rx="14" fill="{BG}"/>']

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=12, weight=400, fill=INK, anchor="start", family=FONT):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(s)}</text>')

    def rect(self, x, y, w, h, fill=CARD, stroke=LINE, rx=10, sw=1, dash=None, opacity=None):
        extra = (f' stroke-dasharray="{dash}"' if dash else "") + (f' opacity="{opacity}"' if opacity is not None else "")
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{extra}/>')

    def card(self, x, y, w, h, fill=CARD, stroke=LINE):
        self.rect(x, y + 1.5, w, h, fill="#101828", stroke="none", opacity=0.06)
        self.rect(x, y, w, h, fill, stroke)

    def pill(self, x, y, s, color, size=11, weight=600, pad=9, h=21):
        w = tw(s, size) + pad * 2
        self.rect(x, y, w, h, fill=TINT.get(color, "#EEF2F7"), stroke="none", rx=h / 2)
        self.text(x + pad, y + h / 2 + size * 0.36, s, size, weight, color)
        return w

    def num(self, cx, cy, n, fill=INK, r=11):
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"/>')
        self.text(cx, cy + 4.2, n, 12, 700, "#FFFFFF", "middle")

    def line(self, pts, color=INK, width=1.6, marker="k", dash=None):
        d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        mk = f' marker-end="url(#m{marker})"' if marker else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"{extra}{mk}/>')

    def save(self, name):
        self.parts.append("</svg>")
        svg = "\n".join(self.parts)
        p = HERE / f"{name}.svg"
        p.write_text(svg, encoding="utf-8")
        render(p, self.w, self.h)
        return p


def render(svg_path, w, h, scale=2):
    page = svg_path.with_suffix(".render.html")
    page.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:{BG}}}</style></head>'
                    f'<body>{svg_path.read_text(encoding="utf-8")}</body></html>', encoding="utf-8")
    png = svg_path.with_suffix(".png")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--force-device-scale-factor={scale}",
                    f"--window-size={w},{h}", f"--screenshot={png}", page.as_uri()], check=True, capture_output=True)
    page.unlink()


# ----------------------------------------------------------------------------- 1. 식 연결도
def formula_map():
    W, H = 1520, 1100
    s = Svg(W, H, "PPT 계산식이 수리계획법에 들어가는 길", "멘토링 PPT 06~12쪽의 규칙을 계산식 P1~P23으로 옮기고, 그 값이 팀 최종본 본체 식 (1)~(8)의 입력 Ω·F·C·q가 된다. 본체 식은 바꾸지 않는다.")
    s.text(28, 40, "PPT 계산식이 수리계획법에 들어가는 길", 20, 700)
    s.text(28, 63, "PPT 06~12쪽 규칙은 모두 '솔버에 넣기 전의 값'이 된다 · 팀 최종본 본체 식 (1)~(8)은 한 글자도 바꾸지 않는다", 13, 400, MUTED)
    s.pill(W - 196, 24, "본체 식 변경 0줄", TEAL, 12, 700, 12, 26)
    cols = [(24, 300, "① 멘토링 PPT", "무엇을 정했나", MUTED), (372, 404, "② 계산식 P1~P23", "PPT를 식으로 (pptcalc · planner)", BLUE),
            (824, 300, "③ 솔버 입력", "풀기 전에 정해지는 숫자", PURPLE), (1172, 324, "④ 본체 식 (1)~(8)", "팀 최종본 그대로 (solver.py)", TEAL)]
    for x, w, t, sub, c in cols:
        s.text(x + 2, 104, t, 15, 700, c)
        s.text(x + 2, 123, sub, 11.5, 400, MUTED)
    for (x1, w1, *_), (x2, *_) in zip(cols, cols[1:]):
        s.line([(x1 + w1 + 8, 112), (x2 - 10, 112)], MUTED, 2.2, "g")

    ppt = [("06쪽", "ETB = 조건별 접안 가능 시각의 교집합", "FIX 선박은 자동 산출에서 제외"),
           ("07쪽", "이전 선박 ETU + Switching / ETA + Direction", "Shifting 표 · FIX 앞에 못 끼면 접안불가"),
           ("08쪽", "야간 도선 → 다가오는 08시", "동일 화물 그룹 · 동시 접안 ETU − 2h · 부두 제약"),
           ("09쪽", "작업시작 +1h · 이안 +2h · 호스분리 +30분", "ETANR · 정박개시 (Daylight 미적용)"),
           ("10쪽", "정박개시 (Daylight 적용: 07시 · 일출·일몰)", "정박종료 = 정박개시 + LayTime (원유·CFR False → ÷2)"),
           ("11쪽", "Demurrage = 호스분리 − 정박종료", "− 기상체선 시간 ÷ 2 · 체선료 = × Rate ÷ 24"),
           ("12쪽", "선박·부두 제원, 접안 가능 제품, 일출·일몰", "기상 → 부두 제약 설정 · 조석 고려 안 함 · 탱크 재고")]
    y = 140
    for page, a, b in ppt:
        s.card(24, y, 300, 104)
        s.pill(38, y + 14, page, INK if page != "12쪽" else AMBER, 11.5, 700)
        s.text(40, y + 58, a, 12, 600, SUB)
        s.text(40, y + 80, b, 11.2, 400, MUTED)
        y += 116

    groups = [("부두 고르기", ["P1   배정 가능 부두 = 제품 그룹 ∧ 제원 5종 (Draft는 수입선만)"], "12쪽"),
              ("접안 시각 ETB", ["P2   부두가 비어 있을 때: ETA + Direction",
                                "P3   앞 배 뒤: 그 배 이안(ETU) + Switching",
                                "P4   야간 도선 금지 구간 → 다가오는 08시",
                                "P5   부두 제약(기상·공사) → 종료 + Direction",
                                "P6   동일 화물 그룹 · 부두 동시 접안 → 상대 ETU − 2h",
                                "P7   ETB = 금지 구간 밖 가장 이른 시각 (모든 제약 AND)",
                                "P8   FIX 보호: 앞 배 이안 + Switching < FIX ETB"], "06·07·08쪽"),
              ("작업 시각", ["P9   작업시작 = ETB + 1h",
                            "P10  작업완료 = 작업시작 + 물량 ÷ 평균 Rate",
                            "P11  호스분리 = 작업완료 + 30분",
                            "P12  이안 ETU = 작업완료 + 2h"], "09쪽"),
              ("계약 시간", ["P13  ETANR = NVL(NOR Tender, ETA)",
                            "P14  정박개시 (미적용): Early Loading · Miss · From 06시 · +6h",
                            "P15  정박개시 (Daylight): From 07시 · 일출~일몰 · 07시",
                            "P16  정박종료 = 정박개시 + LayTime (원유 · CFR False → ½)"], "09·10쪽"),
              ("체선료", ["P17  공제 = 기상체선 시간 × ½",
                          "P18  체선시간 = max(0, 호스분리 − 정박종료 − 공제)",
                          "P19  체선료 = 체선시간 × Rate ÷ 24"], "11쪽"),
              ("작업계획 만들기", ["P20  Ω: PPT 식이 낼 수 있는 접안 시각 (큰 문제는 30분 눈금)",
                                  "P21  F: 같은 부두 · 동일 화물 그룹 · 동시 접안 · FIX",
                                  "P22  q · D: 하역 +, 선적 −, 공정 소비",
                                  "P23  고른 조합을 PPT 식으로 다시 계산 · 위반 검사"], "06쪽 '재확인'")]
    y = 140
    for name, lines, src in groups:
        h = 44 + len(lines) * 21 + 8
        s.card(372, y, 404, h)
        s.text(388, y + 26, name, 13.5, 700, BLUE)
        s.pill(776 - 16 - tw(src, 10.5) - 16, y + 11, src, MUTED, 10.5, 600, 8, 20)
        for n, ln in enumerate(lines):
            s.text(388, y + 50 + n * 21, ln, 11.4, 500, SUB)
        y += h + 12

    inputs = [("Ω[i]  작업계획 집합", ["입항 건 × 부두 × 접안 시각", "각 계획에 s·a·c·h·u (P9~P12)"], "P1~P8 · P20", 98),
              ("C[i,k]  체선료", ["작업계획 하나의 금액 (센트 정수)", "근거: P13~P19 숫자 대입 그대로"], "P9~P19", 98),
              ("F  충돌 쌍", ["같이 고를 수 없는 두 계획", "큰 문제는 '겹치는 묶음' 한 줄로"], "P3 · P6 · P8 · P21", 98),
              ("q[i,k,t] · D[t] · R⁰ · R_min · R_max", ["원유 탱크 1,000만 배럴 · 공정 처리", "하역 시작~완료를 구간에 나눔"], "P22 · 12쪽", 98),
              ("k_fix[i]  FIX · 작업 중", ["입력값 그대로 고정", "앞에 못 끼는 계획은 Ω에서 뺌"], "P8 · 06쪽", 98)]
    y = 140
    for name, lines, src, h in inputs:
        s.card(824, y, 300, h)
        s.text(840, y + 26, name, 12.6, 700, PURPLE)
        for n, ln in enumerate(lines):
            s.text(840, y + 50 + n * 20, ln, 11.2, 400, SUB)
        s.text(1108, y + 26, src, 10.5, 600, MUTED, "end")
        y += h + 14

    s.card(1172, 140, 324, 600)
    body = [("(1)", "min  Σ_i Σ_k  C[i,k] · z[i,k]", "총 예상 체선료 (모든 입항 건)"),
            ("(2)", "Σ_k z[i,k] = 1", "입항 건마다 작업계획 하나"),
            ("(3)", "z[i,k] + z[j,l] ≤ 1   ∀ F", "충돌하는 계획은 같이 못 고름"),
            ("(4)", "R[t+1] = R[t] + ΣΣ q·z − D[t]", "시간대별 원유 재고 수지"),
            ("(5)", "R[0] = R⁰", "처음 재고"),
            ("(6)", "R_min ≤ R[t] ≤ R_max", "최소 허용 재고 · 저장용량"),
            ("(7)", "z ∈ {0,1}", "고르거나 안 고르거나"),
            ("(8)", "z[i, k_fix] = 1", "FIX 입항 건")]
    yy = 172
    for tag, f, k in body:
        s.text(1190, yy, tag, 12.5, 700, TEAL)
        s.text(1226, yy, f, 13, 600, INK, family="'SF Mono',Menlo,monospace,"+FONT)
        s.text(1226, yy + 19, k, 11, 400, MUTED)
        yy += 58
    s.add(f'<line x1="1188" y1="{yy - 22}" x2="1480" y2="{yy - 22}" stroke="{LINE}"/>')
    s.text(1190, yy + 6, "(+)", 12.5, 700, ORANGE)
    s.text(1226, yy + 6, "다음 후보안: 방금 고른 조합 금지", 12, 600, INK)
    s.text(1226, yy + 25, "FR-42 · 2안·3안을 낼 때만 더한다", 11, 400, MUTED)

    s.card(1172, 760, 324, 236, fill="#FFFFFF")
    s.text(1190, 788, "풀고 나서 (식 밖, 순서만)", 13, 700, INK)
    steps = ["1차 총 체선료 최소 → 2차 일찍 대는 쪽", "고른 조합을 PPT 식으로 다시 계산 (P23)",
             "규칙 위반 다시 검사 → 하나라도 있으면 멈춤", "근거 = 입항 건마다 P7~P19 숫자 대입", "LLM은 숫자를 만들지 않는다 (NFR-01)"]
    for n, t in enumerate(steps):
        s.num(1200, 816 + n * 34, str(n + 1), TEAL, 10)
        s.text(1220, 820.5 + n * 34, t, 11.8, 500, SUB)

    s.rect(24, 1050 - 6, 1124, 30, fill="#FFFFFF", stroke=LINE, rx=15)
    s.text(40, 1064 - 1, "읽는 법: 왼쪽에서 오른쪽으로. PPT 한 장의 규칙은 ②의 식 몇 개가 되고, 그 식이 낸 숫자가 ③으로 모여 ④의 기호 자리에 들어간다.", 11.5, 500, SUB)
    return s.save("formula-map")


# ----------------------------------------------------------------------------- 2. 인프라 흐름
def infra_flow():
    W, H = 1520, 1020
    s = Svg(W, H, "수리계획법이 인프라와 주고받는 것", "Spring Boot가 입력을 모아 요청 JSON을 만들고 Python 계산 서비스에 보낸다. Python 서비스의 LangGraph 그래프가 검증, 수리계획법, 근거, 보고서 초안 순서로 돌고 결과 JSON을 DB에 남긴다. 사람이 후보를 고르면 Spring이 결정을 기록한다.")
    s.text(28, 40, "수리계획법이 우리 인프라와 주고받는 것", 20, 700)
    s.text(28, 63, "Spring Boot ↔ Python 계산 서비스(LangGraph + 수리계획법) · REST(JSON) + SSE · EKS · PostgreSQL · S3 — 요청 한 건은 번호 순서로 흐른다", 13, 400, MUTED)
    s.pill(W - 170, 24, "제안 · 팀 확인 전", AMBER, 12, 600, 12, 26)

    # 입력 원천
    s.text(28, 112, "입력이 오는 곳", 14, 700, SUB)
    src = [("SEAGATE · 업무 입력", "입항 건 · ETA · NOR · 상태 · FIX"), ("계약 (C/P)", "LayCan · LayTime · Rate · CFR"),
           ("부두 기준정보", "제원 · 제품 그룹 · Shifting 표 · 규칙 버전"), ("부두 제약 설정", "기상 악화(전 부두) · 공사(부두별)"),
           ("공공데이터", "울산 일출·일몰 (매일 배치)"), ("탱크 · 공정", "원유 재고 · 처리량 · 생산량"), ("과거 Shipment", "평균 Rate · 호스분리 Term (배치)")]
    y = 126
    for t, d in src:
        s.card(24, y, 262, 62)
        s.text(40, y + 25, t, 12.6, 700, INK)
        s.text(40, y + 45, d, 11, 400, MUTED)
        s.line([(288, y + 31), (322, y + 31)], MUTED, 1.3, "g", "4 3")
        y += 72

    # EKS 영역
    s.rect(330, 100, 1166, 640, fill="#FFFFFF", stroke=LINE, rx=16)
    s.pill(1496 - 18 - tw("제공받은 EKS · 팀 namespace (ADR-016)", 11.5) - 22, 112, "제공받은 EKS · 팀 namespace (ADR-016)", MUTED, 11.5, 600, 11, 24)
    s.rect(350, 146, 360, 574, fill="#EFEDFB", stroke="none", rx=14)
    s.text(366, 172, "Spring Boot API (Java)", 15, 700, PURPLE)
    s.text(366, 192, "로그인 · 권한 · 업무 데이터 · 결정 기록", 11.5, 400, SUB)
    sp = [("입력 모으기", "부두·입항 건·계약·제약·재고 → 요청 하나", "rules 버전 + 입력 지문(hash) 저장"),
          ("임시 조건 · 제약 켜고 끄기", "FR-26 '이 배는 #3 금지' · FR-28", "→ restrictions · rule_patch로 보냄"),
          ("결과 보여 주기", "1·2·3안 비교표 · 부두별 간트 · 근거", "근거는 trace(P7~P19) 그대로"),
          ("사람의 결정", "선택 · 취소 · 현업 반영 완료 (FR-47·48)", "SEAGATE에 자동 반영하지 않는다")]
    y = 210
    for t, a, b in sp:
        s.card(366, y, 328, 108)
        s.text(382, y + 28, t, 13, 700, INK)
        s.text(382, y + 54, a, 11.5, 500, SUB)
        s.text(382, y + 76, b, 11, 400, MUTED)
        y += 122

    s.rect(850, 146, 630, 574, fill="#E3F4F1", stroke="none", rx=14)
    s.text(866, 172, "Python 계산 서비스 (FastAPI · 밖에 열지 않음)", 15, 700, TEAL)
    s.text(866, 192, "LangGraph 그래프 = 순서가 고정된 노드 · 수리계획법은 정해진 한 단계", 11.5, 400, SUB)
    s.pill(1464 - tw("같은 입력 → 같은 답 (NFR-02)", 10.5) - 16, 158, "같은 입력 → 같은 답 (NFR-02)", TEAL, 10.5, 600, 8, 20)
    nodes = [("입력 검증", "필수값 · 단위 · 시각 · 부두 이름", "멈춤 → 422 + 빠진 항목"),
             ("수리계획법  run.optimize()", "P20~P22 작업계획 생성 → HiGHS 본체 식 (1)~(8)", "→ P23 PPT 식으로 재계산 · 위반 검사 · 1·2·3안"),
             ("산출 근거", "입항 건마다 P7~P19 숫자 대입 (explain)", "기준안 대비 바뀐 것 · 바뀐 이유"),
             ("보고서 초안 (LLM)", "문장만 쓴다 · 숫자는 응답 JSON에서 복사", "금액 계산에 LLM 0건 (NFR-01)")]
    y = 210
    for n, (t, a, b) in enumerate(nodes):
        hl = n == 1
        s.card(866, y, 598, 108, fill="#FFFFFF", stroke=TEAL if hl else LINE)
        s.text(884, y + 28, t, 13.5 if hl else 13, 700, TEAL if hl else INK)
        s.text(884, y + 54, a, 11.8 if hl else 11.5, 600 if hl else 500, SUB)
        s.text(884, y + 76, b, 11.2, 400, MUTED)
        if n < 3:
            s.line([(1165, y + 108), (1165, y + 120)], TEAL, 1.6, "t")
        y += 122

    # 화살표 1~4
    s.line([(286 + 36, 450), (350, 450)], INK, 1.8, "k")
    s.num(334, 432, "1", INK)
    mx = 780
    s.line([(710, 250), (850, 250)], INK, 1.8, "k")
    s.num(mx, 232, "2", INK)
    s.text(mx, 270, "POST", 10, 700, INK, "middle", family="'SF Mono',Menlo,monospace")
    s.text(mx, 284, "/v1/optimizations", 9.6, 600, INK, "middle", family="'SF Mono',Menlo,monospace")
    s.text(mx, 298, "→ 202 + 작업 ID", 10, 500, SUB, "middle")
    s.line([(850, 360), (710, 360)], BLUE, 1.6, "b", "5 3")
    s.num(mx, 342, "3", BLUE)
    s.text(mx, 380, "SSE 진행 상황", 10.5, 600, BLUE, "middle")
    s.text(mx, 395, "/events", 9.6, 600, BLUE, "middle", family="'SF Mono',Menlo,monospace")
    s.line([(850, 520), (710, 520)], INK, 1.8, "k")
    s.num(mx, 502, "4", INK)
    s.text(mx, 540, "응답 JSON", 10.5, 600, INK, "middle")
    s.text(mx, 555, "/result", 9.6, 600, INK, "middle", family="'SF Mono',Menlo,monospace")

    # 아래: 저장소 · 배치
    s.card(350, 770, 530, 120)
    s.text(368, 798, "PostgreSQL (외부 DB, 스키마를 나눔)", 13.5, 700, INK)
    s.pill(368, 812, "app", PURPLE, 11, 700)
    s.text(410, 827, "입력 스냅샷 · 입력 지문 · 결정 · 감사 기록", 11.5, 500, SUB)
    s.pill(368, 846, "agent", TEAL, 11, 700)
    s.text(422, 861, "작업 상태 · 응답 JSON · 실행 시간 · 모델 크기", 11.5, 500, SUB)
    s.card(900, 770, 290, 120)
    s.text(918, 798, "CronJob · 매일 09:00 KST", 13.5, 700, INK)
    s.text(918, 822, "같은 이미지 · 다음 7일을 다시 풀어", 11.5, 500, SUB)
    s.text(918, 842, "아침 보고서용 응답 JSON 저장", 11.5, 500, SUB)
    s.text(918, 866, "확정 · 발송은 하지 않는다", 11, 400, MUTED)
    s.card(1210, 770, 286, 120)
    s.text(1228, 798, "S3 · reports/<날짜>/", 13.5, 700, INK)
    s.text(1228, 822, "검증된 응답 JSON · 보고서", 11.5, 500, SUB)
    s.text(1228, 842, "배치 서비스 계정만 쓰기 권한", 11.5, 500, SUB)
    s.text(1228, 866, "Pod Identity (ADR-016)", 11, 400, MUTED)
    s.line([(560, 720), (560, 770)], INK, 1.6, "k")
    s.num(578, 745, "5", INK)
    s.line([(1165, 720), (1165, 770)], MUTED, 1.4, "g", "4 3")
    s.line([(1190, 830), (1210, 830)], MUTED, 1.4, "g", "4 3")

    s.card(24, 910, 1472, 92)
    s.text(42, 936, "요청 한 건 따라가기", 13.5, 700, INK)
    steps = [("1", "스케줄러가 기간을 정하고 '후보 계산'을 누른다 → Spring이 입력을 모아 요청 JSON 하나로 만든다"),
             ("2", "Spring이 Python 서비스에 POST → 202 + 작업 ID. 계산은 1~2분 (샘플 54건 97초)"),
             ("3", "진행 상황은 SSE: 입력 검증 → 작업계획 n개 → 풀이 1/3 → 재계산 · 검사 → 근거"),
             ("4", "응답 JSON: 1·2·3안 · 기준안 · 현행 계획 · 입항 건마다 근거 · 모델 크기 · 버전"),
             ("5", "결과는 DB(agent)에, 사람이 고른 안은 DB(app)에 결정으로 남는다")]
    for n, (k, t) in enumerate(steps):
        col, row = n % 3, n // 3
        x, y = 42 + col * 486, 962 + row * 26
        s.num(x + 9, y - 4, k, INK, 9)
        s.text(x + 24, y + 0.5, t, 11.2, 500, SUB)
    return s.save("infra-flow")


# ----------------------------------------------------------------------------- 3. 샘플 간트
def sample_gantt():
    resp = json.loads((ROOT / "out" / "SAMPLE-W46.response.json").read_text(encoding="utf-8"))
    cur, c1 = resp["current_plan"], resp["candidates"][0]
    berths = ["#3", "#5-5", "#6", "#7", "#8", "BUOY2", "BUOY3"]
    t0, t1 = datetime(2026, 11, 9), datetime(2026, 11, 18)
    W = 1520
    LX, RX = 120, W - 40
    span = (t1 - t0).total_seconds()

    def X(iso):
        d = datetime.fromisoformat(iso)
        return LX + max(0.0, min(1.0, (d - t0).total_seconds() / span)) * (RX - LX)

    def lanes(plans):
        """같은 부두에서 겹치는 배는 줄을 나눈다"""
        out = {}
        for b in berths:
            rows = []
            for p in sorted([p for p in plans if p["berth"] == b], key=lambda p: p["etb"]):
                for r, last in enumerate(rows):
                    if p["etb"] >= last:
                        rows[r] = p["etu"]
                        out[p["arrival_id"]] = (b, r)
                        break
                else:
                    rows.append(p["etu"])
                    out[p["arrival_id"]] = (b, len(rows) - 1)
        return out

    panels = [("현행 계획 — 샘플 '접안계획 예시'의 부두·ETB를 PPT 식으로 계산", cur, RED),
              ("1안 — 수리계획법 (본체 식 (1)~(8) · PPT 식으로 재계산)", c1, TEAL)]
    lane_h, gap = 30, 10
    heights = []
    for _, sched, _ in panels:
        ln = lanes(sched["plans"])
        n = sum(max([r for (b, r) in ln.values() if b == bb] + [0]) + 1 for bb in berths)
        heights.append(n * lane_h + (len(berths) - 1) * gap + 70)
    H = 92 + sum(heights) + 156
    s = Svg(W, H, "샘플 주간 현행 계획 vs 1안", "샘플 엑셀의 접안계획 예시를 PPT 식으로 계산한 현행 계획과 수리계획법 1안을 대형 부두 7곳에서 비교한다.")
    s.text(28, 40, "샘플 주간 (11/09~11/17) — 현행 계획 vs 1안, 대형 부두 7곳", 20, 700)
    s.text(28, 63, f"막대 = 접안(ETB) ~ 이안(ETU) · 색 = 그 배의 예상 체선료 · 빨간 테두리 = PPT 규칙과 맞지 않는 배 · 전체 54건 합계: 현행 ${cur['total_usd']:,.0f} → 기준안 ${resp['baseline']['total_usd']:,.0f} → 1안 ${c1['total_usd']:,.0f}", 12.5, 400, MUTED)
    bad_ids = set()
    for v in cur["violations"]:
        head = v.split(":")[0]
        for part in head.split("·"):
            bad_ids.add(part.strip())

    def color(usd):
        if usd <= 0:
            return "#C9D3E0", INK
        if usd < 5000:
            return "#F6C79E", INK
        if usd < 20000:
            return "#EE9450", "#FFFFFF"
        return "#C8501A", "#FFFFFF"

    y = 92
    for (title, sched, accent), ph in zip(panels, heights):
        s.card(24, y, W - 48, ph - 10)
        s.text(42, y + 28, title, 14, 700, accent)
        tot = sum(p["demurrage_usd"] for p in sched["plans"] if p["berth"] in berths)
        s.text(W - 44, y + 28, f"이 7개 부두 합계 ${tot:,.0f}" + (f" · 규칙 위반 {len(sched['violations'])}건 (54건 전체)" if sched["violations"] else " · 규칙 위반 0건"), 12.5, 700, accent, "end")
        top = y + 52
        d = t0
        while d <= t1:
            x = X(d.isoformat())
            s.add(f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{y + ph - 22}" stroke="#E7ECF2" stroke-width="1"/>')
            if d < t1:
                s.text(x + 4, top - 10, d.strftime("%m/%d"), 10.5, 600, MUTED)
            d = d.replace(day=d.day + 1) if d.day < 30 else d
            if d.day == t1.day and d == t1:
                x = X(d.isoformat())
                s.add(f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{y + ph - 22}" stroke="#E7ECF2" stroke-width="1"/>')
                break
        ln = lanes(sched["plans"])
        yy = top
        for b in berths:
            n = max([r for (bb, r) in ln.values() if bb == b] + [0]) + 1
            s.rect(LX - 4, yy - 2, RX - LX + 8, n * lane_h + 4, fill="#F8FAFC", stroke="none", rx=6)
            s.text(LX - 14, yy + n * lane_h / 2 + 4, b, 12.5, 700, SUB, "end")
            for p in sched["plans"]:
                if p["berth"] != b:
                    continue
                r = ln[p["arrival_id"]][1]
                x0, x1 = X(p["etb"]), X(p["etu"])
                if x1 <= LX:
                    continue
                fill, ink = color(p["demurrage_usd"])
                by = yy + r * lane_h + 3
                bad = sched is cur and p["arrival_id"] in bad_ids
                s.rect(x0, by, max(3, x1 - x0), lane_h - 6, fill=fill, stroke=RED if bad else "none", rx=5, sw=2 if bad else 0)
                label = p["arrival_id"] + (f" ${p['demurrage_usd'] / 1000:,.1f}k" if p["demurrage_usd"] > 0 else "")
                if tw(label, 10.5) + 8 < x1 - x0:
                    s.text(x0 + 6, by + (lane_h - 6) / 2 + 3.8, label, 10.5, 700, ink)
                elif tw(p["arrival_id"], 10.5) + 6 < x1 - x0:
                    s.text(x0 + 4, by + (lane_h - 6) / 2 + 3.8, p["arrival_id"], 10.5, 700, ink)
            yy += n * lane_h + gap
        y += ph

    # 범례 · 해설
    s.card(24, y + 6, W - 48, 136)
    lx = 42
    for t, (f, _) in (("체선료 0", color(0)), ("5천 달러 미만", color(1)), ("5천~2만", color(6000)), ("2만 이상", color(30000))):
        s.rect(lx, y + 22, 22, 14, fill=f, stroke="none", rx=4)
        s.text(lx + 30, y + 34, t, 11.5, 500, SUB)
        lx += tw(t, 11.5) + 66
    s.rect(lx, y + 22, 22, 14, fill="#FFFFFF", stroke=RED, rx=4, sw=2)
    s.text(lx + 30, y + 34, "현행 계획에서 PPT 규칙과 맞지 않는 배 (같은 부두 겹침 · 야간 도선 등)", 11.5, 500, SUB)
    notes = ["1안이 한 일: S57(LR1 DSL)을 #7에서 #8로 옮기고 S54(R-G, #7만 가능)를 11/15 18:30 → 11/14 08:30으로 앞당겼다 (−$54,196)",
             "그 대신 S53(JET)은 #8에서 S57 뒤로 50시간 기다린다 (+$30,390). S41은 #5-5 대신 #6에 바로 댄다 (−$5,479) → 기준안 대비 합계 −$29,284",
             "현행 계획은 같은 부두 충돌이 10쌍이다: 시간이 실제로 겹치는 곳 4쌍(예: #7 S51·S52) + 앞 배 이안 뒤 Switching 시간을 못 채운 곳 6쌍. 한 부두에 한 척씩이라는 PPT 07쪽 규칙으로는 실행할 수 없는 일정 — 두 척을 대는 부두인지 확인 필요"]
    for n, t in enumerate(notes):
        s.text(42, y + 66 + n * 22, t, 11.6, 500 if n < 2 else 400, SUB if n < 2 else MUTED)
    return s.save("sample-gantt")


# ----------------------------------------------------------------------------- 4. PPT 13장 한눈 보기
def ppt_pages():
    used = {0: ("표지", "—"), 1: ("배경 · 문제점", "목적: 체선료 ↓ · 숙련자 의존 ↓"), 2: ("사용자 · 활용 자원", "입력 데이터 목록"),
            3: ("PoC ①② 범위", "목적함수 (1) · 후보 1·2·3안"), 4: ("의사결정 보조 ③", "후보 비교 · 남은 리스크 · 보고서"),
            5: ("기대효과", "같은 기준으로 빠르게 비교"), 6: ("ETB 교집합 · FIX 제외", "P7 · P8 · 식 (8)"),
            7: ("① 이전 선박 · Shifting 표", "P2 · P3 · P8 · F"), 8: ("② 야간 도선 ③ 동시 접안·부두 제약", "P4 · P5 · P6 · F"),
            9: ("작업 시각 · 정박개시(미적용)", "P9~P14"), 10: ("정박개시(Daylight) · 정박종료", "P15 · P16"),
            11: ("체선료 · 사용시간 그림", "P17~P19 → C[i,k]"), 12: ("개발에 필요한 데이터", "입력 · 탱크 → 식 (4)~(6)")}
    names = ["ppt-p00-cover.png"] + [f"ppt-p{n:02d}.png" for n in range(1, 13)]
    cells = []
    for n, nm in enumerate(names):
        t, f = used[n]
        cells.append(f'<figure><img src="../slides/{nm}"><figcaption><b>{"표지" if n == 0 else f"{n:02d}쪽"}</b> {esc(t)}<span>{esc(f)}</span></figcaption></figure>')
    W, H = 1520, 1005
    page = HERE / "ppt-pages.render.html"
    page.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:{BG};font-family:{FONT};color:{INK}}}
.wrap{{padding:26px 28px}} h1{{font-size:20px;margin:0 0 4px}} p{{margin:0 0 18px;color:{MUTED};font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
figure{{margin:0;background:#fff;border:1px solid {LINE};border-radius:10px;overflow:hidden;box-shadow:0 1.5px 0 rgba(16,24,40,.06)}}
img{{width:100%;display:block;border-bottom:1px solid {LINE}}}
figcaption{{padding:8px 11px 10px;font-size:12.5px;line-height:1.45}} figcaption b{{color:{BLUE};margin-right:4px}}
figcaption span{{display:block;color:{TEAL};font-weight:600;font-size:12px}}
</style></head><body><div class="wrap"><h1>멘토링 PPT 13장 — 장마다 어느 식으로 갔나</h1>
<p>원본: SKALA_Mentoring_전무룡Manager.pptx (11-10 받음) · 장마다 캡처는 docs/milp/ppt/slides/ · 초록 글씨 = 이 장이 들어간 계산식·본체 식</p>
<div class="grid">{''.join(cells)}</div></div></body></html>""", encoding="utf-8")
    png = HERE / "ppt-pages.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2", f"--window-size={W},{H}",
                    f"--screenshot={png}", page.as_uri()], check=True, capture_output=True)
    page.unlink()
    return png


if __name__ == "__main__":
    which = sys.argv[1:] or ["formula-map", "infra-flow", "sample-gantt", "ppt-pages"]
    for name in which:
        p = {"formula-map": formula_map, "infra-flow": infra_flow, "sample-gantt": sample_gantt, "ppt-pages": ppt_pages}[name]()
        print(p)
