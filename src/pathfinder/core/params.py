"""Analysis settings: the maze geometry and the strategy thresholds."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional


@dataclass
class Goal:
    x: float
    y: float
    diameter: float = 10.0
    name: str = "Goal"


@dataclass
class MazeSetup:
    """Geometry of the pool. `None` means "detect automatically from the data"."""
    goal_x: Optional[float] = 0.0
    goal_y: Optional[float] = 0.0
    goal_diameter: Optional[float] = 10.0
    maze_diameter: Optional[float] = 150.0
    centre_x: Optional[float] = 0.0
    centre_y: Optional[float] = 0.0
    corridor_width: float = 40.0   # degrees
    chaining_width: float = 25.0   # annulus width, data units
    thigmotaxis_zone: float = 15.0  # data units
    truncate_at_goal: bool = False
    extra_goals: list[Goal] = field(default_factory=list)

    @property
    def goal_auto(self) -> bool:
        return self.goal_x is None or self.goal_y is None

    @property
    def centre_auto(self) -> bool:
        return self.centre_x is None or self.centre_y is None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MazeSetup":
        d = dict(d)
        d["extra_goals"] = [Goal(**g) for g in d.get("extra_goals", [])]
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


STRATEGIES = [
    # key, display name, score, colour
    ("direct", "Direct Path", 3, "#2E7D32"),
    ("focal", "Focal Search", 2, "#43A047"),
    ("directed", "Directed Search", 2, "#7CB342"),
    ("indirect", "Indirect Search", 2, "#C0CA33"),
    ("semifocal", "Semi-focal Search", 2, "#FDD835"),
    ("chaining", "Chaining", 1, "#FB8C00"),
    ("scanning", "Scanning", 1, "#F4511E"),
    ("thigmotaxis", "Thigmotaxis", 0, "#8E24AA"),
    ("random", "Random Search", 0, "#5E35B1"),
    ("none", "Not Recognized", None, "#9E9E9E"),
]
STRATEGY_NAMES = [s[1] for s in STRATEGIES]
STRATEGY_COLOURS = {s[1]: s[3] for s in STRATEGIES}


@dataclass
class StrategyParams:
    """Thresholds for classifying a trial. Defaults are those of the published method."""
    ipeMaxVal: float = 125
    headingMaxVal: float = 40
    distanceToSwimMaxVal: float = 30
    distanceToPlatMaxVal: float = 30
    distanceToSwimMaxVal2: float = 50
    distanceToPlatMaxVal2: float = 50
    corridorAverageMinVal: float = 70
    directedSearchMaxDistance: float = 400
    focalMinDistance: float = 100
    focalMaxDistance: float = 400
    semiFocalMinDistance: float = 0
    semiFocalMaxDistance: float = 500
    corridoripeMaxVal: float = 1500
    annulusCounterMaxVal: float = 90
    quadrantTotalMaxVal: float = 4
    chainingMaxCoverage: float = 40
    percentTraversedMaxVal: float = 20
    percentTraversedMinVal: float = 5
    distanceToCentreMaxVal: float = 60
    thigmoMinDistance: float = 400
    fullThigmoMinVal: float = 65
    smallThigmoMinVal: float = 35
    ipeIndirectMaxVal: float = 300
    percentTraversedRandomMaxVal: float = 10
    headingIndirectMaxVal: float = 70
    useDirect: bool = True
    useFocal: bool = True
    useDirected: bool = True
    useIndirect: bool = True
    useSemiFocal: bool = False
    useChaining: bool = True
    useScanning: bool = True
    useRandom: bool = True
    useThigmotaxis: bool = True

    def is_default(self) -> bool:
        return self == StrategyParams()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "StrategyParams":
        try:
            data = json.loads(Path(path).read_text())
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known})
        except Exception:  # noqa: BLE001 - missing/corrupt settings fall back to defaults
            return cls()


# Layout of the Settings window: strategy -> (enable flag, [(field, label, unit), ...])
PARAM_GROUPS = [
    ("Direct Path", "useDirect", [
        ("ipeMaxVal", "Ideal path error", "max"),
        ("headingMaxVal", "Average heading error", "max, degrees"),
    ]),
    ("Focal Search", "useFocal", [
        ("distanceToSwimMaxVal", "Distance to swim-path centroid", "max, % of radius"),
        ("distanceToPlatMaxVal", "Distance to goal", "max, % of radius"),
        ("focalMinDistance", "Distance covered", "min"),
        ("focalMaxDistance", "Distance covered", "max"),
    ]),
    ("Directed Search", "useDirected", [
        ("corridorAverageMinVal", "Time in angular corridor", "min, % of trial"),
        ("directedSearchMaxDistance", "Distance covered", "max"),
        ("corridoripeMaxVal", "Ideal path error", "max"),
    ]),
    ("Indirect Search", "useIndirect", [
        ("ipeIndirectMaxVal", "Ideal path error", "max"),
        ("headingIndirectMaxVal", "Average heading error", "max, degrees"),
    ]),
    ("Semi-focal Search", "useSemiFocal", [
        ("distanceToSwimMaxVal2", "Distance to swim-path centroid", "max, % of radius"),
        ("distanceToPlatMaxVal2", "Distance to goal", "max, % of radius"),
        ("semiFocalMinDistance", "Distance covered", "min"),
        ("semiFocalMaxDistance", "Distance covered", "max"),
    ]),
    ("Chaining", "useChaining", [
        ("annulusCounterMaxVal", "Time in annulus zone", "min, % of trial"),
        ("quadrantTotalMaxVal", "Quadrants visited", "min"),
        ("chainingMaxCoverage", "Area of maze traversed", "max, % of maze"),
    ]),
    ("Scanning", "useScanning", [
        ("percentTraversedMinVal", "Area of maze traversed", "min, % of maze"),
        ("percentTraversedMaxVal", "Area of maze traversed", "max, % of maze"),
        ("distanceToCentreMaxVal", "Average distance to centre", "max, % of radius"),
    ]),
    ("Thigmotaxis", "useThigmotaxis", [
        ("fullThigmoMinVal", "Time in full wall zone", "min, % of trial"),
        ("smallThigmoMinVal", "Time in outer wall zone", "min, % of trial"),
        ("thigmoMinDistance", "Distance covered", "min"),
    ]),
    ("Random Search", "useRandom", [
        ("percentTraversedRandomMaxVal", "Area of maze traversed", "min, % of maze"),
    ]),
]
