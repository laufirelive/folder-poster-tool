import sys
from pathlib import Path


def test_save_and_load_state(tmp_path):
    # Pytest puts `tests` on sys.path; `import core` then resolves to tests/core/ during
    # collection and caches it. Drop so we can load the project `core` package.
    _root = str(Path(__file__).resolve().parents[2])
    sys.path.insert(0, _root)
    bad = sys.modules.get("core")
    if bad is not None:
        f = (getattr(bad, "__file__", "") or "").replace("\\", "/")
        if f.endswith("/tests/core/__init__.py") or "/tests/core/" in f:
            del sys.modules["core"]
            for k in list(sys.modules):
                if k.startswith("core."):
                    del sys.modules[k]

    from models import ProjectState
    from core.state_manager import StateManager

    temp_dir = tmp_path / "temp"
    manager = StateManager(str(temp_dir))

    state = ProjectState(project_id="proj_1", input_path="/test", mode="image")
    manager.save_state(state)

    file_path = temp_dir / "proj_1.json"
    assert file_path.exists()

    loaded_state = manager.load_state("proj_1")
    assert loaded_state is not None
    assert loaded_state.project_id == "proj_1"
    assert loaded_state.input_path == "/test"


def test_load_state_missing_file_returns_none(tmp_path):
    _root = str(Path(__file__).resolve().parents[2])
    sys.path.insert(0, _root)
    bad = sys.modules.get("core")
    if bad is not None:
        f = (getattr(bad, "__file__", "") or "").replace("\\", "/")
        if f.endswith("/tests/core/__init__.py") or "/tests/core/" in f:
            del sys.modules["core"]
            for k in list(sys.modules):
                if k.startswith("core."):
                    del sys.modules[k]

    from core.state_manager import StateManager

    temp_dir = tmp_path / "temp"
    manager = StateManager(str(temp_dir))
    assert manager.load_state("nonexistent_project") is None
