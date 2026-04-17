import pytest
from models import (
    Material,
    MatteRecord,
    ProjectState,
    ScannedFile,
    material_source_id_for_video,
    scanned_file_source_id_for_material,
)


def test_material_source_id_for_video_suffix():
    assert material_source_id_for_video("abc123", 0) == "abc123_frame_00"
    assert material_source_id_for_video("abc123", 5) == "abc123_frame_05"
    assert material_source_id_for_video("abc123", 31) == "abc123_frame_31"


def test_scanned_file_source_id_for_image_material():
    m = Material(source_id="hash_only", frame_idx=None, selected=True)
    assert scanned_file_source_id_for_material(m) == "hash_only"


def test_scanned_file_source_id_for_video_material_strips_frame_suffix():
    m = Material(source_id="vid01_frame_02", frame_idx=2, selected=True)
    assert scanned_file_source_id_for_material(m) == "vid01"


def test_project_state_initialization():
    state = ProjectState(project_id="test_1", input_path="/tmp", mode="video")
    assert state.depth == 3
    assert len(state.scanned_files) == 0
    
def test_scanned_file():
    sf = ScannedFile(path="/tmp/vid.mp4", name="vid.mp4", type="video")
    assert sf.type == "video"


def test_scanned_file_has_source_id():
    sf = ScannedFile(
        path="/tmp/a.mp4",
        name="a.mp4",
        type="video",
        source_id="abc123",
    )
    assert sf.source_id == "abc123"


def test_matte_record_mask_path_defaults_to_empty():
    rec = MatteRecord(
        source_id="id-1",
        source_mtime=123.0,
        matte_path="/tmp/matte.png",
        is_active=True,
    )
    assert rec.mask_path == ""


def test_matte_record_accepts_mask_path():
    rec = MatteRecord(
        source_id="id-1",
        source_mtime=123.0,
        matte_path="/tmp/matte.png",
        is_active=True,
        mask_path="/tmp/mask.png",
    )
    assert rec.mask_path == "/tmp/mask.png"
