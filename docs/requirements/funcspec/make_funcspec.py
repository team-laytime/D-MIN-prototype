#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기능명세서 생성기 (표준 라이브러리만).

spec_data.py → ① funcspec-board.html (피그마에 넣는 보드의 원본) ② ../14-functional-spec.md (글로 된 명세서)

  python3 docs/requirements/funcspec/make_funcspec.py

보드는 16개다: 머리·읽는 법 / 업무 단계 한 줄 / 계산 한 번의 안쪽 / 그룹 G1~G10 / 용어 / 비기능 / 확인할 것.
줄바꿈은 브라우저에서 한 번 계산해 <br>로 굳힌다(bake). 피그마는 한글을 글자 단위로 끊기 때문이다.
"""
from __future__ import annotations

import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_data as D  # noqa: E402

D.check()
esc = html.escape

AR = ('<svg width="44" height="24" viewBox="0 0 44 24" fill="none"><path d="M3 12H40M30 4L40 12L30 20" '
      'stroke="#98A2B3" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>')
AR_BIG = ('<svg width="84" height="40" viewBox="0 0 84 40" fill="none"><path d="M4 20H78M60 5L78 20L60 35" '
          'stroke="#667085" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>')
AR_DOWN = ('<svg width="24" height="40" viewBox="0 0 24 40" fill="none"><path d="M12 3V36M4 26L12 36L20 26" '
           'stroke="#98A2B3" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>')

CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#FFFFFF}
body{font-family:'Noto Sans KR',sans-serif;color:#0E1726;font-size:28px;line-height:42px;font-weight:400}
.w{word-break:keep-all;overflow-wrap:normal}
.en{font-family:'Inter',sans-serif}
.canvas{width:30392px;padding:220px;display:flex;flex-direction:column;gap:160px}
.row{display:flex;gap:80px;align-items:flex-start}
.board{background:#F6F8FB;border-radius:56px;padding:64px;display:flex;flex-direction:column;gap:44px;flex:none}

/* 판 머리 */
.bh{display:flex;align-items:flex-start;gap:28px}
.gno{font-family:'Inter',sans-serif;font-weight:700;font-size:40px;line-height:76px;height:76px;padding:0 24px;border-radius:20px;background:#0E1726;color:#FFFFFF;flex:none;white-space:nowrap}
.bhx{flex:1;min-width:0;display:flex;flex-direction:column;gap:14px}
.bt{font-size:64px;line-height:76px;font-weight:700;white-space:nowrap}
.bs{font-size:30px;line-height:46px;color:#475467}
.bm{display:flex;flex-wrap:wrap;gap:12px}
.meta{font-size:24px;line-height:40px;padding:0 20px;border-radius:20px;background:#FFFFFF;border:2px solid #E2E7EE;color:#344054;white-space:nowrap}
.sec{font-size:26px;line-height:36px;font-weight:700;color:#667085;white-space:nowrap}

/* 흐름 */
.flow{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:32px;padding:36px 40px 40px;display:flex;flex-direction:column;gap:32px}
.lane{display:flex;flex-direction:column;gap:14px}
.ln{font-size:24px;line-height:34px;font-weight:700;color:#667085;white-space:nowrap}
.steps{display:flex;align-items:flex-start}
.st{flex:none;display:flex;flex-direction:column;gap:10px}
.sb{height:212px;border-radius:20px;padding:16px 18px 14px;display:flex;flex-direction:column;justify-content:space-between;border:2px solid #B2CCFF;background:#EEF4FF}
.sbt{display:flex;flex-direction:column;gap:8px}
.stop{display:flex;align-items:center;gap:10px}
.sn{font-family:'Inter',sans-serif;font-weight:700;font-size:21px;width:36px;height:36px;line-height:36px;border-radius:18px;text-align:center;flex:none;background:#2F6FED;color:#FFFFFF}
.swho{font-size:20px;line-height:30px;font-weight:700;color:#1D4ED8;white-space:nowrap}
.stt{font-size:25px;line-height:33px;font-weight:700}
.sfr{font-family:'Inter',sans-serif;font-size:20px;line-height:28px;font-weight:500;color:#475467;white-space:nowrap}
.sb.hu{background:#0E1726;border-color:#0E1726;color:#FFFFFF}
.sb.hu .sn{background:#FFFFFF;color:#0E1726}.sb.hu .swho{color:#B2CCFF}.sb.hu .sfr{color:#D0D5DD}
.sb.llm{background:#F3F0FF;border-color:#C9BDF5}.sb.llm .sn{background:#6E56CF}.sb.llm .swho{color:#5B45B8}
.sb.ext{background:#E6F7F4;border-color:#99D8CC}.sb.ext .sn{background:#0E9384}.sb.ext .swho{color:#0E7A6B}
.sb.out{background:#ECFDF3;border-color:#A6E3BF}.sb.out .swho{color:#067647}
.ar{flex:none;width:56px;height:212px;display:flex;align-items:center;justify-content:center}
.br{font-size:21px;line-height:30px;border-radius:14px;padding:8px 12px}
.br.a{background:#FFF4DF;color:#93370D}
.br.x{background:#FEE4E2;color:#912018}
.flow.wide .sb{height:156px}
.flow.wide .ar{height:156px}

/* 기능 카드 */
.cards{display:grid;gap:40px;align-items:stretch}
.cards.c1{grid-template-columns:1800px}
.cards.c2{grid-template-columns:1800px 1800px}
.cards.c3{grid-template-columns:1800px 1800px 1800px}
.card{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:32px;padding:40px 44px 44px;display:flex;flex-direction:column;gap:26px}
.ch{display:flex;align-items:center;gap:16px}
.fid{font-family:'Inter',sans-serif;font-weight:700;font-size:28px;line-height:50px;height:50px;padding:0 18px;border-radius:14px;background:#0E1726;color:#FFFFFF;flex:none;white-space:nowrap}
.cn{font-size:38px;line-height:50px;font-weight:700;flex:1;min-width:0;white-space:nowrap}
.tags{display:flex;gap:10px;flex:none}
.tg{font-size:21px;line-height:38px;height:38px;font-weight:700;padding:0 14px;border-radius:19px;white-space:nowrap}
.tg.must{background:#2F6FED;color:#FFFFFF}
.tg.should{background:#EEF4FF;color:#1D4ED8}
.tg.could{background:#F2F4F7;color:#667085}
.tg.who{background:#0E1726;color:#FFFFFF}
.tg.sys{background:#EEF4FF;color:#1D4ED8}
.tg.llm{background:#F3F0FF;color:#5B45B8}
.tg.ext{background:#E6F7F4;color:#0E7A6B}
.tg.uc{background:#FFFFFF;color:#667085;border:2px solid #E2E7EE;font-family:'Inter',sans-serif;line-height:34px}
.what{font-size:29px;line-height:44px;color:#344054}
.rows{display:flex;flex-direction:column}
.r{display:flex;gap:26px}
.rl{flex:none;width:118px;display:flex;flex-direction:column;align-items:center}
.pl{width:118px;height:42px;text-align:center;font-size:23px;line-height:42px;font-weight:700;border-radius:12px;white-space:nowrap}
.pl.i{background:#EEF2F6;color:#475467}.pl.p{background:#E8F0FF;color:#1D4ED8}.pl.o{background:#E3F6EC;color:#067647}
.rail{flex:1;width:4px;background:#D5DBE5;min-height:14px}
.rc{flex:1;min-width:0;padding-bottom:26px;display:flex;flex-direction:column;gap:6px}
.rc.last{padding-bottom:0}
.li{display:flex;gap:14px}
.no{flex:none;width:36px;font-family:'Inter',sans-serif;font-weight:700;font-size:24px;line-height:42px;color:#2F6FED}
.dot{flex:none;width:36px;height:42px;display:flex;align-items:center}
.dot i{display:block;width:10px;height:10px;border-radius:5px;background:#98A2B3;margin-left:6px}
.tx{flex:1;min-width:0}
.bx{display:flex;gap:14px;border-radius:14px;padding:8px 16px;font-size:25px;line-height:38px}
.bx.a{background:#FFF4DF;color:#93370D}.bx.x{background:#FEE4E2;color:#912018}
.bxt{flex:none;font-weight:700;white-space:nowrap;width:86px}
.foot{display:flex;flex-direction:column;gap:12px;border-top:2px solid #EEF1F5;padding-top:24px}
.fr{display:flex;gap:26px;font-size:25px;line-height:38px}
.fl{flex:none;width:118px;font-weight:700;color:#5B45B8;white-space:nowrap}
.fl.rel{color:#667085}
.frt{flex:1;min-width:0;color:#344054}

/* 머리 판 */
.cols{display:flex;gap:28px;align-items:stretch}
.title{font-size:168px;line-height:190px;font-weight:700;white-space:nowrap}
.sub{font-size:52px;line-height:70px;font-weight:500;color:#344054;white-space:nowrap}
.facts{display:flex;flex-wrap:wrap;gap:16px}
.fact{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:24px;padding:18px 26px;display:flex;flex-direction:column;gap:2px}
.fk{font-size:22px;line-height:32px;color:#667085;white-space:nowrap}
.fv{font-size:32px;line-height:44px;font-weight:700;white-space:nowrap}
.panel{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:32px;padding:36px 40px;display:flex;flex-direction:column;gap:20px}
.ph{font-size:34px;line-height:46px;font-weight:700;white-space:nowrap}
.lg{display:flex;align-items:center;gap:20px}
.lgk{flex:none;display:flex;gap:10px;align-items:center;width:440px}
.lgv{flex:1;min-width:0;font-size:27px;line-height:40px;color:#344054}
.order{display:flex;align-items:stretch;gap:0}
.ob{flex:none;background:#F6F8FB;border-radius:20px;padding:20px 24px;display:flex;flex-direction:column;gap:6px}
.obn{font-family:'Inter',sans-serif;font-weight:700;font-size:26px;line-height:36px;color:#2F6FED}
.obt{font-size:30px;line-height:42px;font-weight:700;white-space:nowrap}
.obd{font-size:24px;line-height:36px;color:#475467}
.oar{flex:none;width:64px;display:flex;align-items:center;justify-content:center}
.swatch{width:54px;height:38px;border-radius:10px;border:2px solid #B2CCFF;background:#EEF4FF;flex:none}

/* 업무 단계 한 줄 */
.stages{display:flex;align-items:stretch}
.stg{display:flex;flex-direction:column;gap:16px}
.stn{height:60px;border-radius:16px;background:#0E1726;color:#FFFFFF;font-size:30px;line-height:60px;font-weight:700;text-align:center;white-space:nowrap}
.stb{display:flex;align-items:stretch;flex:1}
.gb{width:760px;background:#FFFFFF;border:2px solid #E2E7EE;border-radius:28px;padding:28px 30px 30px;display:flex;flex-direction:column;gap:18px}
.gb.wide{width:1440px}
.gbh{display:flex;align-items:center;gap:14px}
.gbn{font-family:'Inter',sans-serif;font-weight:700;font-size:26px;line-height:44px;height:44px;padding:0 14px;border-radius:12px;background:#0E1726;color:#FFFFFF;white-space:nowrap}
.gbt{font-size:32px;line-height:44px;font-weight:700;white-space:nowrap}
.gbw{font-size:23px;line-height:34px;color:#475467}
.chips{display:grid;gap:8px 16px;grid-template-columns:1fr}
.gb.wide .chips{grid-template-columns:1fr 1fr}
.chip{display:flex;align-items:center;gap:12px;height:46px;border-radius:12px;background:#F6F8FB;padding:0 14px}
.pd{flex:none;width:16px;height:16px;border-radius:8px;background:#2F6FED}
.pd.should{background:#FFFFFF;border:4px solid #2F6FED}
.pd.could{background:#FFFFFF;border:4px solid #98A2B3}
.cid{font-family:'Inter',sans-serif;font-weight:700;font-size:21px;line-height:46px;color:#344054;white-space:nowrap;flex:none;width:68px}
.cnm{font-size:23px;line-height:46px;white-space:nowrap}
.hand{border-top:2px solid #EEF1F5;padding-top:16px;display:flex;flex-direction:column;gap:4px;margin-top:4px}
.hk{font-size:21px;line-height:30px;font-weight:700;color:#067647;white-space:nowrap}
.hv{font-size:24px;line-height:36px;color:#344054}
.gate{flex:none;width:250px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:0 14px}
.gate.in{width:110px;padding:0}
.gtx{font-size:21px;line-height:30px;color:#93370D;background:#FFF4DF;border-radius:12px;padding:8px 12px;text-align:center}
.common{background:#0E1726;color:#FFFFFF;border-radius:24px;padding:22px 32px;display:flex;align-items:center;gap:22px}
.common .fid{background:#FFFFFF;color:#0E1726}
.cmt{font-size:28px;line-height:42px}

/* 계산 한 번의 안쪽 */
.eng{display:flex;align-items:stretch}
.eg{display:flex;flex-direction:column;gap:14px}
.egn{font-size:24px;line-height:34px;font-weight:700;color:#667085;white-space:nowrap;height:34px}
.egb{display:flex;align-items:center;flex:1}
.loop{border:4px dashed #2F6FED;border-radius:32px;padding:26px 26px 30px;background:#F7FAFF;display:flex;flex-direction:column;gap:18px}
.lph{display:flex;align-items:center;gap:16px}
.lpt{font-size:30px;line-height:42px;font-weight:700;color:#1D4ED8;white-space:nowrap}
.lpd{font-size:25px;line-height:38px;color:#475467}
.es{width:470px;height:262px;border-radius:20px;border:2px solid #B2CCFF;background:#EEF4FF;padding:18px 20px 16px;display:flex;flex-direction:column;justify-content:space-between;flex:none}
.es.g{background:#ECFDF3;border-color:#A6E3BF}
.es.r{background:#FEF3F2;border-color:#FDA29B}
.est{font-size:32px;line-height:44px;font-weight:700}
.esn{font-size:25px;line-height:38px;color:#475467}
.esf{font-family:'Inter',sans-serif;font-size:22px;line-height:32px;font-weight:600;color:#1D4ED8;white-space:nowrap}
.ea{flex:none;width:52px;display:flex;align-items:center;justify-content:center}
.formula{background:#0E1726;color:#FFFFFF;border-radius:24px;padding:26px 34px;display:flex;flex-direction:column;gap:8px}
.fml{font-size:36px;line-height:52px;font-weight:700;white-space:nowrap}
.fmn{font-size:25px;line-height:38px;color:#D0D5DD}

/* 접안 가능시각 여섯 가지 */
.six{display:flex;align-items:center;gap:0}
.sixl{flex:1;min-width:0;display:flex;flex-direction:column;gap:10px}
.sx{display:flex;align-items:center;gap:18px;background:#F6F8FB;border-radius:16px;padding:10px 20px}
.sxn{flex:none;width:300px;font-size:27px;line-height:40px;font-weight:700;white-space:nowrap}
.sxf{flex:1;min-width:0;font-size:26px;line-height:40px;color:#344054;white-space:nowrap}
.sixa{flex:none;width:150px;display:flex;align-items:center;justify-content:center}
.sixr{flex:none;width:1080px;display:flex;flex-direction:column;gap:16px}
.etb{background:#0E1726;color:#FFFFFF;border-radius:24px;padding:28px 32px;display:flex;flex-direction:column;gap:10px}
.etbt{font-size:38px;line-height:52px;font-weight:700;white-space:nowrap}
.etbd{font-size:25px;line-height:38px;color:#D0D5DD}
.no2{background:#FEF3F2;border:2px solid #FDA29B;border-radius:24px;padding:22px 28px;display:flex;flex-direction:column;gap:6px}
.no2t{font-size:28px;line-height:40px;font-weight:700;color:#912018;white-space:nowrap}
.no2d{font-size:25px;line-height:38px;color:#7A271A}

/* 시간축 */
.tl{display:flex;flex-direction:column;gap:10px}
.tlr{display:flex;align-items:stretch}
.tlk{flex:none;width:250px;font-size:24px;line-height:34px;font-weight:700;color:#667085;display:flex;align-items:center;white-space:nowrap}
.tlt{flex:none;display:flex}
.seg{flex:none;height:64px;display:flex;align-items:center;justify-content:center;font-size:24px;line-height:34px;font-weight:700;white-space:nowrap;overflow:hidden}
.mk{flex:none;display:flex;flex-direction:column;gap:2px;border-left:4px solid #0E1726;padding-left:12px;overflow:visible}
.mkt{font-size:25px;line-height:34px;font-weight:700;white-space:nowrap}
.mkd{font-size:21px;line-height:30px;color:#475467;white-space:nowrap}

/* 아래 줄: 용어 · 비기능 · 확인할 것 */
.grid{display:grid;gap:24px}
.term{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:24px;padding:24px 28px;display:flex;flex-direction:column;gap:8px}
.tk{font-size:30px;line-height:42px;font-weight:700;white-space:nowrap}
.tv{font-size:25px;line-height:38px;color:#344054}
.nf{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:24px;padding:26px 28px 28px;display:flex;flex-direction:column;gap:12px}
.nfh{display:flex;align-items:center;gap:12px}
.nfn{font-size:30px;line-height:44px;font-weight:700;white-space:nowrap;flex:1;min-width:0}
.nfd{font-size:25px;line-height:38px;color:#344054}
.nfk{font-size:21px;line-height:30px;font-weight:700;color:#5B45B8;white-space:nowrap;margin-top:4px}
.nfk.rel{color:#667085}
.nfv{font-size:24px;line-height:36px;color:#344054}
.oq{background:#FFFFFF;border:2px solid #FEDF89;border-radius:24px;padding:26px 28px 28px;display:flex;flex-direction:column;gap:10px}
.oqh{display:flex;gap:14px;align-items:flex-start}
.oqn{flex:none;font-family:'Inter',sans-serif;font-weight:700;font-size:24px;line-height:44px;width:44px;height:44px;border-radius:22px;background:#B54708;color:#FFFFFF;text-align:center}
.oqt{flex:1;min-width:0;font-size:30px;line-height:44px;font-weight:700}
.oqd{font-size:25px;line-height:38px;color:#344054}
"""

