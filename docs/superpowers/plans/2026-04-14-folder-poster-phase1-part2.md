# Folder Poster Phase 1 Part 2: Materials Selection & Video Frame Extraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement FFmpeg-based extraction of 32 evenly spaced preview frames per video, the materials list UI with thumbnails, a 32-frame picker modal for video mode, and navigation/state wiring from the home page so `ProjectState` reflects user selections.

**Architecture:** Core extraction lives in `core/extractor.py` (subprocess `ffprobe` + `ffmpeg`). The materials view (`ui/pages/materials_page.py`) shows scanned files in a scrollable grid; video rows open `ui/widgets/video_frames_modal.py` (a `QDialog`) to pick one of 32 frames by index. Image mode skips the modal and toggles selection directly. `MainWindow` owns `StateManager`, runs `scan_directory`, generates a `project_id`, updates `ProjectState.current_step`, and persists on meaningful changes.

**Tech Stack:** Python 3.11+, PyQt6, pytest, FFmpeg/ffprobe on PATH (documented prerequisite for runtime and integration tests).

---

## File structure (create / modify)

| Path | Responsibility |
|------|----------------|
| `models.py` | Add `source_id` on `ScannedFile` for stable `Material.source_id` linkage |
| `core/scanner.py` | Populate `source_id` when building each `ScannedFile` |
| `core/extractor.py` | `ffprobe` duration + `ffmpeg` extraction of exactly 32 PNG frames to a temp dir |
| `ui/pages/materials_page.py` | List/grid of scanned files, thumbnails, mode-specific actions, signals for selection changes |
| `ui/widgets/video_frames_modal.py` | Modal dialog: 32 frame previews, single selection, returns chosen `frame_idx` |
| `ui/main_window.py` | Stack: Home → Materials; build `ProjectState`; scan; save; wire signals |
| `tests/core/test_scanner.py` | Assert `source_id` present and stable |
| `tests/core/test_extractor.py` | Mock subprocess; test duration parsing and command assembly |
| `tests/test_models.py` | `ScannedFile` includes `source_id` |

---

### Task 1: Stable `source_id` on `ScannedFile`

**Files:**
- Modify: `models.py`
- Modify: `core/scanner.py`
- Modify: `tests/test_models.py`
- Modify: `tests/core/test_scanner.py`

- [ ] **Step 1: Write failing tests for `source_id`**

Append to `tests/test_models.py`:

```python
def test_scanned_file_has_source_id():
    from models import ScannedFile

    sf = ScannedFile(
        path="/tmp/a.mp4",
        name="a.mp4",
        type="video",
        source_id="abc123",
    )
    assert sf.source_id == "abc123"
```

Append to `tests/core/test_scanner.py` inside `test_scan_directory`, after building `images`, assert 16-char hex `source_id` and stability across two scans:

```python
    images = scan_directory(str(tmp_path), mode="image", max_depth=3)
    assert len(images) == 2
    by_path = {f.path: f.source_id for f in images}
    for sid in by_path.values():
        assert len(sid) == 16
    again = scan_directory(str(tmp_path), mode="image", max_depth=3)
    for f in again:
        assert f.source_id == by_path[f.path]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py tests/core/test_scanner.py -v`

Expected: FAIL (unknown field `source_id` or attribute error)

- [ ] **Step 3: Implement `source_id` in models and scanner**

Edit `models.py` — extend `ScannedFile`:

```python
@dataclass
class ScannedFile:
    path: str
    name: str
    type: str
    source_id: str = ""
```

Edit `core/scanner.py` — add imports and helper, set `source_id` when appending:

```python
import hashlib
import os
from typing import List

from models import ScannedFile

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov"}


def _source_id_for_path(full_path: str) -> str:
    normalized = os.path.normcase(os.path.normpath(os.path.abspath(full_path)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def scan_directory(base_path: str, mode: str, max_depth: int = 3) -> List[ScannedFile]:
    results = []
    base_path = os.path.abspath(base_path)
    base_depth = base_path.count(os.sep)

    target_exts = IMAGE_EXTS if mode == "image" else VIDEO_EXTS

    for root, dirs, files in os.walk(base_path):
        current_depth = root.count(os.sep) - base_depth
        if current_depth >= max_depth:
            dirs.clear()

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in target_exts:
                full_path = os.path.join(root, file)
                results.append(
                    ScannedFile(
                        path=full_path,
                        name=file,
                        type=mode,
                        source_id=_source_id_for_path(full_path),
                    )
                )

    return results
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_models.py tests/core/test_scanner.py -v`

Expected: PASS

- [ ] **Step 5: Regression — state manager still loads**

