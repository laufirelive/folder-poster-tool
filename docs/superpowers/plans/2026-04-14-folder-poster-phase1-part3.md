# Folder Poster Phase 1 Part 3: BiRefNet Matting Engine & Progress UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the non-installable `birefnet` PyPI dependency with a Hugging Face `transformers`-based BiRefNet pipeline, expose a small matting API in `core/birefnet.py`, build the matting progress page (dual-pane thumbnails + progress bar), and wire navigation from the materials page so selected `Material`s flow into matting with `ProjectState` updated (`matte_map`, `current_step`).

**Architecture:** `core/birefnet.py` owns lazy model load, single-image inference (batch = sequential loop in the worker), and writing `{basename}_matte.png` under the project cache. The UI runs inference off the main thread via `QThread` + signals so the window stays responsive. `MattingPage` receives `ProjectState` + resolved raster paths per material; it displays left=source / right=matte and reflects row-level status (pending / running / done / error). `MainWindow` adds the page to `QStackedWidget`, connects Materials **下一步**, and persists state through existing `StateManager`.

**Tech Stack:** Python 3.11+, PyQt6, PyTorch, `transformers`, Pillow; Hugging Face model `ZhengPeng7/BiRefNet` (verify `trust_remote_code` / preprocessor requirements on the model card at implementation time). Remove invalid `birefnet` from `requirements.txt` and add `transformers` (and any peer deps the model card lists, e.g. `accelerate`, `timm`—only if required).

**Related spec:** `folder-poster-design.md` §3.6, §4.x (matting), §5 (original birefnet-gui path—**superseded** by HF + `transformers` for installability).

---

## File structure (create / modify)

| Path | Responsibility |
|------|----------------|
| `requirements.txt` | Drop `birefnet`; add `transformers` (+ optional deps per HF model card); keep `torch` / `torchvision` / `pillow` |
| `core/birefnet.py` | `MattingEngine`: device selection, lazy `transformers` load for `ZhengPeng7/BiRefNet`, `predict_matte(input_path, output_path) -> None`, optional env-based stub for tests/CI |
| `tests/core/test_birefnet.py` | Unit tests with `unittest.mock` for heavy imports; test output file created and basic PIL sanity |
| `ui/pages/matting_page.py` | Progress UI: global progress bar, current file label, scrollable left/right grids, per-row status; signals: `cancel_requested`, `matting_finished` (or similar) |
| `ui/pages/materials_page.py` | Footer: **下一步** `QPushButton`, enabled iff `len(selected_materials) >= 1`; signal `next_requested` |
| `ui/main_window.py` | Add `MattingPage` to stack; on `next_requested`, set `current_step`, navigate, start `QThread` worker that calls `MattingEngine` per material; update `matte_map` + save; map each `Material` to a source raster path (image `sf.path` or video `previews/{source_id}/frame_{idx+1:03d.png}`) |

---

## Chunk 1: Dependencies and `core/birefnet.py`

### Task 1: Fix dependencies (remove fake `birefnet` package)

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Edit `requirements.txt`**

Remove the line `birefnet>=1.0.0`. Add `transformers>=4.38.0` (pin higher if the model card requires). Add a comment that optional packages (`accelerate`, `timm`, etc.) should be added only if `ZhengPeng7/BiRefNet` fails to load without them.

- [ ] **Step 2: Install and smoke-import**

Run: `pip install -r requirements.txt`

Run: `python -c "import transformers; print(transformers.__version__)"`

Expected: prints a version string with no ImportError.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: use transformers for BiRefNet, drop nonexistent birefnet"
```

---

### Task 2: `MattingEngine` in `core/birefnet.py` (HF `ZhengPeng7/BiRefNet`)

**Files:**
- Create: `core/birefnet.py`
- Create: `tests/core/test_birefnet.py`

**Design notes (implementer must read HF model card):**
- Use `transformers` to load `ZhengPeng7/BiRefNet`. Many BiRefNet ports use custom code or a specific `AutoModel` class; follow the official README on Hugging Face for preprocessing (resize normalization) and output tensor shape (foreground mask).
- Prefer **single-image** API used in a loop from the UI worker (matches design: sequential processing to limit GPU memory).
- Device: `cuda` if available, else `mps` on macOS if `torch.backends.mps.is_available()`, else `cpu`.
- Output: RGBA PNG with original RGB and alpha from the predicted mask (or RGB + separate mask file—**pick one** and document in module docstring; spec prefers layered PSD input later, so RGBA is a good default).

- [ ] **Step 1: Write failing test (mocked inference)**

Create `tests/core/test_birefnet.py`:

```python
import os
from unittest.mock import MagicMock, patch

