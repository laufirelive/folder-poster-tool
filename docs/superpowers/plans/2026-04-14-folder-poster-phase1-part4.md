# Folder Poster Phase 1 Part 4: PSD Export & Finalization

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `core/psd_export.py` using `pytoshop` to write a fixed 2:3 canvas PSD with every **active** matte PNG centered on its own **hidden** layer; add a **完成页** (`ExportPage`) with success summary, default save folder, canvas size presets (default **4000×6000**), and **导出 PSD**; wire `MainWindow` so that when `MattingWorker` completes without cancel, the app navigates to the export page and runs export on demand (with optional “open containing folder” after success).

**Architecture:** Pure-Python `export_matte_psd(...)` accepts `List[MatteRecord]` (or iterable), `canvas_width` / `canvas_height`, and `output_psd_path`. It loads each matte PNG with Pillow, converts to RGBA, splits into per-channel `numpy.uint8` planes for `pytoshop.enums.ChannelId` (`red`/`green`/`blue`/`transparency`), and builds `pytoshop.user.nested_layers.Image` layers with `visible=False`, `top`/`left` computed to **center** the layer in the document. The document size is fixed via `nested_layers_to_psd(..., size=(canvas_width, canvas_height), color_mode=enums.ColorMode.rgb)`. The UI keeps disk and PSD work off the main thread using `QThread` + a thin `QObject` worker (mirror `MattingWorker`) so the window stays responsive on large files.

**Tech Stack:** Python 3.11+, PyQt6, Pillow, `pytoshop`, `numpy` (required by `pytoshop` layer paths; pin explicitly), `six` (undeclared dependency of `pytoshop` import chain—add to `requirements.txt`).

**Related spec:** `folder-poster-design.md` §1.2 PSD 规范, §3.6–3.7, §4.x PSD 生成流程.

---

## File structure (create / modify)

| Path | Responsibility |
|------|----------------|
| `requirements.txt` | Add `numpy>=1.24.0`, `six>=1.16.0` (verify versions against your Python) |
| `core/psd_export.py` | Build PSD from `matte_map` active records; center layers; hidden; 2:3 canvas |
| `tests/core/test_psd_export.py` | Unit tests: synthetic PNGs → PSD file exists, non-empty, optional sanity read |
| `ui/pages/export_page.py` | 完成页: summary, `QLineEdit` + browse, canvas preset combo + custom spins, export button, back button |
| `ui/workers/psd_export_worker.py` (optional) | `QObject` + `run(output_path, w, h)` signal `finished(ok, err)` — keeps `main_window` small |
| `ui/pages/matting_page.py` | Optional: bottom **导出 PSD** enabled when all rows terminal (success or error) to jump to export without relying on auto-nav only—**or** omit if product accepts **only** auto-navigation to 完成页 |
| `ui/main_window.py` | Stack `ExportPage`; on matting thread finish (not cancel): `current_step="export"`, show export page; connect export signals; run PSD worker; `QDesktopServices.openUrl` folder on success |

---

## Task 0: Dependencies (`numpy`, `six`)

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add pins**

Append (or insert with other runtime deps):

```
numpy>=1.24.0
six>=1.16.0
```

- [ ] **Step 2: Install and smoke-import**

Run: `pip install -r requirements.txt`

Run: `python -c "import numpy, six, pytoshop; from pytoshop.user.nested_layers import Image, nested_layers_to_psd"`

Expected: no `ModuleNotFoundError`.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: pin numpy and six for pytoshop PSD export"
```

---

## Task 1: `core/psd_export.py` (Pytoshop PSD creation)

**Files:**
- Create: `core/psd_export.py`
- Create: `tests/core/test_psd_export.py`

**Design notes:**
- **Inputs:** Only include `MatteRecord` entries with `is_active` true and `os.path.isfile(matte_path)`.
- **Canvas:** `canvas_width` × `canvas_height` must preserve 2:3 (e.g. 4000×6000, 2000×3000); validate with a simple ratio check (allow small float tolerance) or assert `width * 3 == height * 2` for integers.
- **Ordering:** Bottom-to-top in Photoshop = first layer in the list is often the bottom-most after PSD conventions—pick one order (e.g. same order as `matte_map`) and document in the module docstring.
- **Centering:** For an image of size `(iw, ih)`, `left = (canvas_width - iw) // 2`, `top = (canvas_height - ih) // 2` (PSD coordinates: `top`/`left` are inclusive pixel indices; set `right`/`bottom` from dimensions or let `Image` infer from channels—match patterns in `pytoshop.user.nested_layers`).
- **Visibility:** Each `Image` layer: `visible=False`.
- **Layer name:** Sanitize `os.path.basename(matte_path)` (max length Photoshop allows—truncate safely, e.g. 127 bytes UTF-8).
- **API sketch:**