WHO_STEP = {"sch": ("hu", "선박 스케줄러"), "adm": ("hu", "기준 정보 관리자"), "qa": ("hu", "검증 담당자"),
            "sys": ("", "시스템"), "llm": ("llm", "LLM"), "ext": ("ext", "공공데이터포털"), "out": ("out", "넘어가는 것")}
PRI_CLS = {"Must": "must", "Should": "should", "Could": "could"}


def W(text, cls):
    return f'<div class="w {cls}">{esc(text)}</div>'


def card(fid):
    f = D.FN[fid]
    tags = [f'<span class="tg {PRI_CLS[f["p"]]}">{f["p"]}</span>']
    if f["who"] == "sys":
        tags.append('<span class="tg sys">시스템</span>')
    else:
        tags.append(f'<span class="tg who">{D.WHO[f["who"]]}</span>')
    if "view" in f["tag"]:
        tags.append('<span class="tg who">체선 지불 부서</span>')
    if "llm" in f["tag"]:
        tags.append('<span class="tg llm">LLM</span>')
    if "ext" in f["tag"]:
        tags.append('<span class="tg ext">외부 API</span>')
    tags.append(f'<span class="tg uc">{esc(f["uc"])}</span>')

    def bullets(items):
        return "".join(f'<div class="li"><div class="dot"><i></i></div>{W(t, "tx")}</div>' for t in items)

    steps = "".join(f'<div class="li"><div class="no">{i}</div>{W(t, "tx")}</div>' for i, t in enumerate(f["proc"], 1))
    alts = "".join(f'<div class="bx {k}"><div class="bxt">{"다른 길" if k == "a" else "멈춤"}</div>{W(t, "tx")}</div>'
                   for k, t in f["alt"])
    rows = (
        f'<div class="r"><div class="rl"><div class="pl i">입력</div><div class="rail"></div></div><div class="rc">{bullets(f["inp"])}</div></div>'
        f'<div class="r"><div class="rl"><div class="pl p">처리</div><div class="rail"></div></div><div class="rc">{steps}{alts}</div></div>'
        f'<div class="r"><div class="rl"><div class="pl o">출력</div></div><div class="rc last">{bullets(f["out"])}</div></div>'
    )
    foot = f'<div class="fr"><div class="fl">완료 기준</div>{W(f["done"], "frt")}</div>'
    if f["rel"]:
        foot += f'<div class="fr"><div class="fl rel">관련</div>{W(f["rel"], "frt")}</div>'
    return (f'<article class="card" data-fr="{fid}"><div class="ch"><div class="fid">{fid}</div><div class="cn">{esc(f["n"])}</div>'
            f'<div class="tags">{"".join(tags)}</div></div>{W(f["what"], "what")}<div class="rows">{rows}</div>'
            f'<div class="foot">{foot}</div></article>')


