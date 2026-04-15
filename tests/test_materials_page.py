"""Tests for materials page video pick button labels."""

import sys
from pathlib import Path

import pytest
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QPushButton

from models import Material, ProjectState, ScannedFile, material_source_id_for_video


def _sf(**kwargs):
    """ScannedFile with required fields for ProjectState."""
    defaults = {"path": "/x", "name": "x", "type": "video", "source_id": ""}
    defaults.update(kwargs)
    return ScannedFile(**defaults)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _root_on_path():
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)


def _video_pick_buttons(page) -> list[QPushButton]:
    return [
        b
        for b in page.findChildren(QPushButton)
        if b.text() == "选择帧" or (b.text().startswith("已选 ") and b.text().endswith(" 帧"))
    ]


def test_video_button_select_frames_when_none_selected(qapp):
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    sf = _sf(path="/v/a.mp4", name="a.mp4", type="video", source_id="abc123")
    state = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[sf],
        selected_materials=[],
    )
    page = MaterialsPage(state)
    vbtns = _video_pick_buttons(page)
    assert len(vbtns) == 1
    assert vbtns[0].text() == "选择帧"


def test_video_button_shows_selected_count(qapp):
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    sid = "vidhash"
    sf = _sf(path="/v/a.mp4", name="a.mp4", type="video", source_id=sid)
    mats = [
        Material(
            source_id=material_source_id_for_video(sid, 0),
            frame_idx=0,
            selected=True,
        ),
        Material(
            source_id=material_source_id_for_video(sid, 5),
            frame_idx=5,
            selected=True,
        ),
    ]
    state = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[sf],
        selected_materials=mats,
    )
    page = MaterialsPage(state)
    vbtns = _video_pick_buttons(page)
    assert len(vbtns) == 1
    assert vbtns[0].text() == "已选 2 帧"


def test_set_state_updates_video_button_text(qapp):
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    sid = "vidhash"
    sf = _sf(path="/v/a.mp4", name="a.mp4", type="video", source_id=sid)
    state0 = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[sf],
        selected_materials=[],
    )
    page = MaterialsPage(state0)
    assert _video_pick_buttons(page)[0].text() == "选择帧"

    state1 = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[sf],
        selected_materials=[
            Material(source_id=material_source_id_for_video(sid, 1), frame_idx=1, selected=True)
        ],
    )
    page.set_state(state1)
    assert _video_pick_buttons(page)[0].text() == "已选 1 帧"


def test_video_thumbnail_refresh_keeps_button_label(qapp, tmp_path):
    """set_video_thumbnail triggers rebuild; selection label must stay correct."""
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    sid = "vidhash"
    sf = _sf(path="/v/a.mp4", name="a.mp4", type="video", source_id=sid)
    state = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[sf],
        selected_materials=[
            Material(source_id=material_source_id_for_video(sid, 2), frame_idx=2, selected=True)
        ],
    )
    page = MaterialsPage(state)
    pm = QPixmap(8, 8)
    pm.fill()
    page.set_video_thumbnail(sid, pm)
    assert _video_pick_buttons(page)[0].text() == "已选 1 帧"
