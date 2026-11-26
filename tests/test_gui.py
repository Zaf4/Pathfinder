"""End-to-end checks of the window: load data, set up the maze, run, review, heatmap, menus."""
import csv
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QStandardPaths, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    QStandardPaths.setTestModeEnabled(True)
    cfg = tmp_path / "config"
    cfg.mkdir()
    monkeypatch.setattr("pathfinder.gui.state.config_dir", lambda: cfg)
    monkeypatch.setattr("pathfinder.gui.state.documents_dir", lambda: tmp_path / "Pathfinder")
    monkeypatch.setattr("pathfinder.gui.app.documents_dir", lambda: tmp_path / "Pathfinder")
    # never open Finder/Excel/browser during tests
    monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl", lambda *a: True)
    monkeypatch.setattr("pathfinder.gui.results_page.reveal", lambda *a: None)
    shown = []

    def fake_exec(box):
        shown.append((box.text(), box.informativeText(), box.detailedText()))
        print("MESSAGE BOX:", shown[-1])
        return 0
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    yield shown


@pytest.fixture
def win(qtbot):
    from pathfinder.gui.app import MainWindow, apply_theme
    apply_theme(QApplication.instance())
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    return w


def load(qtbot, win, path):
    win.data_page.open_path(str(path))
    qtbot.waitUntil(lambda: win.state.experiment is not None and win.data_page.stack.currentIndex() == 1,
                    timeout=20000)


def run(qtbot, win):
    win.go(1)
    win.maze_page.run_btn.click()
    qtbot.waitUntil(lambda: win.pages.currentIndex() == 2, timeout=15000)


@pytest.mark.parametrize("fmt,expected", [("ethovision", "ethovision"), ("anymaze", "anymaze"),
                                          ("eztrack", "eztrack"), ("watermaze", "watermaze")])
def test_full_flow_each_format(qtbot, win, fmt, expected):
    load(qtbot, win, FIX / fmt)
    assert win.state.software == expected
    assert win.data_page.t_trials.value.text() == "14"
    assert win.steps[1].isEnabled() and not win.steps[2].isEnabled()

    win.go(1)
    mp = win.maze_page
    mp.maze_d.setValue(150)
    mp.cx.setValue(0)
    mp.cy.setValue(0)
    mp.gx.setValue(30)
    mp.gy.setValue(30)
    assert not mp.warn.isVisible()
    assert mp.run_btn.text().startswith("Analyze 14 Trials")
    run(qtbot, win)

    rp = win.results_page
    out = win.state.output_dir
    csv_path = out / "strategies.csv"
    assert csv_path.exists() and (out / "settings used.json").exists()
    rows = list(csv.DictReader(open(csv_path)))
    assert len(rows) == 14
    assert {r["Strategy"] for r in rows} == {"Direct Path", "Directed Search", "Focal Search", "Chaining",
                                            "Thigmotaxis", "Scanning", "Random Search"}
    if fmt == "watermaze":  # fixed: date columns are filled, not shifted
        assert rows[0]["Date"] == "2024-03-01" and rows[0]["Day"] == "1"
    assert rp.model.rowCount() == 14
    rp.table.selectRow(0)
    assert "trial" in rp.path_title.text()
    assert rp.h_canvas is not None
    assert win.steps[2].isEnabled()


def test_detect_and_goal_drag(qtbot, win):
    load(qtbot, win, FIX / "anymaze")
    win.go(1)
    mp = win.maze_page
    mp.maze_d.setValue(3)  # wrong units on purpose
    mp.gx.setValue(0)
    mp.gy.setValue(0)
    assert mp.warn.isVisibleTo(mp)
    mp.detect()
    assert 140 < mp.maze_d.value() < 150
    assert not mp.warn.isVisibleTo(mp)
    mp.view._move_goal(mp.view.to_screen(20, 25))
    assert abs(mp.gx.value() - 20) < 0.5 and abs(mp.gy.value() - 25) < 0.5


def test_single_file_cannot_detect(qtbot, win):
    f = sorted((FIX / "eztrack").glob("*.csv"))[0]
    load(qtbot, win, f)
    assert win.state.single_file
    win.go(1)
    assert not win.maze_page.detect_btn.isEnabled()
    assert "folder" in win.maze_page.detect_note.text()


def test_extra_goal_writes_second_file(qtbot, win):
    load(qtbot, win, FIX / "eztrack")
    win.go(1)
    win.maze_page.gx.setValue(30)
    win.maze_page.gy.setValue(30)
    win.maze_page.maze_d.setValue(150)
    win.maze_page.add_goal()
    assert len(win.state.setup.extra_goals) == 1
    run(qtbot, win)
    files = sorted(p.name for p in win.state.output_dir.glob("*.csv"))
    assert len(files) == 2 and "strategies.csv" in files
    assert win.results_page.goal_pick.count() == 2
    win.results_page.goal_pick.setCurrentIndex(1)
    win.maze_page._remove_goal(win.maze_page.extra_rows[0])
    assert win.state.setup.extra_goals == []