def flow(g, inner):
    lanes = []
    for name, steps in g["flow"]:
        cells = []
        n = 0
        sw = (inner - 56 * (len(steps) - 1)) // len(steps)
        for i, s in enumerate(steps):
            cls, who = WHO_STEP[s["who"]]
            if s["who"] == "out":
                badge = ""
            else:
                n += 1
                badge = f'<div class="sn">{n}</div>'
            brs = "".join(W(("다른 길 · " if k == "a" else "멈춤 · ") + t, f"br {k}") for k, t in s.get("br", ()))
            cells.append(
                f'<div class="st" style="width:{sw}px"><div class="sb {cls}"><div class="sbt"><div class="stop">{badge}<div class="swho">{who}</div></div>'
                f'{W(s["t"], "stt")}</div><div class="sfr">{esc(s["fr"])}</div></div>{brs}</div>')
            if i < len(steps) - 1:
                cells.append(f'<div class="ar">{AR}</div>')
        lanes.append(f'<div class="lane"><div class="ln">{esc(name)}</div><div class="steps">{"".join(cells)}</div></div>')
    return f'<div class="flow{" wide" if g["cols"] > 1 else ""}">{"".join(lanes)}</div>'


def six_block():
    rows = "".join(f'<div class="sx"><div class="fid">{fid}</div><div class="sxn">{esc(n)}</div><div class="sxf">{esc(fm)}</div></div>'
                   for fid, n, fm in D.ETB_SIX)
    return (
        '<div class="flow"><div class="ln">접안 가능시각 여섯 가지 → ETB</div><div class="six">'
        f'<div class="sixl">{rows}</div><div class="sixa">{AR_BIG}</div>'
        '<div class="sixr"><div class="etb"><div class="etbt">ETB = 여섯 시각 가운데 가장 늦은 시각</div>'
        + W("FR-27. ETB가 바뀌면 ETU를 다시 구하고(FR-29), 전체 제약과 다음 FIX 선박 충돌을 다시 검사한다.", "etbd") +
        '</div><div class="no2"><div class="no2t">이 배정은 안 된다고 판정하는 경우</div>'
        + W("선행 선박의 ETU + Switching이 FIX 선박 ETB 이상 (FR-17) · 탱크 용량 초과나 재고 부족 (FR-23) · 지정한 접안 마감을 넘김 (FR-25)", "no2d") +
        '</div></div></div></div>')


