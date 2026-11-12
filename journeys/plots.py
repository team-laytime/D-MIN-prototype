"""그림 두 장: 항차별 레이타임 소진·체선 타임라인, 접안 순서 Gantt(SC-01 · 압축 시나리오).

실행:  python3 -I journeys/plots.py journeys/data/vessel_journeys.csv journeys/out
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

import berth_milp as bm  # noqa: E402
import laytime_csv as lc  # noqa: E402
import run_milp as rm  # noqa: E402

plt.rcParams["font.family"] = ["AppleGothic", "NanumGothic", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

GRAY, BLUE, RED, NAVY, GREEN = "#d0d0d0", "#6b9bd1", "#d9534f", "#1f2d4a", "#7fb685"


def timeline(results: list[lc.Result], calls: list[lc.Call], terms: lc.Terms, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 9.2))
    n = len(results)
    xmax = 0.0
    for i, (r, c) in enumerate(zip(results, calls)):
        y = n - 1 - i
        h = lambda t: (t - r.nor_t).total_seconds() / 3600  # noqa: E731
        s, e = h(r.laytime_start), h(r.hose_off)
        ex = h(r.laytime_expiry) if r.laytime_expiry else e
        ax.barh(y, s, height=0.56, color=GRAY, zorder=1)
        ax.barh(y, ex - s, left=s, height=0.56, color=BLUE, zorder=2)
        if e > ex:
            ax.barh(y, e - ex, left=ex, height=0.56, color=RED, zorder=2)
        edges = [r.ops_start] + [t for g in c.gaps for t in g] + [r.ops_end]
        for a, b in zip(edges[::2], edges[1::2]):       # 하역 도중 이안한 구간은 비워 둔다
            ax.barh(y, h(b) - h(a), left=h(a), height=0.2, color=NAVY, zorder=3)
        ax.plot(h(r.allfast), y + 0.42, marker="v", color="black", ms=4.5, zorder=4)
        label = f"{r.amount_usd / 1000:,.0f}k$  ({r.demurrage_h:.0f}h)" if r.demurrage_h else "체선 없음"
        ax.text(e + 3, y, label, va="center", fontsize=8.5, color=RED if r.demurrage_h else "#555555")
        flag = " ⚑" if "NOR-EARLY" in r.flags else ""
        ax.text(-3, y, f"{r.jid}  {r.vessel}  {r.berth}{flag}", va="center", ha="right", fontsize=9)
        xmax = max(xmax, e)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlim(0, xmax + 60)
    ax.set_ylim(-0.7, n - 0.2)
    ax.set_yticks([])
    ax.set_xlabel("NOR 제출 후 경과 시간 (h)")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.grid(axis="x", color="#eeeeee", zorder=0)
    total = sum(r.amount_usd for r in results)
    ax.set_title(f"항차별 레이타임 소진과 체선 — 합계 {total:,.0f} USD ({sum(1 for r in results if r.demurrage_h)}/{n}항차)\n"
                 f"허용 {terms.laytime_hours:g}h · 통지 {terms.notice_hours:g}h · {terms.rate_usd_day:,.0f} USD/일 [가정], "
                 "체선 대부분은 NOR 이후 접안까지의 대기에서 생긴다", fontsize=11.5, loc="left")
    ax.legend(handles=[Patch(color=GRAY, label="NOR → 레이타임 개시 (통지시간)"), Patch(color=BLUE, label="레이타임 소진"),
                       Patch(color=RED, label="체선"), Patch(color=NAVY, label="선적·양하 작업"),
                       Line2D([], [], marker="v", color="black", ls="", ms=5, label="접안 완료(all fast)"),
                       Line2D([], [], marker="$⚑$", color="#444", ls="", ms=8, label="NOR이 투묘보다 빠름(해석 쟁점)")],
              loc="lower right", fontsize=8.5, frameon=False)
    fig.subplots_adjust(left=0.27, right=0.985, top=0.9, bottom=0.07)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def gantt_panel(ax, rows: list[dict], berths: list[str], title: str, free: dict | None = None, xmax=None,
                top: float | None = None) -> None:
    top = top or max((r["cost"] for r in rows), default=0) or 1      # 색 기준은 비교할 패널끼리 같게
    cmap = plt.cm.Reds
    seen: dict[str, int] = {}
    for r in sorted(rows, key=lambda r: r["s"]):
        y = berths.index(r["berth"])
        j = seen[r["berth"]] = seen.get(r["berth"], -1) + 1
        if r["s"] > r["nor"]:
            yy = y - 0.36 - 0.06 * j                                   # 같은 선석 선박의 대기선이 겹치지 않게 쌓는다
            ax.plot([r["nor"], r["s"]], [yy, yy], color="#8a8a8a", lw=2.0, solid_capstyle="butt", zorder=1)
            ax.plot(r["nor"], yy, marker="|", color="#444444", ms=6, zorder=1)
        color = GREEN if r["cost"] <= 0 else cmap(0.35 + 0.55 * r["cost"] / top)
        ax.barh(y, r["e"] - r["s"], left=r["s"], height=0.52, color=color, edgecolor="white", zorder=2)
        txt = f"{r['name']}" + (f"\n{r['cost'] / 1000:,.1f}k$" if r["cost"] > 0 else "")
        ax.text((r["s"] + r["e"]) / 2, y, txt, ha="center", va="center", fontsize=7.5, zorder=3,
                color="white" if r["cost"] / top > 0.55 else "black")
    for k, f in (free or {}).items():
        if k in berths:
            ax.plot([f, f], [berths.index(k) - 0.55, berths.index(k) + 0.42], color="#444444", ls="--", lw=1)
    ax.set_yticks(range(len(berths)), berths)
    ax.set_ylim(len(berths) - 0.3, -0.75)                              # 첫 선석이 맨 위
    ax.set_xlim(0, xmax)
    ax.set_title(title, fontsize=10.5, loc="left")
    ax.grid(axis="x", color="#eeeeee", zorder=0)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def gantt(calls: list[lc.Call], terms: lc.Terms, path: Path) -> None:
    s1 = rm.sc01()
    st = rm.stress(calls, terms, 1.0, False)
    fig, axes = plt.subplots(2, 2, figsize=(14, 7.6))
    free1 = {"SK7": SC01_FREE}
    gantt_panel(axes[0, 0], s1["A"]["rows"], ["SK7"], f"SC-01 순서 A (X 먼저) — {s1['A']['cost']:,.0f} USD  (손계산 52,000)",
                free1, 40, top=52000)
    gantt_panel(axes[0, 1], s1["B"]["rows"], ["SK7"], f"SC-01 순서 B (Y 먼저) — {s1['B']['cost']:,.0f} USD  (손계산 6,000) ← MILP 최적",
                free1, 40, top=52000)
    berths = ["SK #3", "SK #5-4", "SK #5-5"]
    xmax = max(r["e"] for k in ("fcfs", "milp") for r in st[k]["rows"]) + 4
    free = {k: 6.0 for k in berths}
    top2 = max(r["cost"] for k in ("fcfs", "milp") for r in st[k]["rows"])
    gantt_panel(axes[1, 0], st["fcfs"]["rows"], berths, f"압축 시나리오 · 현업 Rule(도착순) — {st['fcfs']['cost']:,.0f} USD", free, xmax, top2)
    gantt_panel(axes[1, 1], st["milp"]["rows"], berths,
                f"압축 시나리오 · MILP 최적 — {st['milp']['cost']:,.0f} USD (완전 탐색과 같음, −{st['fcfs']['cost'] - st['milp']['cost']:,.0f})",
                free, xmax, top2)
    for ax in axes[:, 0]:
        ax.set_xlabel("시각 (h) — 점선: 선석이 비는 시각, 회색 선: NOR 후 대기")
    for ax in axes[:, 1]:
        ax.set_xlabel("시각 (h)")
    fig.suptitle("접안 순서·선석 배정 — 수리계획법(MILP)  |  위: 손계산 정답 SC-01   아래: 실제 서비스 시간 8척 압축 시나리오 [가정]",
                 fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=150)
    plt.close(fig)


SC01_FREE = 6.0


def main(argv=None) -> int:
    csv_path, out = Path(sys.argv[1]), Path(sys.argv[2])
    terms = lc.Terms()
    results, calls = lc.analyze(csv_path, terms)
    out.mkdir(parents=True, exist_ok=True)
    timeline(results, calls, terms, out / "voyage_timeline.png")
    gantt(calls, terms, out / "milp_gantt.png")
    print("saved:", out / "voyage_timeline.png", out / "milp_gantt.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