Run: `pytest tests/core/test_state_manager.py -v`

Expected: PASS (JSON round-trip includes new field; default `""` if missing in old files is acceptable if you add a migration step — optional: in `load_state`, use `ScannedFile(**{**sf, "source_id": sf.get("source_id") or _recompute})` — YAGNI unless you have saved JSON from Part 1 without `source_id`)

- [ ] **Step 6: Commit**

```bash
git add models.py core/scanner.py tests/test_models.py tests/core/test_scanner.py
git commit -m "feat: add stable source_id to ScannedFile for material linkage"
```

---

### Task 2: `core/extractor.py` — FFmpeg 32-frame extraction

**Files:**
- Create: `core/extractor.py`
- Create: `tests/core/test_extractor.py`

**Contract (implement exactly):**

```python
def get_video_duration_seconds(video_path: str) -> float:
    """Parse duration from ffprobe stdout; raise RuntimeError on ffprobe failure; ValueError if duration <= 0."""


def extract_preview_frames(video_path: str, output_dir: str, frame_count: int = 32) -> list[str]:
    """
    Extract exactly `frame_count` PNG images spaced evenly across the video timeline.
    Returns sorted list of absolute paths to written files (one per frame).
    Raises RuntimeError if ffmpeg fails or the expected number of PNG files is not written.
    """
```

- [ ] **Step 1: Write tests with mocked subprocess**

Create `tests/core/test_extractor.py`:

```python
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


def _ensure_project_core():
    _root = str(Path(__file__).resolve().parents[2])
    sys.path.insert(0, _root)
    bad = sys.modules.get("core")
    if bad is not None:
        f = (getattr(bad, "__file__", "") or "").replace("\\", "/")
        if f.endswith("/tests/core/__init__.py") or "/tests/core/" in f:
            del sys.modules["core"]
            for k in list(sys.modules):
                if k.startswith("core."):
                    del sys.modules[k]


def test_get_video_duration_parses_ffprobe_stdout():
    _ensure_project_core()
    from core.extractor import get_video_duration_seconds

    with patch("core.extractor.subprocess.run") as run:
        run.return_value = MagicMock(stdout="12.345\n", returncode=0)
        assert get_video_duration_seconds("/fake/video.mp4") == 12.345
        args, kwargs = run.call_args
        assert "ffprobe" in args[0][0]


def test_extract_preview_frames_invokes_ffmpeg_with_fps_and_frame_cap():
    _ensure_project_core()
    from core.extractor import extract_preview_frames
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmp:
        vp = os.path.join(tmp, "v.mp4")
        open(vp, "wb").close()
        out = os.path.join(tmp, "frames")

        fake_paths = [os.path.join(out, f"frame_{i:03d}.png") for i in range(1, 33)]

        with patch("core.extractor.get_video_duration_seconds", return_value=100.0):
            with patch("core.extractor.subprocess.run") as run:
                run.return_value = MagicMock(returncode=0)
                with patch("core.extractor.glob.glob", return_value=fake_paths):
                    paths = extract_preview_frames(vp, out, frame_count=32)
                assert len(paths) == 32
                assert paths == [os.path.abspath(p) for p in fake_paths]
                ffmpeg_calls = [c for c in run.call_args_list if c[0][0][0] == "ffmpeg"]
                assert len(ffmpeg_calls) == 1
                cmd = ffmpeg_calls[0][0][0]
                assert "-vf" in cmd
                vf_idx = cmd.index("-vf") + 1
                assert cmd[vf_idx] == "fps=32/100.0"
                assert "-frames:v" in cmd
                assert cmd[cmd.index("-frames:v") + 1] == "32"
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/core/test_extractor.py -v`

Expected: FAIL — module missing

- [ ] **Step 3: Implement `core/extractor.py`**

Create `core/extractor.py`:

```python
import os
import subprocess
import glob


def get_video_duration_seconds(video_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or "ffprobe failed")
    line = (completed.stdout or "").strip().splitlines()[0] if completed.stdout else ""
    duration = float(line)
    if duration <= 0:
        raise ValueError("invalid or zero duration")
    return duration


def extract_preview_frames(video_path: str, output_dir: str, frame_count: int = 32) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    duration = get_video_duration_seconds(video_path)
    fps_expr = f"{frame_count}/{duration}"
    pattern = os.path.join(output_dir, "frame_%03d.png")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vf",
        f"fps={fps_expr}",
        "-frames:v",
        str(frame_count),
        pattern,
    ]
    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or "ffmpeg failed")

    paths = sorted(glob.glob(os.path.join(output_dir, "frame_*.png")))
    if len(paths) != frame_count:
        raise RuntimeError(f"expected {frame_count} frames, got {len(paths)}")
    return [os.path.abspath(p) for p in paths]
```