def timeline_block(inner):
    unit = (inner - 250) / 100

    def px(u):
        return round(u * unit)

    def track(key, segs):
        cells = "".join(f'<div class="seg" style="width:{px(u)}px;background:{bg};color:{fg}">{esc(t)}</div>' for u, t, bg, fg in segs)
        return f'<div class="tlr"><div class="tlk">{key}</div><div class="tlt">{cells}</div></div>'

    def marks(key, ms):
        cells = "".join(
            (f'<div class="mk" style="width:{px(u)}px"><div class="mkt">{esc(t)}</div><div class="mkd">{esc(d)}</div></div>' if t else
             f'<div style="width:{px(u)}px;flex:none"></div>') for u, t, d in ms)
        return f'<div class="tlr"><div class="tlk">{key}</div><div class="tlt">{cells}</div></div>'

    return (
        '<div class="flow"><div class="ln">체선 시간이 생기는 자리 (예시: 부두가 비기를 오래 기다린 선박)</div><div class="tl">'
        + marks("", [(30, "ETANR", "NOR Tender, 없으면 ETA"), (4, "ETB", "FR-27"), (44, "작업시작", "ETB + 1시간 (FR-29)"),
                     (6, "작업완료", "+ 작업시간"), (4, "호스분리", "+ 소요시간"), (12, "ETU", "작업완료 + 2시간")])
        + track("현장에서", [(30, "접안 대기", "#EEF2F6", "#475467"), (4, "", "#D5DBE5", "#475467"), (44, "하역 작업", "#B2CCFF", "#0E1726"),
                          (6, "", "#85B0FF", "#0E1726"), (4, "", "#D5DBE5", "#475467"), (12, "", "#FFFFFF", "#FFFFFF")])
        + track("계약 시계", [(8, "", "#EEF2F6", "#475467"), (50, "Laytime (FR-33)", "#A6E3BF", "#05603A"),
                           (26, "체선 시간 (FR-36)", "#FDA29B", "#7A271A"), (16, "", "#FFFFFF", "#FFFFFF")])
        + marks("", [(8, "", ""), (50, "정박개시", "FR-31 · FR-32 (여기서는 ETANR + 6시간)"), (26, "정박종료", "정박개시 + Laytime"),
                     (16, "호스분리", "체선 시간의 끝")])
        + '</div><div class="formula"><div class="fml">체선료 = max(0, 호스분리 − 정박종료 − 기상 공제) × 일 체선료 ÷ 24</div>'
        + W("기상 공제 = 기상 악화로 인한 체선 시간 × 1/2 (FR-35). 호스분리가 정박종료보다 이르면 0이다. 선박별 금액을 USD로 더한 것이 그 배정안의 총 예상 체선료다 (FR-37).", "fmn")
        + '</div></div>')


