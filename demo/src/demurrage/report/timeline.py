"""부두별 타임라인 SVG (FR-37) — 화면과 보고서가 같은 그림을 쓴다(구현 한 곳).

행 = 부두, 가로 = 시간. 선박마다 대기(점선) → 접안·준비 → 작업 → 호스분리 → 이안 준비 막대,
체선 구간(정박종료 ~ 호스분리)은 막대 아래 빨간 줄. 야간·기상 제한·정비 구간은 배경 띠.
색만으로 구별하지 않도록 막대 안·범례에 글자 라벨을 단다. 선박 묶음에는 data-vessel 속성을 달아 화면에서 누르면 근거가 열린다.
"""
from __future__ import annotations

from html import escape

from ..domain.timeutil import DAY, HOUR, day_start, fmt

ROW_H = 58
LEFT = 74
TOP = 34
WIDTH = 1180

COLORS = {
    "work": "#2f6fd6", "work_fixed": "#6b7a90", "prep": "#a9c4f2", "hose": "#14a3a3", "unberth": "#c9d3e0",
    "wait": "#8a94a6", "demurrage": "#d93a3a", "night": "#eef1f7", "WEATHER": "#f6a03c", "MAINTENANCE": "#c0392b", "USER": "#7d3cc0",
}


def _x(t, t0, span):
    return LEFT + (t - t0) / span * (WIDTH - LEFT - 16)


