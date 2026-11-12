#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수리계획법 최종본 보드 생성기.

milp_final_content.py(글) + milp_final_example.py(숫자) →
  ① milp-board.html   피그마에 넣는 보드의 원본 (머리띠 1 + 판 9)
  ② milp-final.md     같은 내용의 글 버전

  python3 docs/milp/make_milp_board.py

줄바꿈은 브라우저에서 한 번 계산해 <br>로 굳힌다(bake). 피그마는 한글을 글자 단위로 끊기 때문이다.
식 안의 빈칸은 줄어들지 않게 모두 NBSP로 바꾼다.
"""
from __future__ import annotations

import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import milp_final_content as C  # noqa: E402
import milp_final_example as E  # noqa: E402

esc = html.escape
X = E.run()
P = X["plans"]
TAU = X["tau"]
NT = len(TAU) - 1
SOL = X["solutions"]
COMBOS = X["combos"]
BYCOMBO = {"+".join(r["combo"]): r for r in COMBOS}
T2 = X["type2"]
NB = C.NBOARD


# ─────────────────────────── 숫자 쓰는 법 ───────────────────────────
def hh(x):
    """시각·시간: 0.5 단위면 소수 한 자리, 아니면 두 자리."""
    return f"{x:.1f}" if abs(x * 2 - round(x * 2)) < 1e-9 else f"{x:.2f}"


def vol(x):
    return f"{x:.1f}" if abs(x * 10 - round(x * 10)) < 1e-9 else f"{x:.2f}"


def money(x):
    return "$" + f"{x:,.0f}"


def num(x):
    return f"{x:,.0f}"


def zn(name):
    return f"z[{name[0]},{name[1:]}]"


def tidx(t0):
    return TAU.index(float(t0))


def josa(word, pair):
    """받침에 맞는 조사. pair: '은는' '을를' '과와' '으로로'. 숫자로 끝나면 읽는 소리(일·이·삼…)로 정한다."""
    last = word[-1]
    if last.isdigit():
        final, rieul = last in "013678", last in "178"
    elif "\uac00" <= last <= "\ud7a3":
        code = (ord(last) - 0xAC00) % 28
        final, rieul = code != 0, code == 8
    else:
        final, rieul = False, False
    if pair == "으로로":
        return "으로" if (final and not rieul) else "로"
    return pair[0] if final else pair[1:]


def why_text(r):
    parts = []
    if r["conflict"]:
        parts.append(" · ".join("·".join(pr) + f" {P[pr[0]]['berth']}에서 겹침" for pr in r["conflict"]))
    if "over" in r["why"]:
        parts.append(f"{hh(r['max'][0])}h에 {vol(r['max'][1])} → 저장용량 {vol(X['R_MAX'])} 초과")
    if "under" in r["why"]:
        parts.append(f"{hh(r['min'][0])}h에 {vol(r['min'][1])} → 최소 허용 재고 {vol(X['R_MIN'])} 미달")
    return parts


BEST, SECOND = SOL[0], SOL[1]
BEST_NAME, SECOND_NAME = " + ".join(BEST["chosen"]), " + ".join(SECOND["chosen"])
OLD_BEST = sum(X["old_cost"][n] for n in BEST["chosen"])
OLD_SECOND = sum(X["old_cost"][n] for n in SECOND["chosen"])
N_VAR = len(P) + NT + 1
N_ROW = len(E.ARRIVALS) + len(X["F"]) + NT + 1

# ─────────────────────────── 스타일 ───────────────────────────
CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#FFFFFF}
body{font-family:'Noto Sans KR',sans-serif;color:#0E1726;font-size:28px;line-height:42px;font-weight:400}
.w{word-break:keep-all;overflow-wrap:normal}
.canvas{width:max-content;padding:120px;display:flex;flex-direction:column;gap:140px}
.row{display:flex;gap:120px;align-items:flex-start}
.board{width:3200px;background:#F6F8FB;border-radius:56px;padding:64px;display:flex;flex-direction:column;gap:40px;flex:none}

/* 머리띠 */
.zone{width:16480px;background:#0E1726;border-radius:56px;padding:64px 88px;display:flex;align-items:center;justify-content:space-between;flex:none;color:#FFFFFF}
.zl{display:flex;flex-direction:column;gap:14px}
.zk{font-size:40px;line-height:56px;font-weight:700;color:#B2CCFF;white-space:nowrap}
.zt{font-size:150px;line-height:176px;font-weight:700;white-space:nowrap}
.zs{font-size:44px;line-height:64px;color:#D0D5DD;white-space:nowrap}
.zr{display:flex;flex-direction:column;gap:18px}
.zrow{display:flex;gap:18px;align-items:center}
.zrk{width:330px;font-size:30px;line-height:80px;font-weight:700;color:#98A2B3;white-space:nowrap;flex:none}
.zchip{height:80px;border-radius:20px;background:#1D2939;padding:0 28px;display:flex;align-items:center;gap:16px;white-space:nowrap;flex:none}
.zcn{font-family:'Inter',sans-serif;font-weight:700;font-size:34px;line-height:80px;color:#B2CCFF}
.zcx{font-size:32px;line-height:80px;font-weight:500}

/* 판 머리 */
.bh{display:flex;align-items:flex-start;gap:28px}
.gno{font-family:'Inter',sans-serif;font-weight:700;font-size:40px;line-height:76px;height:76px;padding:0 26px;border-radius:20px;background:#0E1726;color:#FFFFFF;flex:none;white-space:nowrap}
.bhx{width:2840px;display:flex;flex-direction:column;gap:12px;flex:none}
.bt{font-size:64px;line-height:76px;font-weight:700;white-space:nowrap}
.bs{font-size:30px;line-height:46px;color:#475467}
.sech{display:flex;align-items:flex-end;gap:24px}
.sec{font-size:40px;line-height:56px;font-weight:700;white-space:nowrap}
.secn{font-size:26px;line-height:48px;color:#667085;white-space:nowrap}

.panel{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:32px;padding:36px 40px 40px;display:flex;flex-direction:column;gap:20px}
.ph{font-size:34px;line-height:46px;font-weight:700;white-space:nowrap}
.pn{font-size:26px;line-height:40px;color:#475467}
.bl{display:flex;gap:16px;align-items:flex-start}
.bd{flex:none;width:12px;height:42px;display:flex;align-items:center}
.bd i{display:block;width:12px;height:12px;border-radius:6px;background:#2F6FED}
.bx{flex:1;min-width:0;font-size:27px;line-height:42px}
.add{flex:none;height:36px;line-height:36px;padding:0 12px;border-radius:10px;background:#FFF4DF;color:#93370D;font-size:21px;font-weight:700;white-space:nowrap;margin-top:3px}

/* 식 */
.fbox{background:#EEF4FF;border-radius:20px;padding:22px 28px;display:flex;flex-direction:column;gap:2px}
.fm{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:34px;line-height:52px;white-space:nowrap;color:#0E1726}
.fm.s{font-size:31px;line-height:48px}
.for{font-size:26px;line-height:44px;font-weight:700;color:#475467;white-space:nowrap}
.chips{display:flex;gap:12px}
.chip{display:flex;gap:10px;align-items:center;height:48px;padding:0 16px;border-radius:12px;background:#F2F4F7;white-space:nowrap;flex:none}
.chs{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:24px;line-height:48px}
.chn{font-size:24px;line-height:48px;color:#344054}
.lt{display:flex;gap:20px;align-items:flex-start}
.ltl{flex:none;width:120px;height:40px;border-radius:10px;font-size:22px;line-height:40px;font-weight:700;text-align:center;white-space:nowrap;background:#E8F0FF;color:#1D4ED8}
.ltl.g{background:#EEF2F6;color:#475467}
.ltt{flex:1;min-width:0;font-size:27px;line-height:40px}
.ltt.k{font-weight:700}
.ex{background:#F7FAFF;border:3px dashed #B2CCFF;border-radius:24px;padding:26px 30px 28px;display:flex;flex-direction:column;gap:16px}
.exh{font-size:24px;line-height:34px;font-weight:700;color:#1D4ED8;white-space:nowrap}
.exl{display:flex;flex-direction:column;gap:2px}
.exk{font-size:23px;line-height:34px;font-weight:700;color:#667085;white-space:nowrap}
.exv{font-size:27px;line-height:40px;font-weight:500}

.fcard{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:32px;padding:36px 40px 40px;display:flex;flex-direction:column;gap:24px}
.fcard.plus{border:3px dashed #F5B94D;background:#FFFCF5}
.fch{display:flex;align-items:center;gap:18px}
.fno{font-family:'Inter',sans-serif;font-weight:700;font-size:30px;line-height:56px;height:56px;padding:0 18px;border-radius:16px;background:#2F6FED;color:#FFFFFF;white-space:nowrap;flex:none}
.fno.plus{background:#B54708}
.fct{font-size:38px;line-height:56px;font-weight:700;white-space:nowrap}
.frng{font-family:'JetBrains Mono',monospace;font-weight:500;font-size:26px;line-height:48px;height:48px;padding:0 18px;border-radius:12px;background:#F2F4F7;color:#344054;white-space:nowrap;flex:none}
.frng.ko{font-family:'Noto Sans KR',sans-serif;font-size:24px}
.fcols{display:flex;gap:36px;align-items:flex-start}
.fl{width:1560px;display:flex;flex-direction:column;gap:20px;flex:none}
.fr{width:1392px;flex:none}
.fl2{width:1060px;display:flex;flex-direction:column;gap:20px;flex:none}
.fr2{width:1892px;flex:none}
.g2{display:grid;grid-template-columns:1516px 1516px;gap:40px;align-items:stretch}
.g2 .fcard{padding:32px 36px 36px;gap:20px}
.grp{display:flex;align-items:center;gap:20px}
.grpn{height:60px;border-radius:16px;background:#0E1726;color:#FFFFFF;font-size:30px;line-height:60px;font-weight:700;padding:0 24px;white-space:nowrap;flex:none}
.grpd{font-size:27px;line-height:60px;color:#475467;white-space:nowrap}
.defs{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:28px;padding:30px 36px 34px;display:flex;flex-direction:column;gap:12px}
.defh{font-size:26px;line-height:38px;font-weight:700;color:#667085;white-space:nowrap}

/* 판 1 */
.hero{display:flex;flex-direction:column;gap:22px}
.kickrow{display:flex;align-items:center;gap:22px}
.kick{font-size:36px;line-height:76px;font-weight:700;color:#1D4ED8;white-space:nowrap}
.title{font-size:132px;line-height:158px;font-weight:700;white-space:nowrap}
.sub{font-size:44px;line-height:62px;font-weight:500;color:#344054;white-space:nowrap}
.lead{font-size:36px;line-height:56px;color:#0E1726}
.facts{display:flex;gap:16px}
.fact{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:24px;padding:18px 26px;display:flex;flex-direction:column;gap:2px;flex:none}
.fk{font-size:22px;line-height:32px;color:#667085;white-space:nowrap}
.fv{font-size:31px;line-height:44px;font-weight:700;white-space:nowrap}
.order{display:grid;grid-template-columns:1008px 1008px 1008px;gap:20px 24px}
.oc{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:20px;padding:16px 20px 18px;display:flex;gap:16px;align-items:flex-start}
.oc.me{background:#0E1726;border-color:#0E1726;color:#FFFFFF}
.ocn{flex:none;width:48px;height:48px;border-radius:24px;background:#2F6FED;color:#FFFFFF;font-family:'Inter',sans-serif;font-weight:700;font-size:26px;line-height:48px;text-align:center}
.ocx{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.oct{font-size:26px;line-height:48px;font-weight:700;white-space:nowrap}
.ocd{font-size:21px;line-height:32px;color:#667085}
.oc.me .ocd{color:#D0D5DD}
.glance{background:#0E1726;border-radius:36px;padding:44px 48px 48px;display:flex;flex-direction:column;gap:6px;color:#FFFFFF}
.glh{display:flex;align-items:flex-end;gap:24px;margin-bottom:18px}
.glt{font-size:44px;line-height:60px;font-weight:700;white-space:nowrap}
.gln{font-size:26px;line-height:48px;color:#B2CCFF;white-space:nowrap}
.gr{display:flex;align-items:center;gap:28px;height:86px;border-top:2px solid #1D2939}
.gn{flex:none;width:84px;height:52px;border-radius:14px;background:#FFFFFF;color:#0E1726;font-family:'Inter',sans-serif;font-weight:700;font-size:28px;line-height:52px;text-align:center}
.gf{flex:none;width:1500px;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:36px;line-height:52px;white-space:nowrap}
.grng{flex:none;width:500px;font-family:'JetBrains Mono',monospace;font-weight:500;font-size:27px;line-height:52px;color:#B2CCFF;white-space:nowrap}
.gk{flex:none;width:800px;font-size:28px;line-height:52px;color:#E4E7EC;white-space:nowrap}
.pipe{display:flex;align-items:stretch}
.pb{width:705px;border-radius:24px;padding:24px 28px 28px;background:#FFFFFF;border:2px solid #E2E7EE;display:flex;flex-direction:column;gap:8px;flex:none}
.pb.hi{background:#EEF4FF;border-color:#B2CCFF}
.pk{font-family:'Inter',sans-serif;font-size:24px;line-height:34px;font-weight:700;color:#1D4ED8;white-space:nowrap}
.pt{font-size:36px;line-height:50px;font-weight:700;white-space:nowrap}
.pd{font-size:24px;line-height:36px;color:#475467}
.par{flex:none;width:84px;display:flex;align-items:center;justify-content:center}
.scope{display:flex;gap:44px}
.scol{width:1472px;display:flex;flex-direction:column;gap:12px;flex:none}
.tgrid{display:grid;grid-template-columns:1516px 1516px;gap:32px 40px;align-items:stretch}
.tc{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:28px;padding:30px 34px 32px;display:flex;flex-direction:column;gap:14px}
.tct{font-size:36px;line-height:50px;font-weight:700;white-space:nowrap}
.tr{display:flex;gap:18px;align-items:flex-start}
.trl{flex:none;width:110px;height:40px;border-radius:10px;font-size:22px;line-height:40px;font-weight:700;text-align:center;white-space:nowrap}
.trl.yes{background:#E3F6EC;color:#067647}
.trl.not{background:#FEE4E2;color:#912018}
.trt{flex:1;min-width:0;font-size:27px;line-height:40px}

/* 판 2 */
.sgh{font-size:32px;line-height:46px;font-weight:700;white-space:nowrap;padding-bottom:6px}
.sr{display:flex;gap:28px;padding:12px 0;border-top:2px solid #EEF1F5;align-items:flex-start}
.ss{flex:none;width:540px;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:28px;line-height:42px;white-space:nowrap}
.sn{flex:none;width:500px;font-size:27px;line-height:42px;font-weight:700;white-space:nowrap}
.sd{flex:none;width:1560px;font-size:26px;line-height:42px;color:#344054}
.su{flex:none;width:240px;font-size:24px;line-height:42px;color:#667085;white-space:nowrap}
.dh{display:flex;gap:28px;padding:0 0 10px}
.dhc{font-size:23px;line-height:34px;font-weight:700;color:#667085;white-space:nowrap;flex:none}
.dr{display:flex;gap:28px;padding:16px 0;border-top:2px solid #EEF1F5;align-items:flex-start}
.dk{flex:none;width:420px;display:flex;flex-direction:column;gap:8px;align-items:flex-start}
.dkn{font-size:28px;line-height:40px;font-weight:700;white-space:nowrap}
.dtag{height:38px;line-height:38px;padding:0 14px;border-radius:19px;background:#FDE8E8;color:#B42318;font-size:21px;font-weight:700;white-space:nowrap}
.dc{flex:none;width:1240px;font-size:25px;line-height:40px;color:#344054}
.du{flex:none;width:1240px;font-size:25px;line-height:40px;font-weight:500}

/* 다섯 시각 그림 */
.five{display:flex;align-items:center}
.fnode{width:372px;border-radius:20px;background:#FFFFFF;border:3px solid #B2CCFF;padding:16px 20px 18px;display:flex;flex-direction:column;gap:2px;flex:none}
.fnode.in{border-color:#D0D5DD;background:#F9FAFB}
.fnode.key{border-color:#0E1726}
.fns{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:36px;line-height:48px;white-space:nowrap}
.fnn{font-size:26px;line-height:38px;font-weight:700;white-space:nowrap}
.fnv{font-size:24px;line-height:36px;color:#1D4ED8;font-weight:700;white-space:nowrap}
.fnu{font-size:21px;line-height:32px;color:#667085;white-space:nowrap}
.farr{flex:none;width:212px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px}
.farl{font-size:21px;line-height:30px;font-weight:700;color:#344054;white-space:nowrap}
.fare{font-family:'Inter',sans-serif;font-size:20px;line-height:28px;font-weight:600;color:#1D4ED8;white-space:nowrap}
.fbr{display:flex;flex-direction:column;gap:20px;flex:none}
.fbrr{display:flex;align-items:center}

/* 그림 공통 */
.fig{position:relative;flex:none}
.abs{position:absolute;white-space:nowrap}
.legend{display:flex;gap:30px;align-items:center}
.lgi{display:flex;gap:12px;align-items:center;white-space:nowrap;flex:none}
.lgt{font-size:23px;line-height:34px;color:#344054}
.calc{display:flex;flex-direction:column;gap:10px}
.cl{display:flex;gap:18px;align-items:flex-start}
.cln{flex:none;width:170px;height:40px;border-radius:10px;background:#E8F0FF;color:#1D4ED8;font-family:'Inter',sans-serif;font-weight:700;font-size:22px;line-height:40px;text-align:center;white-space:nowrap}
.clt{flex:1;min-width:0;font-size:27px;line-height:40px}

/* 예제 입력 */
.incards{display:grid;grid-template-columns:744px 744px 744px 744px;gap:32px;align-items:stretch}
.inc{background:#FFFFFF;border:2px solid #E2E7EE;border-radius:28px;padding:28px 30px 30px;display:flex;flex-direction:column;gap:6px}
.inct{font-size:32px;line-height:46px;font-weight:700;white-space:nowrap;padding-bottom:8px}
.inr{display:flex;justify-content:space-between;align-items:center;height:48px;border-top:2px solid #EEF1F5}
.ink{font-size:23px;line-height:46px;color:#475467;white-space:nowrap}
.inv{font-size:26px;line-height:46px;font-weight:700;white-space:nowrap}
.inv.v{color:#B54708}

/* 표 */
.tb{display:flex;flex-direction:column}
.trw{display:flex;align-items:center;border-top:2px solid #EEF1F5;min-height:58px}
.trw.h{border-top:none;min-height:50px}
.trw.hi{background:#F0F6FF}
.trw.sum{background:#F9FAFB}
.td{flex:none;font-size:25px;line-height:38px;white-space:nowrap;padding:8px 10px}
.td.h{font-size:21px;line-height:30px;font-weight:700;color:#667085}
.td.b{font-weight:700}
.td.n{font-family:'Inter',sans-serif;font-weight:600;font-size:25px}
.td.z{color:#C4CAD4}
.td.r{color:#B42318;font-weight:700}
.td.g{color:#067647;font-weight:700}
.pill{display:inline-block;height:40px;line-height:40px;padding:0 14px;border-radius:12px;font-family:'Inter',sans-serif;font-weight:700;font-size:23px;white-space:nowrap;background:#0E1726;color:#FFFFFF}
.pill.a{background:#2F6FED}
.pill.b{background:#0E9384}
.vd{display:inline-block;height:40px;line-height:40px;padding:0 14px;border-radius:20px;font-size:22px;font-weight:700;white-space:nowrap}
.vd.ok{background:#E3F6EC;color:#067647}
.vd.no{background:#FEE4E2;color:#912018}
.vd.amb{background:#FFF4DF;color:#93370D}

/* 충돌 쌍 */
.pairs{display:flex;flex-direction:column;gap:14px}
.pr{display:flex;gap:24px;align-items:center;background:#FFFFFF;border:2px solid #E2E7EE;border-radius:20px;padding:18px 24px}
.pr.bad{border-color:#FDA29B;background:#FFFBFA}
.prn{flex:none;width:330px;display:flex;gap:10px;align-items:center}
.prb{font-size:23px;line-height:40px;color:#475467;white-space:nowrap}
.prc{flex:none;width:1010px;font-size:25px;line-height:38px}
.prv{flex:none;width:420px;display:flex;justify-content:flex-end}

/* 조합 */
.cb{display:flex;gap:24px;align-items:center;background:#FFFFFF;border:2px solid #E2E7EE;border-radius:20px;padding:16px 24px;min-height:84px}
.cb.pass{border:3px solid #12B76A;background:#F6FEF9}
.cbr{flex:none;width:60px;font-family:'Inter',sans-serif;font-weight:700;font-size:28px;line-height:44px;color:#98A2B3;text-align:center}
.cbn{flex:none;width:250px;display:flex;gap:10px;align-items:center}
.cbp{font-size:26px;font-weight:700;color:#98A2B3;line-height:40px}
.cbc{flex:none;width:230px;font-family:'Inter',sans-serif;font-weight:700;font-size:32px;line-height:44px;text-align:right;white-space:nowrap}
.cbw{flex:none;width:1820px;font-size:25px;line-height:38px;color:#344054}
.cbv{flex:none;width:400px;display:flex;justify-content:flex-end;gap:10px}

/* 솔버 답 */
.zrow2{display:flex;gap:14px;align-items:center}
.zc{height:60px;border-radius:14px;padding:0 20px;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:28px;line-height:60px;white-space:nowrap;background:#F2F4F7;color:#98A2B3;flex:none}
.zc.on{background:#2F6FED;color:#FFFFFF}
.obj{font-size:30px;line-height:60px;font-weight:700;white-space:nowrap;margin-left:18px}
.rstrip{display:flex}
.rc{flex:none;width:242px;display:flex;flex-direction:column;align-items:center;border-left:2px solid #EEF1F5;padding:6px 0}
.rct{font-size:21px;line-height:30px;color:#667085;white-space:nowrap}
.rcv{font-family:'Inter',sans-serif;font-weight:700;font-size:32px;line-height:46px;white-space:nowrap}
.rck{font-family:'JetBrains Mono',monospace;font-weight:500;font-size:20px;line-height:28px;color:#98A2B3;white-space:nowrap}
.two{display:grid;grid-template-columns:1516px 1516px;gap:40px;align-items:stretch}
.note{background:#FFF4DF;border-radius:24px;padding:24px 30px;font-size:27px;line-height:42px;color:#7A2E0E}
.okbar{background:#E3F6EC;border-radius:24px;padding:24px 30px;font-size:29px;line-height:44px;font-weight:700;color:#05603A}

/* 판 8 */
.fx{display:flex;gap:28px;padding:18px 0;border-top:2px solid #EEF1F5;align-items:flex-start}
.fxk{flex:none;width:470px;font-size:29px;line-height:42px;font-weight:700}
.fxo{flex:none;width:1140px;font-size:26px;line-height:40px;color:#667085}
.fxn{flex:none;width:1290px;font-size:26px;line-height:40px;font-weight:500}
.adk{flex:none;width:600px;font-size:28px;line-height:42px;font-weight:700}
.adt{flex:none;width:1880px;font-size:26px;line-height:40px;color:#344054}
.ads{flex:none;width:420px;font-size:23px;line-height:40px;font-weight:700;color:#5B45B8}
.oq{background:#FFFFFF;border:2px solid #FEDF89;border-radius:24px;padding:26px 30px 28px;display:flex;gap:22px;align-items:flex-start}
.oqn{flex:none;font-family:'Inter',sans-serif;font-weight:700;font-size:24px;line-height:46px;width:46px;height:46px;border-radius:23px;background:#B54708;color:#FFFFFF;text-align:center}
.oqx{flex:none;width:1960px;display:flex;flex-direction:column;gap:6px}
.oqt{font-size:31px;line-height:46px;font-weight:700;white-space:nowrap}
.oqd{font-size:26px;line-height:40px;color:#344054}
.oqb{flex:none;width:860px;background:#FFFAEB;border-radius:16px;padding:14px 20px;display:flex;flex-direction:column;gap:2px}
.oqbk{font-size:21px;line-height:30px;font-weight:700;color:#93370D;white-space:nowrap}
.oqbv{font-size:25px;line-height:38px;font-weight:500}
"""

