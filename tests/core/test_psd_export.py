import os
import sys
from pathlib import Path

import pytest
from PIL import Image

from models import MatteRecord


def _ensure_project_core() -> None:
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


def test_export_matte_psd_writes_file(tmp_path):
    _ensure_project_core()
    from core.psd_export import export_matte_psd

    png_a = tmp_path / "a_matte.png"
    png_b = tmp_path / "b_matte.png"
    Image.new("RGBA", (100, 80), color=(255, 0, 0, 200)).save(png_a)
    Image.new("RGBA", (60, 120), color=(0, 255, 0, 180)).save(png_b)

    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(png_a), is_active=True),
        MatteRecord(source_id="s2", source_mtime=0.0, matte_path=str(png_b), is_active=False),
    ]
    out = tmp_path / "out.psd"
    export_matte_psd(records, 4000, 6000, str(out))

    assert out.is_file()
    assert out.stat().st_size > 100


def test_export_matte_psd_roundtrip_header_dimensions(tmp_path):
    _ensure_project_core()
    from pytoshop import core

    from core.psd_export import export_matte_psd

    png = tmp_path / "one.png"
    Image.new("RGBA", (32, 24), color=(10, 20, 30, 255)).save(png)
    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(png), is_active=True),
    ]
    out = tmp_path / "out.psd"
    export_matte_psd(records, 4000, 6000, str(out))

    with open(out, "rb") as f:
        psd = core.PsdFile.read(f)
    assert psd.width == 4000
    assert psd.height == 6000


def test_export_matte_psd_no_layers_raises(tmp_path):
    _ensure_project_core()
    from core.psd_export import export_matte_psd

    missing = tmp_path / "nope.png"
    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(missing), is_active=True),
    ]
    out = tmp_path / "empty.psd"
    with pytest.raises(ValueError, match="no active matte images"):
        export_matte_psd(records, 4000, 6000, str(out))
    assert not os.path.isfile(out)


def test_export_matte_psd_rejects_bad_aspect(tmp_path):
    _ensure_project_core()
    from core.psd_export import export_matte_psd

    png = tmp_path / "x.png"
    Image.new("RGBA", (10, 10), color=(0, 0, 0, 255)).save(png)
    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(png), is_active=True),
    ]
    with pytest.raises(ValueError, match="2:3"):
        export_matte_psd(records, 1000, 1000, str(tmp_path / "bad.psd"))
