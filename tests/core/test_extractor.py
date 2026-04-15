import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


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
    import os
    import tempfile

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


def test_random_timestamps_for_slots_respects_duration_and_rng():
    _ensure_project_core()
    from core.extractor import random_timestamps_for_slots
    import random

    rng = random.Random(42)
    m = random_timestamps_for_slots(10.0, [0, 1, 2], rng)
    assert set(m.keys()) == {0, 1, 2}
    for t in m.values():
        assert 0 < t < 10.0


def test_extract_frames_at_slots_one_ffmpeg_per_slot_with_ss():
    _ensure_project_core()
    from core.extractor import extract_frames_at_slots
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        vp = os.path.join(tmp, "v.mp4")
        open(vp, "wb").close()
        out = os.path.join(tmp, "frames")
        os.makedirs(out, exist_ok=True)

        slot_map = {0: 1.5, 3: 9.25}

        with patch("core.extractor.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            paths = extract_frames_at_slots(vp, out, slot_map, frame_count=32)
            assert len(paths) == 2
            assert paths == sorted(
                [os.path.abspath(os.path.join(out, "frame_001.png")), os.path.abspath(os.path.join(out, "frame_004.png"))]
            )
            ffmpeg_calls = [c for c in run.call_args_list if c[0][0][0] == "ffmpeg"]
            assert len(ffmpeg_calls) == 2
            by_out = {}
            for c in ffmpeg_calls:
                cmd = c[0][0]
                ss_idx = cmd.index("-ss") + 1
                out_f = cmd[-1]
                by_out[out_f] = float(cmd[ss_idx])
            assert by_out[os.path.join(out, "frame_001.png")] == 1.5
            assert by_out[os.path.join(out, "frame_004.png")] == 9.25


def test_regenerate_unselected_slots_skips_kept_indices():
    _ensure_project_core()
    from core.extractor import regenerate_unselected_preview_frames
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        vp = os.path.join(tmp, "v.mp4")
        open(vp, "wb").close()
        out = os.path.join(tmp, "frames")

        keep = {5}
        missing_ts = {i: float(i) for i in range(32) if i != 5}

        with patch("core.extractor.get_video_duration_seconds", return_value=100.0):
            with patch("core.extractor.random_timestamps_for_slots") as rts:
                rts.return_value = missing_ts
                with patch("core.extractor.subprocess.run") as run:
                    run.return_value = MagicMock(returncode=0)
                    paths = regenerate_unselected_preview_frames(
                        vp, out, keep_indices=keep, frame_count=32, rng=None
                    )
                assert len(paths) == 31
                rts.assert_called_once()
                ca = rts.call_args[0]
                assert ca[0] == 100.0
                assert set(ca[1]) == set(range(32)) - keep
                ffmpeg_calls = [c for c in run.call_args_list if c[0][0][0] == "ffmpeg"]
                assert len(ffmpeg_calls) == 31
                outs = {c[0][0][-1] for c in ffmpeg_calls}
                assert os.path.join(out, "frame_006.png") not in outs