Adjust test if your shell/OS quotes differ — the test checks `fps=32/100.0` string inside argv list.

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_extractor.py -v`

Expected: PASS

- [ ] **Step 5: Optional manual integration check (document only)**

Prerequisite: `ffmpeg` and `ffprobe` on PATH, a short sample `.mp4`.

```bash
python -c "
from core.extractor import extract_preview_frames
import tempfile, os
# set SAMPLE to a real file path
SAMPLE = 'sample.mp4'
with tempfile.TemporaryDirectory() as d:
    ps = extract_preview_frames(SAMPLE, d, 32)
    print(len(ps), ps[0])
"
```

- [ ] **Step 6: Commit**

```bash
git add core/extractor.py tests/core/test_extractor.py
git commit -m "feat: add ffmpeg-based 32-frame preview extraction"
```

---

### Task 3: Materials page UI (thumbnails + list)

**Files:**
- Create: `ui/pages/materials_page.py`
- Modify: `ui/pages/__init__.py` (export if needed)

**Behavior:**
- Constructor: `MaterialsPage(project_state: ProjectState, parent=None)` — hold reference, rebuild grid when `set_state` called.
- Display `state.scanned_files` in a `QScrollArea` + grid of `QFrame` cards: thumbnail (`QLabel` scaled pixmap), file name, and primary action: **video** → button “选择帧”; **image** → checkbox or “选用” toggle.
- Thumbnail loading: use `QPixmap` from file path for images; for video use first extracted frame if `preview_frames` cached on page instance, else a placeholder icon/text “视频” until frames exist (modal will populate cache — see Task 5).
- Signals:
  - `image_toggle_requested(source_id: str, selected: bool)`
  - `video_pick_requested(source_id: str)` — opens modal from outside (MainWindow) to keep extractor I/O out of the widget, OR modal opened from page — plan recommends **MainWindow** opens modal; then MaterialsPage only emits `video_pick_requested`.

- [ ] **Step 1: Create `ui/pages/materials_page.py`**

```python
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models import ProjectState


