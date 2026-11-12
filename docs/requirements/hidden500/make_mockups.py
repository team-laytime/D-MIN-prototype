"""역할별 화면 목업 3장 — 번호마다 UX 항목 ID를 붙인다 (가상 예시 화면).

  fig-4-ui-instructor.svg   작업 지시자 첫 화면 (U12)
  fig-5-ui-payment.svg      지불 부서 첫 화면 (U13)
  fig-6-ui-input.svg        입력 · 문서 확인 화면 (U02 · U03)
실행: python3 docs/requirements/hidden500/make_mockups.py  (PNG는 make_hidden500.py --png 가 같이 만든다)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from svgkit import (AMBER, BLUE, CARD, GREEN, INK, INK2, INK3, INK4, LINE, NAVY, RED, Svg, tw)  # noqa: E402

HERE = Path(__file__).parent
W = 680
ROLES = ["스케줄러", "작업 지시자", "지불 부서"]


def frame(s, y, h, title, sub, role):
    s.rect(16, y + 2, 648, h, fill="#101828", rx=12, extra=' opacity="0.06"')
    s.rect(16, y, 648, h, fill=CARD, stroke=LINE, rx=12)
    s.raw(f'<path d="M16 {y + 12} a12 12 0 0 1 12 -12 h624 a12 12 0 0 1 12 12 v26 h-648 Z" fill="{NAVY}"/>')
    s.text(32, y + 24.5, title, 13, 700, "#FFFFFF")
    s.text(32 + tw(title, 13) + 8, y + 24.5, sub, 11.5, 400, "#9FB3C8")
    widths = [tw(r, 11.5) + 18 for r in ROLES]
    seg = sum(widths) + 6
    sx = 16 + 648 - 14 - seg
    s.rect(sx, y + 8, seg, 22, fill="#16314D", rx=11)
    cx = sx + 3
    for i, (r, w) in enumerate(zip(ROLES, widths)):
        if i == role:
            s.rect(cx, y + 10.5, w, 17, fill="#FFFFFF", rx=8.5)
            s.text(cx + w / 2, y + 23, r, 11.5, 600, NAVY, "middle")
        else:
            s.text(cx + w / 2, y + 23, r, 11.5, 500, "#C9D6E3", "middle")
        cx += w


def legend(s, y, entries):
    s.text(24, y + 4, "번호 설명 · 오른쪽 ID는 15-hidden-nfr-ux-500.md의 UX 항목", 12.5, 700)
    colw = (W - 48 - 12) / 2
    for i, (n, uid, t, why) in enumerate(entries):
        col, row = i % 2, i // 2
        x = 24 + col * (colw + 12)
        yy = y + 16 + row * 50
        s.card(x, yy, colw, 42)
        s.badge(n, x + 18, yy + 21)
        s.text(x + 36, yy + 17, t, 12, 700)
        s.text(x + colw - 10, yy + 17, uid, 11, 600, INK4, "end")
        s.text(x + 36, yy + 33, why, 11, 400, INK3)
    rows = (len(entries) + 1) // 2
    return y + 16 + rows * 50


def button(s, x, y, label, primary=False, w=None, h=22, size=11.5):
    w = w or tw(label, size) + 24
    if primary:
        s.rect(x, y, w, h, fill=BLUE, rx=6)
        s.text(x + w / 2, y + h / 2 + size * 0.36, label, size, 700, "#FFFFFF", "middle")
    else:
        s.rect(x, y, w, h, fill="#FFFFFF", stroke="#C9D3E1", rx=6)
        s.text(x + w / 2, y + h / 2 + size * 0.36, label, size, 600, INK2, "middle")
    return w


def chip(s, x, y, label, kind="gray", size=10.5, h=17):
    pal = {
        "gray": ("#EEF1F5", INK2, None),
        "amber": ("#FFF4DF", "#8A5300", None),
        "red": ("#FDECEC", RED, None),
        "blue": ("#E8F0FE", BLUE, None),
        "green": ("#E7F5EE", GREEN, None),
        "line": ("#FFFFFF", INK2, "#D0D5DD"),
    }[kind]
    return s.pill(x, y, label, size, pal[1], pal[0], stroke=pal[2], h=h, padx=6, weight=600)


# --------------------------------------------------------------------------- 작업 지시자
def instructor():
    H = 966
    s = Svg(W, H, "작업 지시자 첫 화면 목업",
            "확정본만 시간순 할 일 목록으로 보여 주는 작업 지시자 화면. 확정본 판 표시, 본 뒤 바뀐 것, 앞으로 2시간, 도선 신청 마감 카운트다운, 주의 배지, 인쇄를 번호로 표시한다.")
    s.header("작업 지시자 첫 화면 — 확정본 할 일 목록", "가상 예시 · 금액 없이 '언제 무엇을 준비하나'만")
    y0 = 72
    frame(s, y0, 628, "오늘 할 일", "11/12 (목) 14:05 · 울산 CLX · 가상 데이터", 1)

    # ⑦ 확정본 판 · ⑥ 금액 숨김
    y = y0 + 48
    s.rect(28, y, 624, 28, fill="#EEF3FB", stroke="#D5E0F2", rx=7)
    s.text(44, y + 18.5, "확정본 v3 · 11/12 09:40 확정 · 확정자: 스케줄러 계정", 11.5, 600, "#1B3D61")
    note = "요율·금액은 이 화면에 없어요"
    s.text(640, y + 18.5, note, 11, 500, INK3, "end")
    s.badge(7, 28, y + 1)
    s.badge(6, 640 - tw(note, 11) - 16, y + 14)

    # ⑤ 본 뒤 바뀐 것
    y = y0 + 86
    s.rect(28, y, 624, 74, fill="#FFF8EB", stroke="#F2D29B", rx=9)
    s.text(44, y + 21, "마지막으로 본 뒤 바뀐 것 2건 · 11:30 이후", 12.5, 700, "#7A4A00")
    cw = chip(s, 44, y + 32, "변경", "amber")
    s.text(44 + cw + 8, y + 44.5, "B호 접안 11/12 11:00 → 17:00 · ETA 10:30 → 16:30 (대리점 연락)", 11.5, 500, INK2)
    cw = chip(s, 44, y + 52, "변경", "amber")
    s.text(44 + cw + 8, y + 64.5, "C호 부두 #6 → #3 · 접안 11/13 12:00 → 09:00", 11.5, 500, INK2)
    s.badge(5, 28, y + 1)

    # ② 앞으로 2시간 · ③ 도선 마감
    y = y0 + 170
    s.rect(28, y, 414, 120, fill="#F5F8FF", stroke="#9DB5E8", rx=9)
    s.text(44, y + 22, "앞으로 2시간 · 14:05 ~ 16:05", 12.5, 700)
    rows = [("14:30", "K호 · #1 · 이안", "예선 2척 · 확정된 FIX 일정", ("FIX", "gray")),
            ("15:40", "D호 · #6 · 작업 완료 예상", "16:10 호스분리 · 17:40 이안", ("작업 중", "blue"))]
    ry = y + 38
    for t, a, b, (cl, ck) in rows:
        s.line(44, ry, 426, ry, "#E3E9F6")
        s.text(44, ry + 21, t, 14, 700, INK)
        s.text(98, ry + 17, a, 12, 700)
        s.text(98, ry + 33, b, 11, 400, INK3)
        cwid = tw(cl, 10.5) + 12
        chip(s, 426 - cwid, ry + 9, cl, ck)
        ry += 40
    s.badge(2, 28, y + 1)

    s.rect(452, y, 200, 120, fill=CARD, stroke=LINE, rx=9)
    s.text(466, y + 22, "도선 신청 마감", 12.5, 700)
    s.text(466, y + 62, "1:50", 30, 700, AMBER)
    s.text(466 + tw("1:50", 30) + 6, y + 62, "남음", 12, 600, AMBER)
    s.text(466, y + 84, "Last POB 15:55 · 일몰 17:25 − 1.5h", 11, 500, INK2)
    s.text(466, y + 102, "넘기면 A호 접안은 내일 08:00 이후", 11, 500, RED)
    s.badge(3, 452, y + 1)

    # ① 시간순 할 일 · ④ 주의 배지
    y = y0 + 300
    s.rect(28, y, 624, 282, fill=CARD, stroke=LINE, rx=9)
    s.text(44, y + 22, "오늘 · 내일 할 일 (시간순)", 12.5, 700)
    tx = 640
    for lab, on in (("부두별", False), ("시간순", True)):
        wl = tw(lab, 11) + 16
        tx -= wl
        s.rect(tx, y + 9, wl, 20, fill="#E8F0FE" if on else "#FFFFFF", stroke="#9DB5E8" if on else "#D0D5DD", rx=6)
        s.text(tx + wl / 2, y + 23, lab, 11, 600, BLUE if on else INK3, "middle")
        tx -= 4
    items = [
        ("14:30", "K호 · #1", "이안 · 예선 2척", [("FIX", "gray")]),
        ("15:40", "D호 · #6", "작업 완료 → 16:10 호스분리", [("작업 중", "blue")]),
        ("17:00", "B호 · #3", "접안 · 도선 승선 16:00", [("변경", "amber"), ("야간 직전", "gray")]),
        ("18:00", "E호 · #6", "접안", [("동일 화물 그룹 #6·#7·#8", "amber")]),
        ("11/13 03:00", "전 부두", "강풍 제한 시작 · 하역 중단 대비", [("강풍 03~09", "red")]),
        ("11/13 09:00", "A호 · #1", "접안 (강풍 해제 뒤)", [("대기 18h", "gray")]),
        ("11/13 09:00", "C호 · #3", "접안", [("변경", "amber")]),
    ]
    ry = y + 40
    for t, v, task, chips in items:
        s.line(44, ry, 636, ry, "#F0F2F5")
        s.text(44, ry + 21.5, t, 12.5 if len(t) < 6 else 11.5, 700, INK)
        s.text(132, ry + 21.5, v, 12, 700)
        s.text(206, ry + 21.5, task, 11.5, 400, INK2)
        cx = 636
        for lab, kind in reversed(chips):
            wl = tw(lab, 10.5) + 12
            cx -= wl
            chip(s, cx, ry + 9, lab, kind)
            cx -= 4
        ry += 34
    s.badge(1, 28, y + 1)
    s.badge(4, 636 - tw("동일 화물 그룹 #6·#7·#8", 10.5) - 22, y + 40 + 34 * 3 + 17)

    # ⑧ 인쇄 · 준비 완료
    y = y0 + 592
    bw = button(s, 28, y, "오늘·내일 한 장 인쇄")
    s.badge(8, 28 + bw + 14, y + 11)
    bw2 = tw("준비 완료 알리기", 11.5) + 24
    button(s, 652 - bw2, y, "준비 완료 알리기", primary=True)
    button(s, 652 - bw2 - 8 - (tw("타임라인에서 보기", 11.5) + 24), y, "타임라인에서 보기")

    legend(s, y0 + 628 + 26, [
        (1, "UX-191", "시간순 할 일 목록", "계획과 주의점을 보고 준비한다 (원문 2절)"),
        (2, "UX-192", "2시간 안의 일 강조", "당장 할 일이 먼저다"),
        (3, "UX-193", "도선 신청 마감 카운트다운", "놓치면 하루를 기다린다"),
        (4, "UX-194", "주의 배지", "반영 못 한 변수를 같이 받는다 (원문 3절)"),
        (5, "UX-195", "본 뒤 바뀐 것 먼저", "놓치면 틀린 배를 준비한다"),
        (6, "UX-196", "요율·금액 숨김", "작업에 필요 없고 상업적으로 민감하다"),
        (7, "UX-201", "확정본 판·시각·확정자", "어떤 판을 보는지 알아야 한다"),
        (8, "UX-198", "오늘·내일 한 장 인쇄", "현장에 붙여 둔다 [추정]"),
    ])
    (HERE / "fig-4-ui-instructor.svg").write_text(s.render(), encoding="utf-8")


# --------------------------------------------------------------------------- 지불 부서
def payment():
    H = 1022
    s = Svg(W, H, "지불 부서 첫 화면 목업",
            "예상 체선료가 큰 순으로 선박을 보여 주는 지불 부서 화면. 요약 문장, 주별 추이, 확정본 기준 표시, 범위, 다툼 표시, 계약 조항 링크, 해석 차이가 큰 배, 곧 체선이 시작되는 배를 번호로 표시한다.")
    s.header("지불 부서 첫 화면 — 큰 금액과 다툼 위험부터", "가상 예시 · 숫자는 설명용 (선박 10척 중 6척 표시)")
    y0 = 72
    WH = 642
    frame(s, y0, WH, "체선료 노출", "11/12 (목) · 이번 주 · 가상 데이터", 2)

    # ⑨ 요약 문장 · ⑤ 추이
    y = y0 + 48
    s.rect(28, y, 624, 92, fill=CARD, stroke=LINE, rx=9)
    s.text(44, y + 22, "이번 주 예상 체선료", 11.5, 500, INK3)
    s.text(44, y + 52, "$412,000", 26, 700, INK)
    s.text(44, y + 74, "범위 $356,000 ~ $498,000 · ETA ±6h", 11, 400, INK3)
    chip(s, 250, y + 30, "다툼 가능 3척", "red", size=11, h=20)
    chip(s, 250, y + 56, "곧 체선 시작 2척", "amber", size=11, h=20)
    s.badge(9, 28, y + 1)
    # 추이 막대
    bx0, base = 420, y + 72
    weeks = [("10/20주", 318, False), ("10/27주", 455, False), ("11/03주", 389, False), ("이번 주", 412, True)]
    s.text(420, y + 18, "주별 합계 ($k)", 11, 600, INK3)
    for i, (lab, v, cur) in enumerate(weeks):
        hgt = 30 * v / 455
        x = bx0 + i * 56
        s.rect(x, base - hgt, 30, hgt, fill="#C9D7F2" if not cur else "#7398E6", rx=3)
        s.text(x + 15, base - hgt - 4, str(v), 10.5, 600, INK2, "middle")
        s.text(x + 15, base + 13, lab, 10.5, 400, INK3, "middle")
    s.badge(5, 640, y + 14)

    # ⑥ 기준 표시
    y = y0 + 150
    s.rect(28, y, 624, 26, fill="#EEF3FB", stroke="#D5E0F2", rx=7)
    s.text(44, y + 17.5, "기준: 확정본 v3 (11/12 09:40) · 작업본 금액은 이 화면에 섞지 않아요", 11.5, 600, "#1B3D61")
    s.badge(6, 28, y + 1)

    # ① 목록 · ② 다툼 · ③ 범위 · ④ 조항
    y = y0 + 186
    th = 40 + 6 * 34 + 34
    s.rect(28, y, 624, th, fill=CARD, stroke=LINE, rx=9)
    cols = [(44, "선박"), (98, "계약"), (222, "예상 체선료"), (236, "범위 (ETA ±6h)"), (352, "다툼 표시"), (532, "근거 조항")]
    for x, lab in cols:
        s.text(x, y + 25, lab, 11, 700, INK3, "end" if lab == "예상 체선료" else "start")
    s.line(40, y + 34, 640, y + 34, LINE)
    rows = [
        ("A호", "CFR", 96500, (81, 118), [("해석 갈림", "red"), ("야간 대기", "amber")], "CT-07 · 6조"),
        ("F호", "FOB", 71200, (64, 80), [("기상 공제 1/2", "amber")], "CT-12 · 8조"),
        ("B호", "CP", 58300, (52, 71), [("NOR 시각", "red")], "CT-03 · (H)"),
        ("D호", "FOB", 41000, (37, 46), [], "CT-15 · 7조"),
        ("C호", "FOB", 27600, (21, 33), [], "CT-09 · 7조"),
        ("E호", "CP", 9400, (0, 19), [("곧 체선", "amber")], "CT-05 · (H)"),
    ]
    ry = y + 34
    for v, c, amt, (lo, hi), dz, cl in rows:
        s.text(44, ry + 22, v, 12, 700)
        s.text(98, ry + 22, c, 11.5, 500, INK2)
        s.text(222, ry + 22, f"${amt:,}", 12.5, 700, RED if amt > 50000 else INK, "end")
        x0, x1 = 236, 336
        s.line(x0, ry + 17, x1, ry + 17, "#E4E7EC", 4, ' stroke-linecap="round"')
        def px(k):
            return x0 + (x1 - x0) * k / 130
        s.line(px(lo), ry + 17, px(hi), ry + 17, "#9DB5E8", 4, ' stroke-linecap="round"')
        s.circle(px(amt / 1000), ry + 17, 3.4, BLUE)
        cx = 352
        for lab, kind in dz:
            cx += chip(s, cx, ry + 9, lab, kind) + 4
        s.text(532, ry + 22, cl, 11.5, 600, BLUE)
        s.text(532 + tw(cl, 11.5) + 4, ry + 22, "↗", 11.5, 600, BLUE)
        ry += 34
        s.line(40, ry, 640, ry, "#F0F2F5")
    s.text(44, ry + 22, "외 4척 $108,000 ▸ 펼치기", 11.5, 500, INK3)
    s.text(640, ry + 22, "합계 $412,000", 12, 700, INK, "end")
    s.badge(1, 28, y + 1)
    s.badge(3, 236 + tw("범위 (ETA ±6h)", 11) + 14, y + 21)
    s.badge(2, 352 + tw("다툼 표시", 11) + 14, y + 21)
    s.badge(4, 532 + tw("근거 조항", 11) + 14, y + 21)

    # ⑧ 해석 차이 · ⑦ 곧 체선
    y = y0 + 186 + th + 10
    cwid = (624 - 10) / 2
    s.rect(28, y, cwid, 112, fill="#FFF7F6", stroke="#F4C7C2", rx=9)
    s.text(44, y + 22, "해석에 따라 차이가 큰 배", 12.5, 700)
    s.text(44, y + 46, "A호 · NOR 제출 + 6h 기준", 11.5, 500, INK2)
    s.text(28 + cwid - 14, y + 46, "$96,500", 12.5, 700, INK, "end")
    s.text(44, y + 68, "A호 · NOR 승인 시각 기준", 11.5, 500, INK2)
    s.text(28 + cwid - 14, y + 68, "$12,300", 12.5, 700, INK, "end")
    s.line(44, y + 78, 28 + cwid - 14, y + 78, "#F4C7C2")
    s.text(44, y + 98, "차이 $84,200 · 협상 전에 조항 확인", 11.5, 700, RED)
    s.badge(8, 28, y + 1)

    x2 = 28 + cwid + 10
    s.rect(x2, y, cwid, 112, fill="#FFFBF2", stroke="#F2D29B", rx=9)
    s.text(x2 + 16, y + 22, "곧 체선이 시작되는 배", 12.5, 700)
    for i, (v, left, when, frac) in enumerate([("E호", "남은 Laytime 3.5h", "17:35 체선 시작 예상", 0.15),
                                               ("G호", "남은 Laytime 6.0h", "20:05 체선 시작 예상", 0.25)]):
        yy = y + 44 + i * 34
        s.text(x2 + 16, yy, v, 12, 700)
        s.text(x2 + 48, yy, left, 11.5, 600, "#8A5300")
        s.text(x2 + 48, yy + 15, when, 11, 400, INK3)
        gx = x2 + cwid - 104
        s.rect(gx, yy - 9, 88, 8, fill="#F2E4C8", rx=4)
        s.rect(gx, yy - 9, 88 * frac, 8, fill="#E39A1B", rx=4)
    s.badge(7, x2, y + 1)

    # 아래 막대
    y = y0 + WH - 34
    chip(s, 28, y + 2, "용어 풀이: 정박개시 · Laytime · NOR ▸", "line", size=11, h=20)
    bw = tw("엑셀로 내보내기", 11.5) + 24
    button(s, 652 - bw, y, "엑셀로 내보내기")

    legend(s, y0 + WH + 26, [
        (1, "UX-206", "예상 체선료 큰 순 목록", "크게 날 가능성을 점검한다 (원문 2절)"),
        (2, "UX-207", "다툼 표시 4종", "분쟁 위험을 미리 본다 (원문 2절)"),
        (3, "UX-208", "선박별 범위", "예상은 숫자 하나가 아니다"),
        (4, "UX-209", "계약 조항 바로가기", "근거를 조항까지 확인한다"),
        (5, "UX-210", "주·월 합계 추이", "규모를 본다 (9월 약 180억 원, 멘토링)"),
        (6, "UX-214", "확정본 기준만", "작업본 숫자를 확정으로 오해한다"),
        (7, "UX-216", "곧 체선이 시작되는 배", "미리 손쓸 기회가 있다"),
        (8, "UX-217", "해석 차이가 큰 배", "협상 전에 조항을 확인한다"),
        (9, "UX-220", "요약 문장 한 줄", "바쁜 사람은 한 문장만 읽는다"),
    ])
    (HERE / "fig-5-ui-payment.svg").write_text(s.render(), encoding="utf-8")


# --------------------------------------------------------------------------- 입력 · 문서 확인
def input_screen():
    H = 910
    s = Svg(W, H, "입력과 문서 확인 화면 목업",
            "표 붙여넣기, 변경 한 건 입력, 원문 옆 추출값 확인, 위험한 값 먼저, 모호한 날짜 두 해석, C/P와 NOR 충돌, 확인 진행 막대, 문서에 없는 값 직접 입력을 번호로 표시한다.")
    s.header("입력 · 문서 확인 화면 — 옮겨 적기와 확인을 줄인다", "가상 예시 · 계약서 문구는 설명용으로 지어낸 것")
    y0 = 72
    WH = 576
    frame(s, y0, WH, "입력 · 문서 확인", "S05 강풍 예보 + 선박 집중 · 작업본", 0)

    # 단계 표시
    y = y0 + 48
    steps = ["입력", "계산", "비교", "리스크", "보고서", "확정"]
    x = 28
    for i, st in enumerate(steps):
        on = i == 0
        wl = tw(st, 11) + 26
        s.rect(x, y, wl, 22, fill="#E8F0FE" if on else "#F6F8FB", stroke="#9DB5E8" if on else "#E4E7EC", rx=11)
        s.text(x + wl / 2, y + 15, f"{i + 1} {st}", 11, 700 if on else 500, BLUE if on else INK4, "middle")
        x += wl + 6

    # ① 붙여넣기 · ② 변경 한 건
    y = y0 + 80
    s.rect(28, y, 330, 104, fill=CARD, stroke=LINE, rx=9)
    s.text(44, y + 22, "표 붙여넣기", 12.5, 700)
    s.text(44 + tw("표 붙여넣기", 12.5) + 8, y + 22, "SEAGATE 접안계획에서 복사한 12행", 11, 400, INK3)
    cx = 44
    for lab, kind in (("Berth → 부두 ✓", "green"), ("ETA ✓", "green"), ("ETB ✓", "green"), ("ETU ✓", "green")):
        cx += chip(s, cx, y + 36, lab, kind) + 5
    chip(s, 44, y + 60, "Biz → ? 열을 골라 주세요", "amber")
    button(s, 358 - 16 - (tw("가져오기", 11.5) + 24), y + 70, "가져오기", primary=True)
    s.badge(1, 28, y + 1)

    x2 = 368
    s.rect(x2, y, 284, 104, fill=CARD, stroke=LINE, rx=9)
    s.text(x2 + 16, y + 22, "변경 한 건", 12.5, 700)
    s.text(x2 + 16 + tw("변경 한 건", 12.5) + 8, y + 22, "대리점 연락 한 통 = 세 번 클릭", 11, 400, INK3)
    fields = [("선박", "B호 ▾", 52), ("새 ETA", "11/12 16:30", 96), ("출처", "대리점 연락 ▾", 96)]
    fx = x2 + 16
    for lab, val, wv in fields:
        s.text(fx, y + 46, lab, 10.5, 600, INK3)
        s.rect(fx, y + 52, wv, 22, fill="#FFFFFF", stroke="#C9D3E1", rx=5)
        s.text(fx + 7, y + 67, val, 11, 600, INK)
        fx += wv + 8
    bw = tw("저장", 11.5) + 24
    button(s, x2 + 284 - 16 - bw, y + 78, "저장", primary=True, h=20)
    s.badge(2, x2, y + 1)

    # 문서 확인 카드
    y = y0 + 194
    ch = WH - 194 - 14
    s.rect(28, y, 624, ch, fill=CARD, stroke=LINE, rx=9)
    s.text(44, y + 22, "C/P · NOR 확인 — B호 · CT-2611-03 (가상)", 12.5, 700)
    # ⑦ 진행 막대
    s.text(640, y + 22, "확인 14 / 18", 12, 700, INK, "end")
    s.rect(500, y + 30, 140, 6, fill="#E4E7EC", rx=3)
    s.rect(500, y + 30, 140 * 14 / 18, 6, fill=GREEN, rx=3)
    s.text(640, y + 50, "남은 4개를 확인해야 계산할 수 있어요", 11, 500, AMBER, "end")
    s.badge(7, 488, y + 22)

    # ③ 원문
    dy = y + 62
    s.rect(40, dy, 250, ch - 74, fill="#FBFBF7", stroke="#E6E2D3", rx=6)
    chip(s, 50, dy + 10, "스캔본 · 꼼꼼히 확인", "amber")
    def lat_w(t, size):
        w = 0.0
        for ch in t:
            if ch == " ":
                w += 0.28
            elif ch in ".,:;'()/":
                w += 0.30
            elif ch.isdigit():
                w += 0.58
            elif ch.isupper():
                w += 0.64
            else:
                w += 0.50
        return w * size

    lines = [
        ("CHARTER PARTY (가상 예시)", 10.5, 700, INK3, None),
        ("PART I", 11, 700, INK, None),
        ("(H) Laytime:", 11, 500, INK, None),
        ("36 running hours", 11, 600, INK, "#FFE58F"),
        ("(I) Demurrage: USD 28,000 / day", 11, 500, INK, None),
        ("6. NOR: laytime starts 6 hours after", 11, 500, INK, None),
        ("NOR or on all fast, whichever is earlier.", 11, 500, INK, None),
        ("NOR tendered:", 11, 500, INK, None),
        ("12/11/2026 15:10 UTC", 11, 600, INK, "#FFD8B0"),
        ("Master's note:", 11, 500, INK, None),
        ("laytime 30 hrs", 11, 600, INK, "#FAD1CF"),
    ]
    ly = dy + 48
    for txt, size, wt, col, hl in lines:
        if hl:
            s.rect(47, ly - 12.5, lat_w(txt, size) + 8, 17, fill=hl, rx=3)
        s.text(50, ly, txt, size, wt, col)
        ly += 21
    s.badge(3, 40, dy + 1)

    # ④ 오른쪽 값 목록 (위험한 값부터)
    rx0, rw = 302, 338
    s.text(rx0, dy + 12, "위험한 값부터", 11.5, 700, INK3)
    s.badge(4, rx0 + tw("위험한 값부터", 11.5) + 14, dy + 8)
    yy = dy + 24
    # ⑤ 모호한 날짜
    s.rect(rx0, yy, rw, 66, fill="#FFF8EB", stroke="#F2D29B", rx=7)
    s.text(rx0 + 12, yy + 19, "NOR 제출 시각 · 날짜 순서가 모호해요", 12, 700, "#7A4A00")
    s.text(rx0 + 12, yy + 36, "원문 12/11/2026 15:10 UTC → KST로는 다음 날 00:10", 11, 400, INK2)
    bx = rx0 + 12
    bx += button(s, bx, yy + 42, "11월 12일 (일/월)", h=19, size=11) + 6
    button(s, bx, yy + 42, "12월 11일 (월/일)", h=19, size=11)
    s.badge(5, rx0 + rw, yy + 1)
    yy += 74
    # ⑥ 충돌
    s.rect(rx0, yy, rw, 66, fill="#FFF7F6", stroke="#F4C7C2", rx=7)
    s.text(rx0 + 12, yy + 19, "Laytime · C/P와 NOR 메모가 달라요", 12, 700, RED)
    s.text(rx0 + 12, yy + 36, "C/P (H) 36h ↔ 선장 메모 30h", 11, 400, INK2)
    bx = rx0 + 12
    bx += button(s, bx, yy + 42, "C/P 36h 쓰기", h=19, size=11) + 6
    button(s, bx, yy + 42, "메모 30h 쓰기", h=19, size=11)
    s.badge(6, rx0 + rw, yy + 1)
    yy += 74
    # 나머지 값
    rest = [
        ("청구 기한", "문서에 없음", "직접 입력", "line", 8),
        ("일 체선료", "$28,000 / day", "확인함 ✓", "green", None),
        ("Laycan", "11/10 ~ 11/12", "고침 · 원래 11/10 ~ 11/11", "blue", None),
    ]
    for lab, val, tag, kind, num in rest:
        s.line(rx0, yy, rx0 + rw, yy, "#F0F2F5")
        s.text(rx0 + 4, yy + 20, lab, 11.5, 700, INK)
        s.text(rx0 + 74, yy + 20, val, 11.5, 500, INK2 if val != "문서에 없음" else AMBER)
        wl = tw(tag, 10.5) + 12
        chip(s, rx0 + rw - wl, yy + 8, tag, kind)
        if num:
            s.badge(num, rx0 + rw - wl - 14, yy + 16)
        yy += 30
    s.text(rx0 + 4, yy + 20, "Enter 확인 · ↓ 다음 값", 11, 500, INK4)

    legend(s, y0 + WH + 26, [
        (1, "UX-016", "붙여넣기 열 자동 맞춤", "연동이 없어 사람이 옮겨 적는다"),
        (2, "UX-027", "'변경 한 건' 입력창", "ETA 연락은 한 건씩 온다 [추정]"),
        (3, "UX-036", "원문 옆 근거 강조", "근거를 봐야 확인할 수 있다"),
        (4, "UX-037", "위험한 값부터", "사람의 시간을 위험한 값에 쓴다"),
        (5, "UX-042", "모호한 날짜 두 해석", "12/11은 두 날짜로 읽힌다"),
        (6, "UX-046", "C/P와 NOR 충돌 고르기", "교차 검증은 사람이 정한다 (FR-07)"),
        (7, "UX-039", "확인 진행 막대", "미확인이 있으면 계산이 막힌다 (FR-06)"),
        (8, "UX-044", "문서에 없으면 직접 입력", "지어낸 값을 막는다"),
    ])
    (HERE / "fig-6-ui-input.svg").write_text(s.render(), encoding="utf-8")


if __name__ == "__main__":
    instructor()
    payment()
    input_screen()
    print("mockups 3")
