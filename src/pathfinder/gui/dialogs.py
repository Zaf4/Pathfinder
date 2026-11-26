"""Dialog windows: column picker, settings, manual review, messages."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QDialog, QDoubleSpinBox, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QMessageBox, QPushButton, QScrollArea,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.params import PARAM_GROUPS, STRATEGIES, StrategyParams
from ..core.readers import CustomColumns, read_table
from . import theme
from .maze_view import MazeView
from .widgets import Card, hbox, label


def dot_icon(colour: str, size: int = 12) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(colour))
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return QIcon(pm)


def show_error(parent, title, text, details=None):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(text)
    if details:
        box.setDetailedText(details)
    box.exec()


# ---------------------------------------------------------------- column picker
class ColumnPickerDialog(QDialog):
    """Click a cell in the X column, then Y, then time. Replaces the old 'Define' window."""
    ROLES = ["X position", "Y position", "Time"]

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Columns")
        self.resize(900, 600)
        self.columns: CustomColumns | None = None
        self.picks: list[tuple[int, int]] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(label("Show Pathfinder where your data is", "PageTitle"))
        self.instruction = label("", "PageSubtitle", wrap=True)
        lay.addWidget(self.instruction)
        lay.addWidget(label(f"Sample file: {Path(filename).name}", "Hint"))

        try:
            table = read_table(filename)
        except Exception as e:  # noqa: BLE001
            table = None
            lay.addWidget(label(f"Could not open this file: {e}", "Error", wrap=True))
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        if table is not None:
            nr, nc = min(len(table), 60), min(table.shape[1], 30)
            self.table.setRowCount(nr)
            self.table.setColumnCount(nc)
            self.table.setHorizontalHeaderLabels([f"Column {i + 1}" for i in range(nc)])
            self.table.setVerticalHeaderLabels([str(i + 1) for i in range(nr)])
            for r in range(nr):
                for c in range(nc):
                    v = table.iat[r, c]
                    self.table.setItem(r, c, QTableWidgetItem("" if str(v) == "nan" else str(v)))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.cellClicked.connect(self._picked)
        lay.addWidget(self.table, 1)

        self.summary = label("", "Muted")
        reset = QPushButton("Start Over")
        reset.clicked.connect(self._reset)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Use These Columns")
        self.ok.setObjectName("Primary")
        self.ok.clicked.connect(self._accept)
        lay.addWidget(hbox(self.summary, None, reset, cancel, self.ok))
        self._refresh()

    def _refresh(self):
        t = theme.current()
        n = len(self.picks)
        if n < 3:
            self.instruction.setText(f"Click the <b>first {self.ROLES[n]} value</b> in the table "
                                     f"(step {n + 1} of 3). Pick a number in the first row of real data, "
                                     "not a header.")
        else:
            self.instruction.setText("All set. Check the highlighted columns, then click “Use These Columns”.")
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                if it:
                    it.setBackground(QColor(0, 0, 0, 0))
        colours = ["#E3F2FD", "#E8F5E9", "#FFF3E0"] if not t.dark else ["#1E3A5F", "#1E4620", "#4A3416"]
        for (r, c), col in zip(self.picks, colours):
            for rr in range(r, self.table.rowCount()):
                it = self.table.item(rr, c)
                if it:
                    it.setBackground(QColor(col))
        self.summary.setText("   ".join(f"{self.ROLES[i]}: column {c + 1}" for i, (_, c) in enumerate(self.picks)))
        self.ok.setEnabled(n == 3)

    def _picked(self, r, c):
        if len(self.picks) >= 3:
            return
        if any(pc == c for _, pc in self.picks):
            return
        self.picks.append((r, c))
        self._refresh()

    def _reset(self):
        self.picks = []
        self._refresh()

    def _accept(self):
        (rx, cx), (_, cy), (_, ct) = self.picks
        self.columns = CustomColumns(x_col=cx, y_col=cy, t_col=ct, start_row=rx)
        self.accept()


# ---------------------------------------------------------------- settings
class SettingsDialog(QDialog):
    def __init__(self, params: StrategyParams, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Strategy Thresholds")
        self.resize(720, 680)
        self.params = params
        self.inputs: dict[str, QWidget] = {}
        self.toggles: dict[str, QCheckBox] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        lay.addWidget(label("Strategy thresholds", "PageTitle"))
        lay.addWidget(label("These rules decide which strategy each swim is assigned. Trials are checked from top "
                            "to bottom and get the first strategy whose rules they meet. The defaults are the "
                            "published Pathfinder values. Distances use the units of your data.",
                            "PageSubtitle", wrap=True))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 4, 8, 4)
        bl.setSpacing(10)
        for title, flag, items in PARAM_GROUPS:
            card = Card(padding=14, spacing=8)
            cb = QCheckBox(title)
            cb.setObjectName("SectionTitle")
            cb.setStyleSheet("font-weight: 600; font-size: 14px;")
            self.toggles[flag] = cb
            card.lay.addWidget(cb)
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(6)
            for r, (fname, text, unit) in enumerate(items):
                grid.addWidget(label(text), r, 0)
                w = QSpinBox() if fname == "quadrantTotalMaxVal" else QDoubleSpinBox()
                w.setRange(0, 1_000_000)
                if isinstance(w, QDoubleSpinBox):
                    w.setDecimals(1)
                w.setFixedWidth(120)
                w.setAlignment(Qt.AlignRight)
                self.inputs[fname] = w
                grid.addWidget(w, r, 1)
                u = label(unit, "Hint")
                u.setFixedWidth(120)
                grid.addWidget(u, r, 2)
            grid.setColumnStretch(0, 1)
            card.lay.addLayout(grid)
            cb.toggled.connect(lambda on, g=grid: self._enable(g, on))
            bl.addWidget(card)
        bl.addStretch(1)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

        reset = QPushButton("Restore Defaults")
        reset.clicked.connect(lambda: self._load(StrategyParams()))
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("Primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        lay.addWidget(hbox(reset, None, cancel, save))
        self._load(params)

    def _enable(self, grid, on):
        for i in range(grid.count()):
            w = grid.itemAt(i).widget()
            if w:
                w.setEnabled(on)

    def _load(self, p: StrategyParams):
        for name, w in self.inputs.items():
            w.setValue(getattr(p, name))
        for name, cb in self.toggles.items():
            cb.setChecked(getattr(p, name))
            cb.toggled.emit(cb.isChecked())

    def _save(self):
        vals = {}
        for f in fields(StrategyParams):
            if f.name in self.inputs:
                v = self.inputs[f.name].value()
                vals[f.name] = int(v) if f.name == "quadrantTotalMaxVal" else float(v)
            elif f.name in self.toggles:
                vals[f.name] = self.toggles[f.name].isChecked()
        self.params = StrategyParams(**vals)
        self.accept()


# ---------------------------------------------------------------- manual review
class ReviewDialog(QDialog):
    """Step through trials and confirm or change the strategy. Keys 1–9 pick, Enter/→ next, ← back."""

    def __init__(self, results, geom, setup, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Trials")
        self.resize(980, 640)
        self.results = results
        self.pos = 0
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(18)

        self.view = MazeView(interactive=False)
        self.view.set_geometry((geom.centre_x, geom.centre_y), geom.maze_diameter, (geom.goal_x, geom.goal_y),
                               geom.goal_diameter, setup.corridor_width, setup.chaining_width,
                               setup.thigmotaxis_zone)
        lay.addWidget(self.view, 3)

        side = QVBoxLayout()
        side.setSpacing(8)
        self.counter = label("", "Muted")
        self.title = label("", "PageTitle")
        self.auto = label("", "PageSubtitle", wrap=True)
        side.addWidget(self.counter)
        side.addWidget(self.title)
        side.addWidget(self.auto)
        side.addSpacing(6)
        side.addWidget(label("What strategy is this?", "SectionTitle"))
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (_key, name, _score, colour) in enumerate(STRATEGIES):
            key = str((i + 1) % 10)
            b = QPushButton(f"  {key}    {name}")
            b.setObjectName("Strategy")
            b.setCheckable(True)
            b.setIcon(dot_icon(colour))
            self.group.addButton(b, i)
            side.addWidget(b)
            QShortcut(QKeySequence(key), self, activated=lambda i=i: self._choose(i))
        self.group.idClicked.connect(self._choose)
        side.addStretch(1)
        self.back = QPushButton("←  Back")
        self.back.clicked.connect(lambda: self._go(-1))
        self.next = QPushButton("Next  →")
        self.next.setObjectName("Primary")
        self.next.clicked.connect(lambda: self._go(1))
        side.addWidget(hbox(self.back, None, self.next))
        side.addWidget(label("Tip: press 1–9 or 0 to choose, Enter for next.", "Hint"))
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=lambda: self._go(1))
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=lambda: self._go(-1))
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=lambda: self._go(1))
        w = QFrame()
        w.setLayout(side)
        w.setFixedWidth(320)
        lay.addWidget(w)
        self._show()

    def _current(self):
        return self.results[self.pos]

    def _show(self):
        r = self._current()
        self.counter.setText(f"Trial {self.pos + 1} of {len(self.results)}")
        name = r.trial.label
        self.title.setText(f"{name} · trial {r.trial_number}")
        self.auto.setText(f"Pathfinder says: <b>{r.strategy}</b>")
        colour = dict((s[1], s[3]) for s in STRATEGIES).get(r.final_strategy, "#0B7A8A")
        self.view.set_path(r.xs, r.ys, colour)
        names = [s[1] for s in STRATEGIES]
        idx = names.index(r.final_strategy) if r.final_strategy in names else len(names) - 1
        self.group.button(idx).setChecked(True)
        self.back.setEnabled(self.pos > 0)
        self.next.setText("Finish" if self.pos == len(self.results) - 1 else "Next  →")

    def _choose(self, i):
        name = STRATEGIES[i][1]
        self._current().manual_strategy = name
        self.group.button(i).setChecked(True)
        self.view.path_colour = STRATEGIES[i][3]
        self.view.update()

    def _go(self, d):
        checked = self.group.checkedId()
        if checked >= 0:  # record the reviewer's answer, like the original "Strategy (manual)" column
            self._current().manual_strategy = STRATEGIES[checked][1]
        n = self.pos + d
        if n >= len(self.results):
            self.accept()
            return
        if n < 0:
            return
        self.pos = n
        self._show()
