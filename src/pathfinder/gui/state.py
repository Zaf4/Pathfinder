"""Shared application state and where things are saved."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QStandardPaths, Signal

from ..core.analysis import Geometry, TrialResult
from ..core.models import Experiment
from ..core.params import MazeSetup, StrategyParams
from ..core.readers import CustomColumns


def config_dir() -> Path:
    p = Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation))
    p.mkdir(parents=True, exist_ok=True)
    return p


def documents_dir() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)) / "Pathfinder"


def safe_name(s: str) -> str:
    return re.sub(r"[^\w\- .]+", "_", s).strip() or "Results"


class AppState(QObject):
    experimentChanged = Signal()
    setupChanged = Signal()
    paramsChanged = Signal()
    resultsChanged = Signal()

    def __init__(self):
        super().__init__()
        self.path: Optional[str] = None
        self.software: Optional[str] = None
        self.custom: Optional[CustomColumns] = None
        self.experiment: Optional[Experiment] = None
        self.single_file = False
        self.setup = self._load_setup()
        self.params = StrategyParams.load(self.params_file)
        self.review_mode = "none"  # none | unrecognized | all
        self.geometry: Optional[Geometry] = None
        self.results: list[TrialResult] = []
        self.extra_results: list[tuple[str, Geometry, list[TrialResult]]] = []
        self.output_dir: Optional[Path] = None

    # ---------------------------------------------------------- persistence
    @property
    def params_file(self) -> Path:
        return config_dir() / "strategy_thresholds.json"

    @property
    def setup_file(self) -> Path:
        return config_dir() / "maze_setup.json"

    def _load_setup(self) -> MazeSetup:
        try:
            return MazeSetup.from_dict(json.loads(self.setup_file.read_text()))
        except Exception:  # noqa: BLE001
            return MazeSetup()

    def save_setup(self):
        try:
            self.setup_file.write_text(json.dumps(self.setup.to_dict(), indent=2))
        except OSError:
            pass

    def set_params(self, params: StrategyParams):
        self.params = params
        params.save(self.params_file)
        self.paramsChanged.emit()

    # ---------------------------------------------------------- results folder
    def new_output_dir(self) -> Path:
        base = documents_dir()
        name = Path(self.path).stem if self.path else "Results"
        stamp = datetime.now().strftime("%Y-%m-%d %H.%M")
        d = base / f"{safe_name(name)} – {stamp}"
        n = 2
        while d.exists():
            d = base / f"{safe_name(name)} – {stamp} ({n})"
            n += 1
        d.mkdir(parents=True, exist_ok=True)
        self.output_dir = d
        return d
