import os
import sys
from pathlib import Path


def _ensure_project_core() -> None:
    """Avoid ``tests/core`` package shadowing project ``core`` when pytest manipulates sys.path."""
    _root = str(Path(__file__).resolve().parents[1])
    sys.path.insert(0, _root)
    bad = sys.modules.get("core")
    if bad is not None:
        f = (getattr(bad, "__file__", "") or "").replace("\\", "/")
        if f.endswith("/tests/core/__init__.py") or "/tests/core/" in f:
            del sys.modules["core"]
            for k in list(sys.modules):
                if k.startswith("core."):
                    del sys.modules[k]


def test_resolve_image_material(tmp_path):
    _ensure_project_core()
    from core.material_paths import resolve_material_raster_path
    from models import Material, ProjectState, ScannedFile

    img = tmp_path / "a.png"
    img.write_bytes(b"fake")
    sid = "abc123"
    state = ProjectState(
        project_id="p1",
        input_path=str(tmp_path),
        mode="image",
        scanned_files=[
            ScannedFile(
                path=str(img),
                name="a.png",
                type="image",
                source_id=sid,
            )
        ],
    )
    m = Material(source_id=sid, frame_idx=None, selected=True)
    got = resolve_material_raster_path(str(tmp_path), state, m)
    assert got == str(img.resolve())


def test_resolve_video_frame(tmp_path):
    _ensure_project_core()
    from core.material_paths import resolve_material_raster_path
    from models import Material, ProjectState, ScannedFile

    base = tmp_path / "cache"
    proj = "proj9"
    sid = "vid01"
    previews = base / proj / "previews" / sid
    previews.mkdir(parents=True)
    frame_path = previews / "frame_003.png"
    frame_path.write_bytes(b"x")
    state = ProjectState(
        project_id=proj,
        input_path=str(tmp_path),
        mode="video",
        scanned_files=[
            ScannedFile(
                path=str(tmp_path / "v.mp4"),
                name="v.mp4",
                type="video",
                source_id=sid,
            )
        ],
    )
    m = Material(source_id=sid, frame_idx=2, selected=True)
    got = resolve_material_raster_path(str(base), state, m)
    assert os.path.abspath(got) == os.path.abspath(str(frame_path))


def test_resolve_video_missing_frame_returns_none(tmp_path):
    _ensure_project_core()
    from core.material_paths import resolve_material_raster_path
    from models import Material, ProjectState, ScannedFile

    base = tmp_path / "cache"
    state = ProjectState(
        project_id="p",
        input_path=str(tmp_path),
        mode="video",
        scanned_files=[
            ScannedFile(
                path="/x/v.mp4",
                name="v.mp4",
                type="video",
                source_id="s",
            )
        ],
    )
    m = Material(source_id="s", frame_idx=0, selected=True)
    assert resolve_material_raster_path(str(base), state, m) is None