def test_review_unrecognized_and_edit(qtbot, win, monkeypatch):
    load(qtbot, win, FIX / "eztrack")
    win.go(1)
    mp = win.maze_page
    mp.maze_d.setValue(150)
    mp.gx.setValue(30)
    mp.gy.setValue(30)
    mp.review.setCurrentIndex(mp.review.findData("all"))

    def answer():
        dlg = QApplication.activeModalWidget()
        assert dlg is not None and dlg.windowTitle() == "Review Trials"
        dlg._choose(8)  # Random Search for the first trial
        for _ in range(14):
            dlg._go(1)
    QTimer.singleShot(500, answer)
    run(qtbot, win)
    rows = list(csv.DictReader(open(win.state.output_dir / "strategies.csv")))
    assert rows[0]["Strategy (manual)"] == "Random Search"
    assert rows[1]["Strategy (manual)"] == rows[1]["Strategy"]
    mp.review.setCurrentIndex(0)


def test_custom_columns(qtbot, win, tmp_path):
    src = sorted((FIX / "eztrack").glob("*.csv"))[0]
    d = tmp_path / "custom"
    d.mkdir()
    with open(src) as fi, open(d / "a.csv", "w", newline="") as fo:
        rows = list(csv.reader(fi))
        w = csv.writer(fo)
        w.writerow(["my time", "pos x", "pos y"])
        for r in rows[1:]:
            w.writerow([int(r[8]) / 10, r[9], r[10]])

    def pick():
        dlg = QApplication.activeModalWidget()
        assert dlg is not None and dlg.windowTitle() == "Choose Columns"
        assert not dlg.ok.isEnabled()
        dlg._picked(1, 1)
        dlg._picked(1, 2)
        dlg._picked(1, 0)
        assert dlg.ok.isEnabled()
        dlg._accept()
    QTimer.singleShot(400, pick)
    win.data_page.open_path(str(d))
    qtbot.waitUntil(lambda: win.state.experiment is not None, timeout=10000)
    assert win.state.software == "custom"
    assert len(win.state.experiment.trials[0]) > 10


def test_bad_format_shows_message(qtbot, win):
    load(qtbot, win, FIX / "eztrack")
    win.data_page.software.setCurrentIndex(win.data_page.software.findData("anymaze"))
    win.data_page._software_picked()
    qtbot.waitUntil(lambda: win.data_page.warning.isVisibleTo(win.data_page), timeout=10000)
    assert win.state.experiment is None
    assert not win.steps[1].isEnabled()


def test_settings_dialog_roundtrip(qtbot, win):
    from pathfinder.gui.dialogs import SettingsDialog
    dlg = SettingsDialog(win.state.params, win)
    dlg.inputs["ipeMaxVal"].setValue(200)
    dlg.toggles["useSemiFocal"].setChecked(True)
    dlg._save()
    win.state.set_params(dlg.params)
    assert win.state.params.ipeMaxVal == 200 and win.state.params.useSemiFocal
    assert "custom" in win.maze_page.thresholds.text()
    dlg2 = SettingsDialog(win.state.params, win)
    dlg2._load(type(win.state.params)())
    dlg2._save()
    win.state.set_params(dlg2.params)
    assert win.state.params.is_default()


def test_scrolling_does_not_change_numbers(qtbot, win):
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    load(qtbot, win, FIX / "eztrack")
    win.go(1)
    sb = win.maze_page.thigmo
    before = sb.value()
    ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                     Qt.NoScrollPhase, False)
    QApplication.sendEvent(sb, ev)
    assert sb.value() == before


def test_menus_have_working_actions(qtbot, win):
    titles = [a.text().replace("&", "") for a in win.menuBar().actions()]
    assert titles == ["File", "Edit", "View", "Window", "Help"]
    acts = {a.text(): a for m in win.menuBar().actions() for a in m.menu().actions() if a.text()}
    for name in ["Open Folder…", "Open File…", "Show Results Folder", "Close Window", "Quit Pathfinder", "Cut",
                 "Copy", "Paste", "Select All", "Strategy Thresholds…", "Data", "Maze Setup", "Results",
                 "Minimize", "Zoom", "Enter Full Screen", "Pathfinder Guide", "How to Cite Pathfinder",
                 "Report a Problem…", "Check for Updates…", "About Pathfinder"]:
        assert name in acts, name
    # View menu respects what's available
    assert not acts["Maze Setup"].isEnabled()
    acts["Maze Setup"].trigger()
    assert win.pages.currentIndex() == 0
    # Window menu: minimize really minimizes, zoom toggles
    acts["Zoom"].trigger()
    qtbot.waitUntil(win.isMaximized, timeout=3000)
    acts["Zoom"].trigger()
    qtbot.waitUntil(lambda: not win.isMaximized(), timeout=3000)
    acts["Show Results Folder"].trigger()
    # Edit menu routes to the focused field
    load(qtbot, win, FIX / "eztrack")
    win.go(1)
    le = win.maze_page.gx.lineEdit()
    win.maze_page.gx.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() in (le, win.maze_page.gx), timeout=3000)
    acts["Select All"].trigger()
    acts["Copy"].trigger()
    assert QApplication.clipboard().text() == le.text()
