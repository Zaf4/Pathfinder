"""Render every screen to PNG (light and dark) for docs and visual review.

    uv run python tools/screenshots.py OUTDIR [DATA_FOLDER]

DATA_FOLDER defaults to the real-data test subset (tests/fixtures/real_overall2019/acquisition).
The README screenshots use the full acquisition phase of the same dataset (180 trials,
Overall & Kempermann 2019, https://doi.org/10.6084/m9.figshare.10248158.v3, CC BY 4.0).
"""
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs/screenshots")
FIX = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "tests/fixtures/real_overall2019/acquisition"
OUT.mkdir(parents=True, exist_ok=True)

QStandardPaths.setTestModeEnabled(True)
app = QApplication(sys.argv)
from pathfinder.gui import app as appmod, state, theme  # noqa: E402

tmp = Path(tempfile.mkdtemp())
state.results_root = lambda: tmp / state.RESULTS_FOLDER
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
    state.results_root = lambda m=mode: tmp / m / state.RESULTS_FOLDER  # no "(2)" suffix on the 2nd run
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
    mp.detect()  # exactly what a user clicks
    pump()
    w.grab().save(str(OUT / f"{mode}-3-maze.png"))
    mp.run_btn.click()
    wait(lambda: w.pages.currentIndex() == 2)
    pump(600)
    rp = w.results_page
    w.grab().save(str(OUT / f"{mode}-4-summary.png"))
    rp.tabs.setCurrentIndex(1)
    # show a clean direct swim beside the table
    m = rp.table.model()
    hit = next((r for r in range(m.rowCount()) if m.index(r, 2).data() == "Direct Path"), 3)
    rp.table.selectRow(hit)
    rp.table.scrollTo(m.index(hit, 0))
    pump()
    w.grab().save(str(OUT / f"{mode}-5-trials.png"))
    rp.tabs.setCurrentIndex(2)
    pump(600)
    w.grab().save(str(OUT / f"{mode}-6-heatmap.png"))
    from pathfinder.gui.dialogs import ReviewDialog, SettingsDialog
    res = rp.sets[0][2]
    pick = [next((r for r in res if r.strategy == k), None) for k in ("Directed Search", "Indirect Search", "Scanning")]
    pick = [r for r in pick if r is not None]
    d = ReviewDialog((pick or res)[:3], rp.sets[0][1], w.state.setup, w)
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
