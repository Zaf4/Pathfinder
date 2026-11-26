"""The new analysis must reproduce the original Pathfinder's results exactly.

Golden CSVs in tests/golden/ were produced by the original Tkinter program
(see tests/golden/make_golden_legacy.py).
"""
import csv
import json
from pathlib import Path

import pytest

from pathfinder.core.analysis import analyze, resolve_geometry, result_rows
from pathfinder.core.params import MazeSetup, StrategyParams
from pathfinder.core.readers import load_experiment

TESTS = Path(__file__).parent
CASES = json.loads((TESTS / "golden" / "cases.json").read_text())


def _num(v):
    return None if v in ("Auto", "") else float(v)


def _setup(c):
    gx, gy = (None, None) if c["goal"] == "Auto" else map(float, c["goal"].split(","))
    cx, cy = (None, None) if c["centre"] == "Auto" else map(float, c["centre"].split(","))
    return MazeSetup(goal_x=gx, goal_y=gy, goal_diameter=_num(c["goal_diam"]), maze_diameter=_num(c["maze_diam"]),
                     centre_x=cx, centre_y=cy, corridor_width=float(c["corridor"]),
                     chaining_width=float(c["chaining"]), thigmotaxis_zone=float(c["thigmo"]),
                     truncate_at_goal=c["truncate"])


def _same(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return float(a) == pytest.approx(float(b), rel=1e-12, abs=1e-12)
    except ValueError:
        return False


@pytest.mark.parametrize("case", CASES, ids=[c["case"] for c in CASES])
def test_matches_original(case):
    path = TESTS / (case["file"] or case["directory"])
    exp = load_experiment(case["software"], path)
    setup = _setup(case)
    geom = resolve_geometry(exp, setup, single_file=bool(case["file"]))
    results = analyze(exp, geom, setup, StrategyParams())
    headers, rows = result_rows(exp, results)
    got = [headers] + [[str(v) for v in r] for r in rows]

    with open(TESTS / "golden" / f"{case['case']}.csv", newline="") as f:
        want = list(csv.reader(f))

    assert got[0] == want[0]
    assert len(got) == len(want)
    skip = 3 if exp.has_date_info else 0  # original left Date/Time/Day empty (shifted columns)
    for g, w in zip(got[1:], want[1:]):
        g = g[skip:]
        assert len(g) == len(w)
        for col, (gv, wv) in enumerate(zip(g, w)):
            assert _same(gv, wv), f"{headers[col + skip]}: new={gv!r} original={wv!r}"
