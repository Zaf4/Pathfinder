"""Render the app icon (PNG sizes + macOS .icns). Run: uv run python tools/make_icon.py"""
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/pathfinder/gui/assets"


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 1024
    # rounded-square background (macOS grid: 824px body inside 1024 canvas)
    body = QRectF(100 * s, 100 * s, 824 * s, 824 * s)
    g = QLinearGradient(body.topLeft(), body.bottomRight())
    g.setColorAt(0, QColor("#0F8FA0"))
    g.setColorAt(1, QColor("#075563"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(body, 185 * s, 185 * s)
    c = body.center()
    R = 300 * s
    # pool
    p.setBrush(QColor(255, 255, 255, 40))
    p.drawEllipse(c, R, R)
    p.setPen(QPen(QColor("#FFFFFF"), 26 * s))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c, R, R)
    # swim path: a curving search that homes in on the platform
    start = QPointF(c.x() - 0.72 * R, c.y() + 0.62 * R)
    goal = QPointF(c.x() + 0.38 * R, c.y() - 0.36 * R)
    path = QPainterPath(start)
    path.cubicTo(QPointF(c.x() - 0.2 * R, c.y() + 0.9 * R), QPointF(c.x() + 0.55 * R, c.y() + 0.35 * R),
                 QPointF(c.x() + 0.05 * R, c.y() + 0.05 * R))
    path.cubicTo(QPointF(c.x() - 0.35 * R, c.y() - 0.25 * R), QPointF(c.x() + 0.05 * R, c.y() - 0.75 * R),
                 goal)
    pen = QPen(QColor("#FFD54F"), 30 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.drawPath(path)
    # start dot + platform
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(start, 34 * s, 34 * s)
    p.setBrush(QColor("#FF5252"))
    p.setPen(QPen(QColor("#FFFFFF"), 14 * s))
    p.drawEllipse(goal, 62 * s, 62 * s)
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512):
        render(size).save(str(ASSETS / f"icon_{size}.png"))
    if sys.platform == "darwin" and shutil.which("iconutil"):
        iconset = ROOT / "build/AppIcon.iconset"
        iconset.mkdir(parents=True, exist_ok=True)
        for base in (16, 32, 128, 256, 512):
            render(base).save(str(iconset / f"icon_{base}x{base}.png"))
            render(base * 2).save(str(iconset / f"icon_{base}x{base}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ROOT / "src/pathfinder/gui/assets/AppIcon.icns")],
                       check=True)
        shutil.rmtree(iconset.parent)
    print("icons written")