def group_board(g):
    width = {1: 1928, 2: 3768, 3: 5608}[g["cols"]]
    inner = width - 128 - 84  # 판 여백 64×2, 흐름 상자 여백 40×2 + 테두리 2×2
    n = len(g["fns"])
    from collections import Counter
    c = Counter(D.FN[f]["p"] for f in g["fns"])
    pri = " · ".join(f"{k} {c[k]}" for k in ("Must", "Should", "Could") if c[k])
    meta = "".join(f'<span class="meta">{esc(t)}</span>' for t in
                   [f"단계: {g['stage']}", f"기능 {n}개 ({pri})", f"누가: {g['who']}", f"유스케이스 {g['uc']}"])
    extra = six_block() if g["id"] == "G3" else timeline_block(inner) if g["id"] == "G4" else ""
    cards = "".join(card(f) for f in g["fns"])
    return (
        f'<section class="board" id="b-{g["id"]}" data-name="{g["id"]} {esc(g["name"])}" style="width:{width}px">'
        f'<div class="bh"><div class="gno">{g["id"]}</div><div class="bhx"><div class="bt">{esc(g["name"])}</div>'
        f'{W(g["goal"], "bs")}<div class="bm">{meta}</div></div></div>'
        f'<div class="sec">흐름 — 왼쪽에서 오른쪽으로</div>{flow(g, inner)}{extra}'
        f'<div class="sec">기능 {n}개 — 입력 → 처리 → 출력</div><div class="cards c{g["cols"]}">{cards}</div></section>')


def title_board():
    from collections import Counter
    c = Counter(f["p"] for f in D.FN.values())
    facts = [("기준", "요구사항서 v1.0 실시간 탭"), ("요구사항", "FR 60 · NFR 22"), ("기능", f"60개 · 그룹 10개"),
             ("우선순위", f"Must {c['Must']} · Should {c['Should']} · Could {c['Could']}"), ("작성", "2026-11-11"), ("상태", "제안 · 팀 확인 전")]
    facts_h = "".join(f'<div class="fact"><div class="fk">{k}</div><div class="fv">{esc(v)}</div></div>' for k, v in facts)
    order = [("1", "업무 단계 한 줄", "누가 무엇을 하고 다음 단계로 무엇이 넘어가는지. 기능 60개가 어디에 있는지."),
             ("2", "계산 한 번의 안쪽", "계산을 누르면 규칙 엔진과 최적화가 도는 순서."),
             ("3", "그룹 판 G1 ~ G10", "판마다 위쪽은 그 그룹의 흐름, 아래쪽은 기능 카드."),
             ("4", "용어 · 비기능 · 확인할 것", "모르는 말, 모든 기능에 걸리는 규칙, 아직 정해지지 않은 것.")]
    order_h = ""
    ow = (4400 - 128 - 84 - 64 * (len(order) - 1)) // len(order)
    for i, (n, t, d) in enumerate(order):
        order_h += f'<div class="ob" style="width:{ow}px"><div class="obn">{n}</div><div class="obt">{esc(t)}</div>{W(d, "obd")}</div>'
        if i < len(order) - 1:
            order_h += f'<div class="oar">{AR}</div>'
    lg = [
        ('<span class="fid">FR-27</span>', "기능 ID. 요구사항 ID와 같은 번호를 쓴다."),
        ('<span class="tg must">Must</span><span class="tg should">Should</span><span class="tg could">Could</span>', "우선순위. 요구사항서 그대로다."),
        ('<span class="tg who">선박 스케줄러</span><span class="tg sys">시스템</span>', "이 기능을 시작하는 쪽. '시스템'은 계산 중에 자동으로 돈다."),
        ('<span class="tg llm">LLM</span><span class="tg ext">외부 API</span>', "LLM이나 공공데이터포털을 부르는 기능."),
        ('<span class="pl i">입력</span><span class="pl p">처리</span><span class="pl o">출력</span>', "카드는 위에서 아래로 읽는다. 처리의 번호가 순서다."),
        ('<span class="tg" style="background:#FFF4DF;color:#93370D">다른 길</span><span class="tg" style="background:#FEE4E2;color:#912018">멈춤</span>',
         "다르게 가도 끝나는 경우 / 거기서 더 나아가지 않는 경우."),
        ('<span class="tg" style="background:#EFEBFF;color:#5B45B8">완료 기준</span>', "요구사항서의 수용기준 그대로. 이 문장이 참이면 끝난 것이다."),
        ('<span class="tg could">[가정]</span><span class="tg could">[확인 필요]</span>', "요구사항서에 없어 채운 것 / 팀이나 멘토에게 물을 것."),
    ]
    lg_h = "".join(f'<div class="lg"><div class="lgk">{k}</div>{W(v, "lgv")}</div>' for k, v in lg)
    sw = [("#0E1726", "#0E1726", "사람이 하는 일"), ("#EEF4FF", "#B2CCFF", "시스템이 하는 일 (규칙 엔진 · 최적화 · 화면)"), ("#F3F0FF", "#C9BDF5", "LLM을 부르는 일"),
          ("#E6F7F4", "#99D8CC", "외부 API를 부르는 일"), ("#ECFDF3", "#A6E3BF", "다음으로 넘어가는 결과")]
    sw_h = "".join(f'<div class="lg"><div class="lgk" style="width:80px"><div class="swatch" style="background:{bg};border-color:{bd}"></div></div>'
                   f'<div class="lgv">{t}</div></div>' for bg, bd, t in sw)
    notes = ["금액 · 시각 · 제약 판정 · 후보 정렬에는 LLM을 쓰지 않는다 (NFR-01).",
             "후보를 확정하는 것은 사람이다. Agent는 조회, 계산, 초안 작성만 한다 (NFR-17).",
             "메일은 초안만 만든다. 보내는 일은 사람이 시스템 밖에서 한다 (FR-52)."]
    notes_h = "".join(f'<div class="li"><div class="dot"><i></i></div>{W(t, "tx")}</div>' for t in notes)
    return (
        '<section class="board" id="b-title" data-name="기능명세서 · 머리와 읽는 법" style="width:4400px">'
        '<div style="display:flex;flex-direction:column;gap:6px"><div class="title">기능명세서</div>'
        '<div class="sub">체선료 최적화 Agent (척화비)</div></div>'
        f'<div class="facts">{facts_h}</div>'
        f'<div class="panel"><div class="ph">읽는 순서</div><div class="order">{order_h}</div></div>'
        '<div class="cols">'
        f'<div class="panel" style="width:2560px;flex:none"><div class="ph">기능 카드에 나오는 표시</div>{lg_h}</div>'
        f'<div class="panel" style="width:1684px;flex:none"><div class="ph">흐름 그림의 상자 색</div>{sw_h}'
        f'<div class="ph" style="margin-top:14px">세 가지 원칙</div>{notes_h}</div>'
        '</div></section>')


