"""Occupancy heatmaps (port of the original hexbin heatmap)."""
from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from scipy.ndimage import gaussian_filter

from .models import Experiment


def trial_numbers(exp: Experiment) -> list[int]:
    """n-th trial of each animal, in experiment order."""
    seen: dict = {}
    out = []
    for t in exp.trials:
        seen[t.animal] = seen.get(t.animal, 0) + 1
        out.append(seen[t.animal])
    return out


def day_numbers(exp: Experiment) -> list[int]:
    days: dict = {}
    out = []
    for t in exp.trials:
        if exp.has_date_info and t.date is not None:
            out.append(days.setdefault(t.date.date(), len(days) + 1))
        else:
            out.append(0)
    return out


def collect_points(exp: Experiment, trials: Optional[tuple[int, int]] = None,
                   days: Optional[tuple[int, int]] = None, animals: Optional[set] = None):
    xs, ys = [], []
    for t, n, d in zip(exp.trials, trial_numbers(exp), day_numbers(exp)):
        if trials and not (trials[0] <= n <= trials[1]):
            continue
        if days and d and not (days[0] <= d <= days[1]):
            continue
        if animals is not None and t.animal not in animals:
            continue
        for p in t:
            xs.append(float(p.x))
            ys.append(float(p.y))
    return xs, ys


def heatmap_figure(xs, ys, grid_size=70, max_value=None, title="", centre=None, diameter=None,
                   cmap="turbo", dark=False) -> Figure:
    fg = "#E8EDF2" if dark else "#16202A"
    bg = "#1C2228" if dark else "#FFFFFF"
    fig = Figure(figsize=(5, 5), facecolor=bg, layout="constrained")
    ax = fig.add_subplot(111)
    ax.set_facecolor(bg)
    if xs:
        X = gaussian_filter(np.asarray(xs, float), sigma=2, order=0)
        Y = gaussian_filter(np.asarray(ys, float), sigma=2, order=0)
        kw = dict(gridsize=int(grid_size), cmap=cmap, vmin=0, linewidths=0.25, mincnt=1)
        if max_value:
            kw["vmax"] = max_value
        hb = ax.hexbin(X, Y, **kw)
        cb = fig.colorbar(hb, ax=ax, shrink=0.8)
        cb.set_label("samples", color=fg)
        cb.ax.yaxis.set_tick_params(color=fg, labelcolor=fg)
        cb.outline.set_edgecolor(fg)
    if centre is not None and diameter:
        ax.add_patch(Circle(centre, diameter / 2, fill=False, lw=1.5, ec=fg))
        r = diameter / 2 * 1.04
        ax.set_xlim(centre[0] - r, centre[0] + r)
        ax.set_ylim(centre[1] - r, centre[1] + r)
    ax.set_aspect("equal")
    ax.set_title(title, color=fg)
    ax.tick_params(colors=fg)
    for s in ax.spines.values():
        s.set_visible(False)
    return fig
