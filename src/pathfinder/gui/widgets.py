"""Small reusable widgets."""
from __future__ import annotations

import gc
import threading
import traceback
from typing import Callable

from PySide6.QtCore import QObject, QRectF, QRunnable, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
                               QWidget)

from . import theme


def label(text: str = "", name: str | None = None, wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class Card(QFrame):
    def __init__(self, parent=None, padding=18, spacing=12):
        super().__init__(parent)
        self.setObjectName("Card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(padding, padding, padding, padding)
        self.lay.setSpacing(spacing)


class Banner(QFrame):
    def __init__(self, text="", info=False, parent=None):
        super().__init__(parent)
        self.setObjectName("InfoBanner" if info else "Banner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        self.text = label(text, wrap=True)
        lay.addWidget(self.text)

    def setText(self, text):
        self.text.setText(text)


class StepButton(QAbstractButton):
    """Sidebar entry: numbered circle + title + subtitle."""

    def __init__(self, number: int, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.number, self.title, self.subtitle = number, title, subtitle
        self.done = False
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(200, 58)

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 3, -8, -3)
        if self.isChecked():
            p.setBrush(QColor(t.accent_soft))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 10, 10)
        elif self.underMouse() and self.isEnabled():
            p.setBrush(QColor(t.surface2))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 10, 10)
        circle = QRectF(r.left() + 10, r.center().y() - 13, 26, 26)
        enabled = self.isEnabled()
        if self.done and not self.isChecked():
            p.setBrush(QColor(t.accent))
            p.setPen(Qt.NoPen)
            p.drawEllipse(circle)
            pen = QPen(QColor(t.accent_text), 2.2)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            c = circle.center()
            path = QPainterPath()
            path.moveTo(c.x() - 5, c.y())
            path.lineTo(c.x() - 1.5, c.y() + 4)
            path.lineTo(c.x() + 5.5, c.y() - 4)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        else:
            active = self.isChecked()
            p.setBrush(QColor(t.accent if active else t.surface2))
            p.setPen(QPen(QColor(t.accent if active else t.border), 1))
            p.drawEllipse(circle)
            p.setPen(QColor(t.accent_text if active else (t.text if enabled else t.muted)))
            f = QFont(self.font())
            f.setBold(True)
            p.setFont(f)
            p.drawText(circle, Qt.AlignCenter, str(self.number))
        tx = circle.right() + 12
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(14)
        p.setFont(f)
        p.setPen(QColor(t.text if enabled else t.muted))
        p.drawText(QRectF(tx, r.top() + 9, r.right() - tx, 20), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        f2 = QFont(self.font())
        f2.setPixelSize(12)
        p.setFont(f2)
        p.setPen(QColor(t.muted))
        p.drawText(QRectF(tx, r.top() + 28, r.right() - tx, 18), Qt.AlignLeft | Qt.AlignVCenter, self.subtitle)

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class BarChart(QWidget):
    """Horizontal bars, one per category: [(label, value, colour)]."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[tuple[str, float, str]] = []
        self.setMinimumHeight(80)

    def set_items(self, items):
        self.items = items
        self.setMinimumHeight(max(80, 30 * len(items) + 8))
        self.update()

    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.items:
            return
        total = sum(v for _, v, _ in self.items) or 1
        label_w = 150
        num_w = 80
        bar_x = label_w + 8
        bar_w = max(10, self.width() - bar_x - num_w)
        maxv = max(v for _, v, _ in self.items) or 1
        y = 4
        for name, v, colour in self.items:
            p.setPen(QColor(t.text))
            p.drawText(QRectF(0, y, label_w, 24), Qt.AlignRight | Qt.AlignVCenter, name)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t.surface2))
            p.drawRoundedRect(QRectF(bar_x, y + 5, bar_w, 14), 7, 7)
            if v:
                p.setBrush(QColor(colour))
                p.drawRoundedRect(QRectF(bar_x, y + 5, max(14, bar_w * v / maxv), 14), 7, 7)
            p.setPen(QColor(t.muted))
            p.drawText(QRectF(bar_x + bar_w + 8, y, num_w - 8, 24), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{int(v)}  ({100 * v / total:.0f}%)")
            y += 30


class Swatch(QWidget):
    def __init__(self, colour: str, size=12, parent=None):
        super().__init__(parent)
        self.colour = colour
        self.setFixedSize(size, size)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.colour))
        p.drawEllipse(self.rect())


# ------------------------------------------------------------------ background work
class WorkerSignals(QObject):
    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str, str)  # message, details


class Worker(QRunnable):
    """Run fn(*args, **kwargs) on a thread-pool thread and report back through signals.

    With controls=True, fn also receives progress=<callable(i, n, label)> and cancelled=<callable() -> bool>.
    The worker keeps no reference cycles, so Python never has to garbage-collect Qt objects off the GUI thread.
    """

    def __init__(self, fn: Callable, *args, controls: bool = False, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.controls = controls
        self.signals = WorkerSignals()
        self._cancel = threading.Event()
        self.setAutoDelete(False)

    def cancel(self):
        self._cancel.set()

    def is_cancelled(self):
        return self._cancel.is_set()

    def run(self):
        kwargs = dict(self.kwargs)
        signals = self.signals
        if self.controls:
            kwargs.update(progress=signals.progress.emit, cancelled=self._cancel.is_set)
        try:
            res = self.fn(*self.args, **kwargs)
        except Exception as e:  # noqa: BLE001
            signals.failed.emit(str(e), traceback.format_exc())
            return
        signals.done.emit(res)


def collect_garbage_on_gui_thread(parent: QObject) -> QTimer:
    """PySide crashes if Python's cyclic GC happens to run on a worker thread and frees Qt objects there.
    Turn automatic GC off and collect from a GUI-thread timer instead."""
    gc.disable()
    counter = {"n": 0}

    def tick():
        counter["n"] += 1
        gc.collect(2 if counter["n"] % 30 == 0 else 0)
    timer = QTimer(parent)
    timer.setInterval(1000)
    timer.timeout.connect(tick)
    timer.start()
    return timer


def hbox(*widgets, spacing=8, margins=(0, 0, 0, 0), stretch_end=False):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for x in widgets:
        if x is None:
            lay.addStretch(1)
        else:
            lay.addWidget(x)
    if stretch_end:
        lay.addStretch(1)
    return w