def stages_board():
    gmap = {g["id"]: g for g in D.GROUPS}

    def gblock(gid):
        g = gmap[gid]
        wide = len(g["fns"]) > 8
        chips = "".join(
            f'<div class="chip"><div class="pd {PRI_CLS[D.FN[f]["p"]] if D.FN[f]["p"] != "Must" else ""}"></div>'
            f'<div class="cid">{f}</div><div class="cnm">{esc(D.FN[f]["n"])}</div></div>' for f in g["fns"])
        return (f'<div class="gb{" wide" if wide else ""}"><div class="gbh"><div class="gbn">{gid}</div><div class="gbt">{esc(g["name"])}</div></div>'
                f'{W("누가: " + g["who"], "gbw")}<div class="chips">{chips}</div>'
                f'<div class="hand"><div class="hk">다음으로 넘기는 것</div>{W(g["hand"], "hv")}</div></div>')

    parts = []
    order = [gid for _, gs in D.STAGES for gid in gs]
    for si, (sname, gs) in enumerate(D.STAGES):
        inner = []
        for i, gid in enumerate(gs):
            inner.append(gblock(gid))
            if i < len(gs) - 1:
                inner.append(f'<div class="gate in">{AR_BIG}</div>')
        parts.append(f'<div class="stg"><div class="stn">{esc(sname)}</div><div class="stb">{"".join(inner)}</div></div>')
        if si < len(D.STAGES) - 1:
            a, b = gs[-1], D.STAGES[si + 1][1][0]
            gate = D.GATES.get((a, b), "")
            gt = W(gate, "gtx") if gate else ""
            parts.append(f'<div class="gate"><div style="height:76px"></div>{AR_BIG}{gt}</div>')
    return (
        '<section class="board" id="b-stages" data-name="업무 단계 한 줄">'
        '<div class="bh"><div class="gno">1</div><div class="bhx"><div class="bt">업무 단계 한 줄</div>'
        + W("준비부터 검증까지 여덟 단계다. 단계 안의 상자가 기능 그룹이고, 그 안의 줄이 기능 60개다. 화살표 아래 글은 다음 단계로 넘어가는 조건이다.", "bs") +
        '<div class="bm"><span class="meta">● Must</span><span class="meta">○ 파란 테 = Should</span><span class="meta">○ 회색 테 = Could</span></div></div></div>'
        f'<div class="stages">{"".join(parts)}</div>'
        '<div class="common"><div class="fid">FR-60</div>'
        '<div class="cmt">업무 단계 안내 — 화면은 지금 단계를 항상 보여 주고, 앞 단계가 끝나지 않으면 다음 단계를 사유와 함께 막는다. (입력 → 계산 → 후보 비교 → 리스크 → 보고서 → 일정 확정 → 검증)</div></div>'
        '</section>')


def engine_board():
    def es(s, cls=""):
        return (f'<div class="es {cls}"><div><div class="est w">{esc(s["t"])}</div><div class="esn w">{esc(s["note"])}</div></div>'
                f'<div class="esf">{esc(s["fr"])}</div></div>')

    def chain(items, cls=""):
        out = []
        for i, s in enumerate(items):
            out.append(es(s, cls if not isinstance(cls, list) else cls[i]))
            if i < len(items) - 1:
                out.append(f'<div class="ea">{AR}</div>')
        return "".join(out)

    pre = chain(D.ENGINE["pre"])
    loop = chain(D.ENGINE["loop"])
    post = chain(D.ENGINE["post"], ["g", "r"])
    return (
        '<section class="board" id="b-engine" data-name="계산 한 번의 안쪽">'
        '<div class="bh"><div class="gno">2</div><div class="bhx"><div class="bt">계산 한 번의 안쪽</div>'
        + W("스케줄러가 계산을 누르면 도는 순서다. 점선 안은 배정안(접안 순서와 부두 배정 하나)마다 되풀이한다. 이 안에서는 LLM을 한 번도 부르지 않는다 (NFR-01).", "bs") +
        '</div></div>'
        '<div class="eng">'
        f'<div class="eg"><div class="egn">먼저 한 번</div><div class="egb">{pre}</div></div>'
        f'<div class="ea" style="width:84px;padding-top:48px">{AR_BIG}</div>'
        '<div class="loop"><div class="lph"><div class="fid">FR-42</div><div class="lpt">배정안마다 되풀이</div>'
        '<div class="lpd">G3 제약 판정 · ETB 산정 → G4 체선료 계산</div></div>'
        f'<div class="egb">{loop}</div></div>'
        f'<div class="ea" style="width:84px;padding-top:48px">{AR_BIG}</div>'
        f'<div class="eg"><div class="egn">끝나면</div><div class="egb">{post}</div></div>'
        '</div>'
        '<div class="formula"><div class="fml">체선료 = max(0, 호스분리 − 정박종료 − 기상 공제) × 일 체선료 ÷ 24</div>'
        '<div class="fmn">정박종료 = 정박개시 + Laytime · ETB = 제약별 접안 가능시각 가운데 가장 늦은 시각 · 총 예상 체선료 = 선박별 체선료의 합 (USD)</div></div>'
        '</section>')


TERMS = [
    ("ETA", "터미널 예상 도착시각"),
    ("NOR Tender (N/R)", "선박이 도착해 하역 준비가 끝났다고 통지한 시각"),
    ("ETANR", "NOR Tender, 없으면 ETA"),
    ("Laycan From / To", "계약상 선박이 도착해야 하는 기간의 시작과 끝"),
    ("Laytime", "계약상 허용된 정박·하역 시간. 넘기면 체선료가 생긴다"),
    ("정박개시 / 정박종료", "Laytime 계산이 시작되는 시각 / 정박개시 + Laytime"),
    ("체선료 (Demurrage)", "Laytime을 넘긴 시간만큼 선주에게 내는 비용. 일 요율로 센다"),
    ("ETB / ETU", "예상 접안시각 / 예상 이안(부두를 떠나는) 시각"),
    ("호스분리", "하역 호스를 떼는 시각. 체선 시간 계산의 끝점"),
    ("Direction", "빈 부두에 바로 접안할 때 걸리는 이동 시간 (부두별)"),
    ("Switching", "앞 선박이 떠난 뒤 다음 선박이 들어오는 교대 시간 (부두별)"),
    ("FIX 선박", "접안 일정이 확정돼 바꿀 수 없는 선박"),
    ("Last POB", "도선사가 배에 오를 수 있는 마지막 시각"),
    ("Daylight 조항", "NOR이 주간에 들어왔는지에 따라 Laytime 기산시각을 달리 정하는 계약 조건"),
    ("GRT / DWT", "총톤수(선박 크기) / 재화중량톤수(실을 수 있는 무게)"),
    ("LOA / PBL / Draft", "선박 전체 길이 / 선체가 부두에 닿는 직선 구간 길이 / 물에 잠긴 깊이(흘수)"),
    ("FCFS · 기준안", "도착 순서대로 접안시키는 방식. 이 프로젝트의 비교 기준안"),
    ("C/P · SOF", "용선계약서(Charter Party) / 하역 사실 기록(Statement of Facts)"),
    ("입력 시나리오", "계산에 넣는 선박·계약·부두·재고·접안 제한 한 묶음"),
    ("배정안 · 후보", "접안 순서와 부두 배정 하나 / 그 가운데 제약을 지키고 총 체선료가 낮은 최대 3개"),
]


