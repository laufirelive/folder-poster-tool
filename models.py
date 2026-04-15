from dataclasses import dataclass, field
from typing import List, Optional


def material_source_id_for_video(base_source_id: str, frame_idx: int) -> str:
    """Return a ``Material.source_id`` unique to this video file and frame (0-based index)."""
    return f"{base_source_id}_frame_{frame_idx:02d}"


def scanned_file_source_id_for_material(m: "Material") -> str:
    """
    Return the ``ScannedFile.source_id`` for lookups.

    Image materials store the file hash directly. Video materials use
    ``material_source_id_for_video``; strip the ``_frame_XX`` suffix using ``frame_idx``.
    """
    if m.frame_idx is None:
        return m.source_id
    suffix = f"_frame_{m.frame_idx:02d}"
    if m.source_id.endswith(suffix):
        return m.source_id[: -len(suffix)]
    return m.source_id


@dataclass
class ScannedFile:
    path: str
    name: str
    type: str
    source_id: str = ""

@dataclass
class Material:
    source_id: str
    frame_idx: Optional[int]
    selected: bool

@dataclass
class MatteRecord:
    """``source_id`` matches ``Material.source_id`` (per-frame unique for video)."""

    source_id: str
    source_mtime: float
    matte_path: str
    is_active: bool

@dataclass
class ProjectState:
    project_id: str
    input_path: str
    mode: str
    depth: int = 3
    scanned_files: List[ScannedFile] = field(default_factory=list)
    selected_materials: List[Material] = field(default_factory=list)
    matte_map: List[MatteRecord] = field(default_factory=list)
    current_step: str = "init"
