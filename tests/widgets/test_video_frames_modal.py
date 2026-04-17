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


@pytest.fixture(autouse=True)
def _disable_background_extract():
    with patch.object(VideoFramesModal, "_start_extraction") as mocked:
        yield mocked


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
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)
    label = modal.findChild(QLabel, "selected_count_label")
    assert label is not None
    assert label.text() == "已选 0/32"

    modal._selectors[0].click()
    assert label.text() == "已选 1/32"

    modal._selectors[1].click()
    assert label.text() == "已选 2/32"

    modal._selectors[0].click()
    assert label.text() == "已选 1/32"


def test_multi_select_toggle_and_selected_frame_indices(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)

    modal._selectors[0].click()
    modal._selectors[3].click()
    assert modal._selectors[0].isChecked()
    assert modal._selectors[3].isChecked()
    assert not modal._selectors[1].isChecked()
    assert modal.selected_frame_indices() == [0, 3]


def test_clear_selection(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)

    modal._selectors[0].click()
    modal._selectors[2].click()
    assert modal.selected_frame_indices() == [0, 2]

    clear_btn = modal.findChild(QPushButton, "clear_selection_btn")
    assert clear_btn is not None
    clear_btn.click()

    assert modal.selected_frame_indices() == []
    assert not modal._selectors[0].isChecked()
    assert not modal._selectors[2].isChecked()


def test_initial_selected_indices(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(
        paths, video, pdir, initial_selected_indices=[1, 4], parent=None
    )
    assert modal.selected_frame_indices() == [1, 4]
    assert modal.findChild(QLabel, "selected_count_label").text() == "已选 2/32"


def test_regenerate_triggers_async_extraction_with_keep_indices(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)

    modal = VideoFramesModal(paths, video, pdir, parent=None)
    modal._selectors[0].click()
    modal._selectors[2].click()

    calls = []
    modal._start_extraction = lambda regenerate: calls.append(regenerate)

    regen_btn = modal.findChild(QPushButton, "regenerate_btn")
    assert regen_btn is not None
    regen_btn.click()

    assert calls == [True]


def test_regenerate_clears_unselected_slots_before_async_start(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)
    modal._selectors[0].click()
    modal._selectors[4].click()

    modal._start_extraction = lambda regenerate: None
    regen_btn = modal.findChild(QPushButton, "regenerate_btn")
    assert regen_btn is not None
    regen_btn.click()

    assert modal.selected_frame_indices() == [0, 4]
    assert modal._paths[0] is not None
    assert modal._paths[4] is not None
    assert modal._paths[1] is None
    assert modal._paths[2] is None


def test_accept_returns_sorted_selected_indices(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)
    modal._selectors[2].click()
    modal._selectors[0].click()
    modal.accept()

    assert modal.selected_frame_indices() == [0, 2]


def test_modal_builds_32_slots_and_shows_loading_for_missing_frames(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 2)
    modal = VideoFramesModal(paths, video, pdir, parent=None)
    assert len(modal._buttons) == 32
    assert modal._buttons[0].isEnabled()
    assert modal._buttons[1].isEnabled()
    assert not modal._buttons[2].isEnabled()
    assert "加载" in modal._buttons[2].text()


def test_frame_ready_updates_slot_from_loading_to_clickable(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 1)
    modal = VideoFramesModal(paths, video, pdir, parent=None)
    target = tmp_path / "frame_004.png"
    _make_png(target)

    assert not modal._buttons[3].isEnabled()
    modal._on_frame_ready(3, str(target))
    assert modal._buttons[3].isEnabled()
    assert modal._paths[3] == str(target.resolve())


def test_incomplete_frames_auto_start_background_extraction(qapp, tmp_path, _disable_background_extract):
    paths, video, pdir = _modal_paths(tmp_path, 2)
    VideoFramesModal(paths, video, pdir, parent=None)
    _disable_background_extract.assert_called_once_with(regenerate=False)


def test_loading_spinner_animates_for_pending_slots(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 2)
    modal = VideoFramesModal(paths, video, pdir, parent=None)

    before_icon = modal._buttons[2].icon().pixmap(36, 36).toImage()
    modal._on_loading_tick()
    after1_icon = modal._buttons[2].icon().pixmap(36, 36).toImage()
    modal._on_loading_tick()
    after2_icon = modal._buttons[2].icon().pixmap(36, 36).toImage()

    assert modal._buttons[2].text() == "加载中"
    assert after1_icon != before_icon
    assert after2_icon != after1_icon


def test_selected_button_sets_selected_property_for_clear_highlight(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)

    assert modal._cards[1].property("selected") in (None, False)
    modal._selectors[1].click()
    assert modal._cards[1].property("selected") is True
    modal._selectors[1].click()
    assert modal._cards[1].property("selected") is False


def test_compute_columns_is_responsive_to_dialog_width(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)

    narrow_cols = modal._compute_columns(560)
    wide_cols = modal._compute_columns(1280)
    assert narrow_cols < wide_cols
    assert narrow_cols >= 2


def test_frame_detail_text_contains_resolution_and_path(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)
    pm = QPixmap(paths[0])
    text = modal._frame_detail_text(0, paths[0], pm)
    assert "槽位: 1/32" in text
    assert "尺寸: 4 x 4" in text
    assert f"文件: {paths[0]}" in text


def test_single_click_on_frame_button_toggles_selection(qapp, tmp_path):
    paths, video, pdir = _modal_paths(tmp_path, 32)
    modal = VideoFramesModal(paths, video, pdir, parent=None)

    assert not modal._selectors[5].isChecked()
    modal._buttons[5].click()
    assert modal._selectors[5].isChecked()
    modal._buttons[5].click()
    assert not modal._selectors[5].isChecked()
