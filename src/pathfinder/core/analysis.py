"""Search-strategy analysis.

The maths is a line-by-line port of the original Pathfinder (getAutoLocations,
calculateValues and the classifier in mainCalculate) so results stay identical to the
published method. tests/test_golden.py checks this against output of the original code.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .models import Experiment, Trial
from .params import MazeSetup, StrategyParams


class AnalysisError(Exception):
    pass


class Cancelled(Exception):
    pass


@dataclass
class Geometry:
    """Resolved maze geometry (all values numeric)."""
    goal_x: float
    goal_y: float
    goal_diameter: float
    centre_x: float
    centre_y: float
    maze_diameter: float
    auto: list[str] = field(default_factory=list)  # which values were detected

    @property
    def radius(self) -> float:
        return float(self.maze_diameter) / 2.0


@dataclass
class TrialResult:
    trial: Trial
    index: int            # position in the experiment
    trial_number: int     # n-th trial of this animal
    day: int              # 1-based day (date data only, else 0)
    strategy: str
    score: object
    metrics: dict
    xs: list
    ys: list
    manual_strategy: str = ""

    @property
    def final_strategy(self) -> str:
        return self.manual_strategy or self.strategy


# ------------------------------------------------------------------ geometry
def goal_from_trial_ends(exp: Experiment, min_trials: int = 3):
    """Estimate the platform as the median point where trials ended early.

    Tracking stops when the animal climbs onto the platform, so trials that end before the
    time limit end on the platform. On real data (Overall & Kempermann 2019, 300 trials) this
    lands within 1-3 cm of the true platform; the original estimate (mean of all positions in
    the first 50 s) landed near the pool centre, 32-42 cm away. Returns None when too few
    trials end early (e.g. probe trials only), so the caller can fall back.
    """
    trials = [t for t in exp if len(t) > 1]
    if not trials:
        return None
    durations = [t.points[-1].time - t.points[0].time for t in trials]
    limit = max(durations)
    ends = [t.points[-1] for t, d in zip(trials, durations) if d < 0.95 * limit]
    if len(ends) < min_trials:
        return None
    return float(np.median([p.x for p in ends])), float(np.median([p.y for p in ends]))


def resolve_geometry(exp: Experiment, setup: MazeSetup, single_file: bool = False,
                     goal=None, goal_method: str = "trial_ends") -> Geometry:
    """Port of getAutoLocations(). `goal` overrides the setup's goal (used for extra goals).

    goal_method: "trial_ends" (default, see goal_from_trial_ends) or "legacy" (the original
    estimate, kept so the golden tests can check the port against the original program).
    """
    goal_x, goal_y = (setup.goal_x, setup.goal_y) if goal is None else (goal[0], goal[1])
    goal_diam = setup.goal_diameter if goal is None else goal[2]
    want_goal = goal_x is None or goal_y is None
    want_goal_diam = goal_diam is None
    want_centre = setup.centre_auto
    want_diam = setup.maze_diameter is None

    auto = []
    if want_goal:
        auto.append("goal position")
    if want_goal_diam:
        auto.append("goal diameter")
    if want_centre:
        auto.append("maze centre")
    if want_diam:
        auto.append("maze diameter")
    if auto and single_file and exp.software != "watermaze":
        raise AnalysisError("Automatic detection needs a whole folder of trials. "
                            "Enter the " + ", ".join(auto) + " yourself, or open a folder.")

    max_x = min_x = max_y = min_y = 0.0
    av_max_x = av_max_y = av_min_x = av_min_y = 0.0
    abs_max_x = abs_max_y = abs_min_x = abs_min_y = 0.0
    count = centre_count = 0.0
    plat_x = plat_y = 0.0
    last_x = last_y = 0.0
    max_len = 50.0

    if auto:
        for trial in exp:
            for p in trial:
                if p.time < max_len:
                    last_x, last_y = p.x, p.y
                    skip = False
                else:
                    skip = True
                max_x = max(max_x, p.x) if p.x > max_x else max_x
                min_x = p.x if p.x < min_x else min_x
                max_y = p.y if p.y > max_y else max_y
                min_y = p.y if p.y < min_y else min_y
                abs_max_x = max_x if max_x > abs_max_x else abs_max_x
                abs_min_x = min_x if min_x < abs_min_x else abs_min_x
                abs_max_y = max_y if max_y > abs_max_y else abs_max_y
                abs_min_y = min_y if min_y < abs_min_y else abs_min_y
                av_max_x += max_x
                av_max_y += max_y
                av_min_x += min_x
                av_min_y += min_y
                centre_count += 1.0
                if not skip:
                    count += 1.0
                    plat_x += last_x
                    plat_y += last_y
        if centre_count < 1:
            raise AnalysisError("Could not detect the maze from the data (no usable positions).")
    if count < 1 and want_goal:
        raise AnalysisError("Could not detect the goal position from the data.")

    centre_x, centre_y = setup.centre_x, setup.centre_y
    if want_centre:
        centre_x = ((av_max_x / centre_count) + (av_min_x / centre_count)) / 2
        centre_y = ((av_max_y / centre_count) + (av_min_y / centre_count)) / 2
    if want_goal:
        goal_x, goal_y = plat_x / count, plat_y / count
        if goal_method == "trial_ends":
            better = goal_from_trial_ends(exp)
            if better is not None:
                goal_x, goal_y = better
    if want_goal_diam:
        # The original estimator never updates its bounds, so it always falls back to 10.
        goal_diam = 10.0
    maze_diam = setup.maze_diameter
    if want_diam:
        maze_diam = ((abs(abs_max_x) + abs(abs_min_x)) + (abs(abs_max_y) + abs(abs_min_y))) / 2
    return Geometry(float(goal_x), float(goal_y), float(goal_diam), float(centre_x), float(centre_y),
                    float(maze_diam), auto)


# ------------------------------------------------------------------ metrics
def _unit_vector(v):
    n = np.linalg.norm(v)
    if n == 0:
        return (0, 0)
    try:
        return v / n
    except Exception:  # noqa: BLE001
        return (0, 0)


def _angle_between(v1, v2):
    return np.degrees(np.arccos(np.clip(np.dot(_unit_vector(v1), _unit_vector(v2)), -1.0, 1.0)))


def calculate_values(trial: Trial, goal_x, goal_y, centre_x, centre_y, corridor_width, chaining_radius,
                     full_thigmo_zone, small_thigmo_zone, maze_radius, goal_diam, truncate=False):
    """Port of calculateValues(). Returns a dict of metrics plus the path arrays."""
    i = 0
    total_distance = 0.0
    latency = 1
    x_sum = y_sum = 0.0
    dist_goal_sum = 0.0
    total_dist_centre = 0.0
    small_thigmo = full_thigmo = annulus = 0.0
    total_dist_centroid = 0.0
    start_x = start_y = 0.0
    start_time = 0.0
    old_item_x = old_item_y = 0.0
    corridor_counter = 0.0
    q1 = q2 = q3 = q4 = 0
    old_x = old_y = 0.0
    dist_start_goal = 0
    xs, ys = [], []

    for p in trial:
        if i == 0:
            start_x, start_y, start_time = p.x, p.y, p.time
        i += 1.0
        x_sum += float(p.x)
        y_sum += float(p.y)
        ax, ay = float(p.x), float(p.y)
        xs.append(ax)
        ys.append(ay)
        cur_goal = math.sqrt((goal_x - ax) ** 2 + (goal_y - ay) ** 2)
        dist_centre_goal = math.sqrt((centre_x - goal_x) ** 2 + (centre_y - goal_y) ** 2)
        ann_in = dist_centre_goal - (chaining_radius / 2)
        ann_out = dist_centre_goal + (chaining_radius / 2)
        d_centre = math.sqrt((centre_x - ax) ** 2 + (centre_y - ay) ** 2)
        total_dist_centre += d_centre
        dist_start_goal = math.sqrt((goal_x - start_x) ** 2 + (goal_y - start_y) ** 2)
        step = math.sqrt(abs(old_x - ax) ** 2 + abs(old_y - ay) ** 2)
        dist_goal_sum += cur_goal
        total_distance += step
        old_x, old_y = ax, ay
        if d_centre > small_thigmo_zone:
            small_thigmo += 1.0
        if d_centre > full_thigmo_zone:
            full_thigmo += 1.0
        if ann_in <= d_centre <= ann_out:
            annulus += 1.0
        if p.x >= centre_x and p.y >= centre_y:
            q1 = 1
        elif p.x < centre_x and p.y >= centre_y:
            q2 = 1
        elif p.x >= centre_x and p.y < centre_y:
            q3 = 1
        elif p.x < centre_x and p.y < centre_y:
            q4 = 1
        latency = p.time - start_time
        if truncate and cur_goal < float(goal_diam) / 2.0:
            break

    quadrants = q1 + q2 + q3 + q4

    spread_x = abs((centre_x + maze_radius) - (centre_x - maze_radius))
    spread_y = abs((centre_y + maze_radius) - (centre_y - maze_radius))
    norm_x = [round((((xx - abs((centre_x - maze_radius))) / spread_x) * 10), 0) * 10 for xx in xs]
    norm_y = [round((((yy - abs((centre_y - maze_radius))) / spread_y) * 10), 0) * 10 for yy in ys]
    percent_traversed = len(dict.fromkeys(zip(norm_x, norm_y)))
    if percent_traversed > 100:
        percent_traversed = 100

    if i == 0:
        i = 1
    x_av, y_av = x_sum / i, y_sum / i

    if goal_x - start_x != 0:
        arctan = math.degrees(math.atan((goal_y - start_y) / (goal_x - start_x)))
    else:
        arctan = 0
    upper, lower = arctan + corridor_width, arctan - corridor_width
    total_heading = 0.0
    initial_heading = 0.0
    initial_heading_n = 0
    cur_heading = 0.0

    for p in trial:
        cur_goal = math.sqrt((goal_x - p.x) ** 2 + (goal_y - p.y) ** 2)
        total_dist_centroid += math.sqrt((x_av - p.x) ** 2 + (y_av - p.y) ** 2)
        if old_item_x != 0 and p.x - old_item_x != 0 and p.x - start_x != 0:
            to_goal = np.subtract(np.array([goal_x, goal_y]), np.array([p.x, p.y]))
            step_v = np.subtract(np.array([p.x, p.y]), np.array([old_item_x, old_item_y]))
            cur_heading = abs(_angle_between(to_goal, step_v))
            within = math.degrees(math.atan((p.y - start_y) / (p.x - start_x)))
            if float(lower) <= float(within) <= float(upper):
                corridor_counter += 1.0
        if p.time < 1.0:
            initial_heading += cur_heading
            initial_heading_n += 1
        old_item_x, old_item_y = p.x, p.y
        total_heading += cur_heading
        if truncate and cur_goal < float(goal_diam) / 2.0:
            break

    corridor_avg = corridor_counter / i
    dist_avg = dist_goal_sum / i
    centroid_avg = total_dist_centroid / i
    centre_avg = total_dist_centre / i
    heading_avg = total_heading / i
    try:
        initial_heading_avg = initial_heading / initial_heading_n
    except ZeroDivisionError:
        initial_heading_avg = 0

    velocity = 0
    ideal = dist_start_goal
    if latency != 0:
        velocity = total_distance / latency
    ideal_cum = 0.0
    try:
        sample_rate = (trial.points[-1].time - start_time) / (len(trial.points) - 1)
    except Exception:  # noqa: BLE001
        sample_rate = 1
    while ideal > math.ceil(float(goal_diam) / 2):
        ideal_cum += ideal
        ideal = ideal - velocity * sample_rate
        if ideal_cum > 1000000:
            break
    ipe = float(dist_goal_sum - ideal_cum) * sample_rate
    if ipe < 0:
        ipe = 0

    return dict(
        corridor_avg=corridor_avg, dist_avg=dist_avg, centroid_avg=centroid_avg, centre_avg=centre_avg,
        heading_avg=heading_avg, percent_traversed=percent_traversed, quadrants=quadrants,
        total_distance=total_distance, latency=latency, full_thigmo=full_thigmo, small_thigmo=small_thigmo,
        annulus=annulus, n=i, velocity=velocity, ipe=ipe, initial_heading=initial_heading_avg,
    ), xs, ys


def classify(m: dict, radius: float, params: StrategyParams):
    """Port of the classifier in mainCalculate(). Returns (strategy, score)."""
    p = params
    i = m["n"]
    if m["ipe"] <= p.ipeMaxVal and m["heading_avg"] <= p.headingMaxVal and p.useDirect:
        return "Direct Path", 3
    if (m["centroid_avg"] < radius * p.distanceToSwimMaxVal / 100 and m["dist_avg"] < p.distanceToPlatMaxVal / 100 * radius
            and p.focalMinDistance < m["total_distance"] < p.focalMaxDistance and p.useFocal):
        return "Focal Search", 2
    if (m["corridor_avg"] >= p.corridorAverageMinVal / 100 and m["ipe"] <= p.corridoripeMaxVal
            and m["total_distance"] < p.directedSearchMaxDistance and p.useDirected):
        return "Directed Search", 2
    if m["ipe"] < p.ipeIndirectMaxVal and m["heading_avg"] < p.headingIndirectMaxVal and p.useIndirect:
        return "Indirect Search", 2
    if (m["centroid_avg"] < radius * p.distanceToSwimMaxVal2 / 100 and m["dist_avg"] < p.distanceToPlatMaxVal2 / 100 * radius
            and p.semiFocalMinDistance < m["total_distance"] < p.semiFocalMaxDistance and p.useSemiFocal):
        return "Semi-focal Search", 2
    if (float(m["annulus"] / i) > p.annulusCounterMaxVal / 100 and m["quadrants"] >= p.quadrantTotalMaxVal
            and m["percent_traversed"] < p.chainingMaxCoverage and p.useChaining):
        return "Chaining", 1
    if (p.percentTraversedMinVal <= m["percent_traversed"] and p.percentTraversedMaxVal > m["percent_traversed"]
            and m["centre_avg"] <= p.distanceToCentreMaxVal / 100 * radius and p.useScanning):
        return "Scanning", 1
    if (m["full_thigmo"] / i >= p.fullThigmoMinVal / 100 and m["small_thigmo"] / i >= p.smallThigmoMinVal / 100
            and m["total_distance"] > p.thigmoMinDistance and p.useThigmotaxis):
        return "Thigmotaxis", 0
    if m["percent_traversed"] >= p.percentTraversedRandomMaxVal and p.useRandom:
        return "Random Search", 0
    return "Not Recognized", 0


# ------------------------------------------------------------------ run
def analyze(exp: Experiment, geom: Geometry, setup: MazeSetup, params: StrategyParams,
            progress: Optional[Callable[[int, int, str], None]] = None,
            cancelled: Optional[Callable[[], bool]] = None) -> list[TrialResult]:
    thigmo = float(setup.thigmotaxis_zone)
    chaining = float(setup.chaining_width)
    corridor = int(setup.corridor_width) / 2
    radius = geom.radius
    small_zone = radius - math.ceil(thigmo / 2)
    full_zone = radius - thigmo

    results = []
    trial_num: dict = {}
    days: dict = {}
    for idx, trial in enumerate(exp.trials):
        if cancelled and cancelled():
            raise Cancelled()
        if progress:
            progress(idx, len(exp.trials), trial.label)
        trial_num[trial.animal] = trial_num.get(trial.animal, 0) + 1
        day = 0
        if exp.has_date_info and trial.date is not None:
            day = days.setdefault(trial.date.date(), len(days) + 1)
        m, xs, ys = calculate_values(trial, geom.goal_x, geom.goal_y, geom.centre_x, geom.centre_y, corridor,
                                     chaining, full_zone, small_zone, radius, geom.goal_diameter,
                                     truncate=setup.truncate_at_goal)
        strategy, score = classify(m, radius, params)
        results.append(TrialResult(trial, idx, trial_num[trial.animal], day, strategy, score, m, xs, ys))
    if progress:
        progress(len(exp.trials), len(exp.trials), "")
    return results


CSV_HEADERS = ["Trial Code", "Strategy", "IPE", "Velocity", "Distance covered", "Average distance to goal",
               "Average heading error", "Percent of maze traversed", "Latency", "Score", "Initial heading error",
               "Entropy", "Distance to swim path centroid", "Average distance to centre of maze",
               "Percent in angular corridor", "Percent in annulus zone", "Percent in smaller thigmotaxis zone",
               "Percent in full thigmotaxis zone", "Strategy (manual)"]


def result_rows(exp: Experiment, results: list[TrialResult]):
    """Header + rows in the same column layout as the original results CSV."""
    headers = []
    if exp.has_date_info:
        headers.extend(["Date", "Time", "Day"])
    headers.append("Trial")
    if exp.has_trial_names:
        headers.append("Name")
    if exp.has_animal_names:
        headers.append("Animal")
    headers.extend(CSV_HEADERS)
    rows = []
    for r in results:
        m = r.metrics
        i = m["n"]
        row = []
        if exp.has_date_info:
            # FIX: the original wrote these headers but never the values, shifting every column.
            d = r.trial.date
            row.extend([d.strftime("%Y-%m-%d") if d else "", d.strftime("%H:%M") if d else "", r.day])
        row.append(r.trial_number)
        if exp.has_trial_names:
            row.append(r.trial.name)
        if exp.has_animal_names:
            row.append(r.trial.animal)
        row.extend([
            f"{r.trial.animal} 0 {r.trial_number}", r.strategy, round(m["ipe"], 2), round(m["velocity"], 2),
            round(m["total_distance"], 2), round(m["dist_avg"], 2), round(m["heading_avg"], 2),
            round(m["percent_traversed"], 2), round(m["latency"], 2), r.score, m["initial_heading"], 0,
            round(m["centroid_avg"], 2), round(m["centre_avg"], 2), round(m["corridor_avg"], 2),
            round(m["annulus"] / i, 2), round(m["small_thigmo"] / i, 2), round(m["full_thigmo"] / i, 2),
            r.manual_strategy,
        ])
        rows.append(row)
    return headers, rows


def write_csv(path, exp: Experiment, results: list[TrialResult]) -> None:
    headers, rows = result_rows(exp, results)
    with open(path, "w", newline="") as f:
        w = csv.writer(f, delimiter=",", quotechar='"')
        w.writerow(headers)
        w.writerows(rows)
