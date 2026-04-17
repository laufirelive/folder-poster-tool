# Mask-Based PSD Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace RGBA-layer PSD export with `original image layer + editable layer mask`, while still producing RGBA previews for UI.

**Architecture:** Extend matting output to generate two artifacts (`matte` and `mask`), persist both in state/cache, and switch PSD export to read source raster + mask for each active material. Keep current UI flow unchanged except for using the new mask-backed export path.

**Tech Stack:** Python, PyQt6, Pillow, pytoshop, pytest

---

## File Structure

- Modify: `models.py`
  - Add `mask_path` field to `MatteRecord`.
- Modify: `core/state_manager.py`
  - Backward-compatible load for old state JSON without `mask_path`.
- Modify: `core/birefnet.py`
  - Add dual-output inference API: write RGBA + grayscale mask.
- Modify: `core/matte_cache.py`
  - Cache hit requires both matte and mask files.
- Modify: `ui/workers/matting_worker.py`
  - Emit both output paths from worker.
- Modify: `ui/main_window.py`
  - Persist `mask_path` into `ProjectState.matte_map`.
- Modify: `core/psd_export.py`
  - Build PSD layers from source image + mask-based layer mask (not baked RGBA alpha only).
- Modify tests:
  - `tests/test_models.py`
  - `tests/core/test_state_manager.py`
  - `tests/core/test_birefnet.py`
  - `tests/core/test_matte_cache.py`
  - `tests/test_matting_worker.py`
  - `tests/core/test_psd_export.py`

---

### Task 1: Data Model + State Compatibility

**Files:**
- Modify: `models.py`
- Modify: `core/state_manager.py`
- Test: `tests/test_models.py`
- Test: `tests/core/test_state_manager.py`

- [ ] **Step 1: Write failing tests for `mask_path` field and legacy-load behavior**

```python
# tests/test_models.py
from models import MatteRecord

def test_matte_record_has_mask_path():
    rec = MatteRecord("s", 1.0, "/tmp/a.png", "/tmp/a_mask.png", True)
    assert rec.mask_path.endswith("_mask.png")

# tests/core/test_state_manager.py
import json
from core.state_manager import StateManager

def test_load_legacy_state_without_mask_path(tmp_path):
    mgr = StateManager(base_dir=str(tmp_path))
    raw = {
        "project_id": "p",
        "input_path": "/x",
        "mode": "image",
        "matte_map": [
            {
                "source_id": "s1",
                "source_mtime": 1.0,
                "matte_path": "/tmp/m.png",
                "is_active": True,
            }
        ],
    }
    (tmp_path / "p.json").write_text(json.dumps(raw), encoding="utf-8")
    state = mgr.load_state("p")
    assert state is not None
    assert state.matte_map[0].mask_path == ""
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_models.py tests/core/test_state_manager.py -q`
Expected: FAIL due to `MatteRecord` signature mismatch and/or missing `mask_path` default mapping.

- [ ] **Step 3: Implement minimal model/state changes**

```python
# models.py
@dataclass
class MatteRecord:
    source_id: str
    source_mtime: float
    matte_path: str
    mask_path: str
    is_active: bool

# core/state_manager.py
data["matte_map"] = [
    MatteRecord(
        source_id=mr["source_id"],
        source_mtime=mr["source_mtime"],
        matte_path=mr.get("matte_path", ""),
        mask_path=mr.get("mask_path", ""),
        is_active=mr.get("is_active", True),
    )
    for mr in data.get("matte_map", [])
]
```

- [ ] **Step 4: Re-run tests and verify pass**

Run: `pytest tests/test_models.py tests/core/test_state_manager.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add models.py core/state_manager.py tests/test_models.py tests/core/test_state_manager.py
git commit -m "feat: add mask_path to matte records with legacy state compatibility"
```

---

### Task 2: Dual Matting Outputs (RGBA + Mask)

**Files:**
- Modify: `core/birefnet.py`
- Test: `tests/core/test_birefnet.py`

- [ ] **Step 1: Add failing tests for dual outputs**

```python
# tests/core/test_birefnet.py
from core.birefnet import MattingEngine
from PIL import Image

def test_predict_outputs_matte_and_mask_in_stub(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLDER_POSTER_MATTING_STUB", "1")
    src = tmp_path / "in.png"
    matte = tmp_path / "out_matte.png"
    mask = tmp_path / "out_mask.png"
    Image.new("RGB", (10, 8), (1, 2, 3)).save(src)

    MattingEngine().predict_outputs(str(src), str(matte), str(mask))

    assert matte.is_file()
    assert mask.is_file()
    assert Image.open(mask).mode == "L"
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/core/test_birefnet.py -q`
Expected: FAIL because `predict_outputs` is missing.

- [ ] **Step 3: Implement dual-output API in engine**

```python
# core/birefnet.py (new method)
def predict_outputs(self, input_path: str, matte_path: str, mask_path: str) -> None:
    # generate mask (PIL L) from model/stub
    # save RGBA preview to matte_path
    # save grayscale mask to mask_path

# keep compatibility shim
def predict_matte(self, input_path: str, output_path: str) -> None:
    stem, ext = os.path.splitext(output_path)
    self.predict_outputs(input_path, output_path, f"{stem}_mask{ext}")
```

- [ ] **Step 4: Re-run tests and verify pass**

Run: `pytest tests/core/test_birefnet.py -q`
Expected: PASS with mask mode checks.

- [ ] **Step 5: Commit**

