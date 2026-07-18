"""Per-worker filesystem isolation for the test suite.

The e2e tests boot a MiniCroft that loads this skill under a fixed skill_id.
Skill settings/data live under XDG paths derived from that skill_id, so two
MiniCroft instances loading the same skill_id concurrently -- as happens when
pytest-xdist distributes tests across workers -- race on the same directory and
raise ``FileExistsError``. Give each worker its own XDG roots so those paths
never collide.
"""

import os
import tempfile


def _isolate_xdg_dirs() -> None:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    root = os.path.join(tempfile.gettempdir(), f"ggwave-xdg-{worker}")
    for var, sub in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
    ):
        path = os.path.join(root, sub)
        os.makedirs(path, exist_ok=True)
        os.environ[var] = path


_isolate_xdg_dirs()
