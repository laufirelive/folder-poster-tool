# Folder Poster Phase 1.1 Implementation Plan

**Goal:** Address technical debt and functional gaps identified in the Phase 1 final review, bringing the implementation into full compliance with the `folder-poster-design.md` specifications for Phase 1.

**Key Objectives:**
1. Support multi-selection of frames in the video modal.
2. Implement random frame regeneration while preserving selections.
3. Fix data model identity for video frames (preventing collisions).
4. Introduce caching/skipping for the matting process.
5. Address UI polish and type hinting issues.

---

## Task 1: Data Models, State Manager & Polish
**Objective:** Fix type hints, model identities, and missing dependencies.
- Update `core/state_manager.py`: Change `load_state` return type to `Optional[ProjectState]`.
- Update `models.py`: 
  - Ensure `Material.source_id` is unique per frame (e.g., append `_frame_XX` for videos).
  - Update `MatteRecord` to ensure it can be uniquely mapped to a specific video frame.
- Update `requirements.txt`: Explicitly add `numpy`.
- Update `ui/pages/home_page.py`: Disable the "开始扫描" (Start Scan) button if the path input is empty.

## Task 2: Extractor Enhancements (Random Frames)
**Objective:** Add support for extracting random frames to `core/extractor.py`.
- Modify `extract_preview_frames` (or add a new function) to support extracting specific timestamps or generating random timestamps.
- Ensure the extractor can replace specific missing frames (for the "Regenerate" feature) without overwriting already selected frames.

## Task 3: Video Frames Modal (Multi-Select & Regenerate)
**Objective:** Upgrade `ui/widgets/video_frames_modal.py` to match the design spec.
- Change selection logic from single-select to multi-select.
- Add UI elements: "Selected N/32" label, "Regenerate" (重新生成) button, "Clear" (清空选择) button.
- Implement the "Regenerate" logic: keep selected frames, request new random frames from the extractor to fill the unselected slots, and update the UI.
- Change the modal's return value to provide a list of selected `frame_idx` (and potentially their paths).

## Task 4: Materials Page & Wiring Updates
**Objective:** Connect the updated modal to the main state.
- Update `ui/pages/materials_page.py` and `ui/main_window.py` to handle the new modal return value (list of frames).
- Update the UI to reflect how many frames are selected for a given video in the main materials grid.
- Ensure `ProjectState.selected_materials` can store multiple `Material` entries for the same video `ScannedFile`, differentiated by `frame_idx` and `source_id`.

## Task 5: Matting Caching & Progress UI Retry
**Objective:** Avoid redundant matting work and improve failure recovery.
- Update `core/birefnet.py` (or `MattingWorker`) to check if a valid matte already exists in the `matte_map` (and on disk) before running the model.
- Update `ui/pages/matting_page.py` to allow clicking on a "Failed" row to retry the matting process for that specific item.

---

## Workflow
We will execute this plan using subagent-driven development.
1. Each task will be implemented in its own step.
2. A commit will be made after each task.
3. Code review will be requested via the `code-reviewer` subagent to ensure quality and compliance before proceeding.