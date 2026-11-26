from pathfinder import __version__
from pathfinder.gui.app import is_newer, release_source, version_key, windows_installer


def test_version_key():
    assert version_key("2.1.0") == (2, 1, 0)
    assert version_key("v2.10.1") == (2, 10, 1)
    assert version_key("2.2.0rc1") == (2, 2, 0)
    assert version_key("latest") == ()


def test_is_newer():
    assert is_newer("2.1.1", "2.1.0")
    assert is_newer("2.10.0", "2.9.9")
    assert not is_newer("2.1.0", "2.1.0")
    assert not is_newer("1.3.0", "2.1.0")
    assert not is_newer("nonsense", "2.1.0")
    assert not is_newer(__version__)


def test_update_urls_use_the_tag():
    assert release_source("2.1.0").endswith("/archive/2.1.0.zip")
    assert "/2.1.0/install.ps1" in windows_installer("2.1.0")
