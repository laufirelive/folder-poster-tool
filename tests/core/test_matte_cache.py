"""Tests for matte cache / reuse logic."""

import sys
from pathlib import Path

import pytest

_ROOT = str(Path(__file__).resolve().parents[2])


@pytest.fixture(autouse=True)
def _path():
    sys.path.insert(0, _ROOT)
    yield


def test_find_reusable_matte_paths_returns_none_when_no_match(tmp_path):
    from core.matte_cache import find_reusable_matte_paths
    from models import Material, MatteRecord

    src = tmp_path / "a.png"
    src.write_bytes(b"dummy")
    matte = tmp_path / "m.png"
    matte.write_bytes(b"m")
    mask = tmp_path / "mk.png"
    mask.write_bytes(b"k")

    m = Material(source_id="wrong", frame_idx=None, selected=True)
    assert find_reusable_matte_paths(m, str(src), []) is None

    rec = MatteRecord(
        source_id="id1",
        source_mtime=0.0,
        matte_path=str(matte),
        mask_path=str(mask),
        is_active=True,
    )
    m_ok = Material(source_id="id1", frame_idx=None, selected=True)
    # mtime mismatch
    assert find_reusable_matte_paths(m_ok, str(src), [rec]) is None


def test_find_reusable_matte_paths_hits_when_active_file_mtime_matches(tmp_path):
    from core.matte_cache import find_reusable_matte_paths
    from models import Material, MatteRecord

    src = tmp_path / "a.png"
    src.write_bytes(b"dummy")
    mtime = src.stat().st_mtime

    matte = tmp_path / "m.png"
    matte.write_bytes(b"m")
    mask = tmp_path / "mk.png"
    mask.write_bytes(b"k")

    rec = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(matte),
        mask_path=str(mask),
        is_active=True,
    )
    m = Material(source_id="sid", frame_idx=None, selected=True)
    assert find_reusable_matte_paths(m, str(src), [rec]) == (str(matte), str(mask))


def test_find_reusable_matte_paths_ignores_inactive_or_missing_artifacts(tmp_path):
    from core.matte_cache import find_reusable_matte_paths
    from models import Material, MatteRecord

    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    mtime = src.stat().st_mtime

    matte_ok = tmp_path / "ok.png"
    matte_ok.write_bytes(b"1")
    mask_ok = tmp_path / "ok_mask.png"
    mask_ok.write_bytes(b"2")

    inactive = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(matte_ok),
        mask_path=str(mask_ok),
        is_active=False,
    )
    missing_path = tmp_path / "gone.png"
    missing = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(missing_path),
        mask_path=str(mask_ok),
        is_active=True,
    )
    missing_mask = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(matte_ok),
        mask_path=str(tmp_path / "missing_mask.png"),
        is_active=True,
    )
    m = Material(source_id="sid", frame_idx=None, selected=True)
    assert find_reusable_matte_paths(m, str(src), [inactive, missing, missing_mask]) is None

    good = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(matte_ok),
        mask_path=str(mask_ok),
        is_active=True,
    )
    assert find_reusable_matte_paths(m, str(src), [inactive, missing, missing_mask, good]) == (
        str(matte_ok),
        str(mask_ok),
    )
