"""Interactive drawing of the pool, its zones, the goal(s), start positions and swim paths."""
from __future__ import annotations

import math
from collections import Counter
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme


class MazeView(QWidget):
    goalMoved = Signal(float, float)

    def __init__(self, parent=None, interactive=True, compact=False):
        super().__init__(parent)
        self.interactive = interactive
        self.compact = compact
        self.centre = (0.0, 0.0)
        self.diameter = 150.0
        self.goal: Optional[tuple[float, float]] = (0.0, 0.0)
        self.goal_diameter = 10.0
        self.extra_goals: list[tuple[float, float, float]] = []
        self.corridor = 40.0
        self.chaining = 25.0
        self.thigmo = 15.0
        self.starts: list[tuple[float, float]] = []
        self.path: Optional[tuple[list, list]] = None
        self.path_colour = "#0B7A8A"
        self.show_zones = True
        self._drag = False
        self._hover: Optional[tuple[float, float]] = None
        self.setMouseTracking(True)
        self.setMinimumSize(220 if compact else 320, 220 if compact else 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ------------------------------------------------------------ data
    def set_geometry(self, centre, diameter, goal, goal_diameter, corridor, chaining, thigmo, extra_goals=()):
        self.centre = centre
        self.diameter = diameter if diameter and diameter > 0 else 150.0
        self.goal = goal
        self.goal_diameter = goal_diameter or 0
        self.corridor, self.chaining, self.thigmo = corridor, chaining, thigmo
        self.extra_goals = list(extra_goals)
        self.update()

    def set_starts(self, starts):
        self.starts = [s for s in starts if s is not None]
        self.update()

    def set_path(self, xs, ys, colour=None):
        self.path = (xs, ys) if xs else None
        if colour:
            self.path_colour = colour
        self.update()

    # ------------------------------------------------------------ mapping
    def _scale(self):
        side = min(self.width(), self.height()) - (24 if self.compact else 56)
        return max(side, 10) / self.diameter

    def to_screen(self, x, y) -> QPointF:
        s = self._scale()
        return QPointF(self.width() / 2 + (x - self.centre[0]) * s,
                       self.height() / 2 - (y - self.centre[1]) * s)

    def to_data(self, pt: QPointF):
        s = self._scale()
        return (self.centre[0] + (pt.x() - self.width() / 2) / s,
                self.centre[1] - (pt.y() - self.height() / 2) / s)

    def main_start(self):
        """Most common start position (rounded), used to draw the angular corridor."""
        if not self.starts:
            return None
        step = self.diameter / 20
        c = Counter((round(x / step), round(y / step)) for x, y in self.starts)
        (kx, ky), _ = c.most_common(1)[0]
        pts = [(x, y) for x, y in self.starts if (round(x / step), round(y / step)) == (kx, ky)]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    # ------------------------------------------------------------ painting
    def paintEvent(self, _e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self._scale()
        c = self.to_screen(*self.centre)
        R = self.diameter / 2 * s

        # pool
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.pool))
        p.drawEllipse(c, R, R)

        if self.show_zones and self.goal is not None:
            # chaining annulus
            dcg = math.dist(self.centre, self.goal)
            r_out = (dcg + self.chaining / 2) * s
            r_in = max(0.0, (dcg - self.chaining / 2) * s)
            ring = QPainterPath()
            ring.addEllipse(c, min(r_out, R), min(r_out, R))
            inner = QPainterPath()
            inner.addEllipse(c, r_in, r_in)
            p.setBrush(QColor(t.zone))
            p.drawPath(ring.subtracted(inner))

        if self.show_zones:
            # wall (thigmotaxis) zones
            pen = QPen(QColor(t.muted), 1, Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            for r in (self.diameter / 2 - self.thigmo / 2, self.diameter / 2 - self.thigmo):
                if r > 0:
                    p.drawEllipse(c, r * s, r * s)
            # crosshair
            p.setPen(QPen(QColor(t.border), 1, Qt.DotLine))
            p.drawLine(QPointF(c.x() - R, c.y()), QPointF(c.x() + R, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - R), QPointF(c.x(), c.y() + R))

        # pool edge
        p.setPen(QPen(QColor(t.pool_edge), 2.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, R, R)

        # angular corridor from the main start position
        start = self.main_start()
        if self.show_zones and start and self.goal and not self.path:
            st = self.to_screen(*start)
            g = self.to_screen(*self.goal)
            ang = math.atan2(g.y() - st.y(), g.x() - st.x())
            half = math.radians(self.corridor / 2)
            length = 2 * R
            wedge = QPainterPath(st)
            wedge.lineTo(st.x() + length * math.cos(ang - half), st.y() + length * math.sin(ang - half))
            wedge.lineTo(st.x() + length * math.cos(ang + half), st.y() + length * math.sin(ang + half))
            wedge.closeSubpath()
            clip = QPainterPath()
            clip.addEllipse(c, R, R)
            col = QColor("#F9A825")
            col.setAlpha(55)
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawPath(wedge.intersected(clip))
            col.setAlpha(170)
            p.setPen(QPen(col, 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawLine(st, g)

        # path
        if self.path:
            xs, ys = self.path
            path = QPainterPath(self.to_screen(xs[0], ys[0]))
            for x, y in zip(xs[1:], ys[1:]):
                path.lineTo(self.to_screen(x, y))
            p.setPen(QPen(QColor(self.path_colour), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            p.setPen(QPen(QColor(t.surface), 1.5))
            p.setBrush(QColor("#2E7D32"))
            p.drawEllipse(self.to_screen(xs[0], ys[0]), 5, 5)
            p.setBrush(QColor(t.pool_edge))
            p.drawEllipse(self.to_screen(xs[-1], ys[-1]), 4, 4)

        # extra goals
        for gx, gy, gd in self.extra_goals:
            gp = self.to_screen(gx, gy)
            r = max(gd / 2 * s, 4)
            p.setPen(QPen(QColor("#E65100"), 2, Qt.DashLine))
            p.setBrush(QColor(230, 81, 0, 50))
            p.drawEllipse(gp, r, r)

        # goal
        if self.goal is not None:
            gp = self.to_screen(*self.goal)
            r = max(self.goal_diameter / 2 * s, 5)
            p.setPen(QPen(QColor("#FFFFFF" if not t.dark else "#111"), 2))
            p.setBrush(QColor("#E53935"))
            p.drawEllipse(gp, r, r)

        # start positions
        if not self.path:
            p.setPen(QPen(QColor(t.surface), 1.2))
            p.setBrush(QColor("#2E7D32"))
            for x, y in self.starts:
                p.drawEllipse(self.to_screen(x, y), 4.5, 4.5)

        # hover coordinates
        if self._hover and self.interactive and not self.compact:
            f = QFont(self.font())
            f.setPixelSize(11)
            p.setFont(f)
            p.setPen(QColor(t.muted))
            p.drawText(QRectF(8, self.height() - 24, self.width() - 16, 20), Qt.AlignRight | Qt.AlignVCenter,
                       f"x {self._hover[0]:.1f}   y {self._hover[1]:.1f}")

    # ------------------------------------------------------------ interaction
    def _near_goal(self, pos) -> bool:
        if self.goal is None:
            return False
        gp = self.to_screen(*self.goal)
        r = max(self.goal_diameter / 2 * self._scale(), 8) + 6
        return (pos.x() - gp.x()) ** 2 + (pos.y() - gp.y()) ** 2 <= r * r

    def _inside_pool(self, pos) -> bool:
        c = self.to_screen(*self.centre)
        R = self.diameter / 2 * self._scale()
        return (pos.x() - c.x()) ** 2 + (pos.y() - c.y()) ** 2 <= R * R

    def mousePressEvent(self, e):
        if not self.interactive or e.button() != Qt.LeftButton:
            return
        pos = e.position()
        if self._near_goal(pos) or self._inside_pool(pos):
            self._drag = True
            self._move_goal(pos)

    def mouseMoveEvent(self, e):
        pos = e.position()
        self._hover = self.to_data(pos) if self._inside_pool(pos) else None
        if self.interactive:
            self.setCursor(Qt.ClosedHandCursor if self._drag else
                           Qt.OpenHandCursor if self._near_goal(pos) else
                           Qt.CrossCursor if self._inside_pool(pos) else Qt.ArrowCursor)
        if self._drag:
            self._move_goal(pos)
        self.update()

    def mouseReleaseEvent(self, e):
        self._drag = False

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def _move_goal(self, pos):
        x, y = self.to_data(pos)
        x, y = round(x, 2), round(y, 2)
        self.goal = (x, y)
        self.goalMoved.emit(x, y)
        self.update()