class MaterialsPage(QWidget):
    image_toggle_requested = pyqtSignal(str, bool)
    video_pick_requested = pyqtSignal(str)

    def __init__(self, project_state: ProjectState, parent=None):
        super().__init__(parent)
        self._state = project_state
        self._thumb_cache: dict[str, QPixmap] = {}

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._grid_layout = QGridLayout(self._container)
        self._grid_layout.setSpacing(12)
        self._scroll.setWidget(self._container)

        outer = QVBoxLayout(self)
        outer.addWidget(self._scroll)
        self._rebuild_grid()

    def set_state(self, state: ProjectState) -> None:
        self._state = state
        self._rebuild_grid()

    def set_video_thumbnail(self, source_id: str, pixmap: QPixmap) -> None:
        self._thumb_cache[source_id] = pixmap
        self._rebuild_grid()

    def _is_image_selected(self, source_id: str) -> bool:
        for m in self._state.selected_materials:
            if m.source_id == source_id and m.selected:
                return True
        return False

    def _clear_grid(self) -> None:
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _rebuild_grid(self) -> None:
        self._clear_grid()
        cols = 3
        for i, sf in enumerate(self._state.scanned_files):
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            v = QVBoxLayout(card)
            thumb = QLabel()
            thumb.setFixedSize(160, 90)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet("background: #222222; color: #aaaaaa;")

            if sf.type == "image":
                pm = QPixmap(sf.path)
                if not pm.isNull():
                    thumb.setPixmap(
                        pm.scaled(
                            thumb.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    thumb.setText("图片")
            else:
                cached = self._thumb_cache.get(sf.source_id)
                if cached is not None and not cached.isNull():
                    thumb.setPixmap(
                        cached.scaled(
                            thumb.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    thumb.setText("视频")

            name = QLabel(sf.name)
            name.setWordWrap(False)
            name.setToolTip(sf.path)

            v.addWidget(thumb)
            v.addWidget(name)

            if sf.type == "image":
                cb = QCheckBox("选用")
                cb.setChecked(self._is_image_selected(sf.source_id))
                cb.toggled.connect(
                    lambda checked, sid=sf.source_id: self.image_toggle_requested.emit(sid, checked)
                )
                v.addWidget(cb)
            else:
                btn = QPushButton("选择帧")
                btn.clicked.connect(
                    lambda checked=False, sid=sf.source_id: self.video_pick_requested.emit(sid)
                )
                v.addWidget(btn)

            self._grid_layout.addWidget(card, i // cols, i % cols)
```

- [ ] **Step 2: Manual run**

Run: `python -m py_compile ui/pages/materials_page.py`

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add ui/pages/materials_page.py
git commit -m "feat: add materials page with thumbnail grid and selection signals"
```

---

### Task 4: Video frames modal (32-frame picker)

**Files:**
- Create: `ui/widgets/__init__.py`
- Create: `ui/widgets/video_frames_modal.py`

- [ ] **Step 1: Create `ui/widgets/video_frames_modal.py`**

Grid: 8×4 `QToolButton` tiles with frame thumbnails; single-click selects; OK confirms. `selected_frame_index()` returns `0 .. len(frame_paths)-1`.

Create `ui/widgets/__init__.py` as an empty package marker (or `__all__ = []`).

```python
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QToolButton, QVBoxLayout


class VideoFramesModal(QDialog):
    def __init__(self, frame_paths: list[str], initial_index: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择视频帧")
        self.resize(1100, 520)

        self._paths = list(frame_paths)
        if self._paths:
            self._selected = max(0, min(initial_index, len(self._paths) - 1))
        else:
            self._selected = 0

        self._buttons: list[QToolButton] = []

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        cols = 8
        for i, p in enumerate(self._paths):
            btn = QToolButton()
            pm = QPixmap(p)
            if not pm.isNull():
                scaled = pm.scaled(
                    120,
                    68,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                btn.setIcon(QIcon(scaled))
            btn.setIconSize(QSize(120, 68))
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, idx=i: self._on_pick(idx))
            self._buttons.append(btn)
            grid.addWidget(btn, i // cols, i % cols)

        layout.addLayout(grid)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._highlight(self._selected)

    def _on_pick(self, idx: int) -> None:
        self._selected = idx
        self._highlight(idx)

    def _highlight(self, idx: int) -> None:
        for i, b in enumerate(self._buttons):
            b.setChecked(i == idx)

    def selected_frame_index(self) -> int:
        return self._selected
```

- [ ] **Step 2: Compile check**

Run: `python -m py_compile ui/widgets/video_frames_modal.py`

- [ ] **Step 3: Commit**

```bash
git add ui/widgets/__init__.py ui/widgets/video_frames_modal.py
git commit -m "feat: add 32-frame video picker modal"
```

---

### Task 5: Tie together — MainWindow, scan, navigation, `ProjectState`

**Files:**
- Modify: `ui/main_window.py`
- Modify: `ui/pages/home_page.py` (optional: wire browse folder `QFileDialog`)
- Modify: `main.py` (optional: no change)

**Data flow:**
1. User fills path/mode/depth on `HomePage`, clicks **开始扫描**.
2. `MainWindow.handle_start_scan`:
   - Validate folder exists (`os.path.isdir`).
   - `project_id = uuid.uuid4().hex`
   - `files = scan_directory(path, mode, depth)`
   - Build `ProjectState(project_id=..., input_path=path, mode=mode, depth=depth, scanned_files=files, current_step="materials")`
   - `StateManager.save_state(state)`
   - If `materials_page` not in stack, create and `addWidget`; `setCurrentWidget(materials_page)`
   - `materials_page.set_state(state)`

3. **Image mode:** on `image_toggle_requested`, update `selected_materials`: remove existing `Material` with same `source_id`, append `Material(source_id=..., frame_idx=None, selected=True)` or remove when deselected. Persist with `StateManager.save_state`.

4. **Video mode:** on `video_pick_requested(source_id)`:
   - Resolve `ScannedFile` by `source_id`
   - `out_dir = os.path.join(StateManager.base_dir, project_id, "previews", source_id)` — expose `base_dir` as property or pass temp root into `MainWindow`
   - `paths = extract_preview_frames(file.path, out_dir, 32)`
   - Load first frame thumbnail into materials page via `set_video_thumbnail(source_id, pixmap)`
   - Show `VideoFramesModal(paths, initial_index=0)`; if `exec() == Accepted`, `idx = modal.selected_frame_index()`
   - Upsert `Material(source_id=source_id, frame_idx=idx, selected=True)` in `selected_materials` (replace prior entry for same `source_id`)
   - `save_state`

5. **Back to home (optional YAGNI):** skip for Part 2 unless spec requires; otherwise add “返回” setting `current_step="init"`.

- [ ] **Step 1: Replace `ui/main_window.py` with wiring below**

Uses `StateManager.base_dir` for preview output under `{base_dir}/{project_id}/previews/{source_id}/`. Imports `QDialog.DialogCode` for accept comparison.

```python
import os
import uuid

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QMainWindow, QMessageBox, QStackedWidget

from core.extractor import extract_preview_frames
from core.scanner import scan_directory
from core.state_manager import StateManager
from models import Material, ProjectState
from ui.pages.home_page import HomePage
from ui.pages.materials_page import MaterialsPage
from ui.widgets.video_frames_modal import VideoFramesModal


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder Poster")
        self.resize(800, 600)

        self._state_manager = StateManager()
        self._project_state: ProjectState | None = None
        self._materials_page: MaterialsPage | None = None

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.home_page = HomePage(self.handle_start_scan)
        self.stacked_widget.addWidget(self.home_page)

    def handle_start_scan(self, path: str, mode: str, depth: int) -> None:
        path = path.strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "无效路径", "请选择存在的文件夹路径。")
            return

        files = scan_directory(path, mode, depth)
        if not files:
            QMessageBox.warning(self, "无文件", "该文件夹下没有匹配的文件。")
            return

        project_id = uuid.uuid4().hex
        state = ProjectState(
            project_id=project_id,
            input_path=os.path.abspath(path),
            mode=mode,
            depth=depth,
            scanned_files=files,
            current_step="materials",
        )
        self._state_manager.save_state(state)
        self._project_state = state

        if self._materials_page is None:
            self._materials_page = MaterialsPage(state, self)
            self._materials_page.image_toggle_requested.connect(self._on_image_toggle)
            self._materials_page.video_pick_requested.connect(self._on_video_pick)
            self.stacked_widget.addWidget(self._materials_page)
        else:
            self._materials_page.set_state(state)

        self.stacked_widget.setCurrentWidget(self._materials_page)

    def _on_image_toggle(self, source_id: str, selected: bool) -> None:
        if self._project_state is None:
            return
        mats = [m for m in self._project_state.selected_materials if m.source_id != source_id]
        if selected:
            mats.append(Material(source_id=source_id, frame_idx=None, selected=True))
        self._project_state.selected_materials = mats
        self._state_manager.save_state(self._project_state)
        if self._materials_page is not None:
            self._materials_page.set_state(self._project_state)

    def _on_video_pick(self, source_id: str) -> None:
        if self._project_state is None:
            return
        sf = next((f for f in self._project_state.scanned_files if f.source_id == source_id), None)
        if sf is None:
            return

        out_dir = os.path.join(
            self._state_manager.base_dir,
            self._project_state.project_id,
            "previews",
            source_id,
        )
        try:
            paths = extract_preview_frames(sf.path, out_dir, 32)
        except Exception as exc:
            QMessageBox.warning(self, "提取失败", str(exc))
            return

        pm = QPixmap(paths[0])
        if self._materials_page is not None and not pm.isNull():
            self._materials_page.set_video_thumbnail(source_id, pm)

        modal = VideoFramesModal(paths, initial_index=0, parent=self)
        if modal.exec() != QDialog.DialogCode.Accepted:
            return

        idx = modal.selected_frame_index()
        mats = [m for m in self._project_state.selected_materials if m.source_id != source_id]
        mats.append(Material(source_id=source_id, frame_idx=idx, selected=True))
        self._project_state.selected_materials = mats
        self._state_manager.save_state(self._project_state)
        if self._materials_page is not None:
            self._materials_page.set_state(self._project_state)
```

- [ ] **Step 2: Smoke test**

Run: `python main.py`

Manual: choose a folder with images → see grid; toggle selection; restart app optional (persistence already in Part 1).

- [ ] **Step 3: Full pytest suite**

Run: `pytest tests/ -v`

Expected: all green

- [ ] **Step 4: Commit**

```bash
git add ui/main_window.py ui/pages/home_page.py
git commit -m "feat: wire materials page, frame extraction, and project state updates"
```

---

## Self-review (plan author)

**Spec coverage:** Part 2 scope — materials UI (video + image), FFmpeg extractor for 32 frames, modal for video mode, `ProjectState` updates, home → materials navigation — mapped to Tasks 1–5.

**Placeholder scan:** No TBD/TODO; Task 2 contract uses prose instead of ellipsis; Tasks 3–5 include full Python listings for UI and wiring.

**Type consistency:** `Material.frame_idx` is `Optional[int]` — use `None` for image mode; video mode uses `0..31` (32 frames). `source_id` is `str` everywhere.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-14-folder-poster-phase1-part2.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task; review between tasks; use **superpowers:subagent-driven-development**.

2. **Inline Execution** — Run tasks in this session with checkpoints; use **superpowers:executing-plans**.

**Which approach?**
