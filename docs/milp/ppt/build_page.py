"""README.md → report.html (팀 공유용 페이지). 그림은 figures/, 장별 캡처는 slides/를 상대 경로로 읽는다.

    python3 docs/milp/ppt/build_page.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent


def main():
    md = (HERE / "README.md").read_text(encoding="utf-8")
    body = md.split("\n", 1)[1]                                   # 맨 위 제목은 머리띠로 따로 그린다
    html = markdown.markdown(body, extensions=["tables", "fenced_code"], output_format="html")

    def link(m):                                                  # 페이지에 함께 올리는 것(figures/, slides/)만 링크로 남긴다
        href, text = m.group(1), m.group(2)
        if href.startswith(("figures/", "slides/", "http")):
            return f'<a href="{href}">{text}</a>'
        return text
    html = re.sub(r'<a href="([^"]+)">(.*?)</a>', link, html)
    html = html.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    html = re.sub(r'<p><img alt="([^"]*)" src="([^"]+)"\s*/?></p>', r'<figure><img alt="\1" src="\2"><figcaption>\1</figcaption></figure>', html)
    html = html.replace("<pre><code", '<pre tabindex="0"><code')

    r = json.loads((HERE / "out" / "SAMPLE-W46.response.json").read_text(encoding="utf-8"))
    c1, base = r["candidates"][0]["total_usd"], r["baseline"]["total_usd"]
    tiles = [("1안 총 예상 체선료", f"${c1:,.2f}", "샘플 주간 54건 · 규칙 위반 0"),
             ("기준안 대비", f"−${base - c1:,.2f}", f"−{(base - c1) / base:.1%} · 기준안 ${base:,.2f}"),
             ("최적화 범위", "전체", "부두별 합이 아니라 모든 입항 건의 합"),
             ("본체 식 변경", "0줄", "PPT 규칙은 모두 입력값으로")]
    tiles_html = "".join(f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{s}</div></div>' for k, v, s in tiles)

    page = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPT 기준 수리계획법 최종본</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{
  /* 한 가지 밝은 세계: 그림(PNG)과 같은 회청 바탕 · 흰 카드 · 청록 강조. 글은 가운데 한 줄기, 그림·표만 넓게 */
  --ink: #0E1726; --sub: #344054; --muted: #667085; --line: #E2E7EE; --bg: #F6F8FB; --card: #FFFFFF;
  --accent: #0B8B7B; --accent-tint: #E3F4F1; --blue: #1B5FD9; --amber: #B26A00; --amber-tint: #FFF4DF;
  --font-body: "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  --font-display: "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
  color-scheme: light;
}}
* {{ box-sizing: border-box; }}
html {{ background: var(--bg); }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: 15.5px; line-height: 1.72; }}
.wrap {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 72px; }}
header {{ display: grid; gap: 10px; padding: 8px 0 22px; border-bottom: 1px solid var(--line); margin-bottom: 26px; }}
header .eyebrow {{ color: var(--accent); font-weight: 700; font-size: 13px; letter-spacing: .02em; }}
header h1 {{ font-family: var(--font-display); font-size: 30px; line-height: 1.3; margin: 0; text-wrap: balance; }}
header p {{ margin: 0; color: var(--muted); font-size: 14px; }}
.tiles {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 0 0 28px; }}
.tile {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; display: grid; gap: 2px; }}
.tile .k {{ color: var(--muted); font-size: 12.5px; font-weight: 500; }}
.tile .v {{ font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--ink); }}
.tile .s {{ color: var(--sub); font-size: 12.5px; }}
main > * {{ max-width: 780px; }}
main > figure, main > .tw, main > pre {{ max-width: none; }}
h2 {{ font-family: var(--font-display); font-size: 22px; margin: 48px 0 12px; padding-top: 18px; border-top: 1px solid var(--line); text-wrap: balance; }}
h3 {{ font-size: 17.5px; margin: 30px 0 8px; text-wrap: balance; }}
p, li {{ color: var(--sub); }}
strong {{ color: var(--ink); }}
a {{ color: var(--blue); text-underline-offset: 3px; }}
a:focus-visible, pre:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
ul, ol {{ padding-left: 22px; display: grid; gap: 4px; }}
code {{ font-family: var(--font-mono); font-size: .88em; background: #EEF2F7; padding: 1px 5px; border-radius: 5px; color: var(--ink); }}
pre {{ background: #0F1A2A; color: #E6EDF6; border-radius: 12px; padding: 16px 18px; overflow-x: auto; font-size: 13px; line-height: 1.6; }}
pre code {{ background: none; padding: 0; color: inherit; font-size: inherit; }}
.tw {{ overflow-x: auto; background: var(--card); border: 1px solid var(--line); border-radius: 12px; margin: 14px 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); vertical-align: top; color: var(--sub); }}
th {{ color: var(--ink); background: #F8FAFC; font-weight: 700; white-space: nowrap; }}
tr:last-child td {{ border-bottom: none; }}
td[style*="right"], th[style*="right"] {{ white-space: nowrap; }}
img {{ max-width: 100%; height: auto; }}
figure {{ margin: 18px 0 8px; display: grid; gap: 8px; }}
figure img {{ max-width: 100%; height: auto; border-radius: 12px; border: 1px solid var(--line); background: var(--card); }}
figcaption {{ color: var(--muted); font-size: 13px; }}
footer {{ margin-top: 56px; color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); padding-top: 16px; }}
@media (max-width: 760px) {{
  .tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  header h1 {{ font-size: 24px; }}
  body {{ font-size: 15px; }}
}}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto; }} }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">SKALA 4기 최종 프로젝트 · 체선료 · 2026-11-12</div>
  <h1>멘토링 PPT 기준 수리계획법 — 최종 식 · 적용 · 결과</h1>
  <p>원본: 현업 멘토링 PPT 13장 · Sample data.xlsx · 팀 최종본 본체 식 (1)~(8). 금액은 샘플 엑셀과 [가정] 값으로 낸 것이다.</p>
</header>
<section class="tiles" aria-label="요약 숫자">{tiles_html}</section>
<main>
{html}
</main>
<footer>docs/milp/ppt/README.md에서 만든 페이지 · 코드와 결과 JSON은 저장소의 docs/milp/ppt/에 있다.</footer>
</div>
</body>
</html>
"""
    (HERE / "report.html").write_text(page, encoding="utf-8")
    print("report.html", len(page))


if __name__ == "__main__":
    main()
