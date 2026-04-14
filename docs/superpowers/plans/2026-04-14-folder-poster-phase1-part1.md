# Folder Poster Phase 1: Foundation & Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PyQt6 project structure, data models, state management, and file scanning logic for the Folder Poster tool.

**Architecture:** A PyQt6 application with a main window managing a stacked widget for navigation (HomePage). Core logic is separated into `core/` and data structures in `models.py`. State is persisted to a temp JSON file.

**Tech Stack:** Python 3.11, PyQt6, pytest.

---

### Task 1: Project Setup & Data Models

**Files:**
- Create: `requirements.txt`
- Create: `models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Setup requirements**

Create `requirements.txt`:
```text
PyQt6>=6.4.0
birefnet>=1.0.0
torch>=2.0.0
torchvision>=0.15.0
pillow>=9.0.0
pytoshop>=1.2.0
pytest>=7.0.0
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write failing test for models**

Create `tests/test_models.py`:
```python
import pytest
from models import ProjectState, ScannedFile, Material

def test_project_state_initialization():
    state = ProjectState(project_id="test_1", input_path="/tmp", mode="video")
    assert state.depth == 3
    assert len(state.scanned_files) == 0
    
def test_scanned_file():
    sf = ScannedFile(path="/tmp/vid.mp4", name="vid.mp4", type="video")
    assert sf.type == "video"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models'"

- [ ] **Step 4: Write minimal implementation**

Create `models.py`:
```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ScannedFile:
    path: str
    name: str
    type: str

@dataclass
class Material:
    source_id: str
    frame_idx: Optional[int]
    selected: bool

@dataclass
class MatteRecord:
    source_id: str
    source_mtime: float
    matte_path: str
    is_active: bool

@dataclass
class ProjectState:
    project_id: str
    input_path: str
    mode: str
    depth: int = 3
    scanned_files: List[ScannedFile] = field(default_factory=list)
    selected_materials: List[Material] = field(default_factory=list)
    matte_map: List[MatteRecord] = field(default_factory=list)
    current_step: str = "init"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt models.py tests/test_models.py
git commit -m "feat: add project requirements and core data models"
```

### Task 2: State Manager

**Files:**
- Create: `core/__init__.py`
- Create: `core/state_manager.py`
- Create: `tests/core/__init__.py`
- Create: `tests/core/test_state_manager.py`

- [ ] **Step 1: Write failing test for State Manager**

Create `tests/core/test_state_manager.py`:
```python
import os
import json
from models import ProjectState
from core.state_manager import StateManager

def test_save_and_load_state(tmp_path):
    temp_dir = tmp_path / "temp"
    manager = StateManager(str(temp_dir))
    
    state = ProjectState(project_id="proj_1", input_path="/test", mode="image")
    manager.save_state(state)
    
    file_path = temp_dir / "proj_1.json"
    assert file_path.exists()
    
    loaded_state = manager.load_state("proj_1")
    assert loaded_state.project_id == "proj_1"
    assert loaded_state.input_path == "/test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_state_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'core.state_manager'"

- [ ] **Step 3: Write minimal implementation**

Create `core/state_manager.py`:
```python
import os
import json
import dataclasses
from models import ProjectState, ScannedFile, Material, MatteRecord

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

class StateManager:
    def __init__(self, base_dir: str = "~/.folder-poster/temp"):
        self.base_dir = os.path.expanduser(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        
    def save_state(self, state: ProjectState):
        file_path = os.path.join(self.base_dir, f"{state.project_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, cls=EnhancedJSONEncoder, ensure_ascii=False, indent=2)
            
    def load_state(self, project_id: str) -> ProjectState:
        file_path = os.path.join(self.base_dir, f"{project_id}.json")
        if not os.path.exists(file_path):
            return None
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Convert nested dicts back to dataclasses
        data['scanned_files'] = [ScannedFile(**sf) for sf in data.get('scanned_files', [])]
        data['selected_materials'] = [Material(**m) for m in data.get('selected_materials', [])]
        data['matte_map'] = [MatteRecord(**mr) for mr in data.get('matte_map', [])]
        
        return ProjectState(**data)
```

Create `core/__init__.py` and `tests/core/__init__.py`:
```python
# Create empty files to mark as package
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_state_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/ tests/core/
git commit -m "feat: implement state manager for persisting project state"
```

### Task 3: File Scanner

**Files:**
- Create: `core/scanner.py`
- Create: `tests/core/test_scanner.py`

- [ ] **Step 1: Write failing test for File Scanner**

