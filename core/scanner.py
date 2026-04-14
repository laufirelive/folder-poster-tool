import hashlib
import os
from typing import List

from models import ScannedFile

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov"}


def _source_id_for_path(full_path: str) -> str:
    normalized = os.path.normcase(os.path.normpath(os.path.abspath(full_path)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def scan_directory(base_path: str, mode: str, max_depth: int = 3) -> List[ScannedFile]:
    results = []
    base_path = os.path.abspath(base_path)
    base_depth = base_path.count(os.sep)

    target_exts = IMAGE_EXTS if mode == "image" else VIDEO_EXTS

    for root, dirs, files in os.walk(base_path):
        current_depth = root.count(os.sep) - base_depth
        if current_depth >= max_depth:
            dirs.clear()  # Stop traversing deeper

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in target_exts:
                full_path = os.path.join(root, file)
                results.append(
                    ScannedFile(
                        path=full_path,
                        name=file,
                        type=mode,
                        source_id=_source_id_for_path(full_path),
                    )
                )

    return results