```python
# core/psd_export.py — public entry
from typing import Iterable

from models import MatteRecord

def export_matte_psd(
    matte_records: Iterable[MatteRecord],
    canvas_width: int,
    canvas_height: int,
    output_path: str,
) -> None:
    """Write a PSD with one hidden layer per active matte, centered on a 2:3 canvas."""
    ...
```

- **Implementation path:** Use `PIL.Image.open(path).convert("RGBA")`, then `numpy.array` for R, G, B, A channels. Map to `pytoshop.enums.ChannelId.red/green/blue` and `transparency` (alpha). Build `Image(name=..., visible=False, top=..., left=..., channels={...})`, collect in a list, then `nested_layers_to_psd(layers, color_mode=enums.ColorMode.rgb, size=(canvas_width, canvas_height))`, open `output_path` binary and `psd.write(f)`.
- **Edge case:** Zero valid layers → raise `ValueError("no active matte images")` so the UI can show a message.

- [ ] **Step 1: Write failing test**

Create `tests/core/test_psd_export.py`:

```python
import os
from pathlib import Path

import pytest
from PIL import Image

from models import MatteRecord


def test_export_matte_psd_writes_file(tmp_path):
    from core.psd_export import export_matte_psd

    png_a = tmp_path / "a_matte.png"
    png_b = tmp_path / "b_matte.png"
    Image.new("RGBA", (100, 80), color=(255, 0, 0, 200)).save(png_a)
    Image.new("RGBA", (60, 120), color=(0, 255, 0, 180)).save(png_b)

    records = [
        MatteRecord(source_id="s1", source_mtime=0.0, matte_path=str(png_a), is_active=True),
        MatteRecord(source_id="s2", source_mtime=0.0, matte_path=str(png_b), is_active=False),
    ]
    out = tmp_path / "out.psd"
    export_matte_psd(records, 4000, 6000, str(out))

    assert out.is_file()
    assert out.stat().st_size > 100
```

Run: `pytest tests/core/test_psd_export.py -v`

Expected: FAIL (import error or missing function).

- [ ] **Step 2: Implement `export_matte_psd`**

Implement as per design notes; use `from pytoshop import enums` and `from pytoshop.user.nested_layers import Image, nested_layers_to_psd`.

- [ ] **Step 3: Run tests**

Run: `pytest tests/core/test_psd_export.py -v`

Expected: PASS.

- [ ] **Step 4: Optional read-back smoke**

Run a one-liner (or add a second test) using `pytoshop.core.PsdFile.read` on `out.psd` to assert `header.width == 4000` and `header.height == 6000` if read path works in your environment.

- [ ] **Step 5: Commit**

```bash
git add core/psd_export.py tests/core/test_psd_export.py
git commit -m "feat: export matte layers to centered hidden PSD (pytoshop)"
```

---

## Task 2: `ui/pages/export_page.py` (完成页 / Export Page UI)

**Files:**
- Create: `ui/pages/export_page.py`

**UI contract:**
- Constructor: `ExportPage(project_state: ProjectState, parent: QWidget | None = None)`.
- Read-only summary label, e.g. `✅ 抠像完成` and `共 {n} 张素材已抠像` where `n = len([r for r in state.matte_map if r.is_active])` (or `len(matte_map)` if failures never persist—match how `MainWindow` builds `matte_map`).
- **保存位置:** `QLineEdit`, default text `project_state.input_path`; **浏览** → `QFileDialog.getExistingDirectory`.
- **画布尺寸:** `QComboBox` with entries `4000 × 6000 (推荐)`, `2000 × 3000`, and `自定义`. When custom is selected, show two `QSpinBox` (min 2, max 30000) with width/height locked to 2:3 **or** only height editable and width computed—simplest is three fixed presets only (4000×6000, 2000×3000) plus custom pair with a label “须保持 2:3”.
- **导出 PSD** → `export_requested.emit(str output_path, int width, int height)`.
- **← 返回** → `back_requested.emit()`.

```python
# ui/pages/export_page.py — signals (sketch)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

class ExportPage(QWidget):
    export_requested = pyqtSignal(str, int, int)
    back_requested = pyqtSignal()
```

- Default output **file** path suggestion: `os.path.join(line_edit.text(), "folder_poster_export.psd")` (or include timestamp—YAGNI: fixed name is fine for v1).

- [ ] **Step 1: Create the widget file**

Implement layout per `folder-poster-design.md` §3.7; wire combo + optional spin boxes; validate non-empty directory before emit.