def render_svg(ctx, sch, title: str = "", t_range=None) -> str:
    pl = sch.state.pl
    calcs = sch.calcs
    berths = [b for b in ctx.berth_order if b in ctx.sc.active_berths or any(p.berth == b for p in pl.values())]
    if t_range:
        t0, t1 = t_range
    else:
        t0 = day_start(min([ctx.vessels[v].eta for v in pl] + [ctx.sc.horizon_start]))
        t1 = max([p.etu for p in pl.values()] + [ctx.sc.horizon_start + DAY])
        t1 = day_start(t1) + DAY
    span = t1 - t0
    h = TOP + ROW_H * len(berths) + 70
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {h}" width="100%" font-family="Noto Sans KR, Apple SD Gothic Neo, sans-serif" font-size="11" role="img" aria-label="{escape(title or sch.label)} 부두별 타임라인">',
           '<defs><pattern id="hatchW" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="3" height="6" fill="#f6a03c" fill-opacity="0.45"/></pattern>'
           '<pattern id="hatchM" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="3" height="6" fill="#c0392b" fill-opacity="0.35"/></pattern>'
           '<pattern id="hatchU" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="3" height="6" fill="#7d3cc0" fill-opacity="0.35"/></pattern></defs>']
    if title:
        out.append(f'<text x="{LEFT}" y="16" font-size="13" font-weight="700" fill="#1d2433">{escape(title)}</text>')
    # 야간 띠(일몰~일출)
    d = day_start(t0) - DAY
    while d < t1:
        _, sset = ctx.sun.get(d)
        rise_next, _ = ctx.sun.get(d + DAY)
        a, b = max(sset, t0), min(rise_next, t1)
        if b > a:
            out.append(f'<rect x="{_x(a, t0, span):.1f}" y="{TOP}" width="{_x(b, t0, span) - _x(a, t0, span):.1f}" height="{ROW_H * len(berths)}" fill="{COLORS["night"]}"/>')
        d += DAY
    # 시간 눈금(6시간), 날짜
    t = day_start(t0)
    while t <= t1:
        x = _x(t, t0, span)
        major = (t % DAY == 0)
        out.append(f'<line x1="{x:.1f}" y1="{TOP - 4}" x2="{x:.1f}" y2="{TOP + ROW_H * len(berths)}" stroke="{"#b8c2d3" if major else "#e1e6ef"}" stroke-width="{1.2 if major else 0.8}"/>')
        label = fmt(t)[:5] if major else fmt(t)[6:8] + "시"
        out.append(f'<text x="{x + 2:.1f}" y="{TOP - 7}" fill="#5b6475" font-weight="{700 if major else 400}">{label}</text>')
        t += 6 * HOUR
    for i, bid in enumerate(berths):
        y = TOP + i * ROW_H
        out.append(f'<line x1="{LEFT}" y1="{y + ROW_H}" x2="{WIDTH - 16}" y2="{y + ROW_H}" stroke="#d5dbe6"/>')
        b = ctx.berths[bid]
        out.append(f'<text x="8" y="{y + 24}" font-weight="700" fill="#1d2433">{escape(bid)}</text>')
        out.append(f'<text x="8" y="{y + 39}" fill="#6b7385" font-size="9.5">D{b.direction / 60:g}·S{b.switching / 60:g}h</text>')
        # 제한 띠
        for r in ctx.restr_by_berth.get(bid, []):
            a, bb = max(r.start, t0), min(r.end, t1)
            if bb <= a:
                continue
            fill = {"WEATHER": "url(#hatchW)", "MAINTENANCE": "url(#hatchM)"}.get(r.reason, "url(#hatchU)")
            lab = {"WEATHER": "기상 제한", "MAINTENANCE": "정비 제한"}.get(r.reason, "부두 제한")
            out.append(f'<rect x="{_x(a, t0, span):.1f}" y="{y + 1}" width="{_x(bb, t0, span) - _x(a, t0, span):.1f}" height="{ROW_H - 2}" fill="{fill}"><title>{escape(lab)} {fmt(r.start)}~{fmt(r.end)} {escape(r.note)}</title></rect>')
            out.append(f'<text x="{_x(a, t0, span) + 3:.1f}" y="{y + ROW_H - 4}" font-size="9" fill="{COLORS[r.reason] if r.reason in COLORS else "#7d3cc0"}">{lab}</text>')
    # 선박
    for vid, p in sorted(pl.items(), key=lambda kv: kv[1].etb):
        i = berths.index(p.berth)
        y = TOP + i * ROW_H
        c = calcs[vid]
        v = ctx.vessels[vid]
        X = lambda tt: _x(min(max(tt, t0), t1), t0, span)  # noqa: E731
        fixed = p.kind != "MOVABLE"
        amt = c["amount_cents"]
        tip = (f"{vid} {v.name} | {p.berth} | ETA {fmt(v.eta)} ETB {fmt(p.etb)} 작업 {fmt(p.work_start)}~{fmt(p.work_end)} "
               f"호스분리 {fmt(p.hose_off)} ETU {fmt(p.etu)} | 체선료 ${amt / 100:,.0f}")
        out.append(f'<g class="vessel" data-vessel="{escape(vid)}" style="cursor:pointer"><title>{escape(tip)}</title>')
        if p.etb > v.eta:
            out.append(f'<line x1="{X(v.eta):.1f}" y1="{y + 11}" x2="{X(p.etb):.1f}" y2="{y + 11}" stroke="{COLORS["wait"]}" stroke-width="1.6" stroke-dasharray="4 3"/>')
            out.append(f'<circle cx="{X(v.eta):.1f}" cy="{y + 11}" r="2.6" fill="{COLORS["wait"]}"/>')
            if X(p.etb) - X(v.eta) > 36:
                out.append(f'<text x="{X(v.eta) + 4:.1f}" y="{y + 8}" font-size="9" fill="#5b6475">대기</text>')
        segs = [(p.etb, p.work_start, COLORS["prep"], "준비"),
                (p.work_start, p.work_end, COLORS["work_fixed"] if fixed else COLORS["work"], "작업"),
                (p.work_end, p.hose_off, COLORS["hose"], "호스"),
                (p.hose_off, p.etu, COLORS["unberth"], "이안")]
        for a, bb, col, lab in segs:
            if bb <= a:
                continue
            out.append(f'<rect x="{X(a):.1f}" y="{y + 16}" width="{max(X(bb) - X(a), 0.8):.1f}" height="22" fill="{col}" rx="2"/>')
        wx0, wx1 = X(p.work_start), X(p.work_end)
        label = f"{vid}{' FIX' if p.kind == 'FIX' else (' 작업중' if p.kind == 'WORKING' else '')}"
        if amt:
            label += f" ${amt / 100:,.0f}"
        if wx1 - wx0 > 42:
            out.append(f'<text x="{wx0 + 4:.1f}" y="{y + 31}" fill="#ffffff" font-weight="700">{escape(label)}</text>')
        else:
            out.append(f'<text x="{X(p.etb):.1f}" y="{y + 50}" fill="#1d2433" font-weight="700" font-size="10">{escape(label)}</text>')
        if c["demurrage_raw_minutes"] > 0:
            a = c["laytime_end"]
            out.append(f'<rect x="{X(a):.1f}" y="{y + 41}" width="{max(X(p.hose_off) - X(a), 1):.1f}" height="4" fill="{COLORS["demurrage"]}"/>')
        out.append("</g>")
    # 범례
    ly = TOP + ROW_H * len(berths) + 22
    legend = [("대기(ETA→ETB)", "wait", "line"), ("접안·준비", "prep", "rect"), ("작업", "work", "rect"), ("고정·작업 중 선박", "work_fixed", "rect"),
              ("호스분리", "hose", "rect"), ("이안 준비", "unberth", "rect"), ("체선 구간", "demurrage", "rect"), ("야간", "night", "rect"),
              ("기상 제한", "hatchW", "pat"), ("정비 제한", "hatchM", "pat")]
    x = LEFT
    for lab, key, kind in legend:
        if kind == "line":
            out.append(f'<line x1="{x}" y1="{ly}" x2="{x + 18}" y2="{ly}" stroke="{COLORS[key]}" stroke-width="1.6" stroke-dasharray="4 3"/>')
        elif kind == "pat":
            out.append(f'<rect x="{x}" y="{ly - 6}" width="18" height="12" fill="url(#{key})" stroke="#c9d0dc"/>')
        else:
            out.append(f'<rect x="{x}" y="{ly - 6}" width="18" height="12" fill="{COLORS[key]}" stroke="#c9d0dc"/>')
        out.append(f'<text x="{x + 22}" y="{ly + 4}" fill="#3b4354">{lab}</text>')
        x += 24 + len(lab) * 10.5
    out.append(f'<text x="{LEFT}" y="{ly + 24}" fill="#6b7385" font-size="10">D = Direction, S = Switching(시간). 막대에 마우스를 올리면 시각, 누르면 산출 근거. 가상 데이터 · 의사결정 보조용</text>')
    out.append("</svg>")
    return "\n".join(out)