def test_predict_matte_writes_file(tmp_path):
    from PIL import Image

    inp = tmp_path / "in.png"
    Image.new("RGB", (32, 32), color=(255, 0, 0)).save(inp)
    out = tmp_path / "out_matte.png"

    mock_model = MagicMock()
    # Configure mock forward to return a mask-like tensor; shape must match your implementation's unpack logic

    with patch("core.birefnet._load_model", return_value=(mock_model, MagicMock())):
        from core.birefnet import MattingEngine

        eng = MattingEngine()
        eng.predict_matte(str(inp), str(out))

    assert out.is_file()
    im = Image.open(out)
    assert im.mode in ("RGBA", "RGB")
```

Adjust the mock after you define real `_load_model` / forward handling.

Run: `pytest tests/core/test_birefnet.py -v`

Expected: FAIL (module or class missing).

- [ ] **Step 2: Implement `MattingEngine` skeleton**

Create `core/birefnet.py` with:
- `MODEL_ID = "ZhengPeng7/BiRefNet"`
- Class `MattingEngine` with `__init__(self)`, lazy `_ensure_loaded(self)`, and `predict_matte(self, input_path: str, output_path: str) -> None`.
- If environment variable `FOLDER_POSTER_MATTING_STUB=1`, skip torch and write a trivial RGBA copy of the input (for CI and dev without GPU).

- [ ] **Step 3: Run tests**

Run: `pytest tests/core/test_birefnet.py -v`

Expected: PASS (with stub or mock).

- [ ] **Step 4: Manual GPU smoke (optional on dev machine)**

Run: `FOLDER_POSTER_MATTING_STUB=0 python -c "from core.birefnet import MattingEngine; e=MattingEngine(); ..."` on a real PNG.

Expected: writes a matte file without crash (first run may download weights).

- [ ] **Step 5: Commit**

```bash
git add core/birefnet.py tests/core/test_birefnet.py
git commit -m "feat(core): MattingEngine via transformers BiRefNet"
```

---

## Chunk 2: `ui/pages/matting_page.py`

### Task 3: Matting progress page UI

**Files:**
- Create: `ui/pages/matting_page.py`

**UI contract (minimum for Part 3):**
- Constructor accepts `parent` and holds references to `ProjectState` and a **precomputed** ordered list of items: `(display_name, source_image_path, material_key)` where `material_key` is enough to correlate with `Material` / `MatteRecord` (e.g. `source_id` + `frame_idx`).
- Top: `QProgressBar` (0–100) + `QLabel` for “当前文件” and “剩余 n/m”.
- Center: `QHBoxLayout` with two `QScrollArea`s: **left** “原始”, **right** “抠像结果”. Each side uses a grid of small preview `QLabel`s with consistent row order.
- Row states: show text or icon for 等待 / 处理中 / 完成 / 失败 (can be emoji or QLabel text for speed).
- Bottom: `QPushButton` “取消” (emit `cancel_requested`), `QPushButton` “导出 PSD” **disabled** with tooltip “Part 4” or hidden until Part 4 exists—YAGNI: either disable + TODO or omit button until export exists; **prefer** single **取消** for Part 3 to match scope.

Signals:
- `cancel_requested = pyqtSignal()`
- `retry_requested(str)` optional for Part 3.5; **omit** if not implementing retry yet.

Methods:
- `set_row_status(index, status, matte_preview_path: str | None)` where `status` is an Enum or string.
- `set_overall_progress(percent: int)`, `set_current_label(name: str, remaining: tuple[int, int])`.

- [ ] **Step 1: Create layout-only widget**

Implement `matting_page.py` with placeholder thumbnails (empty `QLabel` or gray pixmap).

- [ ] **Step 2: Manual UI check**

Run the app, navigate to the page with mock data (temporary harness in `main_window` or a `if __name__ == "__main__"` block—remove before commit **or** keep a guarded demo).

Expected: window shows dual panes and progress bar without crash.

- [ ] **Step 3: Commit**

```bash
git add ui/pages/matting_page.py
git commit -m "feat(ui): matting progress page layout"
```

---

## Chunk 3: `main_window.py` + materials **下一步**

### Task 4: Materials page — **下一步** button

**Files:**
- Modify: `ui/pages/materials_page.py`

- [ ] **Step 1: Add signal and footer**

```python
next_requested = pyqtSignal()
```

Add a bottom `QHBoxLayout`: stretch + `QPushButton("下一步")` connected to `next_requested.emit`. Enable button only when `len([m for m in self._state.selected_materials if m.selected]) >= 1` inside `_rebuild_grid()` (and when `set_state` runs).

- [ ] **Step 2: Commit**

```bash
git add ui/pages/materials_page.py
git commit -m "feat(ui): materials page next button to matting"
```

---

### Task 5: Path resolution helper (material → raster file)

**Files:**
- Modify: `core/birefnet.py` **or** new `core/material_paths.py` **or** private method on `MainWindow`

Pick **one** place to avoid duplication. Suggested: `core/material_paths.py`:

```python
def resolve_material_raster_path(state: ProjectState, m: Material) -> str:
    ...
