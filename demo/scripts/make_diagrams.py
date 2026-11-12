"""아키텍처 다이어그램 두 장(SVG)을 만든다 — docs/assets와 화면(web/assets)에 같은 파일을 둔다.

  python scripts/make_diagrams.py

손으로 좌표를 잡은 그림이라, 내용을 바꿀 때는 이 파일의 문구·좌표를 고친 뒤 다시 실행한다.
색: 데이터=청록, 엔진=파랑, 결과=보라, 사람=호박, LLM(선택)=점선 호박. 글꼴은 Pretendard(없으면 시스템 한글 글꼴).
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUTS = [ROOT / "docs" / "assets", ROOT / "src" / "demurrage" / "web" / "assets"]

FONT = "Pretendard, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif"
MONO = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"
INK, INK2, INK3, LINE = "#0E1726", "#344054", "#667085", "#E2E7EE"
BRAND, BRAND2 = "#1B5FD9", "#EAF1FE"
TEAL, TEAL2 = "#0B8B7B", "#E3F5F1"
VIOLET, VIOLET2 = "#5B4BC4", "#EFEDFB"
AMBER, AMBER2 = "#B26A00", "#FFF4DF"
GREEN, GREEN2 = "#127A45", "#E5F5EC"
NAVY = "#0B1F33"


def _w(s: str, size: float) -> float:
    """대략적인 글자 폭(한글 1em, 그 밖 0.56em) — 넘침 검사용."""
    return sum(size * (1.0 if ord(c) > 0x2E80 else 0.56) for c in s)


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.items, self.warn = w, h, [], []
        self.title = title

    def add(self, s):
        self.items.append(s)

    def rect(self, x, y, w, h, fill="#fff", stroke=LINE, r=10, sw=1, dash=None, shadow=False):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        f = ' filter="url(#sh)"' if shadow else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{f}/>')

    def text(self, x, y, s, size=12, weight=400, fill=INK, anchor="start", mono=False, maxw=None, rot=None):
        if maxw and _w(s, size) > maxw:
            self.warn.append(f"넘침: '{s}' ({_w(s, size):.0f} > {maxw})")
        fam = MONO if mono else FONT
        tr = f' transform="rotate({rot} {x} {y})"' if rot else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
                 f'text-anchor="{anchor}"{tr}>{escape(s)}</text>')

    def lines(self, x, y, rows, size=11.5, fill=INK2, lh=None, maxw=None, weight=400):
        lh = lh or size * 1.5
        for i, s in enumerate(rows):
            self.text(x, y + i * lh, s, size=size, fill=fill, maxw=maxw, weight=weight)

    def pill(self, x, y, s, fill, color, size=11, h=22, pad=10, weight=600, mono=False):
        w = _w(s, size) + pad * 2
        self.rect(x, y, w, h, fill=fill, stroke="none", r=h / 2)
        self.text(x + pad, y + h / 2 + size * 0.36, s, size=size, fill=color, weight=weight, mono=mono)
        return w

    def arrow(self, pts, color=INK3, dash=None, sw=1.6, marker="a"):
        d = " ".join(("M" if i == 0 else "L") + f"{x},{y}" for i, (x, y) in enumerate(pts))
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{ds} marker-end="url(#{marker})" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')

    def num(self, cx, cy, n, color=BRAND):
        self.add(f'<circle cx="{cx}" cy="{cy}" r="11" fill="#fff" stroke="{color}" stroke-width="2"/>')
        self.text(cx, cy + 4, str(n), size=11, weight=700, fill=color, anchor="middle")

    def render(self):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-label="{escape(self.title)}">'
                '<defs>'
                '<filter id="sh" x="-5%" y="-5%" width="110%" height="120%"><feDropShadow dx="0" dy="1" stdDeviation="1.4" flood-color="#101828" flood-opacity=".07"/></filter>'
                + "".join(f'<marker id="{k}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                          f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
                          for k, c in (("a", INK3), ("ab", BRAND), ("aa", AMBER), ("at", TEAL), ("av", VIOLET)))
                + '</defs>'
                f'<rect width="{self.w}" height="{self.h}" fill="#F6F8FB"/>')
        return head + "".join(self.items) + "</svg>\n"


# ---------------------------------------------------------------- 프로젝트 아키텍처
def project() -> Svg:
    s = Svg(1280, 820, "프로젝트 아키텍처 — 데이터, 결정론 엔진, 결과, 사람의 결정")
    s.text(40, 46, "프로젝트 아키텍처", size=22, weight=700)
    s.text(40, 70, "울산 CLX 체선료 플래너 (SEAGATE Ship Berthing 개선 컨셉) — 계산은 결정론 엔진, 문장은 선택적 LLM, 확정은 사람", size=13, fill=INK3)
    s.pill(1052, 30, "가상 데이터 · 데모", AMBER2, AMBER)

    cols = [(40, 240, "입력 데이터", "파일로 관리 · 버전 해시", TEAL, TEAL2),
            (320, 330, "결정론 엔진", "숫자를 다루는 단계는 LLM 없음", BRAND, BRAND2),
            (700, 260, "결과", "같은 입력이면 같은 결과(지문)", VIOLET, VIOLET2),
            (1000, 240, "사람의 결정", "확정·반영은 담당자만", AMBER, AMBER2)]
    for x, w, t, sub, c, c2 in cols:
        s.rect(x, 96, w, 30, fill=c2, stroke="none", r=8)
        s.text(x + 12, 116, t, size=13, weight=700, fill=c)
        s.text(x + w - 12, 116, sub, size=10.5, fill=c, anchor="end")

    # 1열 — 데이터
    data = [("시나리오 16 + 검증 4", "data/scenarios", ["선박 · ETA · 상태(계획/FIX/작업 중)", "부두 제한 · 예보 · 재고 · 상황 카드"]),
            ("계약서 23건 (가상)", "data/contracts", ["허용 정박시간 · 체선료율 · NOR 통지", "기상 감면 · 주간 NOR · 조항↔규칙"]),
            ("터미널 기준 정보", "data/master", ["부두 제원 · Shifting 표 · 화물 그룹", "동시 접안 조합 · 야간 도선 · 풍속 한계"]),
            ("규칙 표", "data/rules", ["정박개시 분기 · 계약 유형 배수", "규칙 ID 30개 · 리스크 문구"]),
            ("과거 실적 (가상)", "data/history", ["자재·부두별 작업 Rate", "호스 분리 소요 최빈값"]),
            ("공공 데이터 형식", "data/public", ["일출·일몰(NOAA 식) · 조석 시간창", "예보는 기상청 단기예보 형식"])]
    y = 140
    for t, p, rows in data:
        s.rect(40, y, 240, 82, shadow=True)
        s.add(f'<rect x="40" y="{y}" width="4" height="82" rx="2" fill="{TEAL}"/>')
        s.text(56, y + 22, t, size=13, weight=650, maxw=210)
        s.text(56, y + 38, p, size=10.5, fill=TEAL, mono=True)
        s.lines(56, y + 56, rows, size=11, fill=INK2, lh=16, maxw=216)
        y += 92

    # 2열 — 엔진 7단계
    s.rect(320, 140, 330, 542, shadow=True)
    stages = [("입력 검증", "필수값·형식·시각 순서·참조 · 오류면 계산 전 멈춤"),
              ("제약 정리", "강풍·정비 제한 · 야간 도선 · 조석 · 부두 적합성"),
              ("후보 탐색", "기준안 · 지역 탐색 · 분기한정 최적 증명"),
              ("체선료 계산", "정박개시 → 정박종료 → 체선 시간 · 기상 공제"),
              ("리스크 점검", "날씨·설비·탱크·긴급·안전 + ETA ±6h 민감도"),
              ("보고서 작성", "사실 묶음 → 문장 → 숫자 대조 → md·docx·메일"),
              ("결과 검증", "총액=선박 합 · 위반 0 · 결과 지문")]
    s.add(f'<path d="M346,176 L346,{176 + 6 * 72}" stroke="{BRAND2}" stroke-width="3"/>')
    for i, (t, d) in enumerate(stages):
        cy = 176 + i * 72
        s.num(346, cy, i + 1)
        s.text(368, cy + 5, t, size=13.5, weight=650)
        s.text(368, cy + 24, d, size=11, fill=INK2, maxw=272)
    s.pill(336, 650, "규칙·계약은 코드가 아니라 표에서 읽음", BRAND2, BRAND, size=10.5)

    # 3열 — 결과
    outs = [("접안 계획 비교", ["기준안 + 후보 3개(1척 이상 배정 다름)", "부두별 간트 · 바뀐 선박과 증감"]),
            ("선박별 계산서", ["9단계 식에 숫자를 넣은 줄", "근거: 계약 조항 · 운영 기준 · 실적"]),
            ("리스크 · 민감도", ["후보별 남은 리스크 5종", "입력이 바뀌면 순위가 바뀌는가"]),
            ("보고서 · 메일 초안", ["숫자 대조 422개 불일치 0", ".docx · .md · .csv · 메일(발송 없음)"])]
    y = 140
    for t, rows in outs:
        s.rect(700, y, 260, 96, shadow=True)
        s.add(f'<rect x="700" y="{y}" width="4" height="96" rx="2" fill="{VIOLET}"/>')
        s.text(716, y + 26, t, size=13.5, weight=650)
        s.lines(716, y + 50, rows, size=11, lh=17, maxw=232)
        y += 108
    # LLM(선택)
    s.rect(700, 578, 260, 104, fill="#FFFCF5", stroke=AMBER, dash="5 4", r=10)
    s.text(716, 602, "LLM — 보고서 문장만 (선택)", size=12.5, weight=700, fill=AMBER)
    s.lines(716, 624, ["숫자는 자리표시자 → 엔진 값으로 채움", "비용 상한 $1 · 실패하면 템플릿 문장", "키가 없으면 쓰지 않음(기본)"], size=11, fill=INK2, lh=17, maxw=232)

    # 4열 — 사람
    s.rect(1000, 140, 240, 208, shadow=True)
    s.add(f'<circle cx="1030" cy="174" r="16" fill="{AMBER2}"/>')
    s.text(1030, 179, "김", size=13, weight=700, fill=AMBER, anchor="middle")
    s.text(1056, 170, "선박 스케줄러", size=13.5, weight=650)
    s.text(1056, 187, "해상출하팀(예시)", size=10.5, fill=INK3)
    acts = ["후보를 비교해 하나를 확정", "확정 취소 · 현업 반영 완료 표시", "남은 리스크 확인 체크", "메일은 직접 복사해 발송"]
    for i, a in enumerate(acts):
        s.add(f'<circle cx="1022" cy="{220 + i * 28 - 4}" r="3" fill="{AMBER}"/>')
        s.text(1032, 220 + i * 28, a, size=11.5, fill=INK2, maxw=200)
    s.rect(1000, 362, 240, 96, shadow=True)
    s.text(1016, 388, "결정 기록", size=13.5, weight=650)
    s.lines(1016, 410, ["덧붙이기 전용 — 고치기·지우기 없음", "DB 트리거로 막음(SQLite·PostgreSQL)"], size=11, lh=17, maxw=214)
    s.rect(1000, 470, 240, 96, shadow=True)
    s.text(1016, 496, "감사 기록 · 재현 정보", size=13.5, weight=650)
    s.lines(1016, 518, ["실행·결정·내려받기 이벤트", "시나리오·규칙 해시 + 결과 지문"], size=11, lh=17, maxw=214)
    s.rect(1000, 578, 240, 104, fill=GREEN2, stroke="#BFE5CF", r=10)
    s.text(1016, 602, "시스템이 하지 않는 것", size=12.5, weight=700, fill=GREEN)
    s.lines(1016, 624, ["후보 자동 확정 · 규칙 자동 변경", "메일 자동 발송 · 청구 금액 확정"], size=11, fill="#0E5C34", lh=17, maxw=214)

    # 화살표
    s.arrow([(282, 410), (316, 410)], color=TEAL, marker="at", sw=2)
    s.arrow([(652, 410), (696, 410)], color=BRAND, marker="ab", sw=2)
    s.arrow([(962, 245), (996, 245)], color=VIOLET, marker="av", sw=2)
    s.arrow([(650, 536), (676, 536), (676, 600), (696, 600)], color=AMBER, dash="4 3", marker="aa")
    s.arrow([(1120, 350), (1120, 358)], color=AMBER, marker="aa")

    # 아래 띠
    s.rect(40, 702, 610, 84, fill="#fff", shadow=True)
    s.text(56, 728, "품질 문지기", size=13.5, weight=700)
    x = 56
    for t in ("정답 세트 272칸 100%", "검증 시나리오 4개 = 완전 탐색", "pytest 88개", "CI: verify --strict"):
        x += s.pill(x, 744, t, BRAND2, BRAND, size=11) + 8
    s.rect(670, 702, 570, 84, fill="#fff", shadow=True)
    s.text(686, 728, "실행 환경", size=13.5, weight=700)
    x = 686
    for t in ("FastAPI · Python 3.12", "SQLite / PostgreSQL 16", "Docker Compose", "/healthz · /metrics"):
        x += s.pill(x, 744, t, "#EEF2F7", NAVY, size=11) + 8
    return s


# ---------------------------------------------------------------- 백엔드 아키텍처
def backend() -> Svg:
    s = Svg(1280, 900, "백엔드 아키텍처 — FastAPI, 오케스트레이터, 결정론 엔진, 저장소")
    s.text(40, 46, "백엔드 아키텍처", size=22, weight=700)
    s.text(40, 70, "요청 → API → 오케스트레이터(고정 7단계) → 엔진(순수 함수) → 결과 저장. LLM은 보고서 문장 한 곳에서만, 선택적으로.", size=13, fill=INK3)

    # 1. 클라이언트
    clients = [("웹 화면", "정적 SPA · /static · 프레임워크 없음"), ("CLI", "python -m demurrage run · verify · serve"),
               ("CI", "GitHub Actions · pytest · verify --strict")]
    for i, (t, d) in enumerate(clients):
        x = 40 + i * 410
        s.rect(x, 96, 390, 52, shadow=True)
        s.text(x + 16, 118, t, size=13.5, weight=650)
        s.text(x + 16, 136, d, size=11, fill=INK3, maxw=360)

    # 2. API
    s.rect(40, 170, 1200, 168, fill="#fff", shadow=True)
    s.pill(56, 182, "API · FastAPI", BRAND2, BRAND, size=11.5)
    s.text(176, 198, "api/app.py — 입력 검증(Pydantic)과 연결만, 계산은 하지 않음 · 요청 ID · JSON 로그", size=11.5, fill=INK3)
    groups = [("시나리오 · 계약서", ["GET /api/scenarios", "GET /api/scenarios/{id}", "GET /api/contracts", "GET /api/contracts/{id}"]),
              ("실행", ["POST /api/runs", "GET /api/runs/{id}", "GET …/timeline/{안}.svg", "GET …/vessels/{안}/{선박}"]),
              ("보고서", ["GET …/report.md · .html", "GET …/report.docx", "GET …/schedule.csv", "GET …/mail.txt"]),
              ("사람의 결정", ["POST …/decisions", "GET …/decisions", "확정·취소·반영만", "고치기·지우기 API 없음"]),
              ("감사 · 검증 · 운영", ["GET …/audit", "POST /api/verify", "GET /healthz · /readyz", "GET /metrics"])]
    for i, (t, eps) in enumerate(groups):
        x = 56 + i * 236
        s.rect(x, 214, 224, 112, fill="#F8FAFC", stroke=LINE, r=8)
        s.text(x + 12, 234, t, size=12, weight=700, fill=BRAND if i != 3 else AMBER)
        for k, e in enumerate(eps):
            s.text(x + 12, 254 + k * 17, e, size=10.5, fill=INK2, mono=e.startswith(("GET", "POST")), maxw=204)

    # 3. 오케스트레이터
    s.rect(40, 362, 840, 118, fill="#fff", shadow=True)
    s.pill(56, 374, "오케스트레이터", BRAND2, BRAND, size=11.5)
    s.text(170, 390, "agents/orchestrator.py · roles.py — 순서는 코드가 고정, 단계마다 입력·출력·소요(ms) 기록", size=11.5, fill=INK3)
    st = ["입력 검증", "제약 정리", "후보 탐색", "체선료 계산", "리스크 점검", "보고서 작성", "결과 검증"]
    for i, t in enumerate(st):
        x = 56 + i * 117
        s.rect(x, 412, 104, 50, fill=BRAND2 if i != 5 else "#FFFCF5", stroke=BRAND if i != 5 else AMBER, r=8, dash=None if i != 5 else "4 3")
        s.text(x + 52, 432, f"{i + 1}", size=10.5, weight=700, fill=BRAND if i != 5 else AMBER, anchor="middle")
        s.text(x + 52, 450, t, size=12, weight=650, anchor="middle", fill=INK)
        if i < 6:
            s.arrow([(x + 105, 437), (x + 115, 437)], color=BRAND, marker="ab", sw=1.4)

    # 사람만 하는 동작
    s.rect(900, 362, 340, 118, fill=AMBER2, stroke="#F3DCAE", r=10)
    s.text(916, 388, "사람만 하는 동작", size=13, weight=700, fill=AMBER)
    s.lines(916, 410, ["후보 확정 · 확정 취소 · 현업 반영 완료", "규칙 표 변경 · 메일 발송(시스템에 기능 없음)",
                       "어느 처리 단계의 도구 목록에도 없음"], size=11.5, fill="#6D4300", lh=19, maxw=310)

    # 4. 엔진
    s.rect(40, 504, 840, 196, fill="#fff", shadow=True)
    s.pill(56, 516, "결정론 엔진", BRAND2, BRAND, size=11.5)
    s.text(156, 532, "engine/ — 표준 라이브러리만 · 시각은 분 단위 정수 · 금액은 센트 정수 · 반값은 분수", size=11.5, fill=INK3)
    mods = [("intake", "입력 검증 · 계약서 연결"), ("eligibility", "부두 제원·화물 적합성"), ("worktime", "실적 매칭 → 작업시간"),
            ("etb", "접안 가능시각 밀기 반복"), ("laytime", "정박개시·체선·계산서"), ("schedule", "부두별 순서 → 일정"),
            ("optimizer", "기준안·지역탐색·분기한정"), ("validator", "독립 제약 재검사"), ("risk", "리스크 5종 판정"),
            ("sensitivity", "ETA ±6h · 예보 변경"), ("context", "문맥(부두·실적·일출)"), ("build", "시나리오 → 문맥")]
    for i, (m, d) in enumerate(mods):
        x = 56 + (i % 4) * 204
        y = 552 + (i // 4) * 48
        s.rect(x, y, 194, 40, fill="#F8FAFC", stroke=LINE, r=7)
        s.text(x + 10, y + 17, m + ".py", size=11, weight=600, fill=BRAND, mono=True)
        s.text(x + 10, y + 32, d, size=10.5, fill=INK2, maxw=176)

    # 보고서 · LLM
    s.rect(900, 504, 340, 96, fill="#fff", shadow=True)
    s.pill(916, 516, "보고서", VIOLET2, VIOLET, size=11.5)
    s.lines(916, 556, ["report/views · builder · timeline", "사실 묶음 → 문장 → 숫자 대조(불일치 0)", "→ md · html · docx · csv · 메일 초안"],
            size=11, fill=INK2, lh=16, maxw=310)
    s.rect(900, 614, 340, 86, fill="#FFFCF5", stroke=AMBER, dash="5 4", r=10)
    s.text(916, 638, "llm/adapter.py (선택)", size=12.5, weight=700, fill=AMBER, mono=False)
    s.lines(916, 658, ["Anthropic Messages API · 구조화 출력", "비용 상한 $1 · 키 없으면 Disabled → 템플릿"], size=11, fill=INK2, lh=17, maxw=310)

    # 5. 아래 — 저장소 · 규칙/데이터 · 배포
    s.rect(40, 724, 400, 150, fill="#fff", shadow=True)
    s.pill(56, 736, "저장소", GREEN2, GREEN, size=11.5)
    s.text(120, 752, "store/db.py · SQLAlchemy Core", size=11.5, fill=INK3)
    tables = [("runs", "실행 결과 JSON · 지문"), ("decisions", "덧붙이기 전용 트리거"), ("audit_events", "덧붙이기 전용 트리거"), ("llm_calls", "토큰 · 비용 기록")]
    for i, (t, d) in enumerate(tables):
        x = 56 + (i % 2) * 188
        y = 770 + (i // 2) * 46
        s.rect(x, y, 178, 38, fill="#F8FAFC", stroke=LINE, r=7)
        s.text(x + 10, y + 16, t, size=11, weight=600, fill=GREEN, mono=True)
        s.text(x + 10, y + 31, d, size=10.5, fill=INK2, maxw=160)

    s.rect(460, 724, 420, 150, fill="#fff", shadow=True)
    s.pill(476, 736, "규칙 · 데이터 (읽기 전용)", TEAL2, TEAL, size=11.5)
    s.lines(476, 784, ["rules/loader.py — 규칙 표 해시 · '만약' 패치", "rules/contracts.py — 계약서 → 계산 조건 + 조항 표기",
                       "data/ master · rules · contracts · scenarios", "      golden · history · public"], size=11, fill=INK2, lh=19, maxw=392)

    s.rect(900, 724, 340, 150, fill="#fff", shadow=True)
    s.pill(916, 736, "배포 · 운영", "#EEF2F7", NAVY, size=11.5)
    s.lines(916, 784, ["Dockerfile (python:3.12-slim, 비루트)", "docker-compose: api + PostgreSQL 16",
                       "헬스체크 · Prometheus 지표 · JSON 로그", "로컬은 SQLite 파일 하나"], size=11, fill=INK2, lh=19, maxw=310)

    # 화살표
    for x in (235, 645, 1055):
        s.arrow([(x, 150), (x, 166)], color=INK3)
    s.arrow([(460, 340), (460, 358)], color=BRAND, marker="ab", sw=2)
    s.arrow([(460, 482), (460, 500)], color=BRAND, marker="ab", sw=2)
    s.arrow([(1070, 340), (1070, 358)], color=AMBER, marker="aa", sw=2)
    s.arrow([(864, 437), (890, 437), (890, 552), (896, 552)], color=VIOLET, marker="av")
    s.arrow([(1070, 602), (1070, 610)], color=AMBER, dash="4 3", marker="aa")
    s.arrow([(460, 702), (460, 720)], color=TEAL, marker="at", sw=2)
    s.arrow([(40, 254), (24, 254), (24, 800), (36, 800)], color=GREEN, marker="a", sw=1.6)
    s.text(19, 600, "실행 저장 · 결정 · 감사 기록", size=10.5, fill=GREEN, anchor="middle", rot=-90)
    return s


def main():
    for make, name in ((project, "architecture-project.svg"), (backend, "architecture-backend.svg")):
        svg = make()
        for w in svg.warn:
            print("  ⚠", name, w)
        body = svg.render()
        for d in OUTS:
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(body, encoding="utf-8")
        print(f"{name}: {len(body):,} bytes → {', '.join(str(d.relative_to(ROOT)) for d in OUTS)}")


if __name__ == "__main__":
    main()
