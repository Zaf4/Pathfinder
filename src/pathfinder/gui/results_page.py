"""Step 3: results, swim paths and heatmaps."""
from __future__ import annotations

import sys

from collections import Counter, defaultdict
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QSortFilterProxyModel, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
                               QHeaderView, QPushButton, QSpinBox, QTableView, QTabWidget, QVBoxLayout, QWidget)

from ..core.analysis import write_csv
from ..core.heatmap import collect_points, day_numbers, heatmap_figure, trial_numbers
from ..core.params import STRATEGIES, STRATEGY_COLOURS
from . import theme
from .dialogs import ReviewDialog
from .maze_view import MazeView
from .state import AppState
from .widgets import BarChart, Card, hbox, label


def reveal(path: Path):
    """Show a file/folder in Finder / Explorer."""
    import subprocess
    import sys
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    elif sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


class ResultsPage(QWidget):
    new_analysis = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.sets = []  # [(name, geometry, results, csv_path)]
        self.current = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 24)
        outer.setSpacing(14)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = label("Results", "PageTitle")
        self.where = label("", "PageSubtitle", wrap=True)
        titles.addWidget(self.title)
        titles.addWidget(self.where)
        head.addLayout(titles, 1)
        self.goal_pick = QComboBox()
        self.goal_pick.currentIndexChanged.connect(self._pick_set)
        head.addWidget(self.goal_pick, 0, Qt.AlignTop)
        self.open_btn = QPushButton("Open Spreadsheet")
        self.open_btn.setObjectName("Primary")
        self.open_btn.clicked.connect(self.open_csv)
        self.finder_btn = QPushButton({"darwin": "Show in Finder", "win32": "Show in Explorer"}.get(sys.platform, "Show Folder"))
        self.finder_btn.clicked.connect(lambda: reveal(self.sets[self.current][3]))
        head.addWidget(self.finder_btn, 0, Qt.AlignTop)
        head.addWidget(self.open_btn, 0, Qt.AlignTop)
        outer.addLayout(head)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self.tabs.addTab(self._summary_tab(), "Summary")
        self.tabs.addTab(self._trials_tab(), "Trials")
        self.tabs.addTab(self._heatmap_tab(), "Heatmap")

        again = QPushButton("Start a New Analysis")
        again.clicked.connect(self.new_analysis.emit)
        self.review_btn = QPushButton("Review && Edit Strategies…")
        self.review_btn.clicked.connect(self.review_all)
        outer.addWidget(hbox(again, None, self.review_btn))

    # ---------------------------------------------------------- tabs
    def _summary_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(16)
        left = Card()
        left.lay.addWidget(label("Strategies", "SectionTitle"))
        self.bars = BarChart()
        left.lay.addWidget(self.bars)
        self.summary_note = label("", "Hint", wrap=True)
        left.lay.addWidget(self.summary_note)
        left.lay.addStretch(1)
        lay.addWidget(left, 2)
        right = Card()
        right.lay.addWidget(label("Strategies across trials", "SectionTitle"))
        self.trend_fig = Figure(figsize=(5, 3.5), layout="constrained")
        self.trend = FigureCanvasQTAgg(self.trend_fig)
        right.lay.addWidget(self.trend, 1)
        lay.addWidget(right, 3)
        return w

    def _trials_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(16)
        self.model = QStandardItemModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.UserRole + 1)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().currentRowChanged.connect(self._row_selected)
        self.table.doubleClicked.connect(self._review_one)
        lay.addWidget(self.table, 3)
        side = Card(padding=12)
        self.path_title = label("Select a trial to see its swim path", "SectionTitle", wrap=True)
        side.lay.addWidget(self.path_title)
        self.path_view = MazeView(interactive=False, compact=True)
        side.lay.addWidget(self.path_view, 1)
        side.lay.addWidget(label("Double-click a trial to change its strategy.", "Hint", wrap=True))
        side.setMinimumWidth(300)
        lay.addWidget(side, 2)
        return w

    def _heatmap_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(16)
        ctl = Card(padding=16)
        ctl.setFixedWidth(300)
        ctl.lay.addWidget(label("Which swims", "SectionTitle"))
        g = QGridLayout()
        self.h_tfrom, self.h_tto = QSpinBox(), QSpinBox()
        self.h_dfrom, self.h_dto = QSpinBox(), QSpinBox()
        for s in (self.h_tfrom, self.h_tto, self.h_dfrom, self.h_dto):
            s.setRange(1, 9999)
            s.valueChanged.connect(self.draw_heatmap)
        g.addWidget(label("Trials"), 0, 0)
        g.addWidget(self.h_tfrom, 0, 1)
        g.addWidget(label("to"), 0, 2)
        g.addWidget(self.h_tto, 0, 3)
        self.day_label = label("Days")
        g.addWidget(self.day_label, 1, 0)
        g.addWidget(self.h_dfrom, 1, 1)
        self.day_to_label = label("to")
        g.addWidget(self.day_to_label, 1, 2)
        g.addWidget(self.h_dto, 1, 3)
        ctl.lay.addLayout(g)
        self.h_animal = QComboBox()
        self.h_animal.currentIndexChanged.connect(self.draw_heatmap)
        self.animal_label = label("Animal")
        ctl.lay.addWidget(self.animal_label)
        ctl.lay.addWidget(self.h_animal)
        ctl.lay.addSpacing(8)
        ctl.lay.addWidget(label("Look", "SectionTitle"))
        g2 = QGridLayout()
        self.h_grid = QSpinBox()
        self.h_grid.setRange(5, 300)
        self.h_grid.setValue(70)
        self.h_grid.valueChanged.connect(self.draw_heatmap)
        g2.addWidget(label("Detail (grid size)"), 0, 0)
        g2.addWidget(self.h_grid, 0, 1)
        self.h_auto = QCheckBox("Automatic colour range")
        self.h_auto.setChecked(True)
        self.h_max = QSpinBox()
        self.h_max.setRange(1, 1_000_000)
        self.h_max.setValue(50)
        self.h_max.setEnabled(False)
        self.h_auto.toggled.connect(lambda on: (self.h_max.setEnabled(not on), self.draw_heatmap()))
        self.h_max.valueChanged.connect(self.draw_heatmap)
        g2.addWidget(self.h_auto, 1, 0, 1, 2)
        g2.addWidget(label("Maximum"), 2, 0)
        g2.addWidget(self.h_max, 2, 1)
        ctl.lay.addLayout(g2)
        ctl.lay.addStretch(1)
        save = QPushButton("Save Image…")
        save.clicked.connect(self.save_heatmap)
        ctl.lay.addWidget(save)
        lay.addWidget(ctl)
        self.h_holder = Card(padding=8)
        lay.addWidget(self.h_holder, 1)
        self.h_canvas = None
        return w

    # ---------------------------------------------------------- populate
    def show_results(self, sets):
        self.sets = sets
        self.goal_pick.blockSignals(True)
        self.goal_pick.clear()
        for name, *_ in sets:
            self.goal_pick.addItem(name)
        self.goal_pick.setVisible(len(sets) > 1)
        self.goal_pick.blockSignals(False)
        out = self.state.output_dir
        self.where.setText(f"Saved in your home folder › {out.parent.name} › {out.name}" if out else "")
        self._setup_heatmap_controls()
        self._pick_set(0)

    def _pick_set(self, i):
        if i < 0 or i >= len(self.sets):
            return
        self.current = i
        name, geom, results, _path = self.sets[i]
        n = len(results)
        self.title.setText(f"{n} trial{'s' if n != 1 else ''} analyzed")
        counts = Counter(r.final_strategy for r in results)
        self.bars.set_items([(s[1], counts.get(s[1], 0), s[3]) for s in STRATEGIES
                             if counts.get(s[1], 0) or s[0] != "semifocal"])
        manual = sum(1 for r in results if r.manual_strategy)
        self.summary_note.setText(
            f"Goal at ({geom.goal_x:.1f}, {geom.goal_y:.1f}), pool Ø {geom.maze_diameter:.1f}. "
            + (f"{manual} trial(s) set by hand." if manual else ""))
        self._draw_trend(results)
        self._fill_table(results)
        self.path_view.set_geometry((geom.centre_x, geom.centre_y), geom.maze_diameter, (geom.goal_x, geom.goal_y),
                                    geom.goal_diameter, self.state.setup.corridor_width,
                                    self.state.setup.chaining_width, self.state.setup.thigmotaxis_zone)
        self.path_view.set_path([], [])
        self.path_title.setText("Select a trial to see its swim path")
        self.draw_heatmap()

    def _draw_trend(self, results):
        t = theme.current()
        fig = self.trend_fig
        fig.clear()
        fig.set_facecolor(t.surface)
        ax = fig.add_subplot(111)
        ax.set_facecolor(t.surface)
        by_trial = defaultdict(Counter)
        for r in results:
            by_trial[r.trial_number][r.final_strategy] += 1
        xs = sorted(by_trial)
        bottom = [0.0] * len(xs)
        for _k, name, _s, colour in STRATEGIES:
            vals = [by_trial[x][name] / max(1, sum(by_trial[x].values())) * 100 for x in xs]
            if any(vals):
                ax.bar(xs, vals, bottom=bottom, color=colour, label=name, width=0.8, edgecolor=t.surface,
                       linewidth=0.8)
                bottom = [b + v for b, v in zip(bottom, vals)]
        ax.set_xlabel("Trial number (per animal)", color=t.muted)
        ax.set_ylabel("% of swims", color=t.muted)
        ax.set_ylim(0, 100)
        step = 1 if len(xs) <= 12 else (2 if len(xs) <= 24 else 5)  # keep labels readable
        ax.set_xticks([x for x in xs if (x - xs[0]) % step == 0])
        ax.tick_params(colors=t.muted)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(t.border)
        leg = ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=8)
        for txt in leg.get_texts():
            txt.set_color(t.text)
        self.trend.draw_idle()

    def _fill_table(self, results):
        heads = ["Trial", "Animal / file", "Strategy", "Score", "Latency (s)", "Distance", "Velocity", "IPE",
                 "Heading error (°)"]
        self.model.clear()
        self.model.setHorizontalHeaderLabels(heads)
        for idx, r in enumerate(results):
            m = r.metrics
            name = r.trial.label if r.trial.animal is not None else (r.trial.name or "")
            strat = r.final_strategy + ("  ✎" if r.manual_strategy and r.manual_strategy != r.strategy else "")
            vals = [(r.trial_number, r.trial_number), (name, name), (strat, r.final_strategy),
                    (r.score, r.score if r.score != "" else -1), (f"{m['latency']:.1f}", m["latency"]),
                    (f"{m['total_distance']:.0f}", m["total_distance"]), (f"{m['velocity']:.1f}", m["velocity"]),
                    (f"{m['ipe']:.0f}", m["ipe"]), (f"{m['heading_avg']:.1f}", m["heading_avg"])]
            row = []
            for c, (text, key) in enumerate(vals):
                it = QStandardItem(str(text))
                it.setData(key, Qt.UserRole + 1)
                it.setData(idx, Qt.UserRole + 2)
                if c == 2:
                    col = QColor(STRATEGY_COLOURS.get(r.final_strategy, "#999"))
                    it.setForeground(col)
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                if c not in (1, 2):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                row.append(it)
            self.model.appendRow(row)
        self.table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self.proxy.sort(-1)

    def _result_at(self, proxy_index):
        if not proxy_index.isValid():
            return None
        idx = self.proxy.index(proxy_index.row(), 0).data(Qt.UserRole + 2)
        return self.sets[self.current][2][idx]

    def _row_selected(self, cur, _prev):
        r = self._result_at(cur)
        if not r:
            return
        self.path_title.setText(f"{r.trial.label} · trial {r.trial_number}: {r.final_strategy}")
        self.path_view.set_path(r.xs, r.ys, STRATEGY_COLOURS.get(r.final_strategy))

    # ---------------------------------------------------------- review
    def _review_one(self, index):
        r = self._result_at(index)
        if r:
            self._review([r])

    def review_all(self):
        self._review(self.sets[self.current][2])

    def _review(self, results):
        _name, geom, all_results, path = self.sets[self.current]
        dlg = ReviewDialog(results, geom, self.state.setup, self)
        dlg.exec()
        write_csv(path, self.state.experiment, all_results)
        self._pick_set(self.current)

    # ---------------------------------------------------------- heatmap
    def _setup_heatmap_controls(self):
        exp = self.state.experiment
        nums = trial_numbers(exp) or [1]
        days = [d for d in day_numbers(exp) if d]
        for w in (self.h_tfrom, self.h_tto, self.h_dfrom, self.h_dto, self.h_animal):
            w.blockSignals(True)
        self.h_tfrom.setRange(1, max(nums))
        self.h_tto.setRange(1, max(nums))
        self.h_tfrom.setValue(1)
        self.h_tto.setValue(max(nums))
        has_days = bool(days)
        for w in (self.day_label, self.day_to_label, self.h_dfrom, self.h_dto):
            w.setVisible(has_days)
        if has_days:
            self.h_dfrom.setRange(1, max(days))
            self.h_dto.setRange(1, max(days))
            self.h_dfrom.setValue(1)
            self.h_dto.setValue(max(days))
        self.h_animal.clear()
        self.h_animal.addItem("All animals", None)
        for a in exp.animals:
            self.h_animal.addItem(str(a), a)
        self.h_animal.setVisible(bool(exp.animals))
        self.animal_label.setVisible(bool(exp.animals))
        for w in (self.h_tfrom, self.h_tto, self.h_dfrom, self.h_dto, self.h_animal):
            w.blockSignals(False)

    def _heatmap_title(self):
        parts = [f"Trials {self.h_tfrom.value()}–{self.h_tto.value()}"]
        if self.h_dfrom.isVisible():
            parts.insert(0, f"Days {self.h_dfrom.value()}–{self.h_dto.value()}")
        a = self.h_animal.currentData()
        if a is not None:
            parts.append(str(a))
        return " · ".join(parts)

    def _make_figure(self, dark):
        exp = self.state.experiment
        if not exp or not self.sets:
            return None
        geom = self.sets[self.current][1]
        a = self.h_animal.currentData()
        xs, ys = collect_points(exp, trials=(self.h_tfrom.value(), self.h_tto.value()),
                                days=(self.h_dfrom.value(), self.h_dto.value()) if self.h_dfrom.isVisible() else None,
                                animals={a} if a is not None else None)
        return heatmap_figure(xs, ys, grid_size=self.h_grid.value(),
                              max_value=None if self.h_auto.isChecked() else self.h_max.value(),
                              title=self._heatmap_title(), centre=(geom.centre_x, geom.centre_y),
                              diameter=geom.maze_diameter, dark=dark)

    def draw_heatmap(self, *_):
        fig = self._make_figure(theme.current().dark)
        if fig is None:
            return
        if self.h_canvas:
            self.h_canvas.setParent(None)
            self.h_canvas.deleteLater()
        self.h_canvas = FigureCanvasQTAgg(fig)
        self.h_holder.lay.addWidget(self.h_canvas)

    def save_heatmap(self):
        out = self.state.output_dir or Path.home()
        name = "heatmap " + self._heatmap_title().replace("·", "-").replace("–", "-") + ".png"
        path, _ = QFileDialog.getSaveFileName(self, "Save heatmap", str(out / name), "PNG image (*.png)")
        if path:
            self._make_figure(False).savefig(path, dpi=300)

    def open_csv(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.sets[self.current][3])))
