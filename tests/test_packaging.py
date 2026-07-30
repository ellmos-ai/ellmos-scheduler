import json
import sys
import tomllib
from pathlib import Path

from ellmos_scheduler import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_version_metadata_stays_aligned():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    module = json.loads(
        (ROOT / "ellmos-module.v2.json").read_text(encoding="utf-8")
    )

    assert project["project"]["version"] == __version__
    assert module["version"] == __version__


def test_windows_runtime_declares_iana_timezone_data():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]

    assert (
        "tzdata>=2024.1; platform_system == 'Windows'" in dependencies
    )
    if sys.platform == "win32":
        import tzdata  # noqa: F401