Create `tests/core/test_scanner.py`:
```python
import os
from core.scanner import scan_directory

def test_scan_directory(tmp_path):
    # Create mock directory structure
    (tmp_path / "img1.jpg").touch()
    (tmp_path / "vid1.mp4").touch()
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    (sub_dir / "img2.png").touch()
    (sub_dir / "vid2.mkv").touch()
    
    # Test image mode
    images = scan_directory(str(tmp_path), mode="image", max_depth=3)
    assert len(images) == 2
    assert all(f.type == "image" for f in images)
    assert any("img1.jpg" in f.name for f in images)
    
    # Test video mode
    videos = scan_directory(str(tmp_path), mode="video", max_depth=3)
    assert len(videos) == 2
    assert all(f.type == "video" for f in videos)
    
    # Test depth limit
    images_shallow = scan_directory(str(tmp_path), mode="image", max_depth=0)
    assert len(images_shallow) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_scanner.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write minimal implementation**

Create `core/scanner.py`:
```python
import os
from typing import List
from models import ScannedFile

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}
VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov'}

def scan_directory(base_path: str, mode: str, max_depth: int = 3) -> List[ScannedFile]:
    results = []
    base_path = os.path.abspath(base_path)
    base_depth = base_path.count(os.sep)
    
    target_exts = IMAGE_EXTS if mode == "image" else VIDEO_EXTS
    
    for root, dirs, files in os.walk(base_path):
        current_depth = root.count(os.sep) - base_depth
        if current_depth >= max_depth:
            dirs.clear() # Stop traversing deeper
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in target_exts:
                full_path = os.path.join(root, file)
                results.append(ScannedFile(
                    path=full_path,
                    name=file,
                    type=mode
                ))
                
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_scanner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/scanner.py tests/core/test_scanner.py
git commit -m "feat: implement recursive file scanner with depth limits"
```

### Task 4: PyQt6 UI Skeleton & Navigation

**Files:**
- Create: `ui/__init__.py`
- Create: `ui/pages/__init__.py`
- Create: `ui/main_window.py`
- Create: `ui/pages/home_page.py`
- Create: `main.py`

- [ ] **Step 1: Write UI Skeleton implementation**

Create `ui/pages/home_page.py`:
```python
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QRadioButton, QSpinBox, 
                             QHBoxLayout, QButtonGroup)

class HomePage(QWidget):
    def __init__(self, start_callback):
        super().__init__()
        self.start_callback = start_callback
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Folder Poster")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # Path Input
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("文件夹路径")
        browse_btn = QPushButton("浏览")
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # Mode Selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("模式:"))
        self.video_radio = QRadioButton("视频模式")
        self.video_radio.setChecked(True)
        self.image_radio = QRadioButton("图片模式")
        
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.video_radio)
        self.mode_group.addButton(self.image_radio)
        
        mode_layout.addWidget(self.video_radio)
        mode_layout.addWidget(self.image_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Depth Selection
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("递归深度:"))
        self.depth_spinner = QSpinBox()
        self.depth_spinner.setRange(1, 10)
        self.depth_spinner.setValue(3)
        depth_layout.addWidget(self.depth_spinner)
        depth_layout.addWidget(QLabel("层 (1-10)"))
        depth_layout.addStretch()
        layout.addLayout(depth_layout)
        
        # Start Button
        self.start_btn = QPushButton("开始扫描")
        self.start_btn.clicked.connect(self.on_start)
        layout.addWidget(self.start_btn)
        
        layout.addStretch()
        
    def on_start(self):
        path = self.path_input.text()
        mode = "video" if self.video_radio.isChecked() else "image"
        depth = self.depth_spinner.value()
        self.start_callback(path, mode, depth)
```

Create `ui/main_window.py`:
```python
from PyQt6.QtWidgets import QMainWindow, QStackedWidget
from ui.pages.home_page import HomePage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder Poster")
        self.resize(800, 600)
        
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        self.home_page = HomePage(self.handle_start_scan)
        self.stacked_widget.addWidget(self.home_page)
        
    def handle_start_scan(self, path, mode, depth):
        print(f"Scanning: {path}, Mode: {mode}, Depth: {depth}")
        # In a later task, we'll scan files and transition to MaterialPage
```

Create `main.py`:
```python
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```

Create `ui/__init__.py` and `ui/pages/__init__.py`:
```python
# Make modules packages
```

- [ ] **Step 2: Dry Run (Optional verify syntax)**

Run: `python -m py_compile main.py ui/main_window.py ui/pages/home_page.py`
Expected: No output.

- [ ] **Step 3: Commit**

```bash
git add ui/ main.py
git commit -m "feat: setup basic PyQt6 application skeleton and HomePage"
```
