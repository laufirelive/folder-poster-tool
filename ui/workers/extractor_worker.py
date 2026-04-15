from PyQt6.QtCore import QObject, pyqtSignal
from core.extractor import extract_preview_frames

class ExtractorWorker(QObject):
    finished_ok = pyqtSignal(list)
    finished_err = pyqtSignal(str)

    def __init__(self, video_path: str, output_dir: str, frame_count: int = 32):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.frame_count = frame_count

    def run(self):
        try:
            paths = extract_preview_frames(self.video_path, self.output_dir, self.frame_count)
            self.finished_ok.emit(paths)
        except Exception as e:
            self.finished_err.emit(str(e))
