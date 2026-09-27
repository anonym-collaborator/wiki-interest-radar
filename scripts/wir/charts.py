"""Charts (matplotlib, headless). One y-axis, thin marks, fixed colours per row."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .i18n import t  # noqa: E402

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, MUTED, GRID = "#0b0b0b", "#6f6d68", "#e1e0d9"


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _smooth(y: np.ndarray, k: int = 3) -> np.ndarray:
    out = np.full(len(y), np.nan)
    for i in range(len(y)):
        seg = y[max(0, i - k // 2): i + k // 2 + 1]
        seg = seg[np.isfinite(seg)]
        if seg.size:
            out[i] = seg.mean()
    return out


def draw_trend(ax, rows, ui: str = "en", max_rows: int = 8, legend: str = "below") -> None:
    rows = [r for r in rows if r.result.get("status") == "ok"][:max_rows]
    if not rows:
        ax.text(0.5, 0.5, t(ui, "no_data_chart"), ha="center", va="center", color=MUTED)
        ax.set_axis_off()
        return
    _style(ax)
    medians = []
    for i, r in enumerate(rows):
        color = PALETTE[i % len(PALETTE)]
        x = np.array(r.months, dtype="datetime64[D]")
        pm = r.raw / np.where(r.proj > 0, r.proj, np.nan) * 1e6
        sm = _smooth(pm)
        medians.append(np.nanmedian(pm))
        one_topic = len({row.topic.name for row in rows}) == 1
        n_art = len(r.result["articles"])
        if not one_topic:
            label = f"{r.lang} · {r.topic.name}"
        elif n_art == 1:
            label = f"{r.lang} · {r.result['articles'][0]['title']}"
        else:
            label = f"{r.lang} ({n_art})"
        ax.plot(x, pm, color=color, linewidth=0.8, alpha=0.35)
        ax.plot(x, sm, color=color, linewidth=2.0, label=label, solid_capstyle="round")
        spikes = [m for m in r.spike_months]
        if spikes:
            idx = [r.months.index(m) for m in spikes if m in r.months]
            ax.scatter(x[idx], pm[idx], s=22, color=color, edgecolor="white", linewidth=1.2,
                       zorder=5, marker="^")
    med = [m for m in medians if np.isfinite(m) and m > 0]
    if med and max(med) / min(med) > 20:
        ax.set_yscale("log")
        ax.set_ylabel(t(ui, "axis_pm_log"), color=MUTED, fontsize=8)
    else:
        ax.set_ylim(bottom=0)
        ax.set_ylabel(t(ui, "axis_pm"), color=MUTED, fontsize=8)
    r0 = rows[0]
    split = np.datetime64(r0.months[-12], "D")
    ax.axvline(split, color="#c3c2b7", linewidth=1, linestyle=(0, (3, 3)))
    ymax = ax.get_ylim()[1]
    ax.text(split, ymax * (0.97 if ax.get_yscale() == "linear" else 0.9), " " + t(ui, "last12"),
            color=MUTED, fontsize=7, va="top")
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    if legend == "top":
        leg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=3, frameon=False, fontsize=7.5,
                        handlelength=1.6, borderaxespad=0)
        note_xy, note_va = (1.0, 1.02), "bottom"
    else:
        leg = ax.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2, frameon=False, fontsize=7.5,
                        handlelength=1.6)
        note_xy, note_va = (1.0, -0.12), "top"
    for txt in leg.get_texts():
        txt.set_color(INK)
    if any(r.spike_months for r in rows):
        ax.text(*note_xy, "▲ " + t(ui, "spike_marker"), transform=ax.transAxes, ha="right",
                va=note_va, fontsize=7, color=MUTED)


def save_chart(rows, path: Path, title: str, ui: str = "en") -> Path:
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=130)
    draw_trend(ax, rows, ui)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
