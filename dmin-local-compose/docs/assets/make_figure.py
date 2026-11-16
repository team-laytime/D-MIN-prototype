#!/usr/bin/env python3
"""README 그림(로컬 실행판 구조)을 만든다: architecture-compose.svg + .png (PNG는 Chrome 헤드리스로 뜬다).

    python3 docs/assets/make_figure.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONT = "Pretendard,'Apple SD Gothic Neo','Noto Sans KR','Malgun Gothic',sans-serif"
CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"]
INK, SUB, LABEL = "#0E1726", "#667085", "#344054"


def tw(s: str, size: float) -> float:
    """대략의 글자 폭(px). 한글 1.0em, 영문·숫자 0.58em, 공백·문장부호 0.32em."""
    w = 0.0
    for ch in s:
        if ord(ch) >= 0x2E80:
            w += 1.0
        elif ch.isalnum():
            w += 0.58
        elif ch in " .,:;'·|/()[]-":
            w += 0.32
        else:
            w += 0.6
    return w * size


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


ICONS = {
    "user": ("#344054", '<circle cx="14" cy="10.4" r="3.6"/><path d="M6.5 22 C6.5 16.4 21.5 16.4 21.5 22"/>'),
    "weather": ("#0E7490", '<circle cx="11" cy="10.5" r="3"/><path d="M11 4.8 V5.9 M5.3 10.5 H6.4 M7 6.5 L7.8 7.3 M15 6.5 L14.2 7.3"/><path d="M10 21.5 H20 A3.2 3.2 0 0 0 19.6 15.1 A4.6 4.6 0 0 0 11.2 15.9 A2.8 2.8 0 0 0 10 21.5 Z"/>'),
    "compose": ("#1D63ED", '<rect x="5.5" y="14.5" width="5" height="5" rx="1"/><rect x="11.5" y="14.5" width="5" height="5" rx="1"/><rect x="17.5" y="14.5" width="5" height="5" rx="1"/><rect x="11.5" y="8.5" width="5" height="5" rx="1"/>'),
    "lock": ("#1B5FD9", '<rect x="7.5" y="12.5" width="13" height="9.5" rx="2"/><path d="M10.5 12.5 V10 A3.5 3.5 0 0 1 17.5 10 V12.5"/><path d="M14 16.2 V18.3"/>'),
    "clock": ("#7A5AF8", '<circle cx="14" cy="14" r="7.5"/><path d="M14 9.8 V14 L17 15.8"/>'),
    "python": ("#0B8B7B", '<circle cx="8" cy="9" r="2.4"/><circle cx="20" cy="9" r="2.4"/><circle cx="14" cy="20" r="2.4"/><path d="M10.4 9 H17.6 M9.2 11.1 L12.8 17.9 M18.8 11.1 L15.2 17.9"/>'),
    "spring": ("#5B4BC4", '<rect x="5.5" y="8.5" width="17" height="11" rx="2"/><path d="M10 11.2 V16.8 M14 11.2 V16.8 M18 11.2 V16.8"/>'),
    "vue": ("#2F9E6E", '<rect x="5.5" y="7" width="17" height="14" rx="2"/><path d="M5.5 11 H22.5"/><circle cx="8.3" cy="9" r="0.6" fill="#FFFFFF"/><circle cx="10.4" cy="9" r="0.6" fill="#FFFFFF"/>'),
    "db": ("#B26A00", '<ellipse cx="14" cy="8.5" rx="6.5" ry="2.4"/><path d="M7.5 8.5 V19.5 A6.5 2.4 0 0 0 20.5 19.5 V8.5"/><path d="M7.5 14 A6.5 2.4 0 0 0 20.5 14"/>'),
    "flow": ("#475467", '<path d="M7 8 H21 M7 14 H17 M7 20 H13"/><path d="M19 17 L22 20 L19 23" transform="translate(-1 -3)"/>'),
    "bars": ("#E8590C", '<path d="M6 21 H22"/><path d="M8.5 21 V16 M12.2 21 V11 M15.8 21 V13.5 M19.5 21 V8.5"/>'),
    "grid": ("#F59F00", '<rect x="5.5" y="6.5" width="7.5" height="7" rx="1.2"/><rect x="15" y="6.5" width="7.5" height="4.5" rx="1.2"/><rect x="5.5" y="15.5" width="7.5" height="6" rx="1.2"/><rect x="15" y="13" width="7.5" height="8.5" rx="1.2"/>'),
}


class Svg:
    def __init__(self, w: int, h: int, title: str, desc: str):
        self.w, self.h = w, h
        self.o: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
            f"<title>{esc(title)}</title><desc>{esc(desc)}</desc><defs>"
            + "".join(
                f'<marker id="{i}" viewBox="0 0 10 10" refX="8.2" refY="5" markerWidth="6.5" markerHeight="6.5" '
                f'orient="auto-start-reverse"><path d="M1 1.2 L9 5 L1 8.8 Z" fill="{c}"/></marker>'
                for i, c in (("mr", INK), ("mo", SUB))
            )
            + "</defs>"
        ]

    def add(self, s: str) -> None:
        self.o.append(s)

    def rect(self, x, y, w, h, rx=0, fill="none", stroke=None, sw=1, dash=None) -> None:
        a = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"'
        if stroke:
            a += f' stroke="{stroke}" stroke-width="{sw}"'
        if dash:
            a += f' stroke-dasharray="{dash}"'
        self.add(a + "/>")

    def text(self, x, y, s, size=11.0, weight=400, fill=INK, anchor=None) -> None:
        a = f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{fill}"'
        if anchor:
            a += f' text-anchor="{anchor}"'
        self.add(a + f">{esc(s)}</text>")

    def chip(self, x, y, s, size=10.5, h=19, fill="#EEF2F7", color=LABEL, weight=500, right=False) -> float:
        w = round(tw(s, size) + 16, 1)
        if right:
            x = x - w
        self.rect(x, y, w, h, rx=h / 2, fill=fill)
        self.text(x + w / 2, y + h / 2 + size * 0.36, s, size, weight, color, "middle")
        return w

    def net(self, x, y, name) -> None:
        """화살표 옆에 붙이는 네트워크 이름표."""
        self.chip(x, y, name, 9.5, 16, "#E8EEFB", "#1D4ED8", 600)

    def icon(self, x, y, name, size=24.0) -> None:
        color, body = ICONS[name]
        self.add(
            f'<g transform="translate({x} {y}) scale({round(size / 28, 4)})" fill="none" stroke="#FFFFFF" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
            f'<rect width="28" height="28" rx="7" fill="{color}" stroke="none"/>{body}</g>'
        )

    def card(self, x, y, w, h, icon, title, sub, isz=24.0, tsz=12.5) -> None:
        self.rect(x, y, w, h, rx=12, fill="#FFFFFF", stroke="#E2E7EE")
        self.icon(x + 8, y + (h - isz) / 2, icon, isz)
        tx = x + 8 + isz + 8
        self.text(tx, y + h / 2 - 2.5, title, tsz, 700)
        self.text(tx, y + h / 2 + 12.5, sub, 10.5, 400, SUB)

    def bigcard(self, x, y, w, h, icon, title, sub, bullets, color) -> None:
        self.rect(x, y, w, h, rx=12, fill="#FFFFFF", stroke="#E2E7EE")
        self.icon(x + 8, y + 8, icon, 24)
        self.text(x + 40, y + 18, title, 12.5, 700)
        self.text(x + 40, y + 33, sub, 10.5, 400, SUB)
        self.add(f'<path d="M{x + 10} {y + 43} H{x + w - 10}" stroke="#EEF1F5" stroke-width="1"/>')
        for i, t in enumerate(bullets):
            yy = y + 60 + i * 17
            self.add(f'<circle cx="{x + 15}" cy="{yy - 3.6}" r="2" fill="{color}"/>')
            self.text(x + 24, yy, t, 10.5, 400, LABEL)

    def arrow(self, d: str, kind="req") -> None:
        st = {
            "req": f'stroke="{INK}" stroke-width="1.6" marker-end="url(#mr)"',
            "obs": f'stroke="{SUB}" stroke-width="1.3" stroke-dasharray="4 3" marker-end="url(#mo)"',
        }[kind]
        self.add(f'<path d="{d}" fill="none" stroke-linecap="round" stroke-linejoin="round" {st}/>')

    def render(self) -> str:
        return "\n".join(self.o) + "\n</svg>\n"


def build() -> Svg:
    W, H = 720, 742
    s = Svg(W, H, "D-MIN 로컬 실행판 (Docker Compose)",
            "브라우저가 127.0.0.1:18089의 Caddy에 접속하면 Caddy가 / 는 Vue, /api 는 Spring으로 보낸다. Spring이 Python 에이전트와 Postgres를 쓰고, "
            "수집 타이머가 매일 06:00에 Spring을 깨우며, Prometheus가 Spring 지표를 모으고 Grafana가 보여 준다. 밖으로 나가는 길은 Spring의 공공데이터포털 호출뿐이다.")
    s.rect(0, 0, W, H, rx=14, fill="#F6F8FB")
    s.text(24, 34, "D-MIN 로컬 실행판 · Docker Compose", 17, 700)
    s.text(24, 53, "쿠버네티스 없음 · 컨테이너 8개 + 마이그레이션 1회 · 네트워크 8개 · 호스트 포트 2개(127.0.0.1만)", 11.5, 400, SUB)

    # 호스트 쪽
    s.card(24, 84, 230, 48, "user", "브라우저 (이 맥)", "127.0.0.1 에만 열림", 26)
    s.card(320, 84, 214, 48, "weather", "공공데이터포털", "울산항 AIS · 입항 신고", 26)
    for i, (k, t) in enumerate([("req", "요청"), ("obs", "지표")]):
        y = 96 + i * 19
        s.arrow(f"M604 {y} L624 {y}", k)
        s.text(632, y + 3.8, t, 10.5, 500, LABEL)

    # Compose 상자
    s.rect(12, 160, 696, 470, rx=14, fill="#FFFFFF", stroke="#9DB8F0", sw=1.2)
    cw = tw("Docker Compose · 프로젝트 dmin", 11) + 16 + 22
    s.rect(696 - cw, 170, cw, 22, rx=11, fill="#EEF2F7")
    s.icon(696 - cw + 5, 173, "compose", 16)
    s.text(696 - cw + 27, 185.5, "Docker Compose · 프로젝트 dmin", 11, 700, LABEL)

    s.card(40, 206, 214, 48, "lock", "Caddy · 입구", "127.0.0.1:18089", 26)
    s.card(40, 296, 150, 48, "vue", "Vue 화면", "nginx", 24)
    s.bigcard(250, 296, 210, 128, "spring", "Spring Boot", "Java 25 · 1개",
              ["API · 입력 검증", "실행 지휘 (작업 큐)", "규칙 계산 · 재검증", "DB는 앱 계정으로만"], "#5B4BC4")
    s.bigcard(520, 296, 170, 112, "python", "Python 에이전트", "FastAPI · 1개",
              ["솔버 (CP-SAT · HiGHS)", "Spring 요청만 받음", "인터넷 · DB 못 감"], "#0B8B7B")
    s.card(40, 476, 170, 48, "clock", "수집 타이머", "매일 06:00 KST", 24)
    s.card(250, 476, 210, 48, "db", "Postgres 17 + pgvector", "볼륨 dmin_pgdata", 24)
    s.card(520, 476, 170, 48, "bars", "Prometheus", "15초마다 · 3일 보관", 24)
    s.card(250, 560, 210, 48, "flow", "마이그레이션 (Flyway)", "한 번 돌고 끝남", 24)
    s.card(520, 560, 170, 48, "grid", "Grafana", "127.0.0.1:13000", 24)

    # 화살표 + 네트워크 이름
    s.arrow("M100 132 L100 204")                       # 브라우저 → Caddy
    s.net(108, 141, "public")
    s.arrow("M110 254 L110 294")                       # Caddy → Vue
    s.net(118, 266, "web")
    s.arrow("M254 230 L330 230 L330 294")              # Caddy → Spring
    s.net(264, 209, "api")
    s.text(338, 270, "/api", 11, 700, LABEL)
    s.text(118, 290, "/", 11, 700, LABEL)
    s.arrow("M460 350 L518 350")                       # Spring → Python
    s.net(467, 329, "agent")
    s.arrow("M330 424 L330 474")                       # Spring → Postgres
    s.net(338, 441, "db")
    s.arrow("M125 476 L125 396 L248 396")              # 수집 타이머 → Spring
    s.net(133, 428, "jobs")
    s.arrow("M400 560 L400 526")                       # 마이그레이션 → Postgres
    s.net(408, 535, "db")
    s.arrow("M420 296 L420 134")                       # Spring → 공공데이터포털
    s.net(428, 141, "outbound")
    s.arrow("M518 500 L490 500 L490 404 L462 404", "obs")   # Prometheus → Spring
    s.net(470, 446, "metrics")
    s.arrow("M605 560 L605 526", "obs")                # Grafana → Prometheus
    s.net(613, 535, "metrics")

    # 쿠버네티스 판에서 바뀐 것
    s.rect(12, 642, 696, 88, rx=14, fill="#FFFFFF", stroke="#E2E7EE")
    s.text(24, 664, "쿠버네티스 판에서 바뀐 것", 12.5, 700)
    s.text(24 + tw("쿠버네티스 판에서 바뀐 것", 12.5) + 10, 664, "앱 코드는 그대로 · 띄우는 방식만", 10.5, 400, SUB)
    rows = [
        ["Ingress → Caddy", "NetworkPolicy 12장 → 네트워크 8개", "CronJob → 수집 타이머", "Job → 마이그레이션 컨테이너"],
        ["Secret → .env · secrets.env", "Deployment 2개씩 → 컨테이너 1개씩", "Prometheus · Grafana 추가"],
    ]
    for r, chips in enumerate(rows):
        x = 24.0
        for c in chips:
            x += s.chip(x, 674 + r * 25, c) + 6
    return s


def main() -> int:
    fig = build()
    svg, png = HERE / "architecture-compose.svg", HERE / "architecture-compose.png"
    svg.write_text(fig.render(), encoding="utf-8")
    exe = next((c for c in CHROME if Path(c).exists()), None)
    if not exe:
        print("SVG만 만들었습니다(Chrome이 없어 PNG는 건너뜀):", svg.name)
        return 0
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--window-size={fig.w},{fig.h}", f"--screenshot={png}", svg.as_uri()], capture_output=True, text=True, timeout=120)
    ok = png.exists() and png.stat().st_size > 10_000
    print("svg:", svg.name, "| png:", png.name, "| ok:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
