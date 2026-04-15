"""Tests for MainWindow video modal wiring (initial_selected_indices)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

from models import Material, ProjectState, ScannedFile, material_source_id_for_video


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_video_frames_modal_gets_initial_selected_indices_from_state(qapp, tmp_path):
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

    vid = "vidsrc"
    sf = ScannedFile(path=str(tmp_path / "a.mp4"), name="a.mp4", type="video", source_id=vid)
    state = ProjectState(
        project_id="projx",
        input_path=str(tmp_path),
        mode="video",
        depth=1,
        scanned_files=[sf],
        selected_materials=[
            Material(source_id=material_source_id_for_video(vid, 1), frame_idx=1, selected=True),
            Material(source_id=material_source_id_for_video(vid, 4), frame_idx=4, selected=True),
        ],
    )

    fake_paths = [str(tmp_path / f"f{i}.png") for i in range(32)]
    for p in fake_paths:
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        Path(p).write_bytes(b"")

    construct_calls: list[tuple[tuple, dict]] = []

    def fake_modal(*args, **kwargs):
        construct_calls.append((args, kwargs))
        m = MagicMock()
        m.exec.return_value = QDialog.DialogCode.Accepted
        m.selected_frame_indices.return_value = [1, 4]
        return m

    with patch("ui.main_window.extract_preview_frames", return_value=fake_paths):
        with patch("ui.main_window.VideoFramesModal", side_effect=fake_modal):
            from ui.main_window import MainWindow

            win = MainWindow()
            win._state_manager.base_dir = str(tmp_path)
            win._project_state = state
            win._on_video_pick(vid)

    assert len(construct_calls) == 1
    _args, kwargs = construct_calls[0]
    assert kwargs.get("initial_selected_indices") == [1, 4]
