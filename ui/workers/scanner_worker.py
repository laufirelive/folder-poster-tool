"""Directory scanner worker to keep UI responsive."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from core.scanner import scan_directory_in_batches


class ScannerWorker(QObject):
    batch_ready = pyqtSignal(list)  # list[ScannedFile]
    finished_ok = pyqtSignal(str, str, int, int)  # path, mode, depth, total
    finished_err = pyqtSignal(str)

    def __init__(self, path: str, mode: str, depth: int) -> None:
        super().__init__()
        self._path = path
        self._mode = mode
        self._depth = depth

    def run(self) -> None:
        try:
            total = 0
            for batch in scan_directory_in_batches(self._path, self._mode, self._depth):
                total += len(batch)
                self.batch_ready.emit(batch)
            self.finished_ok.emit(self._path, self._mode, self._depth, total)
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc))
