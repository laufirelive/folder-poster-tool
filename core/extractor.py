import glob
import os
import subprocess


def get_video_duration_seconds(video_path: str) -> float:
    """Parse duration from ffprobe stdout; raise RuntimeError on ffprobe failure; ValueError if duration <= 0."""
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
    """
    Extract exactly `frame_count` PNG images spaced evenly across the video timeline.
    Returns sorted list of absolute paths to written files (one per frame).
    Raises RuntimeError if ffmpeg fails or the expected number of PNG files is not written.
    """
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
