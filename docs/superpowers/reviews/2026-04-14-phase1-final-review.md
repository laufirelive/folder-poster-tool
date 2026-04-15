# Phase 1 Final Code Review

## Overview
This document captures the final holistic code review for Phase 1 of the Folder Poster project, conducted by the `code-reviewer` subagent.

## Strengths
- **Clear layering**: Core pieces map cleanly to the design (`scanner.py`, `extractor.py`, `core/birefnet.py`, `psd_export.py`, `material_paths.py`, `state_manager.py`) with PyQt6 pages and `QThread` workers for long work—appropriate for UI responsiveness.
- **PSD export matches core spec**: `export_matte_psd` enforces 2:3 canvas, builds one **hidden** layer per matte, centers content, and documents layer/stack ordering; compression choice is pragmatic.
- **BiRefNet integration is production-minded**: Lazy `MattingEngine`, device selection, CUDA half, and `FOLDER_POSTER_MATTING_STUB=1` for CI or headless environments are good choices; tests can avoid GPU.
- **Automated tests**: cover scanner, extractor, PSD export, material path resolution, and stub matting—good foundation for regression safety.
- **Export UX**: Presets 4000x6000 / 2000x3000, custom 2:3 coupling, folder picker, and opening the output folder on success align well with the design.

## Issues

### Critical (Gaps compared to Design Phase 1)
1. **Video modal is single-frame only**: Design requires 32 thumbnails, multi-select, and "regenerate random". Current implementation only allows single selection.
2. **No "random 32" extraction path**: `extract_preview_frames` only does even temporal sampling. No second code path for random timestamps.

### Important
1. **`MatteRecord` identity for video frames**: Cannot distinguish multiple frames from the same video. `source_id` omits the frame index. This blocks correct reconciliation and caching.
2. **No matte skip/cache**: Matting always runs for each row; no "already processed, skip" path based on mtime or hash.
3. **Video frame cache not as specified**: Frames are extracted on each modal open, rather than utilizing a stable MD5 cache dir.
4. **`StateManager.load_state` contract**: Returns `None` when file is missing, but type hint says `-> ProjectState`.
5. **Home page validation**: Empty path should disable "Start Scan". No drag-and-drop support.
6. **Matting page retry**: No click-to-retry on failed rows.
7. **Dependencies**: `numpy` is missing from `requirements.txt`. System dependencies `ffmpeg` and `ffprobe` need to be documented.
8. **Security**: `trust_remote_code=True` in `core/birefnet.py` should be documented as a supply-chain risk.

### Minor
1. **Extraction sampling**: Even sampling instead of explicit mid-segment sampling.
2. **Materials page UX**: Missing waterfall layout toggle, thumbnail size slider, and per-video selection summary.
3. **Layer names**: Uses sanitized file basename instead of suggested `Folder_Timestamp` format.

## Conclusion
Phase 1 successfully delivers a coherent vertical slice of the application, achieving the primary goal of end-to-end functionality (scan -> select -> matting -> PSD export). 

However, several UX and caching features specified in the original design document were deferred or simplified to achieve this milestone. These gaps (especially the multi-frame video selection and matting caching) should be prioritized as technical debt or Phase 1.1 scope before proceeding to Phase 2.