def glossary_board():
    cells = "".join(f'<div class="term"><div class="tk">{esc(k)}</div>{W(v, "tv")}</div>' for k, v in TERMS)
    return (
        '<section class="board" id="b-terms" data-name="용어" style="width:6399px">'
        '<div class="bh"><div class="gno">용어</div><div class="bhx"><div class="bt">이 명세서에 나오는 말</div>'
        + W("팀 문서의 용어 정의 초안을 옮기고, 이 명세서에서 새로 쓴 말 세 개를 더했다.", "bs") + '</div></div>'
        f'<div class="grid" style="grid-template-columns:repeat(5,1235px)">{cells}</div></section>')


def nfr_board():
    cells = ""
    for nid, name, pri, body, crit, where in D.NFR:
        cells += (f'<div class="nf"><div class="nfh"><div class="fid">{nid}</div><div class="nfn">{esc(name)}</div>'
                  f'<span class="tg {PRI_CLS[pri]}">{pri}</span></div>{W(body, "nfd")}'
                  f'<div class="nfk">기준</div>{W(crit, "nfv")}<div class="nfk rel">걸리는 기능</div>{W(where, "nfv")}</div>')
    return (
        '<section class="board" id="b-nfr" data-name="비기능 요구사항 22개" style="width:13392px">'
        '<div class="bh"><div class="gno">비기능</div><div class="bhx"><div class="bt">모든 기능에 걸리는 규칙 22개</div>'
        + W("비기능 요구사항은 기능 카드 하나에 묶이지 않는다. 어느 기능을 만들 때 지켜야 하는지를 '걸리는 기능'에 적었다.", "bs") + '</div></div>'
        f'<div class="grid" style="grid-template-columns:repeat(11,1184px)">{cells}</div></section>')


def open_board():
    cells = "".join(
        f'<div class="oq"><div class="oqh"><div class="oqn">{i}</div>{W(q, "oqt")}</div>'
        f'<div class="nfk rel">걸리는 기능</div><div class="nfv en" style="white-space:nowrap">{esc(fr)}</div>{W(why, "oqd")}</div>'
        for i, (q, fr, why) in enumerate(D.OPEN, 1))
    return (
        '<section class="board" id="b-open" data-name="확인할 것" style="width:4898px">'
        '<div class="bh"><div class="gno" style="background:#B54708">확인</div><div class="bhx"><div class="bt">아직 정해지지 않은 것 9개</div>'
        + W("요구사항서에 적혀 있지 않아 명세서에 [가정]이나 [확인 필요]로 남긴 것들이다. 답이 정해지면 해당 기능 카드를 고친다.", "bs") + '</div></div>'
        f'<div class="grid" style="grid-template-columns:repeat(3,1574px)">{cells}</div></section>')


BAKE_JS = r"""
function escH(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function bake(){
  document.querySelectorAll('.w').forEach(function(el){
    var words = el.textContent.split(' ');
    el.style.paddingRight = Math.round(el.clientWidth * 0.05) + 'px';  // 피그마에서 영문이 조금 넓게 나오므로 5% 여유를 두고 끊는다
    el.textContent = '';
    var spans = words.map(function(w,i){var s=document.createElement('span'); s.textContent = w + (i<words.length-1?' ':''); el.appendChild(s); return s;});
    var lines=[], cur=[], top=null;
    spans.forEach(function(s){var t=s.offsetTop; if(top===null){top=t;} if(Math.abs(t-top)<3){cur.push(s.textContent);} else {lines.push(cur.join('').replace(/\s+$/,'')); cur=[s.textContent]; top=t;}});
    if(cur.length) lines.push(cur.join('').replace(/\s+$/,''));
    el.innerHTML = lines.map(escH).join('<br>');
    el.style.paddingRight = '';
    el.style.whiteSpace='nowrap';
    el.setAttribute('data-lines', lines.length);
  });
}
var done=false;
function run(){
  if(done) return; done=true;
  var probe=document.createElement('span'); probe.style.cssText='position:absolute;left:-9999px;top:0;font:500 46px "Noto Sans KR";white-space:nowrap'; probe.textContent='기준 정보를 관리한다'; document.body.appendChild(probe);
  var pw=probe.getBoundingClientRect().width; probe.remove();
  bake();
  var boards={}; document.querySelectorAll('.board').forEach(function(b){var r=b.getBoundingClientRect(); boards[b.id]=[Math.round(r.width),Math.round(r.height)];});
  var h=document.documentElement;
  h.setAttribute('data-probe', pw.toFixed(1));
  h.setAttribute('data-font', String(document.fonts.check('500 46px "Noto Sans KR"')) + '/' + document.fonts.size);
  h.setAttribute('data-boards', JSON.stringify(boards));
  h.setAttribute('data-baked','1');
  document.querySelectorAll('script').forEach(function(n){n.remove();});
}
document.fonts.ready.then(function(){ setTimeout(run, 300); });
setTimeout(run, 12000);
"""

FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&'
             'family=Noto+Sans+KR:wght@400;500;700&display=swap">')


def build_html():
    groups = "".join(group_board(g) for g in D.GROUPS)
    body = (f'<div class="canvas"><div class="row">{title_board()}{stages_board()}{engine_board()}{glossary_board()}</div>'
            f'<div class="row">{groups}</div>'
            f'<div class="row">{nfr_board()}{open_board()}</div></div>')
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>기능명세서 · 체선료 최적화 Agent(척화비)</title>'
            f'{FONT_LINK}<style>{CSS}</style></head><body>{body}<script>{BAKE_JS}</script></body></html>')


