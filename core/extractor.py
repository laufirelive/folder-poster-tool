import glob
import os
import random
import subprocess
from typing import Iterable, Mapping


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


def random_timestamps_for_slots(
    duration: float,
    slots: Iterable[int],
    rng: random.Random,
) -> dict[int, float]:
    """Map each frame slot index (0 .. N-1) to a random timestamp in (0, duration)."""
    if duration <= 0:
        raise ValueError("duration must be positive")
    eps = min(0.1, duration * 0.001)
    hi = duration - eps
    if hi <= eps:
        t0 = duration / 2.0
        return {int(s): t0 for s in slots}
    out: dict[int, float] = {}
    for s in slots:
        out[int(s)] = rng.uniform(eps, hi)
    return out


def extract_frames_at_slots(
    video_path: str,
    output_dir: str,
    slot_to_timestamp: Mapping[int, float],
    frame_count: int = 32,
) -> list[str]:
    """
    Write PNG previews only for the given slots using ffmpeg seek + single-frame extract.

    Filenames follow ``frame_{slot+1:03d}.png`` (same as :func:`extract_preview_frames`).
    Slots must be indices in ``0 .. frame_count - 1``. Does not touch slots omitted from
    ``slot_to_timestamp`` (so kept selections on disk are preserved).
    """
    if not slot_to_timestamp:
        return []
    os.makedirs(output_dir, exist_ok=True)
    for slot in slot_to_timestamp:
        if slot < 0 or slot >= frame_count:
            raise ValueError(f"slot {slot} out of range for frame_count={frame_count}")
    written: list[str] = []
    for slot in sorted(slot_to_timestamp):
        ts = float(slot_to_timestamp[slot])
        name = f"frame_{slot + 1:03d}.png"
        out_path = os.path.join(output_dir, name)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(ts),
            "-i",
            video_path,
            "-frames:v",
            "1",
            out_path,
        ]
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or "ffmpeg failed")
        written.append(os.path.abspath(out_path))
    return sorted(written)


def regenerate_unselected_preview_frames(
    video_path: str,
    output_dir: str,
    keep_indices: Iterable[int],
    frame_count: int = 32,
    rng: random.Random | None = None,
) -> list[str]:
    """
    Re-extract random frames for all slots *except* ``keep_indices``, without overwriting
    kept preview files (slots in ``keep_indices`` are skipped entirely).
    """
    keep = {int(i) for i in keep_indices}
    for k in keep:
        if k < 0 or k >= frame_count:
            raise ValueError(f"keep index {k} out of range for frame_count={frame_count}")
    missing = sorted(set(range(frame_count)) - keep)
    if not missing:
        return []
    duration = get_video_duration_seconds(video_path)
    gen = rng or random.Random()
    ts_map = random_timestamps_for_slots(duration, missing, gen)
    return extract_frames_at_slots(video_path, output_dir, ts_map, frame_count=frame_count)
