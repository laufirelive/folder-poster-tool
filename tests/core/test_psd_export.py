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

    src_a = tmp_path / "a_src.png"
    src_b = tmp_path / "b_src.png"
    mask_a = tmp_path / "a_mask.png"
    mask_b = tmp_path / "b_mask.png"
    matte_a = tmp_path / "a_matte.png"
    matte_b = tmp_path / "b_matte.png"
    Image.new("RGB", (100, 80), color=(255, 0, 0)).save(src_a)
    Image.new("RGB", (60, 120), color=(0, 255, 0)).save(src_b)
    Image.new("L", (100, 80), color=200).save(mask_a)
    Image.new("L", (60, 120), color=180).save(mask_b)
    Image.new("RGBA", (100, 80), color=(255, 0, 0, 200)).save(matte_a)
    Image.new("RGBA", (60, 120), color=(0, 255, 0, 180)).save(matte_b)

    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(matte_a), mask_path=str(mask_a), is_active=True),
        MatteRecord(source_id="s2", source_mtime=0.0, matte_path=str(matte_b), mask_path=str(mask_b), is_active=True),
    ]
    out = tmp_path / "out.psd"
    export_matte_psd(records, {"s1": str(src_a), "s2": str(src_b)}, 4000, 6000, str(out))

    assert out.is_file()
    assert out.stat().st_size > 100


def test_export_matte_psd_roundtrip_header_dimensions(tmp_path):
    _ensure_project_core()
    from pytoshop import core
    from pytoshop.enums import ChannelId

    from core.psd_export import export_matte_psd

    src = tmp_path / "one_src.png"
    mask = tmp_path / "one_mask.png"
    matte = tmp_path / "one_matte.png"
    Image.new("RGB", (32, 24), color=(10, 20, 30)).save(src)
    Image.new("L", (32, 24), color=255).save(mask)
    Image.new("RGBA", (32, 24), color=(10, 20, 30, 255)).save(matte)
    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(matte), mask_path=str(mask), is_active=True),
    ]
    out = tmp_path / "out.psd"
    export_matte_psd(records, {"s1": str(src)}, 4000, 6000, str(out))

    with open(out, "rb") as f:
        psd = core.PsdFile.read(f)
    assert psd.width == 4000
    assert psd.height == 6000
    assert all(not rec.visible for rec in psd.layer_and_mask_info.layer_info.layer_records)
    assert all(rec.mask.width > 0 and rec.mask.height > 0 for rec in psd.layer_and_mask_info.layer_info.layer_records)
    assert all(
        ChannelId.transparency in rec.channels
        and ChannelId.user_layer_mask in rec.channels
        for rec in psd.layer_and_mask_info.layer_info.layer_records
    )


def test_export_matte_psd_no_layers_raises(tmp_path):
    _ensure_project_core()
    from core.psd_export import export_matte_psd

    missing = tmp_path / "nope.png"
    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(missing), mask_path=str(missing), is_active=True),
    ]
    out = tmp_path / "empty.psd"
    with pytest.raises(ValueError, match="missing source raster"):
        export_matte_psd(records, {}, 4000, 6000, str(out))
    assert not os.path.isfile(out)


def test_export_matte_psd_accepts_non_2_3_aspect(tmp_path):
    _ensure_project_core()
    from core.psd_export import export_matte_psd

    src = tmp_path / "x_src.png"
    mask = tmp_path / "x_mask.png"
    matte = tmp_path / "x_matte.png"
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(src)
    Image.new("L", (10, 10), color=255).save(mask)
    Image.new("RGBA", (10, 10), color=(0, 0, 0, 255)).save(matte)
    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(matte), mask_path=str(mask), is_active=True),
    ]
    out = tmp_path / "non_2_3.psd"
    export_matte_psd(records, {"s1": str(src)}, 1000, 1000, str(out))
    assert out.is_file()


def test_export_matte_psd_missing_mask_raises(tmp_path):
    _ensure_project_core()
    from core.psd_export import export_matte_psd

    src = tmp_path / "src.png"
    matte = tmp_path / "matte.png"
    missing_mask = tmp_path / "missing_mask.png"
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(src)
    Image.new("RGBA", (10, 10), color=(0, 0, 0, 255)).save(matte)

    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(matte), mask_path=str(missing_mask), is_active=True),
    ]
    with pytest.raises(ValueError, match="missing mask"):
        export_matte_psd(records, {"s1": str(src)}, 1000, 1000, str(tmp_path / "bad.psd"))