```bash
git add core/birefnet.py tests/core/test_birefnet.py
git commit -m "feat: output grayscale masks alongside RGBA mattes"
```

---

### Task 3: Worker + Cache + MainWindow Plumbing

**Files:**
- Modify: `core/matte_cache.py`
- Modify: `ui/workers/matting_worker.py`
- Modify: `ui/main_window.py`
- Test: `tests/core/test_matte_cache.py`
- Test: `tests/test_matting_worker.py`

- [ ] **Step 1: Add failing cache and worker tests**

```python
# tests/core/test_matte_cache.py
from core.matte_cache import find_reusable_matte_paths

def test_cache_hit_requires_mask_path(tmp_path):
    # record missing mask file should not hit
    ...

# tests/test_matting_worker.py
# assert row_done emits matte_path + mask_path on success
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/core/test_matte_cache.py tests/test_matting_worker.py -q`
Expected: FAIL due to old cache predicate and signal payload shape.

- [ ] **Step 3: Implement plumbing changes**

```python
# core/matte_cache.py
def find_reusable_matte_paths(...):
    ...
    if not rec.mask_path or not os.path.isfile(rec.mask_path):
        continue
    return rec.matte_path, rec.mask_path

# ui/workers/matting_worker.py
row_done = pyqtSignal(int, str, str, bool, str)  # index, matte_path, mask_path, ok, err
...
matte_out = os.path.join(out_root, f"{stem}_{i:03d}_matte.png")
mask_out = os.path.join(out_root, f"{stem}_{i:03d}_mask.png")
engine.predict_outputs(src_path, matte_out, mask_out)
self.row_done.emit(i, abs_matte, abs_mask, True, "")

# ui/main_window.py (_on_matting_row_done signature + record)
MatteRecord(..., matte_path=matte_path, mask_path=mask_path, is_active=True)
```

- [ ] **Step 4: Re-run tests and verify pass**

Run: `pytest tests/core/test_matte_cache.py tests/test_matting_worker.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/matte_cache.py ui/workers/matting_worker.py ui/main_window.py tests/core/test_matte_cache.py tests/test_matting_worker.py
git commit -m "feat: persist and reuse matte+mask artifact pairs"
```

---

### Task 4: PSD Export Uses Original Image + Editable Layer Mask

**Files:**
- Modify: `core/psd_export.py`
- Modify: `ui/workers/psd_export_worker.py` (if signature update needed)
- Test: `tests/core/test_psd_export.py`

- [ ] **Step 1: Add failing PSD tests for mask-backed layers**

```python
# tests/core/test_psd_export.py
# Build source image + mask image, export PSD, read back:
# 1) layer.visible is False
# 2) layer has non-empty mask bounds (not 0x0)
# 3) export fails if mask missing
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/core/test_psd_export.py -q`
Expected: FAIL because exporter still uses `matte_path` RGBA directly.

- [ ] **Step 3: Implement mask-based PSD construction**

```python
# core/psd_export.py
# For each active record:
# 1) resolve source raster path from source_id/material mapping
# 2) load source RGB as layer pixels
# 3) load mask L and attach as real layer mask
# 4) visible=False, centered placement

# add strict checks
if not rec.mask_path or not os.path.isfile(rec.mask_path):
    raise ValueError(f"missing mask for {rec.source_id}")
```

- [ ] **Step 4: Re-run tests and verify pass**

Run: `pytest tests/core/test_psd_export.py -q`
Expected: PASS with editable mask checks.

- [ ] **Step 5: Commit**

```bash
git add core/psd_export.py ui/workers/psd_export_worker.py tests/core/test_psd_export.py
git commit -m "feat: export PSD as source layers with editable masks"
```

---

### Task 5: End-to-End Regression + Docs Update

**Files:**
- Modify: `docs/superpowers/specs/2026-04-17-mask-based-psd-export-design.md` (mark implementation notes)
- Test: existing suite

- [ ] **Step 1: Add regression tests for legacy state auto-recompute path**

```python
# tests/test_main_window_*.py
# legacy matte_map without mask_path should trigger re-matting, not crash
```

- [ ] **Step 2: Run targeted regression tests**

Run: `pytest tests/test_main_window_model_gate.py tests/test_main_window_video_pick.py -q`
Expected: PASS.

- [ ] **Step 3: Run full suite**

Run: `./scripts/test.sh`
Expected: all tests PASS.

- [ ] **Step 4: Document behavior delta**

```markdown
# append to spec or release notes
- PSD now exports editable layer masks
- RGBA files are preview artifacts only
- legacy states auto-recompute mask files
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-17-mask-based-psd-export-design.md tests/test_main_window_model_gate.py tests/test_main_window_video_pick.py
git commit -m "test/docs: cover legacy upgrade and mask-based export behavior"
```

---

## Self-Review

### 1. Spec coverage check

- 双产物输出（matte+mask）：Task 2, Task 3
- 数据模型 + 兼容旧状态：Task 1
- 缓存规则升级：Task 3
- PSD 原图+蒙版导出：Task 4
- 错误处理与导出校验：Task 4
- 回归与验收：Task 5

结论：覆盖完整，无遗漏子系统。

### 2. Placeholder scan

已检查无 `TBD/TODO/implement later/similar to` 等占位语句。

### 3. Type consistency

统一使用：
- `MatteRecord.mask_path`
- `MattingEngine.predict_outputs(...)`
- `row_done(index, matte_path, mask_path, ok, err)`

无命名冲突。
