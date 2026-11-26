"""Record reference results from the ORIGINAL Tkinter Pathfinder (upstream commit d707552).

This drives the legacy `mainClass.mainCalculate` headlessly and writes one CSV per case
into tests/golden/. It must be run with the legacy `SearchStrategyAnalysis` package on
sys.path (a checkout of upstream master) and a Python whose Tk is 8.6, e.g.:

    cd <legacy checkout>
    python /path/to/tests/golden/make_golden_legacy.py /path/to/tests

The new code is tested against these files in tests/test_golden.py.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

TESTS = Path(sys.argv[1]).resolve()
FIX = TESTS / "fixtures"
OUT = TESTS / "golden"
sys.path.insert(0, os.getcwd())

work = Path(tempfile.mkdtemp())
os.chdir(work)  # legacy code writes output/ into the cwd

import SearchStrategyAnalysis.Pathfinder as P  # noqa: E402

P.open_file = lambda f: None  # don't pop the CSV open in Excel


def run(case, software, directory="", file="", goal="30,30", goal_diam="10", maze_diam="150",
        centre="0,0", corridor="40", chaining="25", thigmo="15", truncate=False):
    P.theFile = file
    P.fileDirectory = directory
    P.fileFlag = 1 if file else 0
    P.manualFlag = False
    P.useManualForAllFlag = False
    P.useEntropyFlag = False
    P.truncateFlag = truncate
    P.softwareStringVar.set(software)
    P.mazeDiamStringVar.set(maze_diam)
    P.mazeCentreStringVar.set(centre)
    P.corridorWidthStringVar.set(corridor)
    P.chainingRadiusStringVar.set(chaining)
    P.thigmotaxisZoneSizeStringVar.set(thigmo)
    prefix = str(work / case)
    P.outputFileStringVar.set(prefix)
    obj = P.mainClass.__new__(P.mainClass)
    obj.mainCalculate(goal, goal_diam)
    produced = Path(prefix + goal + ".csv")
    shutil.copy(produced, OUT / f"{case}.csv")
    return dict(case=case, software=software, directory=directory, file=file, goal=goal,
                goal_diam=goal_diam, maze_diam=maze_diam, centre=centre, corridor=corridor,
                chaining=chaining, thigmo=thigmo, truncate=truncate)


def rel(p):
    return str(Path(p).relative_to(TESTS))


cases = []
for sw in ["anymaze", "eztrack", "ethovision", "watermaze"]:
    d = str(FIX / sw)
    c = run(f"{sw}_fixed", sw, directory=d)
    c["directory"] = rel(d)
    cases.append(c)
    c = run(f"{sw}_truncate", sw, directory=d, truncate=True)
    c["directory"] = rel(d)
    cases.append(c)
    c = run(f"{sw}_auto", sw, directory=d, goal="Auto", centre="Auto", maze_diam="Auto")
    c["directory"] = rel(d)
    cases.append(c)

one = sorted((FIX / "anymaze").glob("*.csv"))[0]
c = run("anymaze_single", "anymaze", file=str(one), goal="30,30")
c["file"] = rel(one)
cases.append(c)

(OUT / "cases.json").write_text(json.dumps(cases, indent=2))
print("wrote", len(cases), "golden cases to", OUT)
