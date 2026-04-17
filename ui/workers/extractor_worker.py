from __future__ import annotations

import os
import random
from typing import Iterable

from PyQt6.QtCore import QObject, pyqtSignal

from core.extractor import (
    extract_frames_at_slots,
    get_video_duration_seconds,
    random_timestamps_for_slots,
)

class ExtractorWorker(QObject):
    frame_ready = pyqtSignal(int, str)  # slot index, absolute frame path
    finished_ok = pyqtSignal(list)
    finished_err = pyqtSignal(str)

    def __init__(
        self,
        video_path: str,
        output_dir: str,
        frame_count: int = 32,
        *,
        regenerate: bool = False,
        keep_indices: Iterable[int] | None = None,
    ):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.frame_count = frame_count
        self.regenerate = regenerate
        self.keep_indices = {int(i) for i in (keep_indices or [])}
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def _slot_output_path(self, slot: int) -> str:
        return os.path.abspath(
            os.path.join(self.output_dir, f"frame_{slot + 1:03d}.png")
        )

    def _emit_existing_frame_if_present(self, slot: int) -> str | None:
        path = self._slot_output_path(slot)
        if os.path.isfile(path):
            self.frame_ready.emit(slot, path)
            return path
        return None

    def run(self):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            duration = get_video_duration_seconds(self.video_path)
            paths: list[str] = []

            if self.regenerate:
                slots = sorted(set(range(self.frame_count)) - self.keep_indices)
                ts_map = random_timestamps_for_slots(duration, slots, random.Random())
            else:
                # Evenly split the timeline and take the midpoint of each segment.
                ts_map = {
                    slot: ((slot + 0.5) / self.frame_count) * duration
                    for slot in range(self.frame_count)
                }

            for slot in sorted(ts_map):
                if self._stop_requested:
                    break
                if slot in self.keep_indices:
                    existing = self._emit_existing_frame_if_present(slot)
                    if existing is not None:
                        paths.append(existing)
                    continue
                generated = extract_frames_at_slots(
                    self.video_path,
                    self.output_dir,
                    {slot: ts_map[slot]},
                    frame_count=self.frame_count,
                )
                if not generated:
                    continue
                frame_path = os.path.abspath(generated[0])
                self.frame_ready.emit(slot, frame_path)
                paths.append(frame_path)

            # Ensure full-slot availability is surfaced for any already-cached slots.
            for slot in range(self.frame_count):
                if self._stop_requested:
                    break
                existing = self._slot_output_path(slot)
                if os.path.isfile(existing):
                    if existing not in paths:
                        paths.append(existing)
                    self.frame_ready.emit(slot, existing)

            paths = sorted(set(paths))
            self.finished_ok.emit(paths)
        except Exception as e:
            self.finished_err.emit(str(e))
