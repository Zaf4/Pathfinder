"""Step 2: describe the maze and run the analysis."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QPushButton,
                               QScrollArea, QToolButton, QVBoxLayout, QWidget)

from ..core.analysis import AnalysisError, resolve_geometry
from ..core.params import Goal, MazeSetup
from .dialogs import SettingsDialog, show_error
from .maze_view import MazeView
from .state import AppState
from .widgets import Banner, Card, hbox, label


def spin(lo=-100000.0, hi=100000.0, decimals=2, step=1.0, suffix=""):
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setDecimals(decimals)
    w.setSingleStep(step)
    w.setSuffix(suffix)
    w.setAlignment(Qt.AlignRight)
    w.setKeyboardTracking(False)
    w.setMinimumWidth(96)
    return w


class ExtraGoalRow(QWidget):
    removed = Signal(object)
    changed = Signal()

    def __init__(self, goal: Goal, n: int):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.name = label(f"Goal {n}")
        self.name.setMinimumWidth(52)
        self.x, self.y, self.d = spin(), spin(), spin(0.1, 100000)
        self.x.setValue(goal.x)
        self.y.setValue(goal.y)
        self.d.setValue(goal.diameter)
        for w, tip in ((self.x, "X"), (self.y, "Y"), (self.d, "Diameter")):
            w.setToolTip(tip)
            w.setMinimumWidth(70)
            w.valueChanged.connect(self.changed.emit)
        rm = QToolButton()
        rm.setText("✕")
        rm.setToolTip("Remove this goal")
        rm.clicked.connect(lambda: self.removed.emit(self))
        for w in (self.name, self.x, self.y, self.d, rm):
            lay.addWidget(w)

    def goal(self) -> Goal:
        return Goal(self.x.value(), self.y.value(), self.d.value(), self.name.text())


class MazePage(QWidget):
    back = Signal()
    run = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._loading = False
        self.extra_rows: list[ExtraGoalRow] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 24)
        outer.setSpacing(14)
        outer.addWidget(label("Set up the maze", "PageTitle"))
        outer.addWidget(label("Tell Pathfinder where the pool and the goal are, in the same units as your "
                              "tracking data. Click or drag in the drawing to place the goal.",
                              "PageSubtitle", wrap=True))

        body = QHBoxLayout()
        body.setSpacing(20)
        outer.addLayout(body, 1)

        # ---- form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(400)
        form = QWidget()
        fl = QVBoxLayout(form)
        fl.setContentsMargins(0, 0, 10, 0)
        fl.setSpacing(12)
        scroll.setWidget(form)
        body.addWidget(scroll)

        # pool
        pool = Card(padding=16, spacing=10)
        pool.lay.addWidget(label("Pool", "SectionTitle"))
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        self.maze_d = spin(0.1, 100000)
        self.cx, self.cy = spin(), spin()
        g.addWidget(label("Diameter"), 0, 0)
        g.addWidget(self.maze_d, 0, 1, 1, 2)
        g.addWidget(label("Centre (x, y)"), 1, 0)
        g.addWidget(self.cx, 1, 1)
        g.addWidget(self.cy, 1, 2)
        pool.lay.addLayout(g)
        self.detect_btn = QPushButton("Detect Pool and Goal From My Data")
        self.detect_btn.clicked.connect(self.detect)
        pool.lay.addWidget(self.detect_btn)
        self.detect_note = label("", "Hint", wrap=True)
        pool.lay.addWidget(self.detect_note)
        fl.addWidget(pool)

        # goal
        goal = Card(padding=16, spacing=10)
        goal.lay.addWidget(label("Goal (hidden platform)", "SectionTitle"))
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        self.gx, self.gy = spin(), spin()
        self.gd = spin(0.1, 100000)
        g.addWidget(label("Position (x, y)"), 0, 0)
        g.addWidget(self.gx, 0, 1)
        g.addWidget(self.gy, 0, 2)
        g.addWidget(label("Diameter"), 1, 0)
        g.addWidget(self.gd, 1, 1, 1, 2)
        goal.lay.addLayout(g)

        self.extra_box = QVBoxLayout()
        self.extra_box.setSpacing(6)
        goal.lay.addLayout(self.extra_box)
        add = QPushButton("+  Add Another Goal")
        add.setObjectName("Link")
        add.setToolTip("Score the same swims against other locations, e.g. the old platform position in a "
                       "reversal. Each goal gets its own results file.")
        add.clicked.connect(self.add_goal)
        goal.lay.addWidget(hbox(add, None))
        fl.addWidget(goal)

        # zones
        zones = Card(padding=16, spacing=10)
        zones.lay.addWidget(label("Zones", "SectionTitle"))
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        self.corridor = spin(1, 180, 0, 5, " °")
        self.chaining = spin(0.1, 100000)
        self.thigmo = spin(0.1, 100000)
        rows = [("Angular corridor width", self.corridor, "Swims inside this cone from the start toward the goal "
                 "count as heading to the goal (Directed Search)."),
                ("Chaining ring width", self.chaining, "Width of the ring at the goal's distance from the "
                 "centre (Chaining)."),
                ("Wall zone width", self.thigmo, "Width of the zone along the wall (Thigmotaxis).")]
        for r, (text, w, tip) in enumerate(rows):
            lab = label(text)
            lab.setToolTip(tip)
            w.setToolTip(tip)
            g.addWidget(lab, r, 0)
            g.addWidget(w, r, 1)
        g.setColumnStretch(0, 1)
        zones.lay.addLayout(g)
        fl.addWidget(zones)

        # options
        opts = Card(padding=16, spacing=10)
        opts.lay.addWidget(label("Options", "SectionTitle"))
        self.truncate = QCheckBox("Stop each trial when the animal reaches the goal")
        opts.lay.addWidget(self.truncate)
        opts.lay.addWidget(label("Review trials by hand"))
        self.review = QComboBox()
        self.review.addItem("No, classify everything automatically", "none")
        self.review.addItem("Only trials Pathfinder can't classify", "unrecognized")
        self.review.addItem("Every trial", "all")
        opts.lay.addWidget(self.review)
        trow = QHBoxLayout()
        self.thresholds = label("", "Muted")
        edit = QPushButton("Edit…")
        edit.clicked.connect(self.edit_thresholds)
        trow.addWidget(self.thresholds, 1)
        trow.addWidget(edit)
        opts.lay.addLayout(trow)
        fl.addWidget(opts)
        fl.addStretch(1)

        # ---- drawing
        right = QVBoxLayout()
        right.setSpacing(8)
        self.view = MazeView()
        self.view.goalMoved.connect(self._goal_dragged)
        right.addWidget(self.view, 1)
        legend = label("<span style='color:#E53935'>●</span> goal &nbsp;&nbsp; "
                       "<span style='color:#2E7D32'>●</span> where each trial starts &nbsp;&nbsp; "
                       "shaded ring: chaining zone &nbsp;&nbsp; dashed: wall zones &nbsp;&nbsp; cone: angular corridor",
                       "Hint", wrap=True)
        legend.setAlignment(Qt.AlignCenter)
        right.addWidget(legend)
        self.warn = Banner()
        self.warn.hide()
        right.addWidget(self.warn)
        body.addLayout(right, 1)

        # ---- footer
        back = QPushButton("←  Back")
        back.clicked.connect(self.back.emit)
        self.run_btn = QPushButton("Analyze")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self._run)
        outer.addWidget(hbox(back, None, self.run_btn))

        for w in (self.maze_d, self.cx, self.cy, self.gx, self.gy, self.gd, self.corridor, self.chaining,
                  self.thigmo):
            w.valueChanged.connect(self._changed)
        self.truncate.toggled.connect(self._changed)
        self.review.currentIndexChanged.connect(self._changed)
        state.experimentChanged.connect(self.refresh_data)
        state.paramsChanged.connect(self._show_params)
        self.load_setup(state.setup)
        self._show_params()
        self.refresh_data()

    # ---------------------------------------------------------- setup <-> form
    def load_setup(self, s: MazeSetup):
        self._loading = True
        self.maze_d.setValue(s.maze_diameter or 150)
        self.cx.setValue(s.centre_x or 0)
        self.cy.setValue(s.centre_y or 0)
        self.gx.setValue(s.goal_x or 0)
        self.gy.setValue(s.goal_y or 0)
        self.gd.setValue(s.goal_diameter or 10)
        self.corridor.setValue(s.corridor_width)
        self.chaining.setValue(s.chaining_width)
        self.thigmo.setValue(s.thigmotaxis_zone)
        self.truncate.setChecked(s.truncate_at_goal)
        for row in list(self.extra_rows):
            self._remove_goal(row, update=False)
        for gl in s.extra_goals:
            self.add_goal(gl, update=False)
        self.review.setCurrentIndex(max(0, self.review.findData(self.state.review_mode)))
        self._loading = False
        self._changed()

    def current_setup(self) -> MazeSetup:
        return MazeSetup(
            goal_x=self.gx.value(), goal_y=self.gy.value(), goal_diameter=self.gd.value(),
            maze_diameter=self.maze_d.value(), centre_x=self.cx.value(), centre_y=self.cy.value(),
            corridor_width=self.corridor.value(), chaining_width=self.chaining.value(),
            thigmotaxis_zone=self.thigmo.value(), truncate_at_goal=self.truncate.isChecked(),
            extra_goals=[r.goal() for r in self.extra_rows])

    def _changed(self, *_):
        if self._loading:
            return
        s = self.current_setup()
        self.state.setup = s
        self.state.review_mode = self.review.currentData()
        self.state.save_setup()
        self.view.set_geometry((s.centre_x, s.centre_y), s.maze_diameter, (s.goal_x, s.goal_y), s.goal_diameter,
                               s.corridor_width, s.chaining_width, s.thigmotaxis_zone,
                               [(g.x, g.y, g.diameter) for g in s.extra_goals])
        self._check()

    def _goal_dragged(self, x, y):
        self._loading = True
        self.gx.setValue(x)
        self.gy.setValue(y)
        self._loading = False
        self._changed()

    def add_goal(self, goal: Goal | None = None, update=True):
        if goal is None or isinstance(goal, bool):
            r = self.maze_d.value() / 4
            goal = Goal(self.cx.value() - (self.gx.value() - self.cx.value()) or -r,
                        self.cy.value() - (self.gy.value() - self.cy.value()) or -r, self.gd.value())
        row = ExtraGoalRow(goal, len(self.extra_rows) + 2)
        row.removed.connect(self._remove_goal)
        row.changed.connect(self._changed)
        self.extra_rows.append(row)
        self.extra_box.addWidget(row)
        if update:
            self._changed()

    def _remove_goal(self, row, update=True):
        self.extra_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        for i, r in enumerate(self.extra_rows):
            r.name.setText(f"Goal {i + 2}")
        if update:
            self._changed()

    # ---------------------------------------------------------- data
    def refresh_data(self):
        exp = self.state.experiment
        starts = [t.start for t in exp.trials] if exp else []
        self.view.set_starts(starts)
        n = len([t for t in exp.trials if len(t)]) if exp else 0
        self.run_btn.setText(f"Analyze {n} Trial{'s' if n != 1 else ''}  →" if n else "Analyze")
        self.run_btn.setEnabled(n > 0)
        multi = bool(exp) and (not self.state.single_file or exp.software == "watermaze")
        self.detect_btn.setEnabled(multi)
        self.detect_note.setText("" if multi or not exp else
                                 "Detection needs a whole folder of trials. Enter the values yourself.")
        self._check()

    def detect(self):
        exp = self.state.experiment
        if not exp:
            return
        s = self.current_setup()
        s.goal_x = s.goal_y = s.centre_x = s.centre_y = s.maze_diameter = None
        try:
            g = resolve_geometry(exp, s, single_file=self.state.single_file)
        except AnalysisError as e:
            show_error(self, "Couldn't detect the maze", str(e))
            return
        self._loading = True
        self.maze_d.setValue(round(g.maze_diameter, 2))
        self.cx.setValue(round(g.centre_x, 2))
        self.cy.setValue(round(g.centre_y, 2))
        self.gx.setValue(round(g.goal_x, 2))
        self.gy.setValue(round(g.goal_y, 2))
        self._loading = False
        self._changed()
        self.detect_note.setText("Estimated from where the animals swam. Check the drawing and drag the goal "
                                 "if it's not quite right.")

    def _check(self):
        s = self.state.setup
        msgs = []
        R = (s.maze_diameter or 0) / 2
        if R > 0 and math.dist((s.goal_x, s.goal_y), (s.centre_x, s.centre_y)) > R:
            msgs.append("The goal is outside the pool.")
        exp = self.state.experiment
        if exp and R > 0:
            starts = [t.start for t in exp.trials if t.start]
            outside = [p for p in starts if math.dist(p, (s.centre_x, s.centre_y)) > R * 1.1]
            if starts and len(outside) > len(starts) / 2:
                msgs.append("Most trials start outside the pool. The centre or diameter probably doesn't "
                            "match your data's units. Try “Detect Pool and Goal From My Data”.")
        self.warn.setText("⚠  " + " ".join(msgs))
        self.warn.setVisible(bool(msgs))

    def _show_params(self):
        default = self.state.params.is_default()
        self.thresholds.setText("Strategy thresholds: <b>published defaults</b>" if default else
                                "Strategy thresholds: <b>custom</b>")

    def edit_thresholds(self):
        dlg = SettingsDialog(self.state.params, self)
        if dlg.exec():
            self.state.set_params(dlg.params)

    def _run(self):
        self._changed()
        self.run.emit()
