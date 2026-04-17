"""Model bootstrap page shown when local BiRefNet model is missing."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from core.model_manager import ModelManager


class ModelDownloadWorker(QThread):
    progress = pyqtSignal(int, int, str)  # done, total, desc
    finished_ok = pyqtSignal()
    finished_err = pyqtSignal(str)

    def __init__(self, manager: ModelManager) -> None:
        super().__init__()
        self._manager = manager

    def run(self) -> None:
        try:
            self._manager.download_model(progress_cb=self._emit_progress)
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc))

    def _emit_progress(self, done: int, total: int, desc: str) -> None:
        self.progress.emit(done, total, desc)


class ModelDownloadPage(QWidget):
    model_ready = pyqtSignal()

    def __init__(self, manager: ModelManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._worker: ModelDownloadWorker | None = None
        self._build_ui()
        self._refresh_installed_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)

        title = QLabel("需要先下载抠像模型")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        self._hint_label = QLabel(
            "未检测到本地 BiRefNet 模型。请先下载模型，下载完成后会自动解锁主流程。"
        )
        self._hint_label.setWordWrap(True)
        layout.addWidget(self._hint_label)

        self._path_label = QLabel(f"模型目录：{self._manager.get_model_dir()}")
        layout.addWidget(self._path_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("等待下载")
        layout.addWidget(self._status_label)

        self._download_btn = QPushButton("下载模型")
        self._download_btn.clicked.connect(self._start_download)
        layout.addWidget(self._download_btn)
        layout.addStretch()

    def _refresh_installed_state(self) -> None:
        if self._manager.is_installed():
            self._status_label.setText("模型已安装，正在进入主页...")
            self._download_btn.setEnabled(False)
            self.model_ready.emit()
        else:
            self._status_label.setText("未检测到模型，请点击下载。")
            self._download_btn.setEnabled(True)

    def _start_download(self) -> None:
        if self._worker is not None:
            return
        self._download_btn.setEnabled(False)
        self._status_label.setText("正在下载模型...")
        self._progress.setVisible(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)

        self._worker = ModelDownloadWorker(self._manager)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_download_ok)
        self._worker.finished_err.connect(self._on_download_err)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_progress(self, done: int, total: int, desc: str) -> None:
        if total > 0:
            pct = int(done / total * 100)
            self._progress.setValue(max(0, min(100, pct)))
            self._status_label.setText(f"{desc or '下载中'} {pct}%")
        else:
            self._progress.setRange(0, 0)
            self._status_label.setText(desc or "下载中...")

    def _on_download_ok(self) -> None:
        self._status_label.setText("模型下载完成，正在解锁主流程...")
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self.model_ready.emit()

    def _on_download_err(self, err: str) -> None:
        self._progress.setVisible(False)
        self._status_label.setText(f"下载失败：{err}")
        self._download_btn.setEnabled(True)

    def _on_worker_finished(self) -> None:
        if self._worker is None:
            return
        self._worker.deleteLater()
        self._worker = None
