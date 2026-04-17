"""Tests for materials page video pick button labels."""

import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QFrame, QPushButton

from models import Material, ProjectState, ScannedFile, material_source_id_for_video


from unittest.mock import patch

def _sf(**kwargs):
    """ScannedFile with required fields for ProjectState."""
    defaults = {"path": "/x", "name": "x", "type": "video", "source_id": ""}
    defaults.update(kwargs)
    return ScannedFile(**defaults)


@pytest.fixture(autouse=True)
def mock_thumbnail_worker():
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    with patch.object(MaterialsPage, "_start_thumbnail_worker"):
        yield

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


def _video_cards(page):
    return [
        c
        for c in page.findChildren(QFrame)
        if c.objectName() == "MaterialCard" and c.property("sourceType") == "video"
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


def test_selected_video_card_sets_selected_property(qapp):
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    sid = "vid-card-select"
    sf = _sf(path="/v/a.mp4", name="a.mp4", type="video", source_id=sid)
    state = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[sf],
        selected_materials=[
            Material(source_id=material_source_id_for_video(sid, 3), frame_idx=3, selected=True)
        ],
    )
    page = MaterialsPage(state)
    cards = _video_cards(page)
    assert len(cards) == 1
    assert cards[0].property("selected") is True


def test_compute_layout_metrics_avoids_unstable_single_column(qapp):
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    state = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[_sf(path="/v/a.mp4", name="a.mp4", type="video", source_id="v1")],
        selected_materials=[],
    )
    page = MaterialsPage(state)

    cols, card_w = page._compute_layout_metrics(980)
    assert cols >= 3
    assert card_w >= 200


def test_toolbar_view_toggle_changes_mode_and_label(qapp):
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    state = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[_sf(path="/v/a.mp4", name="a.mp4", type="video", source_id="v1")],
        selected_materials=[],
    )
    page = MaterialsPage(state)
    assert page._view_btn.text() == "瀑布流 ▼"
    assert page._waterfall_mode is True

    page._view_btn.click()
    assert page._view_btn.text() == "等宽等高 ▼"
    assert page._waterfall_mode is False


def test_toolbar_size_slider_updates_target_width(qapp):
    _root_on_path()
    from ui.pages.materials_page import MaterialsPage

    state = ProjectState(
        project_id="p1",
        input_path="/in",
        mode="video",
        depth=1,
        scanned_files=[_sf(path="/v/a.mp4", name="a.mp4", type="video", source_id="v1")],
        selected_materials=[],
    )
    page = MaterialsPage(state)
    page._size_slider.setValue(320)

    assert page._card_target_width == 320


def test_image_thumb_loader_keeps_aspect_ratio(qapp, tmp_path):
    _root_on_path()
    from PIL import Image
    from ui.pages.materials_page import MaterialsPage

    img_path = tmp_path / "tall.png"
    Image.new("RGB", (80, 240), (30, 40, 50)).save(img_path)

    pm = MaterialsPage._load_thumb_quick(str(img_path), QSize(200, 120))
    assert not pm.isNull()
    ratio = pm.width() / max(1, pm.height())
    assert ratio < 0.5  # close to source ratio (1:3), not forced to 200:120


def test_toggle_view_mode_recomputes_image_thumb_height(qapp, tmp_path):
    _root_on_path()
    from PIL import Image
    from ui.pages.materials_page import MaterialsPage

    img_path = tmp_path / "square.png"
    Image.new("RGB", (200, 200), (100, 20, 30)).save(img_path)
    sid = "img1"
    state = ProjectState(
        project_id="p1",
        input_path=str(tmp_path),
        mode="image",
        depth=1,
        scanned_files=[ScannedFile(path=str(img_path), name="square.png", type="image", source_id=sid)],
        selected_materials=[],
    )
    page = MaterialsPage(state)

    thumb = page._card_refs[sid]["thumb"]
    h_before = thumb.height()
    page._view_btn.click()
    h_after = thumb.height()

    assert h_before != h_after
