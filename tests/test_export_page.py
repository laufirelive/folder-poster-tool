"""Tests for export page behavior."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from models import MatteRecord, ProjectState


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _root_on_path() -> None:
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)


def _state(tmp_path: Path) -> ProjectState:
    return ProjectState(
        project_id="p1",
        input_path=str(tmp_path),
        mode="image",
        matte_map=[MatteRecord("s1", 0.0, str(tmp_path / "m1.png"), True)],
    )


def test_timestamped_name_format(qapp, tmp_path):
    _root_on_path()
    from ui.pages.export_page import ExportPage

    page = ExportPage(_state(tmp_path))
    name = page._timestamped_psd_name()
    assert re.match(r"^folder_poster_export_\d{8}_\d{6}\.psd$", name)


def test_custom_size_respects_ratio_lock_toggle(qapp, tmp_path):
    _root_on_path()
    from ui.pages.export_page import ExportPage

    page = ExportPage(_state(tmp_path))
    page._size_combo.setCurrentIndex(2)  # 自定义

    page._lock_ratio.setChecked(True)
    page._width_spin.setValue(301)
    assert page._height_spin.value() == 451

    page._lock_ratio.setChecked(False)
    page._width_spin.setValue(500)
    h = page._height_spin.value()
    page._width_spin.setValue(700)
    assert page._height_spin.value() == h


def test_export_clicked_emits_timestamped_path(qapp, tmp_path):
    _root_on_path()
    from ui.pages.export_page import ExportPage

    page = ExportPage(_state(tmp_path))
    page._path_edit.setText(str(tmp_path))
    got: list[tuple[str, int, int]] = []
    page.export_requested.connect(lambda p, w, h: got.append((p, w, h)))
    page._on_export_clicked()

    assert len(got) == 1
    out_path, w, h = got[0]
    assert out_path.startswith(str(tmp_path))
    assert re.search(r"folder_poster_export_\d{8}_\d{6}\.psd$", out_path)
    assert (w, h) == (4000, 6000)


def test_set_exporting_toggles_button_state(qapp, tmp_path):
    _root_on_path()
    from ui.pages.export_page import ExportPage

    page = ExportPage(_state(tmp_path))
    page.set_exporting(True)
    assert not page._export_btn.isEnabled()
    assert page._export_btn.text() == "导出中..."

    page.set_exporting(False)
    assert page._export_btn.isEnabled()
    assert page._export_btn.text() == "导出 PSD"

