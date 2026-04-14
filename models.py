from dataclasses import dataclass, field
from typing import List, Optional

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
