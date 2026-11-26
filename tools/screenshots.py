"""Render every screen to PNG (light and dark) for docs and visual review.

    uv run python tools/screenshots.py OUTDIR
"""
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/ethovision"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

QStandardPaths.setTestModeEnabled(True)
app = QApplication(sys.argv)
from pathfinder.gui import app as appmod, state, theme  # noqa: E402

tmp = Path(tempfile.mkdtemp())
state.results_root = lambda: tmp / "Pathfinder"
state.config_dir = lambda: tmp


def pump(ms=300):
    t = QTimer()
    t.setSingleShot(True)
    t.start(ms)
    while t.isActive():
        app.processEvents()


def wait(cond, ms=20000):
    import time
    end = time.time() + ms / 1000
    while not cond() and time.time() < end:
        app.processEvents()


for mode in ("light", "dark"):
    theme.current = (lambda m=mode: theme.DARK if m == "dark" else theme.LIGHT)
    appmod.apply_theme(app)
    w = appmod.MainWindow()
    w.resize(1240, 820)
    w.show()
    pump()
    w.grab().save(str(OUT / f"{mode}-1-empty.png"))
    w.data_page.open_path(str(FIX))
    wait(lambda: w.state.experiment is not None and w.data_page.stack.currentIndex() == 1)
    pump()
    w.grab().save(str(OUT / f"{mode}-2-data.png"))
    w.go(1)
    mp = w.maze_page
    mp.detect()
    mp.maze_d.setValue(150)
    mp.cx.setValue(0)
    mp.cy.setValue(0)
    mp.gx.setValue(30)
    mp.gy.setValue(30)
    pump()
    w.grab().save(str(OUT / f"{mode}-3-maze.png"))
    mp.run_btn.click()
    wait(lambda: w.pages.currentIndex() == 2)
    pump(600)
    rp = w.results_page
    w.grab().save(str(OUT / f"{mode}-4-summary.png"))
    rp.tabs.setCurrentIndex(1)
    rp.table.selectRow(3)
    pump()
    w.grab().save(str(OUT / f"{mode}-5-trials.png"))
    rp.tabs.setCurrentIndex(2)
    pump(600)
    w.grab().save(str(OUT / f"{mode}-6-heatmap.png"))
    from pathfinder.gui.dialogs import ReviewDialog, SettingsDialog
    d = ReviewDialog(rp.sets[0][2][:3], rp.sets[0][1], w.state.setup, w)
    d.show()
    pump()
    d.grab().save(str(OUT / f"{mode}-7-review.png"))
    d.close()
    s = SettingsDialog(w.state.params, w)
    s.show()
    pump()
    s.grab().save(str(OUT / f"{mode}-8-settings.png"))
    s.close()
    w.close()
print("saved to", OUT)
