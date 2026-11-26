"""Readers for tracking-software exports.

The parsing rules are carried over unchanged from the original Pathfinder (appTrial.py),
so results stay identical. Fixes over the original are marked "FIX".
"""
from __future__ import annotations

import csv
import fnmatch
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

import pandas as pd

from .models import Datapoint, Experiment, Trial

SOFTWARE_LABELS = {
    "ethovision": "EthoVision",
    "anymaze": "ANY-maze",
    "watermaze": "WaterMaze",
    "eztrack": "ezTrack",
    "custom": "Custom columns",
}


class ReadError(Exception):
    """A file could not be read in the chosen format."""


@dataclass
class CustomColumns:
    """Where to find X, Y and time in a file with an unknown layout (0-based)."""
    x_col: int
    y_col: int
    t_col: int
    start_row: int


def _visible(name: str) -> bool:
    # FIX: skip macOS resource forks ("._x.csv") and Excel lock files ("~$x.xlsx")
    return not (name.startswith(".") or name.startswith("~$"))


def find_files(directory: str | os.PathLike, pattern: str) -> list[str]:
    out = []
    for root, _dirs, files in os.walk(directory):
        for basename in sorted(files):
            if fnmatch.fnmatch(basename, pattern) and _visible(basename):
                out.append(os.path.join(root, basename))
    return out


def files_for(software: str, path: str | os.PathLike, custom_ext: str = ".csv") -> list[str]:
    """List the data files a file-or-folder path refers to."""
    path = str(path)
    if os.path.isfile(path):
        return [path]
    if software == "ethovision":
        pattern = "*.xlsx"
    elif software == "custom":
        pattern = "*" + custom_ext  # FIX: original only looked for .csv
    else:
        pattern = "*.csv"
    return find_files(path, pattern)


def _sniff(filename: str):
    with open(filename, newline="") as f:
        return csv.Sniffer().sniff(f.readline())


def _hms_to_seconds(t: str) -> float:
    parts = t.split(":")
    if len(parts) == 3:
        return float(parts[2]) + float(parts[1]) * 60 + float(parts[0]) * 3600
    if len(parts) == 2:
        return float(parts[1]) + float(parts[0]) * 60
    return float(t)


def read_ethovision(filename: str) -> list[Trial]:
    try:
        sheet = pd.read_excel(filename, header=None)
    except Exception as e:  # noqa: BLE001
        raise ReadError(f"Could not open Excel file {Path(filename).name}: {e}") from e
    try:
        header_lines = int(sheet.iloc[0, 1])
    except Exception as e:  # noqa: BLE001
        raise ReadError(f"{Path(filename).name} does not look like an EthoVision export "
                        "(no 'Number of header lines' in the first row).") from e
    trial = Trial(source=filename)
    for row in range(1, header_lines):
        key = str(sheet.iloc[row, 0]).upper()
        if key == "TRIAL NAME":
            trial.name = sheet.iloc[row, 1]
        elif key == "ANIMAL ID":
            trial.animal = sheet.iloc[row, 1]
        elif key == "TRIAL":
            trial.trial = sheet.iloc[row, 1]
    for row in range(header_lines, len(sheet)):
        time, x, y = sheet.iloc[row, 1], sheet.iloc[row, 2], sheet.iloc[row, 3]
        if time == "NaN" or x == "NaN" or y == "NaN":
            trial.corrupted = True
            continue
        try:
            trial.append(Datapoint(float(time), float(x), float(y)))
        except ValueError:
            trial.corrupted = True
    return [trial]


def read_anymaze(filename: str) -> list[Trial]:
    dialect = _sniff(filename)
    columns = defaultdict(list)
    with open(filename) as f:
        reader = csv.reader(f, dialect)
        next(reader)
        for row in reader:
            for i, v in enumerate(row):
                columns[i].append(v)
    trial = Trial(name=filename.split("/")[-1], source=filename)
    # NOTE: like the original, the first row after the header is skipped.
    for time, x, y in zip(columns[0][1:], columns[1][1:], columns[2][1:]):
        try:
            trial.append(Datapoint(_hms_to_seconds_strict(time), float(x), float(y)))
        except Exception:  # noqa: BLE001
            trial.corrupted = True
    return [trial]


def _hms_to_seconds_strict(t: str) -> float:
    h, m, s = t.split(":")[0], t.split(":")[1], t.split(":")[2]
    return float(s) + float(m) * 60 + float(h) * 3600


def read_watermaze(filename: str) -> list[Trial]:
    dialect = _sniff(filename)
    columns = defaultdict(list)
    ncols = 0
    with open(filename) as f:
        for row in csv.reader(f, dialect):
            for i, v in enumerate(row):
                columns[i].append(v)
                ncols = i
    trials = []
    for i in range(0, int(round(ncols / 3))):
        c1, c2, c3 = columns[i * 3], columns[1 + i * 3], columns[2 + i * 3]
        trial = Trial(animal=c1[0], source=filename)
        try:
            trial.date = datetime.strptime(c2[0] + " " + c3[0], "%m/%d/%Y %H:%M %p")
        except Exception:  # noqa: BLE001
            trial.date = None
        for x, y, t in zip(c1[2:], c2[2:], c3[2:]):
            if t == "" and x == "" and y == "":
                break
            if t == "NaN" or x == "NaN" or y == "NaN":
                trial.corrupted = True
                continue
            try:
                trial.append(Datapoint(float(t), float(x), float(y)))
            except ValueError:
                trial.corrupted = True
        if len(trial) > 0:
            trials.append(trial)
    return trials


