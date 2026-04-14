import pytest
from models import ProjectState, ScannedFile, Material

def test_project_state_initialization():
    state = ProjectState(project_id="test_1", input_path="/tmp", mode="video")
    assert state.depth == 3
    assert len(state.scanned_files) == 0
    
def test_scanned_file():
    sf = ScannedFile(path="/tmp/vid.mp4", name="vid.mp4", type="video")
    assert sf.type == "video"
