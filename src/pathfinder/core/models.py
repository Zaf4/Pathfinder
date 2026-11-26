"""Plain data structures for tracking data."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, Optional


@dataclass
class Datapoint:
    time: float
    x: float
    y: float


@dataclass
class Trial:
    points: list[Datapoint] = field(default_factory=list)
    name: Optional[str] = None
    animal: Optional[str] = None
    date: Optional[datetime] = None
    trial: Optional[str] = None
    source: Optional[str] = None  # file the trial came from
    corrupted: bool = False

    def append(self, p: Datapoint) -> None:
        self.points.append(p)

    def __iter__(self) -> Iterator[Datapoint]:
        return iter(self.points)

    def __len__(self) -> int:
        return len(self.points)

    @property
    def label(self) -> str:
        if self.animal is not None:
            return str(self.animal)
        return str(self.name)

    @property
    def start(self) -> Optional[tuple[float, float]]:
        if not self.points:
            return None
        return self.points[0].x, self.points[0].y


@dataclass
class Experiment:
    name: str
    trials: list[Trial] = field(default_factory=list)
    has_animal_names: bool = False
    has_date_info: bool = False
    has_trial_names: bool = False
    software: str = ""

    def __iter__(self) -> Iterator[Trial]:
        return iter(self.trials)

    def __len__(self) -> int:
        return len(self.trials)

    @property
    def animals(self) -> list[str]:
        seen = []
        for t in self.trials:
            if t.animal is not None and t.animal not in seen:
                seen.append(t.animal)
        return seen