def read_eztrack(filename: str) -> list[Trial]:
    dialect = _sniff(filename)
    with open(filename) as f:
        rows = list(csv.reader(f, dialect))
    cols = {name: i for i, name in enumerate(rows[0])}
    try:
        fps_c, frame_c, x_c, y_c = cols["FPS"], cols["Frame"], cols["X"], cols["Y"]
    except KeyError as e:
        raise ReadError(f"{Path(filename).name} is missing the ezTrack column {e}.") from e
    trial = Trial(name=filename.split("/")[-1], source=filename)
    for row in rows[1:]:
        try:
            t = float(row[frame_c]) / float(row[fps_c])
            trial.append(Datapoint(t, float(row[x_c]), float(row[y_c])))
        except Exception:  # noqa: BLE001
            trial.corrupted = True
    return [trial]


def read_table(filename: str) -> pd.DataFrame:
    """Whole file as a header-less table (used by the custom reader and its preview)."""
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(filename, header=None)
    return pd.read_csv(filename, sep=";|,", header=None, engine="python")


def read_custom(filename: str, cols: CustomColumns) -> list[Trial]:
    table = read_table(filename)
    trial = Trial(name=filename.split("/")[-1], source=filename)
    for _, row in table.iloc[cols.start_row:].iterrows():
        try:
            x = float(row[cols.x_col])
            y = float(row[cols.y_col])
            t = row[cols.t_col]
            time = _hms_to_seconds(t) if isinstance(t, str) else float(t)
            if not math.isnan(x) and not math.isnan(y):
                trial.append(Datapoint(time, x, y))
        except Exception:  # noqa: BLE001
            trial.corrupted = True
    return [trial]


FLAGS = {  # has_animal_names, has_date_info, has_trial_names
    "ethovision": (True, False, True),
    "anymaze": (False, False, True),
    "watermaze": (True, True, False),
    "eztrack": (False, False, True),
    "custom": (False, False, False),
}


def load_experiment(software: str, path: str | os.PathLike,
                    custom: Optional[CustomColumns] = None,
                    progress: Optional[Callable[[int, int], None]] = None) -> Experiment:
    """Read a file, or every matching file in a folder, into an Experiment."""
    if software not in FLAGS:
        raise ReadError(f"Unknown tracking software '{software}'.")
    if software == "custom" and custom is None:
        raise ReadError("Choose the X, Y and time columns first.")
    ext = os.path.splitext(str(path))[1] or ".csv"
    if software == "custom" and os.path.isdir(path):
        ext = custom_ext_in(path)
    filenames = files_for(software, path, ext)
    if not filenames:
        raise ReadError("No data files were found in this folder.")
    exp = Experiment(name=str(path), software=software)
    exp.has_animal_names, exp.has_date_info, exp.has_trial_names = FLAGS[software]
    for n, fn in enumerate(filenames):
        if progress:
            progress(n, len(filenames))
        try:
            if software == "ethovision":
                trials = read_ethovision(fn)
            elif software == "anymaze":
                trials = read_anymaze(fn)
            elif software == "watermaze":
                trials = read_watermaze(fn)
            elif software == "eztrack":
                trials = read_eztrack(fn)
            else:
                trials = read_custom(fn, custom)
        except ReadError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ReadError(f"Could not read {Path(fn).name} as {SOFTWARE_LABELS[software]} data: {e}") from e
        exp.trials.extend(trials)
    if exp.has_date_info:
        exp.trials.sort(key=lambda t: (t.date is None, t.date or datetime.min))
    if not any(len(t) for t in exp.trials):
        raise ReadError(f"No X/Y positions were found. Is this really {SOFTWARE_LABELS[software]} data?")
    return exp


def custom_ext_in(directory) -> str:
    for ext in (".csv", ".xlsx"):
        if find_files(directory, "*" + ext):
            return ext
    return ".csv"


# ---------------------------------------------------------------- detection
def _first_file(path: str) -> Optional[str]:
    if os.path.isfile(path):
        return path
    for pat in ("*.xlsx", "*.csv"):
        found = find_files(path, pat)
        if found:
            return found[0]
    return None


def detect_software(path: str | os.PathLike) -> Optional[str]:
    """Guess which program exported this file/folder. Returns a key of SOFTWARE_LABELS or None.

    FIX: the original detectSoftwareType() crashed (undefined names) and its if/else chain
    overwrote ANY-maze and WaterMaze matches with "custom".
    """
    fn = _first_file(str(path))
    if fn is None:
        return None
    ext = os.path.splitext(fn)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            sheet = pd.read_excel(fn, header=None, nrows=3)
            if str(sheet.iloc[0, 0]).strip().lower().startswith("number of header lines"):
                return "ethovision"
            return "custom"
        with open(fn, newline="", errors="replace") as f:
            head = f.read(4096)
        dialect = csv.Sniffer().sniff(head.splitlines()[0] if head else ",", delimiters=";,\t")
        rows = list(csv.reader(head.splitlines()[:2], dialect))
        first = [c.strip() for c in rows[0]] if rows else []
        second = [c.strip() for c in rows[1]] if len(rows) > 1 else []
        if {"Time", "Centre posn X", "Centre posn Y"}.issubset(first):
            return "anymaze"
        if {"FPS", "Frame", "X", "Y"}.issubset(first):
            return "eztrack"
        if {"x", "y", "t"}.issubset(second):
            return "watermaze"
        return "custom"
    except Exception:  # noqa: BLE001
        return None


def iter_points(trials: Iterable[Trial]):
    for t in trials:
        yield from t
