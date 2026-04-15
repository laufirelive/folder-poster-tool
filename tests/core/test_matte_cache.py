"""Tests for matte cache / reuse logic."""

import sys
from pathlib import Path

import pytest

_ROOT = str(Path(__file__).resolve().parents[2])


@pytest.fixture(autouse=True)
def _path():
    sys.path.insert(0, _ROOT)
    yield


def test_find_reusable_matte_path_returns_none_when_no_match(tmp_path):
    from core.matte_cache import find_reusable_matte_path
    from models import Material, MatteRecord

    src = tmp_path / "a.png"
    src.write_bytes(b"dummy")
    matte = tmp_path / "m.png"
    matte.write_bytes(b"m")

    m = Material(source_id="wrong", frame_idx=None, selected=True)
    assert find_reusable_matte_path(m, str(src), []) is None

    rec = MatteRecord(
        source_id="id1",
        source_mtime=0.0,
        matte_path=str(matte),
        is_active=True,
    )
    m_ok = Material(source_id="id1", frame_idx=None, selected=True)
    # mtime mismatch
    assert find_reusable_matte_path(m_ok, str(src), [rec]) is None


def test_find_reusable_matte_path_hits_when_active_file_mtime_matches(tmp_path):
    from core.matte_cache import find_reusable_matte_path
    from models import Material, MatteRecord

    src = tmp_path / "a.png"
    src.write_bytes(b"dummy")
    mtime = src.stat().st_mtime

    matte = tmp_path / "m.png"
    matte.write_bytes(b"m")

    rec = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(matte),
        is_active=True,
    )
    m = Material(source_id="sid", frame_idx=None, selected=True)
    assert find_reusable_matte_path(m, str(src), [rec]) == str(matte)


def test_find_reusable_matte_path_ignores_inactive_or_missing_matte(tmp_path):
    from core.matte_cache import find_reusable_matte_path
    from models import Material, MatteRecord

    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    mtime = src.stat().st_mtime

    matte_ok = tmp_path / "ok.png"
    matte_ok.write_bytes(b"1")

    inactive = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(matte_ok),
        is_active=False,
    )
    missing_path = tmp_path / "gone.png"
    missing = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(missing_path),
        is_active=True,
    )
    m = Material(source_id="sid", frame_idx=None, selected=True)
    assert find_reusable_matte_path(m, str(src), [inactive, missing]) is None

    good = MatteRecord(
        source_id="sid",
        source_mtime=mtime,
        matte_path=str(matte_ok),
        is_active=True,
    )
    assert find_reusable_matte_path(m, str(src), [inactive, missing, good]) == str(matte_ok)
