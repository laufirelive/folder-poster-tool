import os
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal

class ThumbnailWorker(QObject):
    thumbnail_ready = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, video_paths: list[tuple[str, str]], cache_dir: str):
        super().__init__()
        self.video_paths = video_paths
        self.cache_dir = cache_dir

    def run(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        for source_id, vpath in self.video_paths:
            out_path = os.path.join(self.cache_dir, f"thumb_{source_id}.jpg")
            if not os.path.exists(out_path):
                try:
                    cmd = [
                        "ffmpeg", "-y", "-v", "error",
                        "-ss", "00:00:01.000",
                        "-i", vpath,
                        "-frames:v", "1",
                        "-vf", "scale=320:-1",
                        out_path
                    ]
                    subprocess.run(cmd, check=True)
                except Exception:
                    pass
            
            if os.path.exists(out_path):
                self.thumbnail_ready.emit(source_id, out_path)
        self.finished.emit()
