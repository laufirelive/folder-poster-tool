"""Sequential BiRefNet matting in a worker thread."""

from __future__ import annotations

import os
import threading
from typing import List, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from core.birefnet import MattingEngine
from core.matte_cache import find_reusable_matte_paths
from models import Material, MatteRecord

RowWork = Tuple[str, str, Material]  # display_name, source_path, material


class MattingWorker(QObject):
    progress = pyqtSignal(int, int, str, str)  # index, total, source_path, display_name
    row_done = pyqtSignal(int, str, str, bool, str)  # index, matte_path, mask_path, ok, err_msg
    finished = pyqtSignal()

    def __init__(
        self,
        rows: List[RowWork],
        base_dir: str,
        project_id: str,
        cancel_event: threading.Event,
        matte_map: List[MatteRecord] | None = None,
    ) -> None:
        super().__init__()
        self._rows = rows
        self._base_dir = os.path.expanduser(base_dir)
        self._project_id = project_id
        self._cancel_event = cancel_event
        self._matte_map: List[MatteRecord] = list(matte_map or [])

    def run(self) -> None:
        engine = MattingEngine()
        total = len(self._rows)
        out_root = os.path.join(self._base_dir, self._project_id, "mattes")
        for i, (display_name, src_path, mat) in enumerate(self._rows):
            if self._cancel_event.is_set():
                break
            self.progress.emit(i, total, src_path, display_name)
            cached = find_reusable_matte_paths(mat, src_path, self._matte_map)
            if cached is not None:
                matte_path, mask_path = cached
                self.row_done.emit(i, os.path.abspath(matte_path), os.path.abspath(mask_path), True, "")
                continue
            stem = os.path.splitext(os.path.basename(src_path))[0]
            matte_out = os.path.join(out_root, f"{stem}_{i:03d}_matte.png")
            mask_out = os.path.join(out_root, f"{stem}_{i:03d}_mask.png")
            try:
                engine.predict_outputs(src_path, matte_out, mask_out)
                self.row_done.emit(
                    i,
                    os.path.abspath(matte_out),
                    os.path.abspath(mask_out),
                    True,
                    "",
                )
            except Exception as exc:  # noqa: BLE001 — surface to UI
                self.row_done.emit(i, "", "", False, str(exc))
        self.finished.emit()