- [ ] **Step 2: Manual UI smoke**

Run the app with a mocked `ProjectState` (small harness in `if __name__ == "__main__"` guarded block) and click 浏览 / export (optional).

- [ ] **Step 3: Commit**

```bash
git add ui/pages/export_page.py
git commit -m "ui: add export (complete) page with path and canvas presets"
```

---

## Task 3: Tie together in `ui/main_window.py`

**Files:**
- Modify: `ui/main_window.py`
- Create: `ui/workers/psd_export_worker.py` (recommended)
- Optionally modify: `ui/pages/matting_page.py` (see below)

**Behavior:**
1. **Navigate after matting:** In `_on_matting_worker_finished`, when `not self._matting_cancel_requested` and `self._project_state` is not None, set `current_step = "export"`, save state, instantiate or refresh `ExportPage` with current `ProjectState`, add to `QStackedWidget` if first time (or call `set_state`), `setCurrentWidget(export_page)`.
2. **Cancel path:** Keep existing behavior (return to materials)—no export page.
3. **Export execution:** On `export_requested(path, w, h)`:
   - Prefer `QThread` + worker calling `export_matte_psd(self._project_state.matte_map, w, h, path)`.
   - On success: `QMessageBox.information`; `QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))` per spec §3.7.
   - On failure: `QMessageBox.critical` with exception text.
4. **Back from export:** `back_requested` → set `current_step = "matting"`, show matting page again (keep existing `MattingPage` instance if still in stack, or recreate from last specs—simplest: keep reference to `MattingPage` and do not delete it when switching to export, only `setCurrentWidget`).

**Worker sketch (`ui/workers/psd_export_worker.py`):**

```python
from PyQt6.QtCore import QObject, pyqtSignal

class PsdExportWorker(QObject):
    finished_ok = pyqtSignal()
    finished_err = pyqtSignal(str)

    def __init__(self, matte_map, width: int, height: int, output_path: str):
        super().__init__()
        self._matte_map = matte_map
        self._width = width
        self._height = height
        self._output_path = output_path

    def run(self) -> None:
        try:
            from core.psd_export import export_matte_psd
            export_matte_psd(self._matte_map, self._width, self._height, self._output_path)
        except Exception as exc:
            self.finished_err.emit(str(exc))
        else:
            self.finished_ok.emit()
```

- [ ] **Step 1: Add `PsdExportWorker`**

Create file as above; connect `finished_ok` / `finished_err` in `MainWindow`; ensure thread cleanup mirrors `MattingWorker` (`deleteLater`, `quit`).

- [ ] **Step 2: Extend `MainWindow`**

- Import `ExportPage`, `QUrl`, `QDesktopServices`.
- Fields: `self._export_page: ExportPage | None = None`, `self._psd_thread`, `self._psd_worker`.
- Implement navigation and slot handlers.

- [ ] **Step 3: (Optional) Matting page “导出 PSD”**

If §3.6 must show **导出 PSD** after completion: add `export_psd_requested = pyqtSignal()` on `MattingPage`, enable a button when `index == total - 1` for last row processed and worker finished—**or** enable when worker `finished` fires. Connect in `MainWindow` to the same handler as auto-navigation (show export page). If you **only** auto-navigate, this button is redundant; align with PM.

- [ ] **Step 4: End-to-end manual test**

- Run through: home → materials → matting → wait → export page appears.
- Choose folder + 4000×6000 → export → PSD opens in Finder/Explorer via folder reveal; open PSD in Photoshop/GIMP to confirm hidden layers.

- [ ] **Step 5: Commit**

```bash
git add ui/main_window.py ui/workers/psd_export_worker.py ui/pages/export_page.py
git commit -m "feat: wire PSD export page and background export worker"
```

---

## Self-review (plan author)

| Spec item | Task |
|-----------|------|
| 2:3 canvas, configurable size, default 4000×6000 | Task 2 presets; Task 1 `export_matte_psd` params |
| Layers = each matte, default hidden, centered | Task 1 `visible=False`, centering math |
| Save path + export + open folder | Task 2 + Task 3 |
| 完成页 summary | Task 2 |
| Navigate from matting completion | Task 3 `_on_matting_worker_finished` |

**Placeholder scan:** None intentional.

**Type consistency:** `MatteRecord` / `matte_map` matches `models.py`; `export_matte_psd` uses the same types as `StateManager` deserialization.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-14-folder-poster-phase1-part4.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. **REQUIRED SUB-SKILL:** `superpowers:subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints. **REQUIRED SUB-SKILL:** `superpowers:executing-plans`.

Which approach?
