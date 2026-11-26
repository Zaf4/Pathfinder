"""Main window, menus and application entry point."""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QProcess, Qt, QThreadPool, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout,
                               QMainWindow, QMessageBox, QProgressDialog, QStackedWidget, QVBoxLayout, QWidget)

from .. import __version__
from ..core.analysis import AnalysisError, Cancelled, analyze, resolve_geometry, write_csv
from ..core.models import Experiment
from . import theme
from .data_page import DataPage
from .dialogs import SettingsDialog, show_error
from .maze_page import MazePage
from .results_page import ResultsPage, reveal
from .state import AppState, results_root, safe_name
from .widgets import StepButton, Worker, collect_garbage_on_gui_thread, label

ASSETS = Path(__file__).parent / "assets"
REPO = "https://github.com/Zaf4/Pathfinder"
# Updates follow published releases (tags), never the development branch.
LATEST_RELEASE_API = "https://api.github.com/repos/Zaf4/Pathfinder/releases/latest"


def release_source(tag: str) -> str:
    # A plain zip download: installing from git would need git, which a stock Mac doesn't have
    # (calling it pops the "install command line developer tools" dialog).
    return f"jsl-pathfinder @ {REPO}/archive/{tag}.zip"


def windows_installer(tag: str) -> str:
    return f"https://raw.githubusercontent.com/Zaf4/Pathfinder/{tag}/install.ps1"


def version_key(v: str) -> tuple:
    """'2.1.0' -> (2, 1, 0); a leading 'v' and any suffix such as 'rc1' are ignored."""
    import re
    m = re.match(r"\d+(?:\.\d+)*", v.strip().lstrip("vV"))
    return tuple(int(x) for x in m.group().split(".")) if m else ()


def is_newer(tag: str, current: str = __version__) -> bool:
    return bool(version_key(tag)) and version_key(tag) > version_key(current)
WIKI = "https://github.com/MatthewBCooke/Pathfinder/wiki"
CITATION = ("Cooke MB, O'Leary TP, Harris P, et al. (2019) Pathfinder: open source software for analyzing "
            "spatial navigation search strategies. F1000Research 8:1521. "
            "https://doi.org/10.12688/f1000research.20352.2")


def run_analysis(exp, setup, params, single_file, review_mode, progress=None, cancelled=None):
    """Main goal plus any extra goals. Returns [(name, geometry, results)]."""
    geom = resolve_geometry(exp, setup, single_file=single_file)
    goals = [("Goal 1", None)] + [(f"Goal {i + 2}", (g.x, g.y, g.diameter))
                                  for i, g in enumerate(setup.extra_goals)]
    sets = []
    total = len(exp.trials) * len(goals)
    for k, (name, goal) in enumerate(goals):
        g = geom if goal is None else resolve_geometry(exp, setup, single_file=single_file, goal=goal)

        def prog(i, n, lab, k=k):
            if progress:
                progress(k * len(exp.trials) + i, total, lab)
        sets.append((name, g, analyze(exp, g, setup, params, progress=prog, cancelled=cancelled)))
    return sets


