import os
import json
import dataclasses
from typing import Optional

from models import ProjectState, ScannedFile, Material, MatteRecord


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class StateManager:
    def __init__(self, base_dir: str = "~/.folder-poster/temp"):
        self.base_dir = os.path.expanduser(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def save_state(self, state: ProjectState):
        file_path = os.path.join(self.base_dir, f"{state.project_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, cls=EnhancedJSONEncoder, ensure_ascii=False, indent=2)

    def load_state(self, project_id: str) -> Optional[ProjectState]:
        file_path = os.path.join(self.base_dir, f"{project_id}.json")
        if not os.path.exists(file_path):
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Convert nested dicts back to dataclasses
        data["scanned_files"] = [ScannedFile(**sf) for sf in data.get("scanned_files", [])]
        data["selected_materials"] = [
            Material(**m) for m in data.get("selected_materials", [])
        ]
        matte_map = []
        for mr in data.get("matte_map", []):
            # Backward compatibility: old state files may not contain mask_path.
            if "mask_path" not in mr:
                mr = {**mr, "mask_path": ""}
            matte_map.append(MatteRecord(**mr))
        data["matte_map"] = matte_map

        return ProjectState(**data)
