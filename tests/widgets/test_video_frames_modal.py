"""Tests for VideoFramesModal multi-select, count label, clear, and regenerate."""

import sys
from pathlib import Path
from unittest.mock import patch

def _ensure_project_core_and_ui() -> None:
    """Pytest can put ``tests`` on ``sys.path`` so ``import core`` resolves to ``tests/core``."""
    root = str(Path(__file__).resolve().parents[2])
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

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from ui.widgets.video_frames_modal import VideoFramesModal


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _make_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pm = QPixmap(4, 4)
    pm.fill(Qt.GlobalColor.white)
    assert pm.save(str(path))


def _modal_paths(tmp_path: Path, n: int) -> tuple[list[str], str, str]:
    paths = []
    for i in range(n):
        p = tmp_path / f"frame_{i + 1:03d}.png"
        _make_png(p)
        paths.append(str(p.resolve()))
    video = str(tmp_path / "dummy.mp4")
    preview_dir = str(tmp_path)
    return paths, video, preview_dir


def test_selected_count_label_updates(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 4)
    modal = VideoFramesModal(paths, video, pdir, parent=None)
    label = modal.findChild(QLabel, "selected_count_label")
    assert label is not None
    assert label.text() == "Selected 0/32"

    modal._buttons[0].click()
    assert label.text() == "Selected 1/32"

    modal._buttons[1].click()
    assert label.text() == "Selected 2/32"

    modal._buttons[0].click()
    assert label.text() == "Selected 1/32"


def test_multi_select_toggle_and_selected_frame_indices(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 4)
    modal = VideoFramesModal(paths, video, pdir, parent=None)

    modal._buttons[0].click()
    modal._buttons[3].click()
    assert modal._buttons[0].isChecked()
    assert modal._buttons[3].isChecked()
    assert not modal._buttons[1].isChecked()
    assert modal.selected_frame_indices() == [0, 3]


def test_clear_selection(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 3)
    modal = VideoFramesModal(paths, video, pdir, parent=None)

    modal._buttons[0].click()
    modal._buttons[2].click()
    assert modal.selected_frame_indices() == [0, 2]

    clear_btn = modal.findChild(QPushButton, "clear_selection_btn")
    assert clear_btn is not None
    clear_btn.click()

    assert modal.selected_frame_indices() == []
    assert not modal._buttons[0].isChecked()
    assert not modal._buttons[2].isChecked()


def test_initial_selected_indices(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 5)
    modal = VideoFramesModal(
        paths, video, pdir, initial_selected_indices=[1, 4], parent=None
    )
    assert modal.selected_frame_indices() == [1, 4]
    assert modal.findChild(QLabel, "selected_count_label").text() == "Selected 2/32"


@patch("ui.widgets.video_frames_modal.regenerate_unselected_preview_frames")
def test_regenerate_calls_extractor_with_keep_indices(mock_regen, qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 4)
    mock_regen.return_value = []

    modal = VideoFramesModal(paths, video, pdir, parent=None)
    modal._buttons[0].click()
    modal._buttons[2].click()

    regen_btn = modal.findChild(QPushButton, "regenerate_btn")
    assert regen_btn is not None
    regen_btn.click()

    mock_regen.assert_called_once()
    args, kwargs = mock_regen.call_args
    assert args[0] == video
    assert args[1] == pdir
    assert list(args[2]) == [0, 2]


def test_accept_returns_sorted_selected_indices(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 3)
    modal = VideoFramesModal(paths, video, pdir, parent=None)
    modal._buttons[2].click()
    modal._buttons[0].click()
    modal.accept()

    assert modal.selected_frame_indices() == [0, 2]