```

Logic:
- Find `ScannedFile` by `m.source_id`.
- If `type == "image"`: return `sf.path`.
- If `type == "video"`: require `m.frame_idx is not None`; build path under `StateManager.base_dir / project_id / "previews" / source_id / f"frame_{m.frame_idx + 1:03d}.png"` (verify alignment with `extract_preview_frames` naming `frame_%03d.png` starting at 001).

- [ ] **Step 1: Write test**

Create `tests/core/test_material_paths.py` with a fake `ProjectState` and assert paths.

- [ ] **Step 2: Implement and run**

Run: `pytest tests/core/test_material_paths.py -v`

- [ ] **Step 3: Commit**

```bash
git add core/material_paths.py tests/core/test_material_paths.py
git commit -m "feat(core): resolve raster path for Material"
```

*(If implemented as methods inside `main_window.py` only, adjust test location to `tests/test_material_paths.py` and import the function from the chosen module.)*

---

### Task 6: `MainWindow` — stack, navigation, worker thread

**Files:**
- Modify: `ui/main_window.py`
- Optionally create: `ui/workers/matting_worker.py` (if you prefer not to bloat `main_window.py`)

**Behavior:**
- On `MaterialsPage.next_requested`:
  - If no selection, show warning (defensive; button should be disabled).
  - Set `project_state.current_step = "matting"` and `save_state`.
  - Build list of materials + raster paths; if any path missing (e.g. video without extracted frame), show `QMessageBox` and abort.
  - Show `MattingPage` with initial row list; start background matting.

**Worker pattern:**

```python
class MattingWorker(QObject):
    progress = pyqtSignal(int, int, str, str)  # index, total, source_path, name
    row_done = pyqtSignal(int, str, bool, str)  # index, matte_path, ok, err_msg
    finished = pyqtSignal()

    def run(self): ...
```

- Instantiate `MattingEngine()` inside the worker **or** in main thread and pass to worker (careful with thread safety—**create engine in worker thread** is simplest).
- For each index, emit progress, call `predict_matte`, emit `row_done`, append `MatteRecord` to a list; on completion, assign `self._project_state.matte_map = records` and `save_state`.
- On cancel: set a `threading.Event` checked between items and exit early; pop stack back to materials and optionally reset `current_step`.

- [ ] **Step 1: Wire navigation only (no real model)**

Use `FOLDER_POSTER_MATTING_STUB=1` in dev to validate UI flow.

- [ ] **Step 2: Enable real model**

Unset stub locally; confirm one real image processes.

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add ui/main_window.py ui/workers/matting_worker.py  # if created
git commit -m "feat(ui): navigate to matting page and run BiRefNet worker"
```

---

## Execution handoff checklist

- [ ] `requirements.txt` has no `birefnet` line.
- [ ] `core/birefnet.py` documents stub env var and real HF model id.
- [ ] Materials page exposes `next_requested` and enables **下一步** only when selection non-empty.
- [ ] `MainWindow` updates `ProjectState.current_step`, `matte_map`, and persists via `StateManager`.
- [ ] Matting runs off the main thread; UI updates via signals only.

---

## Plan review loop (@superpowers:writing-plans)

After drafting each **Chunk**, optionally run **plan-document-reviewer** (see `plan-document-reviewer-prompt.md`) with the chunk text + path `folder-poster-design.md` until approved.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-14-folder-poster-phase1-part3.md`. Ready to execute?**

**Execution path:** Prefer @superpowers:subagent-driven-development (one subagent per task / task group) with verification from @superpowers:verification-before-completion before merging.
