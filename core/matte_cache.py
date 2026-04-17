"""Reuse existing mattes from ``ProjectState.matte_map`` when source image is unchanged."""

from __future__ import annotations

import os
from typing import Iterable, Optional

from models import Material, MatteRecord


def find_reusable_matte_paths(
    material: Material,
    source_path: str,
    matte_map: Iterable[MatteRecord],
) -> Optional[tuple[str, str]]:
    """
    Return ``(matte_path, mask_path)`` of an **active** cached pair for ``material.source_id``
    when both files exist on disk and ``source_mtime`` still matches current source mtime.
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
        if not rec.mask_path or not os.path.isfile(rec.mask_path):
            continue
        if abs(rec.source_mtime - mtime) > 1e-6:
            continue
        return rec.matte_path, rec.mask_path
    return None


def find_reusable_matte_path(
    material: Material,
    source_path: str,
    matte_map: Iterable[MatteRecord],
) -> Optional[str]:
    """Backward-compatible helper returning only ``matte_path``."""
    hit = find_reusable_matte_paths(material, source_path, matte_map)
    return hit[0] if hit is not None else None
