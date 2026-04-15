"""Reuse existing mattes from ``ProjectState.matte_map`` when source image is unchanged."""

from __future__ import annotations

import os
from typing import Iterable, Optional

from models import Material, MatteRecord


def find_reusable_matte_path(
    material: Material,
    source_path: str,
    matte_map: Iterable[MatteRecord],
) -> Optional[str]:
    """
    Return ``matte_path`` of an **active** cached matte for ``material.source_id`` when the
    file exists on disk and ``source_mtime`` still matches the current ``source_path`` mtime.
    Otherwise return ``None``.
    """
    if not source_path or not os.path.isfile(source_path):
        return None
    try:
        mtime = os.path.getmtime(source_path)
    except OSError:
        return None
    for rec in matte_map:
        if rec.source_id != material.source_id:
            continue
        if not rec.is_active:
            continue
        if not rec.matte_path or not os.path.isfile(rec.matte_path):
            continue
        if abs(rec.source_mtime - mtime) > 1e-6:
            continue
        return rec.matte_path
    return None
