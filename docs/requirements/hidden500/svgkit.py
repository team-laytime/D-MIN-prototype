"""포스터 스타일 SVG를 그리는 작은 도구 (표준 라이브러리만).

글자는 요소마다 인라인 style로 넣는다 — 채팅 위젯에 그대로 붙여도 스타일이 덮이지 않게.
"""

FONT = "Pretendard,'Apple SD Gothic Neo','Noto Sans KR',sans-serif"
INK, INK2, INK3, INK4 = "#0E1726", "#344054", "#667085", "#98A2B3"
LINE, BG, CARD = "#E2E7EE", "#F6F8FB", "#FFFFFF"
NAVY = "#0B1F33"
BLUE, GREEN, AMBER, RED, TEAL, PURPLE = "#1B5FD9", "#127A45", "#B26A00", "#C13A32", "#0B8B7B", "#5B4BC4"
CALL = "#6E56CF"  # 번호 표시(주석) 색


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tw(s, size):
    """대략적인 글자 폭(px). Pretendard 기준 어림값."""
    w = 0.0
    for ch in str(s):
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F:
            w += size * 0.96
        elif ch == " ":
            w += size * 0.28
        elif ch in "·":
            w += size * 0.32
        elif ch in "il.,:;|!'()[]":
            w += size * 0.30
        elif ch.isupper() or ch in "$%#@&mwMW":
            w += size * 0.66
        elif ch in "→←−×~–":
            w += size * 0.9
        else:
            w += size * 0.56
    return w


class Svg:
    def __init__(self, w, h, title, desc):
        self.w, self.h = w, h
        self.title, self.desc = title, desc
        self.defs = []
        self.out = []

    # ---- 기본 도형
    def text(self, x, y, s, size=12, weight=400, fill=INK, anchor="start", opacity=None):
        st = f"font-family:{FONT};font-size:{size}px;font-weight:{weight};fill:{fill}"
        if anchor != "start":
            st += f";text-anchor:{anchor}"
        if opacity is not None:
            st += f";opacity:{opacity}"
        self.out.append(f'<text x="{x:.1f}" y="{y:.1f}" style="{st}">{esc(s)}</text>')

    def rect(self, x, y, w, h, fill="none", stroke=None, sw=1, rx=0, extra=""):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{st}{extra}/>')

    def line(self, x1, y1, x2, y2, stroke=LINE, sw=1, extra=""):
        self.out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{extra}/>')

    def circle(self, cx, cy, r, fill, stroke=None, sw=1):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"{st}/>')

    def raw(self, s):
        self.out.append(s)

    # ---- 조합
    def card(self, x, y, w, h, fill=CARD, rx=10, shadow=True, stroke=LINE, dash=None):
        if shadow:
            self.rect(x, y + 1.5, w, h, fill="#101828", rx=rx, extra=' opacity="0.05"')
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.rect(x, y, w, h, fill=fill, stroke=stroke, rx=rx, extra=extra)

    def pill(self, x, y, s, size=11, fg=INK2, bg="#EEF1F5", stroke=None, weight=500, padx=7, h=19):
        w = tw(s, size) + padx * 2
        self.rect(x, y, w, h, fill=bg, stroke=stroke, rx=h / 2)
        self.text(x + padx, y + h / 2 + size * 0.36, s, size, weight, fg)
        return w

    def badge(self, n, cx, cy, color=CALL):
        self.circle(cx, cy, 10, color, "#FFFFFF", 2)
        self.text(cx, cy + 4.1, str(n), 11.5, 700, "#FFFFFF", "middle")

    def header(self, title, sub, tag="제안 · 팀 확인 전"):
        self.rect(0, 0, self.w, self.h, fill=BG, rx=14)
        self.text(24, 37, title, 17, 700)
        self.text(24, 56, sub, 11.5, 400, INK3)
        if tag:
            pw = tw(tag, 11) + 20
            self.rect(self.w - 24 - pw, 22, pw, 22, fill="#FFF4DF", rx=11)
            self.text(self.w - 24 - pw + 10, 36.96, tag, 11, 600, AMBER)

    def render(self):
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img">'
            f"<title>{esc(self.title)}</title><desc>{esc(self.desc)}</desc>"
        )
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return head + defs + "\n".join(self.out) + "</svg>\n"