class NoScrollEdits(QObject):
    """Scrolling over a number box or drop-down must not silently change it (only when it has focus)."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Wheel and isinstance(obj, (QAbstractSpinBox, QComboBox)) and not obj.hasFocus():
            ev.ignore()
            return True
        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._gc_timer = collect_garbage_on_gui_thread(self)
        self._no_scroll = NoScrollEdits(self)
        QApplication.instance().installEventFilter(self._no_scroll)
        self.state = AppState()
        self.setWindowTitle("Pathfinder")
        self.resize(1240, 820)
        self.setMinimumSize(980, 680)
        self.worker = None

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        # sidebar
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(240)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 22, 10, 16)
        sl.setSpacing(4)
        brand = QVBoxLayout()
        brand.setContentsMargins(12, 0, 12, 18)
        brand.setSpacing(2)
        brand.addWidget(label("Pathfinder", "AppTitle"))
        brand.addWidget(label("Water maze search strategies", "AppSubtitle"))
        sl.addLayout(brand)
        self.steps = [StepButton(1, "Data", "Choose tracking files"),
                      StepButton(2, "Maze", "Pool, goal and zones"),
                      StepButton(3, "Results", "Strategies and heatmaps")]
        self.step_group = QButtonGroup(self)
        for i, b in enumerate(self.steps):
            self.step_group.addButton(b, i)
            sl.addWidget(b)
        self.step_group.idClicked.connect(self.go)
        sl.addStretch(1)
        self.version = label(f"Version {__version__}", "Hint")
        self.version.setContentsMargins(12, 0, 0, 0)
        sl.addWidget(self.version)
        root.addWidget(side)

        # pages
        self.pages = QStackedWidget()
        self.data_page = DataPage(self.state)
        self.maze_page = MazePage(self.state)
        self.results_page = ResultsPage(self.state)
        for p in (self.data_page, self.maze_page, self.results_page):
            self.pages.addWidget(p)
        root.addWidget(self.pages, 1)

        self.data_page.proceed.connect(lambda: self.go(1))
        self.maze_page.back.connect(lambda: self.go(0))
        self.maze_page.run.connect(self.run)
        self.results_page.new_analysis.connect(lambda: self.go(0))
        self.state.experimentChanged.connect(self._update_steps)

        self.statusBar().showMessage("Ready")
        self._menus()
        self.go(0)

    # ---------------------------------------------------------- navigation
    def _update_steps(self):
        has_data = self.state.experiment is not None
        has_results = bool(self.results_page.sets) and has_data
        self.steps[1].setEnabled(has_data)
        self.steps[2].setEnabled(has_results)
        self.steps[0].done = has_data
        self.steps[1].done = has_results
        self.act_maze.setEnabled(has_data)
        self.act_results.setEnabled(has_results)
        for b in self.steps:
            b.update()

    def go(self, i):
        if i == 1 and not self.state.experiment:
            i = 0
        if i == 2 and not self.results_page.sets:
            i = 1 if self.state.experiment else 0
        self.pages.setCurrentIndex(i)
        self.steps[i].setChecked(True)
        self._update_steps()

    # ---------------------------------------------------------- menus
    def _menus(self):
        mb = self.menuBar()

        def act(menu, text, slot, shortcut=None, role=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if role is not None:
                a.setMenuRole(role)
            a.triggered.connect(slot)
            menu.addAction(a)
            return a

        f = mb.addMenu("&File")
        act(f, "Open Folder…", self.data_page.choose_folder, QKeySequence.Open)
        act(f, "Open File…", self.data_page.choose_file, "Ctrl+Shift+O")
        f.addSeparator()
        act(f, "Show Results Folder", self.show_results_folder, "Ctrl+Shift+R")
        f.addSeparator()
        act(f, "Close Window", self.close, QKeySequence.Close)
        act(f, "Quit Pathfinder", QApplication.quit, QKeySequence.Quit, QAction.QuitRole)

        e = mb.addMenu("&Edit")
        for text, seq, slot in (("Cut", QKeySequence.Cut, "cut"), ("Copy", QKeySequence.Copy, "copy"),
                                ("Paste", QKeySequence.Paste, "paste"), ("Select All", QKeySequence.SelectAll,
                                                                       "selectAll")):
            act(e, text, lambda _=False, s=slot: self._edit(s), seq)
        e.addSeparator()
        act(e, "Strategy Thresholds…", self.edit_thresholds, QKeySequence.Preferences, QAction.PreferencesRole)

        v = mb.addMenu("&View")
        act(v, "Data", lambda: self.go(0), "Ctrl+1")
        self.act_maze = act(v, "Maze Setup", lambda: self.go(1), "Ctrl+2")
        self.act_results = act(v, "Results", lambda: self.go(2), "Ctrl+3")

        w = mb.addMenu("&Window")
        act(w, "Minimize", self.showMinimized, "Ctrl+M")
        act(w, "Zoom", lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
        act(w, "Enter Full Screen", lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen(),
            "Ctrl+Meta+F" if sys.platform == "darwin" else "F11")

        h = mb.addMenu("&Help")
        act(h, "Pathfinder Guide", lambda: QDesktopServices.openUrl(QUrl(WIKI)))
        act(h, "How to Cite Pathfinder", self.cite)
        act(h, "Report a Problem…", lambda: QDesktopServices.openUrl(QUrl(REPO + "/issues")))
        h.addSeparator()
        act(h, "Check for Updates…", self.check_updates, role=QAction.ApplicationSpecificRole)
        act(h, "About Pathfinder", self.about, role=QAction.AboutRole)

    def _edit(self, slot):
        w = QApplication.focusWidget()
        if w is not None and hasattr(w, slot):
            getattr(w, slot)()
        elif w is not None and hasattr(w, "lineEdit") and w.lineEdit() is not None:
            getattr(w.lineEdit(), slot)()

    # ---------------------------------------------------------- actions
    def edit_thresholds(self):
        dlg = SettingsDialog(self.state.params, self)
        if dlg.exec():
            self.state.set_params(dlg.params)

    def show_results_folder(self):
        d = self.state.output_dir or results_root()
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def cite(self):
        box = QMessageBox(self)
        box.setWindowTitle("How to cite")
        box.setText("If you use Pathfinder in your work, please cite:")
        box.setInformativeText(CITATION)
        copy = box.addButton("Copy Citation", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is copy:
            QApplication.clipboard().setText(CITATION)

    def about(self):
        QMessageBox.about(self, "About Pathfinder",
                          f"<h3>Pathfinder {__version__}</h3>"
                          "<p>Search strategy and heatmap analysis for the Morris Water Maze.</p>"
                          "<p>Original software by Matthew Cooke, Tim O'Leary and Phelan Harris, "
                          "Jason Snyder Lab, University of British Columbia. This modernized version keeps the "
                          "published analysis unchanged.</p>"
                          f"<p>{CITATION}</p>"
                          "<p>Free software under the GNU GPL v3.</p>")

    # ---------------------------------------------------------- updates
    def check_updates(self):
        """Ask GitHub for the latest release; install it only if it is newer than this version."""
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        self.update_box = QProgressDialog("Checking for updates…", None, 0, 0, self)
        self.update_box.setWindowTitle("Pathfinder")
        self.update_box.setMinimumDuration(0)
        self.update_box.show()
        # Qt's network stack uses the system certificates (Python's urllib may not on a Mac)
        self.net = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(LATEST_RELEASE_API))
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        req.setTransferTimeout(15000)
        self.update_reply = self.net.get(req)
        self.update_reply.finished.connect(self._got_release)

    def _got_release(self):
        from PySide6.QtNetwork import QNetworkReply
        reply = self.update_reply
        reply.deleteLater()
        tag = ""
        if reply.error() == QNetworkReply.NoError:
            try:
                tag = str(json.loads(bytes(reply.readAll()).decode()).get("tag_name") or "")
            except ValueError:
                tag = ""
        if not tag:
            self.update_box.close()
            show_error(self, "Couldn't check for updates", "Check your internet connection and try again.",
                       reply.errorString())
            return
        if not is_newer(tag):
            self.update_box.close()
            QMessageBox.information(self, "Pathfinder", f"You have the latest version ({__version__}).")
            return
        if sys.platform == "win32":
            self.update_box.close()
            return self._update_windows(tag)
        uv = shutil.which("uv") or str(Path.home() / ".local/bin/uv")
        if not os.path.exists(uv):
            self.update_box.close()
            QDesktopServices.openUrl(QUrl(f"{REPO}/releases/latest"))
            return
        self.update_box.setLabelText(f"Installing Pathfinder {tag}…")
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.finished.connect(lambda code, _status: self._updated(code, tag))
        self.proc.start(uv, ["tool", "install", "--force", "--refresh-package", "jsl-pathfinder",
                             "--managed-python", "--python", "3.13", release_source(tag)])

    def _updated(self, code, tag):
        self.update_box.close()
        out = bytes(self.proc.readAll()).decode(errors="replace")
        if code != 0:
            show_error(self, "Couldn't install the update", "Check your internet connection and try again.", out)
        else:
            QMessageBox.information(self, "Pathfinder updated",
                                    f"Version {tag} was installed. Quit and reopen Pathfinder to use it.")

    def _update_windows(self, tag):
        """Windows locks the files of a running program, so update after we quit, then reopen."""
        ok = QMessageBox.question(self, "Update Pathfinder",
                                  f"Pathfinder {tag} is available. Pathfinder will close, download it and "
                                  "reopen by itself.\n\nThis takes about a minute.",
                                  QMessageBox.Ok | QMessageBox.Cancel)
        if ok != QMessageBox.Ok:
            return
        cmd = (f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue; "
               f"$env:PATHFINDER_REF = '{tag}'; irm {windows_installer(tag)} | iex")
        QProcess.startDetached("powershell", ["-NoProfile", "-ExecutionPolicy", "ByPass",
                                              "-WindowStyle", "Minimized", "-Command", cmd])
        QApplication.quit()

    # ---------------------------------------------------------- run
    def run(self):
        st = self.state
        exp0 = st.experiment
        if not exp0:
            return
        exp = Experiment(exp0.name, [t for t in exp0.trials if len(t)], exp0.has_animal_names,
                         exp0.has_date_info, exp0.has_trial_names, exp0.software)
        st.experiment = exp
        self.progress = QProgressDialog("Analyzing swims…", "Cancel", 0, len(exp.trials), self)
        self.progress.setWindowTitle("Pathfinder")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setMinimumDuration(300)
        self.progress.setAutoClose(False)
        self.progress.setAutoReset(False)
        self.worker = Worker(run_analysis, exp, st.setup, st.params, st.single_file, st.review_mode,
                             controls=True)
        self.worker.signals.progress.connect(self._progress)
        self.worker.signals.done.connect(self._finished)
        self.worker.signals.failed.connect(self._failed)
        self.progress.canceled.connect(self.worker.cancel)
        self.statusBar().showMessage("Analyzing…")
        QThreadPool.globalInstance().start(self.worker)

    def _progress(self, i, n, lab):
        self.progress.setMaximum(n)
        self.progress.setValue(i)
        if lab:
            self.progress.setLabelText(f"Analyzing swims…  {lab}")

    def _failed(self, msg, details):
        self.progress.close()
        self.statusBar().showMessage("Ready")
        if "Cancelled" in details:
            return
        show_error(self, "The analysis stopped", msg, details)

    def _finished(self, sets):
        self.progress.close()
        st = self.state
        main = sets[0][2]
        if st.review_mode != "none":
            from .dialogs import ReviewDialog
            todo = main if st.review_mode == "all" else [r for r in main if r.strategy == "Not Recognized"]
            if todo:
                ReviewDialog(todo, sets[0][1], st.setup, self).exec()
        out = st.new_output_dir()
        saved = []
        for name, geom, results in sets:
            if name == "Goal 1":
                fn = out / "strategies.csv"
            else:
                fn = out / safe_name(f"strategies - {name} ({geom.goal_x:g}, {geom.goal_y:g}).csv")
            write_csv(fn, st.experiment, results)
            saved.append((name, geom, results, fn))
        (out / "settings used.json").write_text(json.dumps({
            "pathfinder_version": __version__, "data": st.path, "software": st.software,
            "maze": st.setup.to_dict(), "thresholds": asdict(st.params)}, indent=2))
        st.results = main
        self.results_page.show_results(saved)
        self.statusBar().showMessage(f"Results saved in {out.name}")
        self.go(2)


def _app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 32, 64, 128, 256, 512):
        p = ASSETS / f"icon_{size}.png"
        if p.exists():
            icon.addFile(str(p))
    return icon


def apply_theme(app: QApplication):
    t = theme.current()
    app.setPalette(theme.palette(t))
    app.setStyleSheet(theme.stylesheet(t))


def _macos_app_name(name: str):
    """Show "Pathfinder" (not "python") in the macOS menu bar, via the Objective-C runtime."""
    if sys.platform != "darwin":
        return
    try:
        import ctypes
        import ctypes.util
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        send = objc.objc_msgSend
        send.restype = ctypes.c_void_p
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cls, sel = objc.objc_getClass, objc.sel_registerName
        bundle = send(cls(b"NSBundle"), sel(b"mainBundle"))
        info = send(bundle, sel(b"localizedInfoDictionary")) or send(bundle, sel(b"infoDictionary"))
        if not info:
            return
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        ns_name = send(cls(b"NSString"), sel(b"stringWithUTF8String:"), name.encode())
        key = send(cls(b"NSString"), sel(b"stringWithUTF8String:"), b"CFBundleName")
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        send(info, sel(b"setObject:forKey:"), ns_name, key)
    except Exception:  # noqa: BLE001 - cosmetic only
        pass


def main():
    os.environ.setdefault("QT_API", "pyside6")
    _macos_app_name("Pathfinder")
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Zaf4.Pathfinder")
        except Exception:  # noqa: BLE001 - cosmetic only
            pass
    QApplication.setApplicationName("Pathfinder")
    QApplication.setApplicationDisplayName("Pathfinder")
    QApplication.setOrganizationName("Pathfinder")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(_app_icon())
    apply_theme(app)
    try:
        app.styleHints().colorSchemeChanged.connect(lambda *_: (apply_theme(app), w.update()))
    except AttributeError:
        pass
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        w.data_page.open_path(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
