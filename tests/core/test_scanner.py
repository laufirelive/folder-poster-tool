import sys
from pathlib import Path


def _ensure_project_core():
    """Avoid pytest importing `tests.core` as the top-level `core` package."""
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


def test_scan_directory(tmp_path):
    _ensure_project_core()
    from core.scanner import scan_directory

    # Create mock directory structure
    (tmp_path / "img1.jpg").touch()
    (tmp_path / "vid1.mp4").touch()
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    (sub_dir / "img2.png").touch()
    (sub_dir / "vid2.mkv").touch()

    # Test image mode
    images = scan_directory(str(tmp_path), mode="image", max_depth=3)
    assert len(images) == 2
    assert all(f.type == "image" for f in images)
    assert any("img1.jpg" in f.name for f in images)

    # Test video mode
    videos = scan_directory(str(tmp_path), mode="video", max_depth=3)
    assert len(videos) == 2
    assert all(f.type == "video" for f in videos)

    # Test depth limit
    images_shallow = scan_directory(str(tmp_path), mode="image", max_depth=0)
    assert len(images_shallow) == 1
