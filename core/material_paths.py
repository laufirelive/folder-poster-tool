"""Resolve filesystem path to the raster image used for a selected ``Material``."""

from __future__ import annotations

import os

from models import Material, ProjectState, scanned_file_source_id_for_material


def resolve_material_raster_path(base_dir: str, state: ProjectState, m: Material) -> str | None:
    """
    Return absolute path to the PNG/JPEG used as matting input, or ``None`` if missing.

    - Image materials: the scanned file path.
    - Video materials: extracted preview frame ``frame_{frame_idx+1:03d}.png`` under
      ``base_dir / project_id / previews / source_id /``.
    """
    base_sid = scanned_file_source_id_for_material(m)
    sf = next((f for f in state.scanned_files if f.source_id == base_sid), None)
    if sf is None:
        return None
    if sf.type == "image":
        p = os.path.abspath(sf.path)
        return p if os.path.isfile(p) else None
    if sf.type == "video":
        if m.frame_idx is None:
            return None
        frame_n = m.frame_idx + 1
        p = os.path.join(
            os.path.expanduser(base_dir),
            state.project_id,
            "previews",
            base_sid,
            f"frame_{frame_n:03d}.png",
        )
        p = os.path.abspath(p)
        return p if os.path.isfile(p) else None
    return None