# ─────────────────────────── 글로 된 명세서 ───────────────────────────
def build_md():
    from collections import Counter
    c = Counter(f["p"] for f in D.FN.values())
    o = []
    o.append("# 기능명세서\n")
    o.append("- 작성: 2026-11-11 · 상태: **제안 (팀 확인 전)**")
    o.append("- 기준: 팀 구글 문서 '[판교_2반_1조] 프로젝트정의 요구사항서'의 **실시간 탭 3절** (FR-01~60, NFR-01~22)")
    o.append(f"- 기능 60개 (Must {c['Must']} · Should {c['Should']} · Could {c['Could']}) · 그룹 10개. 기능 ID는 요구사항 ID와 같다")
    o.append("- 그림으로 된 것은 팀 피그마 파일 SKALA-P2-1의 ['기능명세서' 프레임](https://www.figma.com/design/mDE8EoyYV0dS2WjtBLUoet/SKALA-P2-1?node-id=143-762)에 있다 (2026-11-11에 넣음, 판 16개). 이 파일과 피그마 보드는 `funcspec/spec_data.py` 하나에서 나온다")
    o.append("- 유스케이스 다이어그램 [`12`](12-usecase-diagram.md) · 유스케이스 시나리오 [`13`](13-usecase-scenarios.md)\n")
    o.append("## 읽는 법\n")
    o.append("- 기능마다 **입력 → 처리 → 출력** 순서로 적었다. 처리의 번호가 순서다.")
    o.append("- **다른 길**은 다르게 가도 끝나는 경우, **멈춤**은 거기서 더 나아가지 않는 경우다.")
    o.append("- **완료 기준**은 요구사항서의 수용기준을 그대로 옮겼다.")
    o.append("- **[가정]** 은 요구사항서에 없어 채운 것, **[확인 필요]** 는 팀이나 멘토에게 물어야 하는 것이다.\n")
    o.append("## 업무 단계와 그룹\n")
    o.append("| 단계 | 그룹 | 누가 | 기능 | 다음으로 넘기는 것 |")
    o.append("|---|---|---|---|---|")
    gmap = {g["id"]: g for g in D.GROUPS}
    for sname, gs in D.STAGES:
        for gid in gs:
            g = gmap[gid]
            o.append(f"| {sname} | {gid} {g['name']} | {g['who']} | {', '.join(g['fns'])} | {g['hand']} |")
    o.append("\n단계 사이에서 넘어가는 조건 (요구사항서에 적힌 것만)\n")
    for (a, b), t in D.GATES.items():
        o.append(f"- {a} → {b}: {t}")
    o.append("- 공통: FR-60이 지금 단계를 항상 보여 주고, 앞 단계가 끝나지 않으면 다음 단계를 사유와 함께 막는다\n")
    o.append("## 계산 한 번의 안쪽\n")
    o.append("스케줄러가 계산을 누르면 도는 순서다. 이 안에서는 LLM을 부르지 않는다 (NFR-01).\n")
    k = 1
    for s in D.ENGINE["pre"]:
        o.append(f"{k}. {s['t']} ({s['fr']}) — {s['note']}"); k += 1
    o.append(f"{k}. 배정안마다 되풀이 (FR-42)"); k += 1
    for s in D.ENGINE["loop"]:
        o.append(f"   - {s['t']} ({s['fr']}) — {s['note']}")
    for s in D.ENGINE["post"]:
        o.append(f"{k}. {s['t']} ({s['fr']}) — {s['note']}"); k += 1
    o.append("\n```\n체선료 = max(0, 호스분리 − 정박종료 − 기상 공제) × 일 체선료 ÷ 24\n정박종료 = 정박개시 + Laytime\nETB = 제약별 접안 가능시각 가운데 가장 늦은 시각\n```\n")
    o.append("접안 가능시각 여섯 가지\n")
    for fid, n, fm in D.ETB_SIX:
        o.append(f"- {fid} {n}: {fm}")
    o.append("")
    for g in D.GROUPS:
        o.append("---\n")
        o.append(f"## {g['id']} {g['name']}\n")
        o.append(f"- 단계: {g['stage']} · 누가: {g['who']} · 유스케이스: {g['uc']}")
        o.append(f"- {g['goal']}")
        o.append(f"- 다음으로 넘기는 것: {g['hand']}\n")
        o.append("흐름\n")
        for name, steps in g["flow"]:
            o.append(f"- **{name}**")
            n = 0
            for s in steps:
                who = WHO_STEP[s["who"]][1]
                if s["who"] == "out":
                    o.append(f"  - → {s['t']} ({s['fr']})")
                else:
                    n += 1
                    o.append(f"  - {n}. [{who}] {s['t']} ({s['fr']})")
                for kk, t in s.get("br", ()):
                    o.append(f"    - {'다른 길' if kk == 'a' else '멈춤'}: {t}")
        o.append("")
        for fid in g["fns"]:
            f = D.FN[fid]
            who = D.WHO[f["who"]] + ("" if f["who"] != "sys" else " (계산 중 자동)")
            extra = "".join([" · LLM" if "llm" in f["tag"] else "", " · 외부 API" if "ext" in f["tag"] else "",
                             " · 체선 지불 부서도 조회" if "view" in f["tag"] else ""])
            o.append(f"### {fid} {f['n']}\n")
            o.append(f"- 우선순위: {f['p']} · 시작: {who}{extra} · 유스케이스: {f['uc']}")
            o.append(f"- {f['what']}\n")
            o.append("입력\n")
            o.extend(f"- {t}" for t in f["inp"])
            o.append("\n처리\n")
            o.extend(f"{i}. {t}" for i, t in enumerate(f["proc"], 1))
            if f["alt"]:
                o.append("")
                o.extend(f"- {'다른 길' if kk == 'a' else '멈춤'}: {t}" for kk, t in f["alt"])
            o.append("\n출력\n")
            o.extend(f"- {t}" for t in f["out"])
            o.append(f"\n완료 기준: {f['done']}")
            if f["rel"]:
                o.append(f"\n관련: {f['rel']}")
            o.append("")
    o.append("---\n")
    o.append("## 모든 기능에 걸리는 규칙 (비기능 22개)\n")
    o.append("| ID | 이름 | 우선순위 | 내용 | 기준 | 걸리는 기능 |")
    o.append("|---|---|---|---|---|---|")
    for nid, name, pri, body, crit, where in D.NFR:
        o.append(f"| {nid} | {name} | {pri} | {body} | {crit} | {where} |")
    o.append("\n## 아직 정해지지 않은 것\n")
    for i, (q, fr, why) in enumerate(D.OPEN, 1):
        o.append(f"{i}. **{q}** ({fr}) — {why}")
    o.append("\n## 용어\n")
    o.append("| 용어 | 뜻 |")
    o.append("|---|---|")
    for kx, v in TERMS:
        o.append(f"| {kx} | {v} |")
    o.append("\n## 다시 만들기\n")
    o.append("```bash\npython3 docs/requirements/funcspec/make_funcspec.py\n```\n")
    o.append("내용은 `funcspec/spec_data.py`에서 고친다. `funcspec-board.html`은 피그마 보드의 원본이고, 피그마에는 자동으로 반영되지 않는다.")
    return "\n".join(o) + "\n"


def main():
    out_html = os.path.join(HERE, "funcspec-board.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(build_html())
    out_md = os.path.join(os.path.dirname(HERE), "14-functional-spec.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(build_md())
    print("저장:", os.path.relpath(out_html), os.path.getsize(out_html), "bytes")
    print("저장:", os.path.relpath(out_md), os.path.getsize(out_md), "bytes")


if __name__ == "__main__":
    main()
