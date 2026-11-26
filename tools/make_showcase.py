"""Frame screen grabs (from tools/screenshots.py) as macOS-style windows on a gradient,
with a headline, for sharing.

    uv run python tools/screenshots.py SHOTS "<folder of real trials>"
    uv run python tools/make_showcase.py SHOTS OUTDIR
"""
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QRadialGradient)

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
app = QGuiApplication(sys.argv)
from pathfinder import __version__  # noqa: E402

W, H = 3200, 2200
BAR = 64  # title bar height (px at 2x)
CREDIT = "Data: Overall & Kempermann 2019, figshare 10.6084/m9.figshare.10248158 (CC BY 4.0)"


def credit(p):
    f = QFont(); f.setPixelSize(30); p.setFont(f); p.setPen(QColor(255, 255, 255, 150))
    p.drawText(QRectF(0, H - 64, W - 60, 44), Qt.AlignRight | Qt.AlignVCenter, CREDIT)


def background(p, dark):
    g = QLinearGradient(0, 0, W, H)
    if dark:
        g.setColorAt(0, QColor("#0B1B22")); g.setColorAt(1, QColor("#05343D"))
    else:
        g.setColorAt(0, QColor("#0F8FA0")); g.setColorAt(0.55, QColor("#0B6F80")); g.setColorAt(1, QColor("#063F4A"))
    p.fillRect(0, 0, W, H, g)
    glow = QRadialGradient(QPointF(W * 0.8, H * 0.1), W * 0.6)
    glow.setColorAt(0, QColor(255, 255, 255, 40 if not dark else 22))
    glow.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(0, 0, W, H, glow)


def shadow(p, rect, radius):
    for i in range(40, 0, -1):
        a = int(5 * (1 - i / 40) ** 1.5) + 1
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, a))
        p.drawRoundedRect(rect.adjusted(-i, -i + 30, i, i + 30), radius + i, radius + i)


def window(p, img: QImage, rect: QRectF, dark: bool, title="Pathfinder"):
    r = 22
    shadow(p, rect, r)
    clip = QPainterPath(); clip.addRoundedRect(rect, r, r)
    p.save(); p.setClipPath(clip)
    bar = QRectF(rect.left(), rect.top(), rect.width(), BAR * rect.width() / 2480)
    p.fillRect(bar, QColor("#232A31" if dark else "#E9EDF1"))
    p.drawImage(QRectF(rect.left(), bar.bottom(), rect.width(), rect.height() - bar.height()), img)
    p.restore()
    p.setPen(QColor(255, 255, 255, 30) if dark else QColor(0, 0, 0, 40))
    p.setBrush(Qt.NoBrush); p.drawRoundedRect(rect, r, r)
    s = bar.height() / 64
    for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        p.setPen(Qt.NoPen); p.setBrush(QColor(c))
        p.drawEllipse(QPointF(bar.left() + (34 + i * 40) * s, bar.center().y()), 12 * s, 12 * s)
    f = QFont(); f.setPixelSize(int(26 * s)); f.setWeight(QFont.DemiBold); p.setFont(f)
    p.setPen(QColor("#C9D2DA" if dark else "#4A5560"))
    p.drawText(bar, Qt.AlignCenter, title)


def text(p, s, y, size, weight, alpha=255):
    f = QFont(); f.setPixelSize(size); f.setWeight(weight); f.setLetterSpacing(QFont.PercentageSpacing, 99)
    p.setFont(f); p.setPen(QColor(255, 255, 255, alpha))
    p.drawText(QRectF(0, y, W, size * 1.5), Qt.AlignHCenter | Qt.AlignTop, s)


def shot(name, head, sub, dark=False, title="Pathfinder"):
    img = QImage(str(SRC / name))
    out = QImage(W, H, QImage.Format_ARGB32); out.fill(0)
    p = QPainter(out); p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    background(p, dark)
    text(p, head, 150, 104, QFont.Bold)
    text(p, sub, 300, 46, QFont.Normal, 210)
    k = min(2430 / img.width(), 1540 / img.height())
    ww = img.width() * k; wh = img.height() * k + BAR * ww / 2480
    window(p, img, QRectF((W - ww) / 2, 470, ww, wh), dark, title)
    credit(p)
    p.end()
    return out


def hero():
    out = QImage(W, H, QImage.Format_ARGB32); out.fill(0)
    p = QPainter(out); p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    background(p, False)
    text(p, f"Pathfinder {__version__}", 140, 128, QFont.Bold)
    text(p, "Water maze search strategies, now with a one-line install", 320, 50, QFont.Normal, 215)
    sc = 0.72; ww = 2480 * sc; wh = (1640 + BAR) * sc
    window(p, QImage(str(SRC / "dark-6-heatmap.png")), QRectF(W - ww - 150, 840, ww, wh), True)
    window(p, QImage(str(SRC / "light-3-maze.png")), QRectF(150, 540, ww, wh), False)
    credit(p)
    p.end()
    return out


hero().save(str(OUT / "01-hero.png"))
items = [
    ("light-2-data.png", "Drop in a folder. Done.", "EthoVision, ANY-maze, WaterMaze and ezTrack are recognized automatically", False),
    ("light-3-maze.png", "Finds your pool and platform", "Detected from 180 real swims, within 3 cm of the true platform", False),
    ("light-4-summary.png", "Every trial, classified", "Identical to the original Pathfinder on real mouse data", False),
    ("light-5-trials.png", "Check each swim path", "Sortable trial table with the path of every trial", False),
    ("dark-6-heatmap.png", "See where they searched", "The hotspot is the hidden platform. Filter by trial or animal", True),
    ("light-7-review.png", "Review with your keyboard", "Press 1–9 to confirm or correct a strategy", False, "Review Trials"),
    ("dark-3-maze.png", "Dark mode included", "Follows your Mac's appearance automatically", True),
]
for i, (n, h, s, d, *t) in enumerate(items, start=2):
    shot(n, h, s, d, *t).save(str(OUT / f"{i:02d}-{n.split('-', 2)[2][:-4]}{'-dark' if d else ''}.png"))
print("ok")