AR = ('<svg width="56" height="28" viewBox="0 0 56 28" fill="none"><path d="M3 14H50M38 4L50 14L38 24" '
      'stroke="#98A2B3" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
AR_L = ('<svg width="170" height="24" viewBox="0 0 170 24" fill="none"><path d="M3 12H164M152 3L164 12L152 21" '
        'stroke="#2F6FED" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>')

NBSP = " "


def W(text, cls=""):
    """줄바꿈을 구워야 하는 글. 부모나 자기 폭이 정해져 있어야 한다."""
    return f'<div class="w {cls}">{esc(text)}</div>'


def T(text, cls):
    return f'<div class="{cls}">{esc(text)}</div>'


def FM(text, cls="fm"):
    """식 한 줄. 빈칸은 NBSP로."""
    return f'<div class="{cls}">{esc(text).replace(" ", NBSP)}</div>'


def has_ko(s):
    return any("가" <= ch <= "힣" for ch in s)


def fbox(lines, small=False):
    out = []
    for ln in lines:
        if ln == "또는":
            out.append(T(ln, "for"))
        else:
            out.append(FM(ln, "fm s" if small else "fm"))
    return '<div class="fbox">' + "".join(out) + "</div>"


def head(no, title, sub):
    return (f'<div class="bh"><div class="gno">{no} / {NB}</div><div class="bhx">'
            f'{T(title, "bt")}{W(sub, "bs")}</div></div>')


def sec(title, note=""):
    n = T(note, "secn") if note else ""
    return f'<div class="sech">{T(title, "sec")}{n}</div>'


def bullet(text, tag=""):
    t = f'<div class="add">{esc(tag)}</div>' if tag else ""
    return f'<div class="bl"><div class="bd"><i></i></div>{W(text, "bx")}{t}</div>'


def chips(syms):
    return '<div class="chips">' + "".join(
        f'<div class="chip"><span class="chs">{esc(s)}</span><span class="chn">{esc(n)}</span></div>' for s, n in syms) + "</div>"


def lt(label, text, cls="", lcls=""):
    return f'<div class="lt"><div class="ltl {lcls}">{esc(label)}</div>{W(text, "ltt " + cls)}</div>'


def exbox(lines, title="예제에 넣으면"):
    body = "".join(f'<div class="exl">{T(k, "exk")}{W(v, "exv")}</div>' for k, v in lines)
    return f'<div class="ex">{T(title, "exh")}{body}</div>'


def rng(text):
    if not text:
        return ""
    cls = "frng ko" if has_ko(text) else "frng"
    return f'<div class="{cls}">{esc(text).replace(" ", NBSP)}</div>'


def pill(name):
    return f'<span class="pill {"a" if name[0] == "A" else "b"}">{esc(name)}</span>'


# ─────────────────────────── 머리띠 ───────────────────────────
SHORT = {b[0]: b[3] for b in C.BOARDS}


def zone():
    def row(label, nos):
        return (f'<div class="zrow">{T(label, "zrk")}' + "".join(
            f'<div class="zchip"><span class="zcn">{n}</span><span class="zcx">{esc(SHORT[n])}</span></div>' for n in nos) + "</div>")
    return (f'<section class="cap zone" id="zone"><div class="zl">'
            f'{T("수리계획법 · 최종본 · " + C.DATE, "zk")}{T(C.TITLE, "zt")}'
            f'{T("작업계획 선택 MILP — 솔버에 넣는 식 (1)~(8), 풀기 전에 쓰는 규칙 (9)~(20), 검산 예제", "zs")}</div>'
            f'<div class="zr">{row("윗줄 · 모형", C.ROW1)}{row("아랫줄 · 데이터 · 검산", C.ROW2)}</div></section>')


# ─────────────────────────── 판 1 · 한눈에 ───────────────────────────
def board1():
    facts = [("기준", "팀 공유용 최종 정리 (11-11)"), ("식", "20개 = 본체 8 + 생성 규칙 12"),
             ("솔버가 정하는 값", "z[i,k] · R[t]"), ("풀기 전에 만드는 값", "Ω · C · q · F"),
             ("검산 예제의 답", f"{BEST_NAME} · {money(BEST['objective'])}")]
    fh = "".join(f'<div class="fact">{T(k, "fk")}{T(v, "fv")}</div>' for k, v in facts)
    hero = (f'<div class="hero"><div class="kickrow"><div class="gno">1 / {NB}</div>{T("수리계획법 · 최종본 · " + C.DATE, "kick")}</div>'
            f'{T(C.TITLE, "title")}{T("작업계획 선택 MILP — 솔버에 넣는 식 (1)~(8), 풀기 전에 쓰는 규칙 (9)~(20)", "sub")}'
            f'{W(C.ONE_LINE, "lead")}<div class="facts">{fh}</div></div>')
    order = "".join(
        f'<div class="oc{" me" if no == "1" else ""}"><div class="ocn">{no}</div><div class="ocx">{T(SHORT[no], "oct")}{W(d, "ocd")}</div></div>'
        for no, _, d, _s in C.BOARDS)
    gl = "".join(
        f'<div class="gr"><div class="gn">({no})</div>{FM(f, "gf")}{FM(r, "grng")}{T(k, "gk")}</div>' for no, f, r, k in C.GLANCE)
    glance = (f'<div class="glance"><div class="glh">{T("최종 수식 한눈에", "glt")}'
              f'{T("솔버에 넣는 식은 이 여덟 줄이다. C, q, F, Ω는 풀기 전에 식 (9)~(20)으로 만든다", "gln")}</div>{gl}</div>')
    pipe = []
    for i, (k, t, d) in enumerate(C.PIPE):
        if i:
            pipe.append(f'<div class="par">{AR}</div>')
        pipe.append(f'<div class="pb{" hi" if i in (1, 2) else ""}">{T(k, "pk")}{T(t, "pt")}{W(d, "pd")}</div>')
    half = (len(C.SCOPE) + 1) // 2
    scope = ('<div class="panel">' + T("모형의 범위", "ph") + '<div class="scope">'
             + '<div class="scol">' + "".join(bullet(s) for s in C.SCOPE[:half]) + "</div>"
             + '<div class="scol">' + "".join(bullet(s) for s in C.SCOPE[half:]) + "</div></div></div>")
    terms = "".join(
        f'<div class="tc">{T(t, "tct")}<div class="tr"><div class="trl yes">맞는 뜻</div>{W(y, "trt")}</div>'
        f'<div class="tr"><div class="trl not">아닌 것</div>{W(n, "trt")}</div></div>' for t, y, n in C.TERMS)
    return (f'<section class="cap board" id="b1">{hero}'
            f'{sec("읽는 순서", "판 아홉 개. 윗줄 1~5는 모형, 아랫줄 6~9는 입력 데이터 · 검산 · 정리")}<div class="order">{order}</div>'
            f'{glance}{sec("계산이 흘러가는 순서")}<div class="pipe">{"".join(pipe)}</div>{scope}'
            f'{sec("헷갈리기 쉬운 말", "같은 낱말을 다르게 읽지 않도록 뜻을 하나로 정했다")}<div class="tgrid">{terms}</div></section>')


# ─────────────────────────── 판 2 · 기호 / 판 6 · 입력 데이터 ───────────────────────────
def board2():
    units = '<div class="panel">' + T("단위", "ph") + "".join(bullet(u) for u in C.UNITS) + "</div>"
    groups = []
    for gname, rows in C.SYMBOLS:
        rs = "".join(
            f'<div class="sr">{FM(s, "ss")}{T(n, "sn")}{W(d, "sd")}{T(u or "—", "su")}</div>' for s, n, d, u in rows)
        groups.append(f'<div class="panel">{T(gname, "sgh")}{rs}</div>')
    return (f'<section class="cap board" id="b2">'
            f'{head(2, "기호", "기호마다 한글 이름, 정의, 단위를 하나로 정했다. 대괄호 안이 아래첨자다. z[i,k]는 z에 아래첨자 ik를 붙인 것이다.")}'
            f'{units}{"".join(groups)}</section>')


def board_data():
    def dtable(title, note, rows):
        hd = (f'<div class="dh"><div class="dhc" style="width:420px">데이터 구분</div>'
              f'<div class="dhc" style="width:1240px">컬럼</div><div class="dhc" style="width:1240px">식에서 쓰는 곳</div></div>')
        rs = []
        for k, cols, use, tag in rows:
            tg = f'<div class="dtag">표시: {esc(tag)}</div>' if tag else ""
            rs.append(f'<div class="dr"><div class="dk">{T(k, "dkn")}{tg}</div>{W(cols, "dc")}{W(use, "du")}</div>')
        nt = W(note, "pn") if note else ""
        return f'<div class="panel">{T(title, "sgh")}{nt}{hd}{"".join(rs)}</div>'

    r = C.RATE
    rate = (f'<div class="panel">{T(r["title"], "sgh")}{fbox([r["formula"]])}{lt("한글 식", r["korean"], "k")}'
            + "".join(bullet(x) for x in r["lines"]) + f'<div class="note w">{esc(r["example"])}</div></div>')
    return (f'<section class="cap board" id="b6">'
            f'{head(6, "입력 데이터가 들어가는 곳", "페이지 오른쪽에 붙여 둔 입력 컬럼 표와 같은 순서다. 컬럼마다 어느 식의 어느 기호가 되는지 적었다.")}'
            f'{dtable("공통 입력", C.DATA_TAG_NOTE, C.DATA_COMMON)}{dtable("분할 하역(유형 2)에 더 필요한 입력", "", C.DATA_SPLIT)}'
            f'{dtable("위 입력으로 계산해서 솔버에 넘기는 값", C.DATA_NOTE, C.DATA_DERIVED)}'
            f'{sec("하역속도의 단위", "표시해 둔 화물 이송율 표와 식을 잇는다")}{rate}</section>')


# ─────────────────────────── 판 3 · 본체 ───────────────────────────
def body_examples():
    c = {n: P[n]["cost"] for n in P}
    ex = {}
    ex["1"] = [
        ("식에 숫자를 넣으면", "총 체선료 = " + " + ".join(f"{num(c[n])}·{zn(n)}" for n in P)),
        (f"1안 ({BEST_NAME})", " + ".join(f"{n} {money(c[n])}" for n in BEST["chosen"]) + f" = {money(BEST['objective'])}"),
        (f"2안 ({SECOND_NAME})", " + ".join(f"{n} {money(c[n])}" for n in SECOND["chosen"]) + f" = {money(SECOND['objective'])}"),
    ]
    rows = []
    for arr in E.ARRIVALS:
        names = [n for n in P if P[n]["arrival"] == arr]
        rows.append((f"입항 건 {arr} (1안)", " + ".join(zn(n) for n in names) + " = "
                     + " + ".join(str(BEST["z"][n]) for n in names) + " = 1"))
    ex["2"] = rows
    rows = []
    for f in X["F"]:
        a, b = f["pair"]
        s = BEST["z"][a] + BEST["z"][b]
        rows.append((f"충돌 쌍 ({a}, {b}) · 1안", f"{zn(a)} + {zn(b)} = {BEST['z'][a]} + {BEST['z'][b]} = {s} ≤ 1 → 통과"))
    f0 = X["F"][0]["pair"]
    rows.append((f"{f0[0]}{josa(f0[0], '과와')} {f0[1]}{josa(f0[1], '을를')} 같이 고르면", "1 + 1 = 2 > 1 → 답이 될 수 없다"))
    ex["3"] = rows

    def step(t, sol, label):
        ins = [(n, X["q"][n][t]) for n in sol["chosen"] if X["q"][n][t] > 1e-9]
        mid = "".join(f" + {n} 하역 {vol(v)}" for n, v in ins) or " + 하역 0"
        return (f"{label} · 구간 t={t} ({hh(TAU[t])}h~{hh(TAU[t + 1])}h)",
                f"다음 재고 R[{t + 1}] = 지금 재고 {vol(sol['R'][t])}{mid} − 공정 소비 {vol(X['D'][t])} = {vol(sol['R'][t + 1])}")
    ex["4"] = [step(tidx(3), BEST, "1안"), step(tidx(20), BEST, "1안"),
               ("나머지 구간", f"구간 {NT}개 전부는 판 8의 표에 있다 (단위: 만 배럴)")]
    ex["5"] = [("예제", f"R[0] = {vol(X['R0'])}만 배럴 (계획 시작 시점의 재고)")]
    rb = BYCOMBO["+".join(BEST["chosen"])]
    over = next(r for r in COMBOS if r["why"] == ["over"])
    under = next(r for r in COMBOS if r["why"] == ["under"])
    ex["6"] = [
        (f"1안 ({BEST_NAME})", f"가장 낮을 때 {vol(rb['min'][1])} ({hh(rb['min'][0])}h), 가장 높을 때 {vol(rb['max'][1])} ({hh(rb['max'][0])}h) "
                               f"→ {vol(X['R_MIN'])} ≤ R[t] ≤ {vol(X['R_MAX'])} 통과"),
        (" + ".join(over["combo"]), why_text(over)[0] + " → 탈락"),
        (" + ".join(under["combo"]), why_text(under)[0] + " → 탈락"),
    ]
    ex["7"] = [("예제의 변수", f"z {len(P)}개 ({', '.join(P)}) + R {NT + 1}개 (평가 시점 {NT + 1}개) = {N_VAR}개"),
               ("예제의 제약식", f"식 (2) {len(E.ARRIVALS)}줄 + 식 (3) {len(X['F'])}줄 + 식 (4) {NT}줄 + 식 (5) 1줄 = {N_ROW}줄. 식 (6)은 R의 상·하한")]
    fd = X.get("fix_demo")
    fx = fd["fixed"][0]
    assert fd["result"]["status"] != "optimal", "FIX 시연이 가능한 답을 냈다 — 설명 문장을 고쳐야 한다"
    left = [r for r in COMBOS if fx in r["combo"]]
    ex["8"] = [("예제", "FIX 입항 건이 없다. 식 (8)은 쓰이지 않았다"),
               (f"만약 B를 {fx}{josa(fx, '으로로')} 고정하면",
                f"{zn(fx)} = 1을 더한다. 남는 조합은 " + ", ".join(" + ".join(r["combo"]) for r in left)
                + f"뿐인데 모두 탈락한다 (판 8의 {'·'.join(str(r['rank']) for r in left)}번). "
                  "가능한 조합이 없으므로 '실행 가능한 후보 없음'이다. 솔버도 같은 답을 냈다")]
    return ex


def board3():
    ex = body_examples()
    cards = []
    for no, name, lines, rg, syms, kor, read in C.BODY:
        left = fbox(lines) + chips(syms) + lt("한글 식", kor, "k") + lt("읽는 법", read, "", "g")
        cards.append(f'<div class="fcard"><div class="fch"><div class="fno">({no})</div>{T(name, "fct")}{rng(rg)}</div>'
                     f'<div class="fcols"><div class="fl">{left}</div><div class="fr">{exbox(ex[no])}</div></div></div>')
    n = C.NEXT
    s3 = SOL[2] if len(SOL) > 2 else None
    third = "가능한 조합이 없다 → 3안 없음" if (s3 is None or s3["status"] != "optimal") else f"3안 {' + '.join(s3['chosen'])} {money(s3['objective'])}"
    nex = [(f"1안 S = {{{', '.join(BEST['chosen'])}}}을 막으면", " + ".join(zn(x) for x in BEST["chosen"]) + f" ≤ {len(E.ARRIVALS) - 1}"
            + f" → 다시 풀면 2안 {SECOND_NAME} {money(SECOND['objective'])}"),
           (f"2안 S = {{{', '.join(SECOND['chosen'])}}}도 막으면", third)]
    left = fbox(n["lines"]) + chips(n["syms"]) + lt("한글 식", n["korean"], "k") + lt("읽는 법", n["read"], "", "g") + lt("근거", n["src"], "", "g")
    plus = (f'<div class="fcard plus"><div class="fch"><div class="fno plus">(+)</div>{T(n["title"], "fct")}{rng(n["rng"])}'
            f'<div class="add" style="margin-top:0">{esc(n["tag"])}</div></div>'
            f'<div class="fcols"><div class="fl">{left}</div><div class="fr">{exbox(nex)}</div></div></div>')
    notes = '<div class="panel">' + T("식 밖에서 정해 두는 것", "ph") + "".join(
        f'<div class="lt"><div class="ltl g" style="width:210px">{esc(k)}</div>{W(v, "ltt")}</div>' for k, v in C.BODY_NOTES) + "</div>"
    return (f'<section class="cap board" id="b3">'
            f'{head(3, "최적화 본체 · 식 (1)~(8)", "솔버에 넣는 식 전부다. 왼쪽은 식, 기호 이름, 한글 식이고 오른쪽은 검산 예제의 숫자를 넣은 결과다.")}'
            f'{"".join(cards)}{plus}{notes}</section>')


# ─────────────────────────── 판 4·5 · 생성 규칙 ───────────────────────────
def gen_examples():
    a1, a2, b1, b3 = P["A1"], P["A2"], P["B1"], P["B3"]
    A, B = E.ARRIVALS["A"], E.ARRIVALS["B"]
    d3 = E.BERTHS["BUOY3"]
    v1, v2 = T2["visits"]
    ex = {}
    ex["9"] = [("A1", f"방문 1번. 그 방문에서 {vol(A['Q'])}만 배럴 전부")]
    ex["10"] = [("설명용 A4", f"방문 2번 = {v1['berth']} {vol(v1['Q'])}만 + {v2['berth']} {vol(v2['Q'])}만 = {vol(T2['Q'])}만 배럴")]
    ex["11"] = [("A1", f"접안 ≥ 도착 {hh(A['eta'])} + 접안 소요 {hh(d3['direction'])} = {hh(A['eta'] + d3['direction'])}h → 가장 이른 {hh(a1['s'])}h로 만들었다"),
                ("B3", f"가장 이르게는 {hh(B['eta'])} + {hh(d3['direction'])} = {hh(B['eta'] + d3['direction'])}h. A1 뒤에 서도록 {hh(b3['s'])}h로 만들었다 (식 (18))")]
    ex["12"] = [("A1", f"하역 시작 = 접안 {hh(a1['s'])} + 준비 {hh(E.D_SETUP)} = {hh(a1['a'])}h")]
    ex["13"] = [("A1 · BUOY3", f"하역 완료 = 하역 시작 {hh(a1['a'])} + ({vol(a1['Q'])}만 배럴 ÷ 시간당 {vol(a1['rate'])}만 배럴) = {hh(a1['c'])}h"),
                ("A2 · BUOY2", f"{hh(a2['a'])} + ({vol(a2['Q'])} ÷ {vol(a2['rate'])}) = {hh(a2['c'])}h")]
    ex["14"] = [("A1", f"호스분리 = 하역 완료 {hh(a1['c'])} + {hh(E.D_HOSE)} = {hh(a1['h'])}h")]
    ex["15"] = [("A1", f"이안 = 하역 완료 {hh(a1['c'])} + {hh(E.D_DEPART)} = {hh(a1['u'])}h")]
    ex["16"] = [("설명용 A4", f"다음 접안 ≥ {v1['berth']} 이안 {hh(v1['u'])} + 이동 {hh(T2['move'])} = {hh(v2['s'])}h")]
    t1, t0, t8 = tidx(3), 0, tidx(22)
    ex["17"] = [(f"A1 · 구간 t={t1} ({hh(TAU[t1])}h~{hh(TAU[t1 + 1])}h)",
                 f"시간당 {vol(a1['rate'])}만 배럴 × 겹친 {hh(TAU[t1 + 1] - TAU[t1])}시간 = {vol(X['q']['A1'][t1])}만 배럴"),
                (f"A1 · 구간 t={t0} ({hh(TAU[0])}h~{hh(TAU[1])}h)", f"하역 시작({hh(a1['a'])}h) 전이라 겹친 시간 0 → 0"),
                (f"B3 · 구간 t={t8} ({hh(TAU[t8])}h~{hh(TAU[t8 + 1])}h)",
                 f"{vol(b3['rate'])} × {hh(TAU[t8 + 1] - TAU[t8])} = {vol(X['q']['B3'][t8])}만 배럴")]
    sw = d3["switching"]
    ex["18"] = [("A1 · B3 (BUOY3)", f"B3 접안 {hh(b3['s'])} ≥ A1 이안 {hh(a1['u'])} + 교대 {hh(sw)} = {hh(a1['u'] + sw)} → 통과 (같은 시각)"),
                ("A1 · B1 (BUOY3)", f"B1 접안 {hh(b1['s'])} < {hh(a1['u'] + sw)}이고, A1 접안 {hh(a1['s'])} < B1 이안 {hh(b1['u'])} + 교대 {hh(sw)} = {hh(b1['u'] + sw)} "
                                    f"→ 두 순서 모두 안 됨 → F에 넣는다")]
    ex["19"] = [("예제", "A와 B 모두 식 (20) 꼴의 계약으로 두었다")]

    def c20(p, arr):
        a = E.ARRIVALS[arr]
        return (f"({num(a['rate_day'])} ÷ 24) × max(0, 호스분리 {hh(p['h'])} − 정박개시 {hh(a['laytime_start'])} − 허용시간 {hh(a['laytime'])} − 공제 {num(a['deduction'])})"
                f" = {num(a['rate_day'] / 24)} × {hh(p['over'])} = {money(p['cost'])}")
    ex["20"] = [("B3", c20(b3, "B")), ("A2", c20(a2, "A")),
                ("A1", f"호스분리 {hh(a1['h'])}가 정박종료 {hh(a1['laytime_end'])}보다 이르다 → max(0, −{hh(a1['laytime_end'] - a1['h'])}) = 0 → {money(a1['cost'])}")]
    return ex


STACK = {"17", "20"}      # 식이 길어 한 줄을 통째로 쓰는 카드


def gen_card(item, ex, wide):
    no, name, lines, rg, kor = item
    if wide and no in STACK:
        return (f'<div class="fcard"><div class="fch"><div class="fno">({no})</div>{T(name, "fct")}{rng(rg)}</div>{fbox(lines)}'
                f'<div class="fcols"><div class="fl2">{lt("한글 식", kor, "k")}</div><div class="fr2">{exbox(ex[no])}</div></div></div>')
    if wide:
        left = fbox(lines) + lt("한글 식", kor, "k")
        return (f'<div class="fcard"><div class="fch"><div class="fno">({no})</div>{T(name, "fct")}{rng(rg)}</div>'
                f'<div class="fcols"><div class="fl">{left}</div><div class="fr">{exbox(ex[no])}</div></div></div>')
    return (f'<div class="fcard"><div class="fch"><div class="fno">({no})</div>{T(name, "fct")}{rng(rg)}</div>'
            f'{fbox(lines, small=True)}{lt("한글 식", kor, "k")}{exbox(ex[no])}</div>')


def defs_panel(gname):
    return ('<div class="defs">' + T("이 묶음에서 문장으로 정해 두는 것", "defh")
            + "".join(bullet(t, tag) for t, tag in C.GEN_DEFS[gname]) + "</div>")


def grp(i, name, desc):
    return f'<div class="grp"><div class="grpn">{esc(name)}</div>{T(desc, "grpd")}</div>'


def five_fig():
    a1 = P["A1"]
    A = E.ARRIVALS["A"]
    d = E.BERTHS["BUOY3"]["direction"]

    def node(sym, name, val, use, cls=""):
        return (f'<div class="fnode {cls}">{FM(sym, "fns")}{T(name, "fnn")}{T("A1: " + val, "fnv")}{T(use, "fnu")}</div>')

    def arr(label, eq):
        return f'<div class="farr">{T(label, "farl")}{AR_L}{T(eq, "fare")}</div>'
    main = (node("ETA", "도착 예정", hh(A["eta"]) + "h", "입력", "in") + arr(f"+ Direction {hh(d)}h", "식 (11)")
            + node("s", "접안 (ETB)", hh(a1["s"]) + "h", "부두 점유 시작 → 식 (18)") + arr(f"+ δ_setup {hh(E.D_SETUP)}h", "식 (12)")
            + node("a", "하역 시작", hh(a1["a"]) + "h", "하역량 계산 시작 → 식 (17)")
            + arr(f"+ Q ÷ v = {hh(a1['c'] - a1['a'])}h", "식 (13)")
            + node("c", "하역 완료", hh(a1["c"]) + "h", "하역량 계산 끝 → 식 (17)"))
    br = (f'<div class="fbr"><div class="fbrr">{arr(f"+ δ_hose {hh(E.D_HOSE)}h", "식 (14)")}'
          f'{node("h", "호스분리", hh(a1["h"]) + "h", "체선료의 끝점 → 식 (20)", "key")}</div>'
          f'<div class="fbrr">{arr(f"+ δ_departure {hh(E.D_DEPART)}h", "식 (15)")}'
          f'{node("u", "이안 (ETU)", hh(a1["u"]) + "h", "부두 점유 끝 → 식 (18)")}</div></div>')
    return (f'<div class="panel">{T("방문 하나의 다섯 시각", "ph")}'
            f'{W("호스분리와 이안은 둘 다 하역 완료에서 잰다. 체선료는 호스분리까지, 부두 점유는 이안까지다. 숫자는 검산 예제의 작업계획 A1이다.", "pn")}'
            f'<div class="five">{main}{br}</div></div>')


def type2_panel():
    v1, v2 = T2["visits"]
    A = E.ARRIVALS["A"]
    pxh, lw = 100, 190
    cw = 26 * pxh
    rowh, barh = 96, 52
    top = 86
    els = []
    for t in range(0, 27, 2):
        x = lw + t * pxh
        els.append(f'<div class="abs" style="left:{x}px;top:{top - 10}px;width:2px;height:{2 * rowh + 34}px;background:#E2E7EE"></div>')
        els.append(f'<div class="abs" style="left:{x - 40}px;top:{top + 2 * rowh + 30}px;width:80px;text-align:center;font-size:21px;line-height:30px;color:#667085">{t}h</div>')
    ls, le = A["laytime_start"], A["laytime_start"] + A["laytime"]
    els.append(f'<div class="abs" style="left:{lw + ls * pxh}px;top:{top - 10}px;width:{(le - ls) * pxh}px;height:{2 * rowh + 34}px;background:#F3F0FF;border-left:3px dashed #6E56CF;border-right:3px dashed #6E56CF"></div>')
    els.append(f'<div class="abs" style="left:{lw + ls * pxh + 14}px;top:{top - 52}px;font-size:22px;line-height:34px;font-weight:700;color:#5B45B8">'
               f'허용시간 {hh(A["laytime"])}h는 한 번만 · 정박개시 {hh(ls)} → 정박종료 {hh(le)}</div>')
    for i, v in enumerate((v1, v2)):
        y = top + i * rowh + 10
        els.append(f'<div class="abs" style="left:0;top:{y}px;width:{lw - 20}px;font-size:24px;line-height:{barh}px;font-weight:700">방문 {v["m"]} · {v["berth"]}</div>')
        els.append(f'<div class="abs" style="left:{lw + v["s"] * pxh}px;top:{y}px;width:{(v["u"] - v["s"]) * pxh}px;height:{barh}px;background:#C7D7FE;border-radius:12px"></div>')
        els.append(f'<div class="abs" style="left:{lw + v["a"] * pxh}px;top:{y}px;width:{(v["c"] - v["a"]) * pxh}px;height:{barh}px;background:#2F6FED;border-radius:8px;'
                   f'color:#FFFFFF;font-size:22px;line-height:{barh}px;font-weight:700;text-align:center">하역 {vol(v["Q"])}만 배럴 · {hh(v["a"])}~{hh(v["c"])}</div>')
        els.append(f'<div class="abs" style="left:{lw + v["h"] * pxh - 3}px;top:{y - 8}px;width:6px;height:{barh + 16}px;background:#0E1726"></div>')
    y2 = top + rowh + 10
    x0, x1 = lw + v1["u"] * pxh, lw + v2["s"] * pxh
    els.append(f'<div class="abs" style="left:{x0}px;top:{top + 10 + barh // 2 - 2}px;width:{x1 - x0}px;height:4px;background:#98A2B3"></div>')
    els.append(f'<div class="abs" style="left:{x0 + 12}px;top:{top + 10 - 14}px;font-size:21px;line-height:30px;font-weight:700;color:#475467">이동 {hh(T2["move"])}h</div>')
    els.append(f'<div class="abs" style="left:{x1 - 2}px;top:{top + 10 + barh // 2}px;width:4px;height:{rowh - barh // 2}px;background:#98A2B3"></div>')
    xe0, xe1 = lw + le * pxh, lw + T2["H"] * pxh
    els.append(f'<div class="abs" style="left:{xe0}px;top:{y2 + barh + 8}px;width:{xe1 - xe0}px;height:14px;background:#D92D20;border-radius:7px"></div>')
    els.append(f'<div class="abs" style="left:{xe1 + 16}px;top:{y2 + barh - 2}px;font-size:22px;line-height:34px;font-weight:700;color:#B42318">'
               f'초과 {hh(T2["over"])}h · 마지막 방문의 호스분리 {hh(T2["H"])}까지</div>')
    fig = f'<div class="fig" style="width:{lw + cw + 190}px;height:{top + 2 * rowh + 70}px">{"".join(els)}</div>'
    calc = [
        ("식 (10)", f"물량: {vol(v1['Q'])} + {vol(v2['Q'])} = {vol(T2['Q'])}만 배럴 (남은 물량 전부)"),
        ("식 (11)~(15)", f"방문 1 · {v1['berth']}: 접안 {hh(v1['s'])} → 하역 {hh(v1['a'])}~{hh(v1['c'])} ({vol(v1['Q'])} ÷ {vol(v1['rate'])} = {hh(v1['c'] - v1['a'])}시간) → 호스분리 {hh(v1['h'])} → 이안 {hh(v1['u'])}"),
        ("식 (16)", f"이동: 다음 접안 ≥ 이안 {hh(v1['u'])} + 이동 {hh(T2['move'])} = {hh(v2['s'])}"),
        ("식 (12)~(15)", f"방문 2 · {v2['berth']}: 접안 {hh(v2['s'])} → 하역 {hh(v2['a'])}~{hh(v2['c'])} ({vol(v2['Q'])} ÷ {vol(v2['rate'])} = {hh(v2['c'] - v2['a'])}시간) → 호스분리 {hh(v2['h'])} → 이안 {hh(v2['u'])}"),
        ("식 (17)", f"하역량: {hh(v1['a'])}~{hh(v1['c'])}에 시간당 {vol(v1['rate'])}만 배럴, {hh(v2['a'])}~{hh(v2['c'])}에 시간당 {vol(v2['rate'])}만 배럴. 그 사이(이동·준비)는 0"),
        ("식 (20)", f"체선료: 사용시간 종료 H = 마지막 방문의 호스분리 {hh(T2['H'])}. ({num(A['rate_day'])} ÷ 24) × max(0, {hh(T2['H'])} − {hh(ls)} − {hh(A['laytime'])} − {hh(A['deduction'])})"
                    f" = {num(A['rate_day'] / 24)} × {hh(T2['over'])} = {money(T2['cost'])}. 방문 1의 호스분리 {hh(v1['h'])}는 쓰지 않는다"),
    ]
    ch = '<div class="calc">' + "".join(f'<div class="cl"><div class="cln">{esc(k)}</div>{W(v, "clt")}</div>' for k, v in calc) + "</div>"
    return (f'<div class="panel">{T("유형 2 작업계획 하나를 끝까지 계산하면 — 설명용 A4", "ph")}'
            f'{W(f"입항 건 A가 {v1["berth"]}에서 {vol(v1["Q"])}만 배럴을 내리고 {v2["berth"]}로 옮겨 {vol(v2["Q"])}만 배럴을 내리는 계획이다. 부두 간 이동시간 {hh(T2["move"])}시간은 가상 값이다. 검산 예제의 Ω에는 넣지 않았다.", "pn")}'
            f'{fig}{ch}</div>')


def board4():
    ex = gen_examples()
    g = {name: (desc, items) for name, desc, items in C.GEN}
    out = [head(4, "생성 규칙 ① 물량 · 방문 일정 · 식 (9)~(16)",
                "솔버를 돌리기 전에 입항 건마다 작업계획 집합 Ω[i]를 만든다. 작업계획 하나는 방문 한 번 이상이고, 방문마다 시각 다섯 개가 정해진다."),
           five_fig()]
    for name in ("유형별 물량", "방문 일정"):
        desc, items = g[name]
        out.append(grp(0, name, desc))
        out.append('<div class="g2">' + "".join(gen_card(it, ex, False) for it in items) + "</div>")
        out.append(defs_panel(name))
    out.append(type2_panel())
    return f'<section class="cap board" id="b4">{"".join(out)}</section>'


def board5():
    ex = gen_examples()
    g = {name: (desc, items) for name, desc, items in C.GEN}
    out = [head(5, "생성 규칙 ② 하역량 · 충돌 · 체선료 · 식 (17)~(20)",
                "만들어 둔 작업계획에서 솔버가 쓸 숫자 세 가지를 계산한다. 구간별 하역량 q, 충돌 쌍 F, 체선료 C다.")]
    for name in ("구간별 하역량", "충돌 판정", "계약별 체선료"):
        desc, items = g[name]
        out.append(grp(0, name, desc))
        out.extend(gen_card(it, ex, True) for it in items)
        out.append(defs_panel(name))
    st = "".join(f'<div class="lt"><div class="ltl g" style="width:400px">{esc(k)}</div>{W(v, "ltt")}</div>' for k, v in C.GEN_SETTINGS)
    out.append(sec("작업계획을 만들 때 정해야 하는 설정", "답은 만들어 둔 계획 안에서의 최적이다. 이 값이 답의 품질을 정한다"))
    out.append(f'<div class="panel">{st}</div>')
    return f'<section class="cap board" id="b5">{"".join(out)}</section>'


# ─────────────────────────── 판 7 · 검산 예제 ① ───────────────────────────
def gantt():
    pxh, lw, rw = 66, 300, 312
    cw = 36 * pxh
    rowh, barh = 124, 56
    axis_h, ghead, ggap = 56, 56, 40
    els = []
    names = {"A": [n for n in P if P[n]["arrival"] == "A"], "B": [n for n in P if P[n]["arrival"] == "B"]}
    gh = ghead + 3 * rowh
    total_h = axis_h + 2 * gh + ggap + 10
    for t in range(0, 37, 3):
        x = lw + t * pxh
        els.append(f'<div class="abs" style="left:{x}px;top:{axis_h - 6}px;width:2px;height:{total_h - axis_h}px;background:#E2E7EE"></div>')
        els.append(f'<div class="abs" style="left:{x - 40}px;top:6px;width:80px;text-align:center;font-family:Inter,sans-serif;font-weight:600;font-size:22px;line-height:32px;color:#667085">{t}h</div>')
    for gi, arr in enumerate(("A", "B")):
        a = E.ARRIVALS[arr]
        gy = axis_h + gi * (gh + ggap)
        ls, le = a["laytime_start"], a["laytime_start"] + a["laytime"]
        els.append(f'<div class="abs" style="left:{lw + ls * pxh}px;top:{gy + ghead - 8}px;width:{(le - ls) * pxh}px;height:{3 * rowh + 6}px;'
                   f'background:#F3F0FF;border-left:3px dashed #6E56CF;border-right:3px dashed #6E56CF"></div>')
        els.append(f'<div class="abs" style="left:0;top:{gy + 6}px;font-size:26px;line-height:40px;font-weight:700">입항 건 {arr}</div>')
        els.append(f'<div class="abs" style="left:{lw + ls * pxh + 12}px;top:{gy + 8}px;font-size:22px;line-height:36px;font-weight:700;color:#5B45B8">'
                   f'허용시간 {hh(a["laytime"])}h · 정박개시 {hh(ls)} → 정박종료 {hh(le)}</div>')
        for ri, n in enumerate(names[arr]):
            p = P[n]
            y = gy + ghead + ri * rowh + 14
            els.append(f'<div class="abs" style="left:0;top:{y + 8}px;display:flex;gap:12px;align-items:center">{pill(n)}'
                       f'<span style="font-size:24px;line-height:40px;font-weight:700">{p["berth"]}</span></div>')
            els.append(f'<div class="abs" style="left:0;top:{y + 52}px;font-size:20px;line-height:30px;color:#667085">접안 {hh(p["s"])} · 이안 {hh(p["u"])}</div>')
            ex0 = lw + a["eta"] * pxh
            if p["s"] > a["eta"]:
                els.append(f'<div class="abs" style="left:{ex0}px;top:{y + barh // 2 - 2}px;width:{(p["s"] - a["eta"]) * pxh}px;height:0;border-top:4px dashed #98A2B3"></div>')
            els.append(f'<div class="abs" style="left:{ex0 - 9}px;top:{y + barh // 2 - 9}px;width:18px;height:18px;border-radius:9px;background:#FFFFFF;border:4px solid #0E1726"></div>')
            els.append(f'<div class="abs" style="left:{lw + p["s"] * pxh}px;top:{y}px;width:{(p["u"] - p["s"]) * pxh}px;height:{barh}px;background:#C7D7FE;border-radius:12px"></div>')
            els.append(f'<div class="abs" style="left:{lw + p["a"] * pxh}px;top:{y}px;width:{(p["c"] - p["a"]) * pxh}px;height:{barh}px;background:#2F6FED;border-radius:8px;'
                       f'color:#FFFFFF;font-size:22px;line-height:{barh}px;font-weight:700;text-align:center">하역 {hh(p["a"])}~{hh(p["c"])}</div>')
            els.append(f'<div class="abs" style="left:{lw + p["h"] * pxh - 3}px;top:{y - 8}px;width:6px;height:{barh + 16}px;background:#0E1726"></div>')
            if p["over"] > 1e-9:
                els.append(f'<div class="abs" style="left:{lw + le * pxh}px;top:{y + barh + 10}px;width:{p["over"] * pxh}px;height:14px;background:#D92D20;border-radius:7px"></div>')
            rx = lw + cw + 24
            els.append(f'<div class="abs" style="left:{rx}px;top:{y - 2}px;font-size:23px;line-height:34px;font-weight:700">호스분리 {hh(p["h"])}h</div>')
            if p["over"] > 1e-9:
                els.append(f'<div class="abs" style="left:{rx}px;top:{y + 32}px;font-size:23px;line-height:34px;font-weight:700;color:#B42318">초과 {hh(p["over"])}h → {money(p["cost"])}</div>')
            else:
                els.append(f'<div class="abs" style="left:{rx}px;top:{y + 32}px;font-size:23px;line-height:34px;font-weight:700;color:#067647">초과 없음 → {money(0)}</div>')
    fig = f'<div class="fig" style="width:{lw + cw + rw}px;height:{total_h}px">{"".join(els)}</div>'
    lg = [('<span style="display:block;width:18px;height:18px;border-radius:9px;border:4px solid #0E1726;background:#FFFFFF"></span>', "ETA (점선은 접안까지 대기)"),
          ('<span style="display:block;width:56px;height:26px;border-radius:8px;background:#C7D7FE"></span>', "접안~이안 (부두 점유)"),
          ('<span style="display:block;width:56px;height:26px;border-radius:6px;background:#2F6FED"></span>', "하역 중"),
          ('<span style="display:block;width:6px;height:34px;background:#0E1726"></span>', "호스분리 (체선료의 끝점)"),
          ('<span style="display:block;width:56px;height:26px;background:#F3F0FF;border-left:3px dashed #6E56CF;border-right:3px dashed #6E56CF"></span>', "허용시간"),
          ('<span style="display:block;width:56px;height:14px;border-radius:7px;background:#D92D20"></span>', "초과 = 정박종료 → 호스분리")]
    legend = '<div class="legend">' + "".join(f'<div class="lgi">{sw}<span class="lgt">{esc(tx)}</span></div>' for sw, tx in lg) + "</div>"
    return fig + legend


def plan_table():
    cols = [("계획", 150), ("부두", 190), ("접안 s", 200), ("하역 시작 a", 230), ("하역 완료 c", 230), ("호스분리 h", 230), ("이안 u", 200),
            ("정박종료 ℓ + A", 260), ("초과 h − (ℓ + A)", 300), ("체선료 C", 250), ("이전 판 (하역 완료 기준)", 330)]
    hd = '<div class="trw h">' + "".join(f'<div class="td h" style="width:{w}px">{esc(c)}</div>' for c, w in cols) + "</div>"
    rows = []
    for n, p in P.items():
        diff = p["h"] - p["laytime_end"]
        vals = [pill(n), esc(p["berth"]), hh(p["s"]), hh(p["a"]), hh(p["c"]), hh(p["h"]), hh(p["u"]), hh(p["laytime_end"]),
                (f"{hh(p['over'])}h" if diff > 0 else f"없음 (−{hh(-diff)})"), money(p["cost"]), money(X["old_cost"][n])]
        cls = ["", "b", "n", "n", "n", "n b", "n", "n", "n " + ("r" if diff > 0 else "g"), "n b", "n z"]
        rows.append('<div class="trw">' + "".join(
            f'<div class="td {c}" style="width:{w}px">{v}</div>' for v, c, (_, w) in zip(vals, cls, cols)) + "</div>")
    return f'<div class="tb">{hd}{"".join(rows)}</div>'


def pair_rows():
    out = []
    names = list(P)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pa, pb = P[a], P[b]
            if pa["arrival"] == pb["arrival"] or pa["berth"] != pb["berth"]:
                continue
            sw = E.BERTHS[pa["berth"]]["switching"]
            ok1 = pb["s"] >= pa["u"] + sw - 1e-9
            ok2 = pa["s"] >= pb["u"] + sw - 1e-9

            def chk(x, y, ok):
                lhs, rhs = P[x]["s"], P[y]["u"] + sw
                op = "=" if abs(lhs - rhs) < 1e-9 else (">" if lhs > rhs else "<")
                return f"{x} 접안 {hh(lhs)} {op} {y} 이안 {hh(P[y]['u'])} + 교대 {hh(sw)} = {hh(rhs)} → {'된다' if ok else '안 된다'}"
            bad = not (ok1 or ok2)
            verdict = ('<span class="vd no">두 순서 모두 안 됨 → F에 넣는다</span>' if bad
                       else '<span class="vd ok">한 순서가 된다 → 충돌 아님</span>')
            out.append(f'<div class="pr{" bad" if bad else ""}"><div class="prn">{pill(a)}{pill(b)}<span class="prb">{esc(pa["berth"])}</span></div>'
                       f'{W(f"{a} 뒤에 {b}: " + chk(b, a, ok1), "prc")}{W(f"{b} 뒤에 {a}: " + chk(a, b, ok2), "prc")}'
                       f'<div class="prv">{verdict}</div></div>')
    return '<div class="pairs">' + "".join(out) + "</div>"


def tau_events():
    ev = {0.0: ["계획 시작"], X["T_END"]: ["계획 종료"]}
    for n, p in P.items():
        ev.setdefault(p["a"], []).append(f"{n} 하역 시작")
        ev.setdefault(p["c"], []).append(f"{n} 하역 완료")
    out = []
    for i, t in enumerate(TAU):
        items = ev[t]
        starts = [x.split()[0] for x in items if x.endswith("하역 시작")]
        ends = [x.split()[0] for x in items if x.endswith("하역 완료")]
        other = [x for x in items if x.startswith("계획")]
        parts = other + ([" · ".join(starts) + " 하역 시작"] if starts else []) + ([" · ".join(ends) + " 하역 완료"] if ends else [])
        out.append((i, t, ", ".join(parts)))
    return out


def tau_strip():
    cells = "".join(
        f'<div class="rc">{FM(f"τ[{i}]", "rck")}<div class="rcv">{hh(t)}h</div><div class="rct">{esc(why)}</div></div>' for i, t, why in tau_events())
    return f'<div class="rstrip">{cells}</div>'


def q_table():
    w0, w, wt = 330, 222, 200
    hd = f'<div class="trw h"><div class="td h" style="width:{w0}px">구간 t · 시간</div>' + "".join(
        f'<div class="td h" style="width:{w}px">t={t} · {hh(TAU[t])}~{hh(TAU[t + 1])}h</div>' for t in range(NT)) + f'<div class="td h" style="width:{wt}px">합계</div></div>'
    rows = []
    for n in P:
        cells = "".join(
            f'<div class="td n {"z" if X["q"][n][t] < 1e-9 else "b"}" style="width:{w}px">{"·" if X["q"][n][t] < 1e-9 else vol(X["q"][n][t])}</div>' for t in range(NT))
        rows.append(f'<div class="trw"><div class="td" style="width:{w0}px">{pill(n)} <span style="font-size:22px;color:#667085">q[{n[0]},{n[1:]},t]</span></div>{cells}'
                    f'<div class="td n b" style="width:{wt}px">{vol(sum(X["q"][n]))}</div></div>')
    dcells = "".join(f'<div class="td n b" style="width:{w}px">{vol(X["D"][t])}</div>' for t in range(NT))
    rows.append(f'<div class="trw sum"><div class="td b" style="width:{w0}px">공정 소비 D[t]</div>{dcells}<div class="td n b" style="width:{wt}px">{vol(sum(X["D"]))}</div></div>')
    return f'<div class="tb">{hd}{"".join(rows)}</div>'


def board7():
    A, B = E.ARRIVALS["A"], E.ARRIVALS["B"]

    def inc(title, rows):
        rs = "".join(f'<div class="inr">{T(k, "ink")}<div class="inv{" v" if v.endswith("가상") else ""}">{esc(v)}</div></div>' for k, v in rows)
        return f'<div class="inc">{T(title, "inct")}{rs}</div>'

    def arr_rows(a):
        return [("도착 예정 ETA", hh(a["eta"]) + "h"), ("남은 물량 Q", vol(a["Q"]) + "만 배럴"), ("일 체선료 r", money(a["rate_day"])),
                ("정박개시 ℓ", hh(a["laytime_start"]) + "h"), ("허용시간 A", hh(a["laytime"]) + "h"),
                ("정박종료 ℓ + A", hh(a["laytime_start"] + a["laytime"]) + "h"), ("공제시간 e", hh(a["deduction"]) + "h")]
    b3, b2 = E.BERTHS["BUOY3"], E.BERTHS["BUOY2"]
    cards = (inc("입항 건 A", arr_rows(A)) + inc("입항 건 B", arr_rows(B))
             + inc("부두 · 소요시간", [("BUOY3 하역속도 v", f"시간당 {vol(A['v']['BUOY3'])}만 배럴"), ("BUOY2 하역속도 v", f"시간당 {vol(A['v']['BUOY2'])}만 배럴"),
                                  ("Direction", f"{hh(b3['direction'])}h · 가상"), ("Switching", f"{hh(b3['switching'])}h · 가상"),
                                  ("하역 준비 δ_setup", hh(E.D_SETUP) + "h"), ("호스분리 δ_hose", hh(E.D_HOSE) + "h"), ("이안 δ_departure", hh(E.D_DEPART) + "h")])
             + inc("원유 재고 · 계획기간", [("처음 재고 R⁰", vol(X["R0"]) + "만 배럴"), ("최소 허용 재고 R_min", vol(X["R_MIN"]) + "만 배럴"),
                                     ("저장용량 R_max", vol(X["R_MAX"]) + "만 배럴"), ("공정 소비속도", f"시간당 {vol(X['D_RATE'])}만 배럴"),
                                     ("소비속도 변경", "없음 (일정)"), ("계획기간", f"0h ~ {hh(X['T_END'])}h"), ("물량 단위", "만 배럴")]))
    assume = '<div class="panel">' + T("예제에서 이렇게 두었다", "ph") + "".join(bullet(x) for x in C.EXAMPLE_ASSUME) + "</div>"
    plans = (f'<div class="panel">{T("작업계획 6개 — Ω[A] = {A1, A2, A3}, Ω[B] = {B1, B2, B3}", "ph")}'
             f'{W("A1·A2·B1·B2는 가장 이른 접안(식 (11)을 등호로), A3는 B1 뒤, B3는 A1 뒤에 서는 계획(식 (18)을 등호로)이다. 모두 방문이 한 번인 유형 1 계획이다.", "pn")}'
             f'{gantt()}</div>')
    table = f'<div class="panel">{T("작업계획마다 계산해 둔 시각과 체선료 — 식 (11)~(15), (20)", "ph")}{plan_table()}</div>'
    pairs = (f'<div class="panel">{T("충돌 쌍 F — 식 (18)", "ph")}'
             f'{W("같은 부두를 쓰는 서로 다른 입항 건의 작업계획 쌍 다섯 개를 모두 비교했다. 두 순서가 모두 안 되는 세 쌍이 F다.", "pn")}{pair_rows()}'
             f'{W("F = {(A1, B1), (A2, B2), (A3, B3)}", "ltt k")}</div>')
    qt = (f'<div class="panel">{T(f"재고 평가 시점 τ {NT + 1}개와 구간 {NT}개 — 식 (17)", "ph")}'
          f'{W("모든 작업계획의 하역 시작·완료 시각과 계획의 처음·끝을 모아 시간순으로 놓았다. 고르지 않을 계획의 시각도 들어 있다.", "pn")}{tau_strip()}'
          f'{T("구간별 하역량 q[i,k,t]와 공정 소비량 D[t] (만 배럴)", "ph")}{q_table()}</div>')
    return (f'<section class="cap board" id="b7">{head(7, "검산 예제 ① 입력 → 작업계획", C.EXAMPLE_NOTE)}'
            f'{sec("입력", "주황색 값은 받은 자료와 다른 가상 값")}<div class="incards">{cards}</div>{assume}'
            f'{sec("작업계획 만들기", "식 (9)~(20)을 차례로 적용한 결과")}{plans}{table}{pairs}{qt}</section>')


# ─────────────────────────── 판 8 · 검산 예제 ② ───────────────────────────
def combo_rows():
    out = []
    rank_pass = 0
    for r in COMBOS:
        if r["feasible"]:
            rank_pass += 1
            v = f'<span class="vd ok">통과 · {rank_pass}안</span>'
            why = f"부두 충돌 없음 · 재고 {vol(r['min'][1])} ({hh(r['min'][0])}h) ~ {vol(r['max'][1])} ({hh(r['max'][0])}h), 범위 {vol(X['R_MIN'])}~{vol(X['R_MAX'])} 안"
        else:
            tags = []
            if r["conflict"]:
                tags.append('<span class="vd no">식 (3) 충돌</span>')
            if "over" in r["why"]:
                tags.append('<span class="vd no">식 (6) 초과</span>')
            if "under" in r["why"]:
                tags.append('<span class="vd no">식 (6) 미달</span>')
            v = "".join(tags)
            why = " · ".join(why_text(r))
        a, b = r["combo"]
        out.append(f'<div class="cb{" pass" if r["feasible"] else ""}"><div class="cbr">{r["rank"]}</div>'
                   f'<div class="cbn">{pill(a)}<span class="cbp">+</span>{pill(b)}</div><div class="cbc">{money(r["cost"])}</div>'
                   f'{W(why, "cbw")}<div class="cbv">{v}</div></div>')
    return '<div class="pairs">' + "".join(out) + "</div>"


def stock_chart():
    sx, sy, ymax = 74, 27, 24
    lm, tm = 250, 30
    cw, chh = 36 * sx, ymax * sy
    els, svg = [], []

    def X_(t):
        return lm + t * sx

    def Y_(r):
        return tm + (ymax - r) * sy
    rmin, rmax = X["R_MIN"], X["R_MAX"]
    svg.append(f'<rect x="{lm}" y="{Y_(rmax)}" width="{cw}" height="{(rmax - rmin) * sy}" fill="#ECFDF3"/>')
    for t in range(0, 37, 3):
        svg.append(f'<line x1="{X_(t)}" y1="{tm}" x2="{X_(t)}" y2="{tm + chh}" stroke="#E2E7EE" stroke-width="2"/>')
        els.append(f'<div class="abs" style="left:{X_(t) - 40}px;top:{tm + chh + 12}px;width:80px;text-align:center;font-family:Inter,sans-serif;font-weight:600;font-size:22px;line-height:32px;color:#667085">{t}h</div>')
    svg.append(f'<line x1="{lm}" y1="{tm + chh}" x2="{lm + cw}" y2="{tm + chh}" stroke="#98A2B3" stroke-width="3"/>')
    for val, name in ((rmax, "저장용량 R_max"), (rmin, "최소 허용 재고 R_min")):
        svg.append(f'<line x1="{lm}" y1="{Y_(val)}" x2="{lm + cw}" y2="{Y_(val)}" stroke="#067647" stroke-width="4" stroke-dasharray="14 10"/>')
        els.append(f'<div class="abs" style="left:0;top:{Y_(val) - 34}px;width:{lm - 20}px;text-align:right;font-size:21px;line-height:30px;font-weight:700;color:#067647">{esc(name)}</div>')
        els.append(f'<div class="abs" style="left:0;top:{Y_(val) - 4}px;width:{lm - 20}px;text-align:right;font-family:Inter,sans-serif;font-size:30px;line-height:40px;font-weight:700;color:#067647">{vol(val)}</div>')
    els.append(f'<div class="abs" style="left:0;top:{Y_(0) - 22}px;width:{lm - 20}px;text-align:right;font-family:Inter,sans-serif;font-size:24px;line-height:34px;font-weight:600;color:#667085">0</div>')
    over = next(r for r in COMBOS if r["why"] == ["over"])
    under = next(r for r in COMBOS if r["why"] == ["under"])
    rb, rs = BYCOMBO["+".join(BEST["chosen"])], BYCOMBO["+".join(SECOND["chosen"])]
    series = [(over, "#D92D20", 5, "14 10"), (under, "#DC6803", 5, "14 10"), (rs, "#6E56CF", 7, ""), (rb, "#2F6FED", 9, "")]
    for r, col, sw, dash in series:
        pts = " ".join(f"{X_(t):.1f},{Y_(v):.1f}" for t, v in zip(TAU, r["R"]))
        da = f' stroke-dasharray="{dash}"' if dash else ""
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"{da}/>')
    for t, v in zip(TAU, rb["R"]):
        svg.append(f'<circle cx="{X_(t):.1f}" cy="{Y_(v):.1f}" r="9" fill="#FFFFFF" stroke="#2F6FED" stroke-width="5"/>')
    svg.append(f'<circle cx="{X_(over["max"][0]):.1f}" cy="{Y_(over["max"][1]):.1f}" r="12" fill="#D92D20"/>')
    svg.append(f'<circle cx="{X_(under["min"][0]):.1f}" cy="{Y_(under["min"][1]):.1f}" r="12" fill="#DC6803"/>')

    def lab(x, y, text, col, size=23):
        els.append(f'<div class="abs" style="left:{x:.0f}px;top:{y:.0f}px;font-size:{size}px;line-height:34px;font-weight:700;color:{col}">{esc(text)}</div>')
    lab(X_(over["max"][0]) + 26, Y_(over["max"][1]) - 44, f"{' + '.join(over['combo'])} · {hh(over['max'][0])}h에 {vol(over['max'][1])} → 저장용량 초과", "#B42318")
    lab(X_(under["min"][0]) + 26, Y_(under["min"][1]) + 6, f"{' + '.join(under['combo'])} · {hh(under['min'][0])}h에 {vol(under['min'][1])} → 최소 허용 재고 미달", "#B54708")
    w, h = lm + cw + 40, tm + chh + 60

    def sw(col, dash, width):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<svg width="84" height="20" viewBox="0 0 84 20"><line x1="4" y1="10" x2="80" y2="10" stroke="{col}" '
                f'stroke-width="{width}" stroke-linecap="round"{da}/></svg>')
    lg = [(sw("#2F6FED", "", 9), f"1안 {BEST_NAME} · 통과"), (sw("#6E56CF", "", 7), f"2안 {SECOND_NAME} · 통과 (18h부터 1안과 같은 선)"),
          (sw("#D92D20", "14 10", 5), f"{' + '.join(over['combo'])} · 탈락"), (sw("#DC6803", "14 10", 5), f"{' + '.join(under['combo'])} · 탈락")]
    legend = '<div class="legend">' + "".join(f'<div class="lgi">{s_}<span class="lgt">{esc(t_)}</span></div>' for s_, t_ in lg) + "</div>"
    return (legend + f'<div class="fig" style="width:{w}px;height:{h}px"><svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'style="position:absolute;left:0;top:0">{"".join(svg)}</svg>{"".join(els)}</div>')


def berth_mini(sol, title):
    pxh, lw = 33, 170
    cw = 36 * pxh
    rowh, barh, top = 86, 54, 40
    els = []
    for t in range(0, 37, 6):
        x = lw + t * pxh
        els.append(f'<div class="abs" style="left:{x}px;top:{top - 6}px;width:2px;height:{2 * rowh + 6}px;background:#E2E7EE"></div>')
        els.append(f'<div class="abs" style="left:{x - 40}px;top:2px;width:80px;text-align:center;font-family:Inter,sans-serif;font-weight:600;font-size:20px;line-height:30px;color:#667085">{t}h</div>')
    for bi, berth in enumerate(E.BERTHS):
        y = top + bi * rowh + 12
        els.append(f'<div class="abs" style="left:0;top:{y}px;font-size:24px;line-height:{barh}px;font-weight:700">{berth}</div>')
        on = sorted((P[n] for n in sol["chosen"] if P[n]["berth"] == berth), key=lambda p: p["s"])
        if not on:
            els.append(f'<div class="abs" style="left:{lw + 16}px;top:{y}px;font-size:22px;line-height:{barh}px;color:#98A2B3">비어 있음</div>')
        prev = None
        for p in on:
            col = "#2F6FED" if p["arrival"] == "A" else "#0E9384"
            els.append(f'<div class="abs" style="left:{lw + p["s"] * pxh}px;top:{y}px;width:{(p["u"] - p["s"]) * pxh}px;height:{barh}px;background:{col};border-radius:10px;'
                       f'color:#FFFFFF;font-size:22px;line-height:{barh}px;font-weight:700;text-align:center">{p["name"]} · {hh(p["s"])}~{hh(p["u"])}</div>')
            if prev is not None:
                gap = p["s"] - prev["u"]
                els.append(f'<div class="abs" style="left:{lw + prev["u"] * pxh}px;top:{y + barh + 2}px;width:{gap * pxh}px;text-align:center;font-size:18px;line-height:24px;font-weight:700;color:#475467">교대 {hh(gap)}h</div>')
            prev = p
    fig = f'<div class="fig" style="width:{lw + cw + 42}px;height:{top + 2 * rowh + 10}px">{"".join(els)}</div>'
    return f'<div class="panel">{T(title, "ph")}{fig}</div>'


def z_chips(sol):
    ch = "".join(f'<div class="zc{" on" if sol["z"][n] else ""}">{esc(zn(n))} = {sol["z"][n]}</div>' for n in P)
    obj = " + ".join(f"{n} {money(P[n]['cost'])}" for n in sol["chosen"]) + f" = {money(sol['objective'])}"
    return f'<div class="zrow2">{ch}<div class="obj">목적함수 값 = {esc(obj)}</div></div>'


def r_strip(sol):
    cells = "".join(
        f'<div class="rc">{FM(f"R[{i}]", "rck")}<div class="rcv">{vol(v)}</div><div class="rct">{hh(t)}h</div></div>' for i, (t, v) in enumerate(zip(TAU, sol["R"])))
    return f'<div class="rstrip">{cells}</div>'


def sub_table(sol):
    cols = [("구간", 130), ("시간", 250), ("길이", 150), ("지금 재고 R[t]", 300), ("+ 고른 계획의 하역 ∑ q·z", 560),
            ("− 공정 소비 D[t]", 330), ("= 다음 재고 R[t+1]", 380), (f"범위 {vol(X['R_MIN'])}~{vol(X['R_MAX'])}", 300)]
    hd = '<div class="trw h">' + "".join(f'<div class="td h" style="width:{w}px">{esc(c)}</div>' for c, w in cols) + "</div>"
    rows = []
    for t in range(NT):
        ins = [(n, X["q"][n][t]) for n in sol["chosen"] if X["q"][n][t] > 1e-9]
        intxt = " + ".join(f"{n} {vol(v)}" for n, v in ins) if ins else "0"
        nxt = sol["R"][t + 1]
        ok = X["R_MIN"] - 1e-9 <= nxt <= X["R_MAX"] + 1e-9
        vals = [f"t={t}", f"{hh(TAU[t])}h → {hh(TAU[t + 1])}h", f"{hh(TAU[t + 1] - TAU[t])}h", vol(sol["R"][t]), intxt, vol(X["D"][t]),
                vol(nxt), '<span class="vd ok">통과</span>' if ok else '<span class="vd no">벗어남</span>']
        cls = ["b", "n", "n", "n", "n b" if ins else "n z", "n", "n b", ""]
        rows.append('<div class="trw">' + "".join(
            f'<div class="td {c}" style="width:{w}px">{v}</div>' for v, c, (_, w) in zip(vals, cls, cols)) + "</div>")
    return f'<div class="tb">{hd}{"".join(rows)}</div>'


def checks(sol):
    rows = []
    for arr in E.ARRIVALS:
        names = [n for n in P if P[n]["arrival"] == arr]
        rows.append(("식 (2)", f"입항 건 {arr}: " + " + ".join(str(sol["z"][n]) for n in names) + " = 1"))
    rows.append(("식 (3)", " · ".join(f"({a}, {b}): {sol['z'][a]} + {sol['z'][b]} = {sol['z'][a] + sol['z'][b]} ≤ 1" for a, b in (f["pair"] for f in X["F"]))))
    rows.append(("식 (5)", f"R[0] = {vol(sol['R'][0])} = R⁰"))
    lo, hi = min(sol["R"]), max(sol["R"])
    rows.append(("식 (6)", f"가장 낮을 때 {vol(lo)} ≥ {vol(X['R_MIN'])}, 가장 높을 때 {vol(hi)} ≤ {vol(X['R_MAX'])}"))
    return '<div class="calc">' + "".join(
        f'<div class="cl"><div class="cln" style="width:110px">{esc(k)}</div>{W(v, "clt")}</div>' for k, v in rows) + "</div>"


def board8():
    s3 = SOL[2] if len(SOL) > 2 else dict(status="infeasible")
    combos = (f'<div class="panel">{T("조합 9개 전수 조사 — 총 체선료가 낮은 순", "ph")}'
              f'{W("입항 건 A의 계획 3개 × B의 계획 3개 = 9개 조합이다. 금액이 낮은 네 조합은 부두 충돌이나 재고 초과로 탈락하고, 다섯 번째가 답이 된다.", "pn")}{combo_rows()}</div>')
    chart = (f'<div class="panel">{T("시점별 원유 재고 R[t] (만 배럴)", "ph")}'
             f'{W(f"초록 띠가 허용 범위다. 실선은 통과한 두 조합이고 둘 다 {vol(min(BEST['R']))}에서 {vol(max(BEST['R']))} 사이에 있다. 점선은 탈락한 조합 가운데 두 개다. 동그라미는 1안의 평가 시점이다.", "pn")}{stock_chart()}</div>')
    ans1 = (f'<div class="panel">{T(f"솔버가 낸 답 · 1안 {BEST_NAME}", "ph")}{z_chips(BEST)}{T("재고 변수 R[t] (만 배럴)", "defh")}{r_strip(BEST)}'
            f'{T("식 (4)에 구간마다 넣은 결과", "defh")}{sub_table(BEST)}{T("나머지 식 확인", "defh")}{checks(BEST)}</div>')
    cut = " + ".join(zn(n) for n in BEST["chosen"]) + f" ≤ {len(E.ARRIVALS) - 1}"
    ans2 = (f'<div class="panel">{T(f"다시 풀어 낸 답 · 2안 {SECOND_NAME}", "ph")}'
            f'{W(f"1안을 막는 식 {cut}을 더해 다시 풀었다.", "pn")}{z_chips(SECOND)}{T("재고 변수 R[t] (만 배럴)", "defh")}{r_strip(SECOND)}{checks(SECOND)}</div>')
    third = "가능한 조합이 더 없다. 3안은 없다." if s3["status"] != "optimal" else f"3안 {' + '.join(s3['chosen'])} {money(s3['objective'])}"
    minis = f'<div class="two">{berth_mini(BEST, "1안의 부두별 일정")}{berth_mini(SECOND, "2안의 부두별 일정")}</div>'
    okb = (f'<div class="okbar w">전수 조사와 솔버(HiGHS)의 답이 같다. 1안 {BEST_NAME} {money(BEST["objective"])}, '
           f'2안 {SECOND_NAME} {money(SECOND["objective"])}. 두 조합을 모두 막으면 {third} 모형 크기는 변수 {N_VAR}개, 제약식 {N_ROW}줄이다.</div>')
    note = f'<div class="note w">{esc(C.MONEY_NOTE)} 이전 판은 하역 완료 기준이라 1안 {money(OLD_BEST)}, 2안 {money(OLD_SECOND)}였다. 최적 조합은 같다.</div>'
    return (f'<section class="cap board" id="b8">'
            f'{head(8, "검산 예제 ② 조합 9개 → 답", "작업계획 6개로 만들 수 있는 조합을 모두 따져 보고, 같은 문제를 솔버로 풀어 답이 같은지 확인했다.")}'
            f'{combos}{chart}{sec("솔버가 정한 값과 식 대입", "변수 값 전부와 제약식에 넣은 결과")}{ans1}{ans2}{minis}{okb}{note}</section>')


# ─────────────────────────── 판 9 · 고친 것 · 정해야 하는 것 ───────────────────────────
def board9():
    fm = dict(old_best=money(OLD_BEST), best=money(BEST["objective"]), old_second=money(OLD_SECOND), second=money(SECOND["objective"]))
    hd = ('<div class="dh"><div class="dhc" style="width:470px">항목</div><div class="dhc" style="width:1140px">이전 판</div>'
          '<div class="dhc" style="width:1290px">최종</div></div>')
    fx = "".join(f'<div class="fx">{W(k, "fxk")}{W(o, "fxo")}{W(n.format(**fm), "fxn")}</div>' for k, o, n in C.FIXES)
    hd2 = ('<div class="dh"><div class="dhc" style="width:600px">무엇을</div><div class="dhc" style="width:1880px">어떻게</div>'
           '<div class="dhc" style="width:420px">근거</div></div>')
    ad = "".join(f'<div class="fx">{W(k, "adk")}{W(t, "adt")}{W(s, "ads")}</div>' for k, t, s in C.ADDED)
    oq = "".join(
        f'<div class="oq"><div class="oqn">{i}</div><div class="oqx">{T(t, "oqt")}{W(d, "oqd")}</div>'
        f'<div class="oqb">{T("지금 둔 기본", "oqbk")}{W(b, "oqbv")}</div></div>' for i, (t, d, b) in enumerate(C.OPEN, 1))
    keep = ('<div class="panel">' + T("이 페이지의 다른 자료", "ph")
            + bullet("명세 문서 「원유 수입선 하역 일정 최적화」와 프레임 '원유 하역 방식 비교', '작업계획을 선택하는 MILP'는 고치지 않았다. 식은 이 판들과 같고 말만 다르다 (판 1의 '표기').")
            + bullet("이전 보드 '최종 수식 · 식 → 제약식 ①②③ → 검산'은 지우지 않고 숨겨 두었다. 체선료를 하역 완료 기준으로 계산한 판이다.")
            + bullet("오른쪽의 입력 컬럼 표와 화물 이송율 표, 손으로 적은 표시는 그대로 두었다. 판 6이 그 표와 식을 잇는다.")
            + bullet("숫자는 docs/milp/milp_final_example.py가 계산한 값이다. 입력을 바꾸면 판 3~8의 숫자가 함께 바뀐다.") + "</div>")
    return (f'<section class="cap board" id="b9">'
            f'{head(9, "고친 것 · 정해야 하는 것", "이전 판과 달라진 곳, 정리본에 없어서 덧붙인 것, 값이나 결정이 있어야 쓸 수 있는 것을 나눠 적었다.")}'
            f'{sec("이전 판에서 고친 것", "이전 판 = 11-11 오전에 넣은 보드")}<div class="panel">{hd}{fx}</div>'
            f'{sec("정리본 식 (1)~(20)에 없어서 덧붙이거나 바꿔 적은 것", "팀이 보고 빼거나 고칠 수 있게 따로 모았다")}<div class="panel">{hd2}{ad}</div>'
            f'{sec("값이나 결정이 필요한 것", "정해지기 전에는 오른쪽 기본으로 계산한다")}<div class="pairs">{oq}</div>{keep}</section>')


# ─────────────────────────── 굽기 ───────────────────────────
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
  bake();
  var boards={}; document.querySelectorAll('.cap').forEach(function(b){var r=b.getBoundingClientRect(); boards[b.id]=[Math.round(r.width),Math.round(r.height)];});
  var over=[]; document.querySelectorAll('.cap *').forEach(function(el){ if(el.children.length===0 && el.textContent.trim()){ var p=el.parentElement; if(!p) return; var a=el.getBoundingClientRect(), b=p.getBoundingClientRect(); if(a.right > b.right + 1.5 && getComputedStyle(el).position!=='absolute'){ over.push([el.closest('.cap').id, el.className, Math.round(a.right-b.right), el.textContent.slice(0,40)]); } } });
  document.querySelectorAll('.cap .fm, .cap .gf, .cap .ss, .cap .td, .cap .fct, .cap .bt, .cap .oct, .cap .tct, .cap .dkn, .cap .sn, .cap .oqt, .cap .inv, .cap .ink').forEach(function(el){
    if(el.scrollWidth > el.clientWidth + 1){ over.push([el.closest('.cap').id, el.className, el.scrollWidth - el.clientWidth, el.textContent.slice(0,40)]); } });
  document.querySelectorAll('.cap .fbox, .cap .panel, .cap .fcard, .cap .ex, .cap .fig, .cap .five, .cap .zrow2, .cap .rstrip, .cap .tb, .cap .legend, .cap .pipe, .cap .facts').forEach(function(el){
    var p=el.parentElement.getBoundingClientRect(), a=el.getBoundingClientRect();
    var kids=el.children, mx=a.right; for(var i=0;i<kids.length;i++){ var r=kids[i].getBoundingClientRect(); if(r.right>mx) mx=r.right; }
    if(mx > a.right + 1.5 || a.right > p.right + 1.5){ over.push([el.closest('.cap').id, el.className, Math.round(Math.max(mx-a.right, a.right-p.right)), 'box']); } });
  var h=document.documentElement;
  h.setAttribute('data-font', String(document.fonts.check('500 46px "Noto Sans KR"')) + '/' + String(document.fonts.check('700 34px "JetBrains Mono"')) + '/' + document.fonts.size);
  h.setAttribute('data-boards', JSON.stringify(boards));
  h.setAttribute('data-over', JSON.stringify(over.slice(0,60)));
  h.setAttribute('data-baked','1');
  document.querySelectorAll('script').forEach(function(n){n.remove();});
}
document.fonts.ready.then(function(){ setTimeout(run, 400); });
setTimeout(run, 15000);
"""

FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700&'
             'family=JetBrains+Mono:wght@500;700&family=Noto+Sans+KR:wght@400;500;700&display=swap">')


def build_html():
    body = (f'<div class="canvas">{zone()}'
            f'<div class="row">{board1()}{board2()}{board3()}{board4()}{board5()}</div>'
            f'<div class="row">{board_data()}{board7()}{board8()}{board9()}</div></div>')
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>수리계획법 최종본 · {esc(C.TITLE)}</title>'
            f'{FONT_LINK}<style>{CSS}</style></head><body>{body}<script>{BAKE_JS}</script></body></html>')


# ─────────────────────────── 글 버전 ───────────────────────────
def build_md():
    o = []
    o.append(f"# {C.TITLE} — 수리계획법 최종본\n")
    o.append(f"- 작성: {C.DATE} · 기준: 팀 공유용 최종 정리 (본체 식 (1)~(8), 작업계획 생성 규칙 식 (9)~(20))")
    o.append("- 그림으로 된 것은 팀 피그마 파일 SKALA-P2-1의 '수리계획법' 페이지에 있다 — "
             "[수리계획법 최종본 묶음](https://www.figma.com/design/mDE8EoyYV0dS2WjtBLUoet/SKALA-P2-1?node-id=206-643) "
             "(2026-11-11에 넣음, 머리띠 1 + 판 9). 미리보기 그림은 `preview/`에 있다")
    o.append("- 이 파일과 피그마 보드는 `milp_final_content.py`(글) + `milp_final_example.py`(숫자)에서 `make_milp_board.py`로 만든다")
    o.append("- 표기: 대괄호 안이 아래첨자다. `z[i,k]`는 z에 아래첨자 ik\n")
    o.append(f"{C.ONE_LINE}\n")
    o.append("## 1. 범위\n")
    o.extend(f"- {s}" for s in C.SCOPE)
    o.append("\n## 2. 헷갈리기 쉬운 말\n")
    o.append("| 말 | 맞는 뜻 | 아닌 것 |\n|---|---|---|")
    o.extend(f"| {t} | {y} | {n} |" for t, y, n in C.TERMS)
    o.append("\n## 3. 기호\n")
    o.extend(f"- {u}" for u in C.UNITS)
    for gname, rows in C.SYMBOLS:
        o.append(f"\n**{gname}**\n")
        o.append("| 기호 | 이름 | 정의 | 단위 |\n|---|---|---|---|")
        o.extend(f"| `{s}` | {n} | {d} | {u or '—'} |" for s, n, d, u in rows)
    o.append("\n## 4. 최적화 본체 — 식 (1)~(8)\n")
    ex = body_examples()
    for no, name, lines, rg, syms, kor, read in C.BODY:
        o.append(f"### ({no}) {name}\n")
        o.append("```text\n" + "\n".join(lines) + (f"        {rg}" if rg and not has_ko(rg) else "") + "\n```\n")
        o.append(f"- 한글 식: **{kor}**")
        o.append(f"- 읽는 법: {read}")
        o.extend((f"- 예제: {v}" if k == "예제" else f"- 예제 · {k}: {v}") for k, v in ex[no])
        o.append("")
    n = C.NEXT
    o.append(f"### (+) {n['title']} — {n['tag']}\n")
    o.append("```text\n" + "\n".join(n["lines"]) + "\n```\n")
    o.append(f"- 한글 식: **{n['korean']}**\n- 읽는 법: {n['read']}\n- {n['src']}\n")
    o.extend(f"- {k}: {v}" for k, v in C.BODY_NOTES)
    o.append("\n## 5. 작업계획 생성 규칙 — 식 (9)~(20)\n")
    gex = gen_examples()
    for gname, desc, items in C.GEN:
        o.append(f"### {gname}\n\n{desc}\n")
        for no, name, lines, rg, kor in items:
            o.append(f"**({no}) {name}**\n")
            o.append("```text\n" + "\n".join(lines) + (f"        {rg}" if rg else "") + "\n```\n")
            o.append(f"- 한글 식: **{kor}**")
            o.extend((f"- 예제: {v}" if k == "예제" else f"- 예제 · {k}: {v}") for k, v in gex[no])
            o.append("")
        o.append("문장으로 정해 두는 것\n")
        o.extend(f"- {t}" + (f" **[{tag}]**" if tag else "") for t, tag in C.GEN_DEFS[gname])
        o.append("")
    o.append("### 작업계획을 만들 때 정해야 하는 설정\n")
    o.extend(f"- **{k}** — {v}" for k, v in C.GEN_SETTINGS)
    v1, v2 = T2["visits"]
    o.append(f"\n### 유형 2 계산 예 (설명용 A4, 검산 예제의 Ω에는 없음)\n")
    o.append(f"- {v1['berth']} {vol(v1['Q'])}만 배럴: 접안 {hh(v1['s'])} → 하역 {hh(v1['a'])}~{hh(v1['c'])} → 호스분리 {hh(v1['h'])} → 이안 {hh(v1['u'])}")
    o.append(f"- 이동 {hh(T2['move'])}시간(가상 값) → {v2['berth']} {vol(v2['Q'])}만 배럴: 접안 {hh(v2['s'])} → 하역 {hh(v2['a'])}~{hh(v2['c'])} → 호스분리 {hh(v2['h'])} → 이안 {hh(v2['u'])}")
    o.append(f"- 사용시간 종료 = 마지막 방문의 호스분리 {hh(T2['H'])} → 초과 {hh(T2['over'])}시간 → 체선료 {money(T2['cost'])} (허용시간은 한 번만)\n")
    o.append("## 6. 입력 데이터가 들어가는 곳\n")
    for title, rows in (("공통 입력", C.DATA_COMMON), ("분할 하역(유형 2)에 더 필요한 입력", C.DATA_SPLIT), ("계산해서 솔버에 넘기는 값", C.DATA_DERIVED)):
        o.append(f"**{title}**\n")
        o.append("| 데이터 구분 | 컬럼 | 식에서 쓰는 곳 | 페이지의 표시 |\n|---|---|---|---|")
        o.extend(f"| {k} | {c} | {u} | {t or ''} |" for k, c, u, t in rows)
        o.append("")
    o.append(f"{C.DATA_NOTE}\n")
    r = C.RATE
    o.append(f"### {r['title']}\n\n```text\n{r['formula']}\n```\n")
    o.extend(f"- {x}" for x in r["lines"])
    o.append(f"- {r['example']}\n")
    o.append("## 7. 검산 예제\n")
    o.append(f"{C.EXAMPLE_NOTE}\n")
    o.extend(f"- {x}" for x in C.EXAMPLE_ASSUME)
    o.append("\n입력\n")
    for arr, a in E.ARRIVALS.items():
        o.append(f"- 입항 건 {arr}: ETA {hh(a['eta'])}h · 남은 물량 {vol(a['Q'])}만 배럴 · 일 체선료 {money(a['rate_day'])} · 정박개시 {hh(a['laytime_start'])}h · "
                 f"허용시간 {hh(a['laytime'])}h · 공제 {hh(a['deduction'])}h")
    o.append(f"- 하역속도: BUOY3 시간당 {vol(E.ARRIVALS['A']['v']['BUOY3'])}만 배럴, BUOY2 시간당 {vol(E.ARRIVALS['A']['v']['BUOY2'])}만 배럴")
    o.append(f"- Direction {hh(E.BERTHS['BUOY3']['direction'])}h · Switching {hh(E.BERTHS['BUOY3']['switching'])}h · 준비 {hh(E.D_SETUP)}h · 호스분리 {hh(E.D_HOSE)}h · 이안 {hh(E.D_DEPART)}h")
    o.append(f"- 재고: 처음 {vol(X['R0'])} · 최소 허용 {vol(X['R_MIN'])} · 저장용량 {vol(X['R_MAX'])} (만 배럴) · 공정 소비 시간당 {vol(X['D_RATE'])} · 계획기간 0~{hh(X['T_END'])}h\n")
    o.append("작업계획\n")
    o.append("| 계획 | 부두 | 접안 s | 하역 시작 a | 하역 완료 c | 호스분리 h | 이안 u | 정박종료 | 초과 | 체선료 C | 이전 판 |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for nm, p in P.items():
        o.append(f"| {nm} | {p['berth']} | {hh(p['s'])} | {hh(p['a'])} | {hh(p['c'])} | {hh(p['h'])} | {hh(p['u'])} | {hh(p['laytime_end'])} | "
                 f"{hh(p['over'])}h | {money(p['cost'])} | {money(X['old_cost'][nm])} |")
    o.append("\n충돌 쌍 F = " + ", ".join(f"({a}, {b})" for a, b in (f["pair"] for f in X["F"])) + "\n")
    o.append("재고 평가 시점 τ = " + ", ".join(hh(t) for t in TAU) + " (h)\n")
    o.append("| 구간 | " + " | ".join(f"t={t} ({hh(TAU[t])}~{hh(TAU[t + 1])})" for t in range(NT)) + " |\n|---|" + "---|" * NT)
    for nm in P:
        o.append(f"| q[{nm}] | " + " | ".join("·" if X["q"][nm][t] < 1e-9 else vol(X["q"][nm][t]) for t in range(NT)) + " |")
    o.append("| D[t] | " + " | ".join(vol(d) for d in X["D"]) + " |\n")
    o.append("조합 9개\n")
    o.append("| 순위 | 조합 | 총 체선료 | 판정 | 이유 |\n|---|---|---|---|---|")
    k = 0
    for r in COMBOS:
        if r["feasible"]:
            k += 1
            verdict, why = f"통과 · {k}안", f"재고 {vol(r['min'][1])}~{vol(r['max'][1])}"
        else:
            verdict, why = "탈락", " · ".join(why_text(r))
        o.append(f"| {r['rank']} | {' + '.join(r['combo'])} | {money(r['cost'])} | {verdict} | {why} |")
    o.append(f"\n솔버({X['solver']})의 답\n")
    for i, s in enumerate(SOL, 1):
        if s["status"] == "optimal":
            o.append(f"- {i}안 {' + '.join(s['chosen'])} · {money(s['objective'])} · z = " + ", ".join(f"{zn(nm)}={s['z'][nm]}" for nm in P)
                     + " · R = [" + ", ".join(vol(v) for v in s["R"]) + "]")
        else:
            o.append(f"- {i}안 없음 (앞의 조합을 모두 막으면 가능한 조합이 없다)")
    o.append(f"- 전수 조사와 솔버의 답이 같다. 모형 크기: 변수 {N_VAR}개, 제약식 {N_ROW}줄")
    o.append(f"- {C.MONEY_NOTE}\n")
    o.append("## 8. 이전 판에서 고친 것\n")
    fm = dict(old_best=money(OLD_BEST), best=money(BEST["objective"]), old_second=money(OLD_SECOND), second=money(SECOND["objective"]))
    o.append("| 항목 | 이전 판 | 최종 |\n|---|---|---|")
    o.extend(f"| {k_} | {a} | {b.format(**fm)} |" for k_, a, b in C.FIXES)
    o.append("\n## 9. 정리본 식 (1)~(20)에 없어서 덧붙이거나 바꿔 적은 것\n")
    o.append("| 무엇을 | 어떻게 | 근거 |\n|---|---|---|")
    o.extend(f"| {a} | {b} | {c} |" for a, b, c in C.ADDED)
    o.append("\n## 10. 값이나 결정이 필요한 것\n")
    o.append("| # | 무엇 | 설명 | 지금 둔 기본 |\n|---|---|---|---|")
    o.extend(f"| {i} | {a} | {b} | {c} |" for i, (a, b, c) in enumerate(C.OPEN, 1))
    o.append("\n## 다시 만들기\n")
    o.append("```bash\npython3 docs/milp/milp_final_example.py     # 예제 계산과 검산 (전수 조사 = 솔버)\npython3 docs/milp/make_milp_board.py       # milp-board.html + milp-final.md\n```\n")
    return "\n".join(o)


def main():
    with open(os.path.join(HERE, "milp-board.html"), "w", encoding="utf-8") as f:
        f.write(build_html())
    with open(os.path.join(HERE, "milp-final.md"), "w", encoding="utf-8") as f:
        f.write(build_md())
    print("milp-board.html, milp-final.md 만들었다")
    print(f"1안 {BEST_NAME} {money(BEST['objective'])} · 2안 {SECOND_NAME} {money(SECOND['objective'])} · 변수 {N_VAR} · 제약식 {N_ROW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
