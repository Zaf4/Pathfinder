from pathlib import Path

from pathfinder.gui.state import results_root


def test_results_folder_avoids_macos_protected_folders():
    # Documents/Desktop/Downloads trigger a macOS privacy prompt; the home folder does not.
    r = results_root()
    assert r.parent == Path.home()
    assert r.name == "Pathfinder Results"
