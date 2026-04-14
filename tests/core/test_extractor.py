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
