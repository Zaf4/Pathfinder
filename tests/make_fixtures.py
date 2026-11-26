"""Generate synthetic Morris Water Maze tracks in every supported file format.

Run:  python tests/make_fixtures.py
Writes tests/fixtures/<format>/... . The tracks are deterministic (fixed seed) and
cover the main strategies: direct, focal, directed, chaining, scanning, thigmotaxis, random.
"""
import csv
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
OUT = HERE / "fixtures"

RADIUS = 75.0
GOAL = (30.0, 30.0)
START = (-60.0, -40.0)


def _clip(x, y):
    r = math.hypot(x, y)
    if r > RADIUS - 1:
        f = (RADIUS - 1) / r
        return x * f, y * f
    return x, y


def track(kind, rng, hz=10.0, duration=60.0):
    """Return list of (t, x, y)."""
    n = int(duration * hz)
    pts = []
    x, y = START
    heading = math.atan2(GOAL[1] - y, GOAL[0] - x)
    speed = 20.0  # cm/s
    for i in range(n):
        t = i / hz
        if kind == "direct":
            gx, gy = GOAL
            d = math.hypot(gx - x, gy - y)
            if d < 3:
                pts.append((t, x, y))
                break
            heading = math.atan2(gy - y, gx - x) + rng.normal(0, 0.05)
        elif kind == "directed":
            gx, gy = GOAL
            d = math.hypot(gx - x, gy - y)
            if d < 3:
                pts.append((t, x, y))
                break
            heading = math.atan2(gy - y, gx - x) + math.sin(t * 1.5) * 0.9 + rng.normal(0, 0.1)
            speed = 12.0
        elif kind == "focal":
            if i == 0:
                x, y = GOAL[0] - 15, GOAL[1] - 10
            heading += rng.normal(0, 0.8)
            speed = 8.0
            # pull back toward goal
            if math.hypot(GOAL[0] - x, GOAL[1] - y) > 12:
                heading = math.atan2(GOAL[1] - y, GOAL[0] - x)
            duration = 30
            if t > 20:
                break
        elif kind == "chaining":
            r = math.hypot(*GOAL)
            ang0 = math.atan2(START[1], START[0])
            ang = ang0 + t * 0.25
            rr = r + rng.normal(0, 1.5)
            x, y = rr * math.cos(ang), rr * math.sin(ang)
            pts.append((t, x, y))
            continue
        elif kind == "thigmotaxis":
            ang0 = math.atan2(START[1], START[0])
            ang = ang0 + t * 0.35
            rr = RADIUS - 4 + rng.normal(0, 1.0)
            x, y = rr * math.cos(ang), rr * math.sin(ang)
            pts.append((t, x, y))
            continue
        elif kind == "scanning":
            # wander near the centre
            heading += rng.normal(0, 0.6)
            if math.hypot(x, y) > 30:
                heading = math.atan2(-y, -x) + rng.normal(0, 0.3)
            speed = 10.0
        elif kind == "random":
            heading += rng.normal(0, 0.5)
            if math.hypot(x, y) > RADIUS - 8:
                heading = math.atan2(-y, -x) + rng.normal(0, 0.8)
            speed = 22.0
        x += math.cos(heading) * speed / hz
        y += math.sin(heading) * speed / hz
        x, y = _clip(x, y)
        pts.append((t, x, y))
    return pts


KINDS = ["direct", "directed", "focal", "chaining", "thigmotaxis", "scanning", "random"]


def all_tracks(hz=10.0):
    rng = np.random.default_rng(42)
    tracks = []
    for animal in range(1, 3):
        for kind in KINDS:
            tracks.append((f"A{animal}", kind, track(kind, rng, hz=hz)))
    return tracks


def hms(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:06.3f}"


def write_anymaze(dirpath):
    dirpath.mkdir(parents=True, exist_ok=True)
    for i, (animal, kind, pts) in enumerate(all_tracks()):
        with open(dirpath / f"trial{i + 1:02d}_{animal}_{kind}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Time", "Centre posn X", "Centre posn Y", "In Quadrant 1", "In Quadrant 2",
                        "In Quadrant 3", "In Quadrant 4"])
            for t, x, y in pts:
                w.writerow([hms(t), f"{x:.3f}", f"{y:.3f}", 0, 0, 0, 0])


def write_eztrack(dirpath):
    dirpath.mkdir(parents=True, exist_ok=True)
    for i, (animal, kind, pts) in enumerate(all_tracks()):
        with open(dirpath / f"trial{i + 1:02d}_{animal}_{kind}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["", "File", "FPS", "Location_Thresh", "Use_Window", "Window_Weight", "Window_Size",
                        "Start_Frame", "Frame", "X", "Y", "Distance"])
            for j, (t, x, y) in enumerate(pts):
                w.writerow([j, "video.mp4", 10, 99, True, 0.9, 100, 0, j, f"{x:.3f}", f"{y:.3f}", 0])


def write_watermaze(dirpath):
    dirpath.mkdir(parents=True, exist_ok=True)
    tracks = all_tracks()
    longest = max(len(p) for _, _, p in tracks)
    cols = []
    for i, (animal, kind, pts) in enumerate(tracks):
        day = 1 + i // 7
        hour = 9 + (i % 7)
        c1 = [f"{animal}", "x"] + [f"{x:.3f}" for _, x, _ in pts]
        c2 = [f"03/{day:02d}/2024", "y"] + [f"{y:.3f}" for _, _, y in pts]
        c3 = [f"{hour:02d}:00 AM", "t"] + [f"{t:.2f}" for t, _, _ in pts]
        for c in (c1, c2, c3):
            c.extend([""] * (longest + 2 - len(c)))
            cols.append(c)
    with open(dirpath / "watermaze_export.csv", "w", newline="") as f:
        w = csv.writer(f)
        for row in zip(*cols):
            w.writerow(row)


def write_ethovision(dirpath):
    import openpyxl

    dirpath.mkdir(parents=True, exist_ok=True)
    for i, (animal, kind, pts) in enumerate(all_tracks()):
        wb = openpyxl.Workbook()
        ws = wb.active
        header = [
            ["Number of header lines:", 6],
            ["Experiment", "MWM"],
            ["Trial name", f"Trial {i + 1}"],
            ["Animal ID", animal],
            ["Trial", (i % 7) + 1],
            ["Trial time", "Recording time", "X center", "Y center"],
        ]
        for row in header:
            ws.append(row)
        for t, x, y in pts:
            ws.append([t, t, round(x, 3), round(y, 3)])
        wb.save(dirpath / f"trial{i + 1:02d}_{animal}_{kind}.xlsx")


if __name__ == "__main__":
    write_anymaze(OUT / "anymaze")
    write_eztrack(OUT / "eztrack")
    write_watermaze(OUT / "watermaze")
    write_ethovision(OUT / "ethovision")
    print("fixtures written to", OUT)
