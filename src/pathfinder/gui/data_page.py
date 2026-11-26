"""Step 1: choose the tracking data."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QSizePolicy, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.readers import SOFTWARE_LABELS, detect_software, load_experiment
from . import theme
from .dialogs import ColumnPickerDialog, show_error
from .state import AppState
from .widgets import Banner, Card, Worker, hbox, label

DATA_FILTER = "Tracking data (*.csv *.xlsx *.xls);;All files (*)"


class DropZone(QFrame):
    dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._hover = False
        self.setMinimumHeight(260)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)
        self.icon = QLabel()
        self.icon.setFixedSize(64, 52)
        lay.addWidget(self.icon, 0, Qt.AlignHCenter)
        t = label("Drag a folder of trials here", "SectionTitle")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        s = label("A folder with one file per trial (or one WaterMaze export). You can also pick a single file.",
                  "Muted", wrap=True)
        s.setAlignment(Qt.AlignCenter)
        s.setMaximumWidth(420)
        lay.addWidget(s, 0, Qt.AlignHCenter)
        self.folder_btn = QPushButton("Choose Folder…")
        self.folder_btn.setObjectName("Primary")
        self.file_btn = QPushButton("Choose a Single File…")
        lay.addSpacing(6)
        lay.addWidget(hbox(None, self.folder_btn, self.file_btn, None, spacing=10))

    def paintEvent(self, e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        p.setBrush(QColor(t.accent_soft if self._hover else t.surface))
        p.setPen(QPen(QColor(t.accent if self._hover else t.border), 2, Qt.DashLine))
        p.drawRoundedRect(r, 14, 14)
        # folder glyph
        g = self.icon.geometry()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.accent))
        p.drawRoundedRect(QRectF(g.left() + 4, g.top() + 6, 26, 12), 4, 4)
        p.drawRoundedRect(QRectF(g.left() + 4, g.top() + 12, 56, 38), 6, 6)
        p.setBrush(QColor(t.surface))
        p.drawRoundedRect(QRectF(g.left() + 10, g.top() + 20, 44, 3), 1.5, 1.5)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._hover = True
            self.update()

    def dragLeaveEvent(self, e):
        self._hover = False
        self.update()

    def dropEvent(self, e):
        self._hover = False
        self.update()
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.dropped.emit(urls[0])


class Tile(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(0)
        self.value = label("–", "BigNumber")
        lay.addWidget(self.value)
        lay.addWidget(label(title, "Muted"))


class DataPage(QWidget):
    proceed = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.pool = QThreadPool.globalInstance()
        self.worker = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 24)
        outer.setSpacing(16)
        outer.addWidget(label("Choose your tracking data", "PageTitle"))
        outer.addWidget(label("Pathfinder reads exports from EthoVision, ANY-maze, WaterMaze and ezTrack, "
                              "or any table with X, Y and time columns.", "PageSubtitle", wrap=True))

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        # empty state
        self.drop = DropZone()
        self.drop.dropped.connect(self.open_path)
        self.drop.folder_btn.clicked.connect(self.choose_folder)
        self.drop.file_btn.clicked.connect(self.choose_file)
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.setContentsMargins(0, 0, 0, 0)
        el.addWidget(self.drop)
        el.addStretch(1)
        self.stack.addWidget(empty)

        # loaded state
        loaded = QWidget()
        ll = QVBoxLayout(loaded)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(14)

        src = Card(padding=16)
        top = QHBoxLayout()
        self.path_label = label("", "SectionTitle")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        change = QPushButton("Choose Different Data…")
        change.clicked.connect(self.choose_folder)
        top.addWidget(self.path_label, 1)
        top.addWidget(change)
        src.lay.addLayout(top)

        row = QHBoxLayout()
        row.addWidget(label("Recorded with:"))
        self.software = QComboBox()
        for key, name in SOFTWARE_LABELS.items():
            self.software.addItem(name, key)
        self.software.setMinimumWidth(180)
        self.software.activated.connect(self._software_picked)
        row.addWidget(self.software)
        self.detect_note = label("", "Hint")
        row.addWidget(self.detect_note)
        self.columns_btn = QPushButton("Choose Columns…")
        self.columns_btn.clicked.connect(self.pick_columns)
        row.addWidget(self.columns_btn)
        row.addStretch(1)
        src.lay.addLayout(row)
        ll.addWidget(src)

        tiles = QGridLayout()
        tiles.setSpacing(12)
        self.t_trials, self.t_animals, self.t_duration, self.t_points = (
            Tile("trials"), Tile("animals"), Tile("average length (s)"), Tile("positions"))
        for i, t in enumerate((self.t_trials, self.t_animals, self.t_duration, self.t_points)):
            tiles.addWidget(t, 0, i)
        ll.addLayout(tiles)

        self.warning = Banner()
        self.warning.hide()
        ll.addWidget(self.warning)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Trial", "Positions", "Length (s)", "Start (x, y)"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        ll.addWidget(self.table, 1)

        self.next_btn = QPushButton("Continue to Maze Setup  →")
        self.next_btn.setObjectName("Primary")
        self.next_btn.clicked.connect(self.proceed.emit)
        ll.addWidget(hbox(None, self.next_btn))
        self.stack.addWidget(loaded)

        self.loading = label("Reading files…", "Muted")
        self.loading.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(self.loading)

    # ---------------------------------------------------------- choose
    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder of trials", self._start_dir())
        if d:
            self.open_path(d)

    def choose_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choose a tracking file", self._start_dir(), DATA_FILTER)
        if f:
            self.open_path(f)

    def _start_dir(self):
        if self.state.path:
            return str(Path(self.state.path).parent)
        return str(Path.home())

    def open_path(self, path: str):
        if not os.path.exists(path):
            return
        sw = detect_software(path)
        self.state.path = path
        self.state.single_file = os.path.isfile(path)
        self.state.custom = None
        if sw is None:
            show_error(self, "No tracking data here",
                       "Pathfinder couldn't find any .csv or .xlsx files in this location.")
            return
        self.detect_note.setText("Detected automatically" if sw != "custom" else
                                 "Unknown layout. Choose the X, Y and time columns.")
        self._set_software(sw)
        if sw == "custom":
            self.pick_columns()
        else:
            self.load()

    def _set_software(self, sw):
        self.state.software = sw
        self.software.setCurrentIndex(self.software.findData(sw))
        self.columns_btn.setVisible(sw == "custom")

    def _software_picked(self):
        sw = self.software.currentData()
        self.detect_note.setText("")
        self._set_software(sw)
        if sw == "custom" and self.state.custom is None:
            self.pick_columns()
        else:
            self.load()

    def pick_columns(self):
        path = self.state.path
        sample = path
        if os.path.isdir(path):
            from ..core.readers import custom_ext_in, find_files
            files = find_files(path, "*" + custom_ext_in(path))
            sample = files[0] if files else None
        if not sample:
            show_error(self, "No files", "There are no .csv or .xlsx files to read.")
            return
        dlg = ColumnPickerDialog(sample, self)
        if dlg.exec():
            self.state.custom = dlg.columns
            self._set_software("custom")
            self.load()
        elif self.state.experiment is None:
            self.stack.setCurrentIndex(0)

    # ---------------------------------------------------------- load
    def load(self):
        if self.worker:
            self.worker.cancel()
        self.stack.setCurrentIndex(2)
        worker = Worker(load_experiment, self.state.software, self.state.path, self.state.custom)
        self.worker = worker
        # ignore answers from an earlier load that finishes after a newer one was started
        worker.signals.done.connect(lambda exp: self._loaded(exp) if self.worker is worker else None)
        worker.signals.failed.connect(lambda m, d: self._failed(m, d) if self.worker is worker else None)
        self.pool.start(worker)

    def _failed(self, msg, details):
        self.state.experiment = None
        self.state.experimentChanged.emit()
        self.stack.setCurrentIndex(1 if self.state.path else 0)
        self._clear()
        self.warning.setText("⚠  " + msg + "  Try a different “Recorded with” option.")
        self.warning.show()
        self.next_btn.setEnabled(False)

    def _clear(self):
        self.path_label.setText(self.state.path or "")
        self.table.setRowCount(0)
        for t in (self.t_trials, self.t_animals, self.t_duration, self.t_points):
            t.value.setText("–")

    def _loaded(self, exp):
        self.state.experiment = exp
        self.state.results = []
        self.stack.setCurrentIndex(1)
        p = Path(self.state.path)
        self.path_label.setText(("📄  " if p.is_file() else "📁  ") + p.name)
        self.path_label.setToolTip(str(p))
        trials = exp.trials
        self.t_trials.value.setText(str(len(trials)))
        animals = exp.animals
        self.t_animals.value.setText(str(len(animals)) if animals else "–")
        lengths = [t.points[-1].time - t.points[0].time for t in trials if len(t) > 1]
        self.t_duration.value.setText(f"{sum(lengths) / len(lengths):.1f}" if lengths else "–")
        self.t_points.value.setText(f"{sum(len(t) for t in trials):,}")

        bad = [t for t in trials if t.corrupted]
        empty = [t for t in trials if len(t) == 0]
        msgs = []
        if empty:
            msgs.append(f"{len(empty)} trial(s) have no positions and will be skipped.")
        if bad:
            msgs.append(f"{len(bad)} trial(s) contain rows with missing or unreadable values. "
                        "Those rows are ignored.")
        self.warning.setText("⚠  " + " ".join(msgs))
        self.warning.setVisible(bool(msgs))

        self.table.setRowCount(len(trials))
        for i, t in enumerate(trials):
            name = " · ".join(str(v) for v in (t.animal, t.name) if v not in (None, "")) or Path(t.source or "").name
            if t.date:
                name += "   " + t.date.strftime("%Y-%m-%d %H:%M")
            length = t.points[-1].time - t.points[0].time if len(t) > 1 else 0
            start = f"{t.start[0]:.1f}, {t.start[1]:.1f}" if t.start else "–"
            for c, v in enumerate([str(i + 1), name, f"{len(t):,}", f"{length:.1f}", start]):
                it = QTableWidgetItem(v)
                if c != 1:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, c, it)
        self.next_btn.setEnabled(any(len(t) for t in trials))
        self.state.experimentChanged.emit()
