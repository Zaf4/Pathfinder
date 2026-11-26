"""Real mouse water maze data (Overall & Kempermann 2019, CC BY 4.0) - see fixtures/real_overall2019."""
import csv
import json
from pathlib import Path

import pytest

from pathfinder.core.analysis import analyze, resolve_geometry, result_rows
from pathfinder.core.params import MazeSetup, StrategyParams
from pathfinder.core.readers import detect_software, load_experiment

from test_golden import _same

TESTS = Path(__file__).parent
REAL = TESTS / "fixtures" / "real_overall2019"
TRUTH = json.loads((REAL / "truth.json").read_text())


@pytest.mark.parametrize("phase", ["acquisition", "reversal"])
def test_real_data_matches_original_program(phase):
    folder = str(REAL / phase)
    assert detect_software(folder) == "ethovision"
    exp = load_experiment("ethovision", folder)
    g = TRUTH["goals"][phase]
    setup = MazeSetup(goal_x=g["x"], goal_y=g["y"], goal_diameter=g["diameter"],
                      maze_diameter=TRUTH["pool_diameter_cm"], centre_x=0.0, centre_y=0.0)
    res = analyze(exp, resolve_geometry(exp, setup), setup, StrategyParams())
    headers, rows = result_rows(exp, res)
    with open(TESTS / "golden" / f"real_overall2019_{phase}.csv", newline="") as f:
        want = list(csv.reader(f))
    assert headers == want[0]
    key = lambda r: (r[headers.index("Animal")], r[headers.index("Name")])  # noqa: E731
    got = {key([str(v) for v in r]): [str(v) for v in r] for r in rows}
    assert len(got) == len(want) - 1 == len(exp.trials)
    for w in want[1:]:
        gr = got[key(w)]
        for col, (gv, wv) in enumerate(zip(gr, w)):
            assert _same(gv, wv), f"{key(w)} {headers[col]}: new={gv!r} original={wv!r}"


@pytest.mark.parametrize("phase", ["acquisition", "reversal"])
def test_detect_finds_the_real_platform(phase):
    exp = load_experiment("ethovision", str(REAL / phase))
    s = MazeSetup()
    s.goal_x = s.goal_y = s.centre_x = s.centre_y = s.maze_diameter = None  # what the Detect button does
    geom = resolve_geometry(exp, s)
    g = TRUTH["goals"][phase]
    assert abs(geom.centre_x) < 5 and abs(geom.centre_y) < 5  # original method: pool extents
    assert abs(geom.maze_diameter - TRUTH["pool_diameter_cm"]) < 4
    off = ((geom.goal_x - g["x"]) ** 2 + (geom.goal_y - g["y"]) ** 2) ** 0.5
    assert off < 6, f"goal detected {off:.1f} cm from the real platform"
