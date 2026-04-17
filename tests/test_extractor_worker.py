"""Tests for incremental extractor worker behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


def _ensure_project_core_and_ui() -> None:
    root = str(Path(__file__).resolve().parents[1])
    sys.path.insert(0, root)
    bad = sys.modules.get("core")
    if bad is not None:
        f = (getattr(bad, "__file__", "") or "").replace("\\", "/")
        if f.endswith("/tests/core/__init__.py") or "/tests/core/" in f:
            del sys.modules["core"]
            for k in list(sys.modules):
                if k.startswith("core."):
                    del sys.modules[k]


_ensure_project_core_and_ui()

from ui.workers.extractor_worker import ExtractorWorker


@patch("ui.workers.extractor_worker.get_video_duration_seconds", return_value=10.0)
@patch("ui.workers.extractor_worker.extract_frames_at_slots")
def test_worker_emits_frame_ready_for_each_slot(mock_extract, _mock_duration, tmp_path):
    out_dir = tmp_path / "previews"

    def _fake_extract(_video, output, slot_map, frame_count):
        slot = next(iter(slot_map))
        path = out_dir / f"frame_{slot + 1:03d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        return [str(path)]

    mock_extract.side_effect = _fake_extract

    worker = ExtractorWorker("video.mp4", str(out_dir), frame_count=4)
    events: list[tuple[int, str]] = []
    done_paths: list[str] = []
    worker.frame_ready.connect(lambda slot, path: events.append((slot, path)))
    worker.finished_ok.connect(lambda paths: done_paths.extend(paths))
    worker.run()

    assert [slot for slot, _ in events[:4]] == [0, 1, 2, 3]
    assert len(done_paths) == 4


@patch("ui.workers.extractor_worker.get_video_duration_seconds", return_value=10.0)
@patch("ui.workers.extractor_worker.random_timestamps_for_slots", return_value={1: 1.0, 3: 3.0})
@patch("ui.workers.extractor_worker.extract_frames_at_slots")
def test_worker_regenerate_only_unselected_slots(
    mock_extract,
    _mock_ts,
    _mock_duration,
    tmp_path,
):
    out_dir = tmp_path / "previews"
    keep_path = out_dir / "frame_001.png"
    keep_path.parent.mkdir(parents=True, exist_ok=True)
    keep_path.write_bytes(b"k")

    def _fake_extract(_video, output, slot_map, frame_count):
        slot = next(iter(slot_map))
        path = out_dir / f"frame_{slot + 1:03d}.png"
        path.write_bytes(b"x")
        return [str(path)]

    mock_extract.side_effect = _fake_extract

    worker = ExtractorWorker(
        "video.mp4",
        str(out_dir),
        frame_count=4,
        regenerate=True,
        keep_indices=[0, 2],
    )
    events: list[int] = []
    worker.frame_ready.connect(lambda slot, _path: events.append(slot))
    worker.run()

    # 0 is emitted from existing cache, 1/3 regenerated, 2 has no cached file so no emit.
    assert 1 in events
    assert 3 in events
    assert 0 in events
