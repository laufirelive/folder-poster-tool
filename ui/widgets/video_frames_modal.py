import glob
import os
from typing import Iterable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from core.extractor import regenerate_unselected_preview_frames


class VideoFramesModal(QDialog):
    FRAME_COUNT = 32

    def __init__(
        self,
        frame_paths: list[str],
        video_path: str,
        preview_dir: str,
        *,
        initial_selected_indices: Iterable[int] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("选择视频帧")
        self.resize(1100, 520)

        self._video_path = video_path
        self._preview_dir = preview_dir
        self._paths = list(frame_paths)
        self._selected: set[int] = set()
        if initial_selected_indices is not None:
            for i in initial_selected_indices:
                if 0 <= i < len(self._paths):
                    self._selected.add(i)

        self._buttons: list[QToolButton] = []

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._count_label = QLabel()
        self._count_label.setObjectName("selected_count_label")
        self._update_count_label()
        toolbar.addWidget(self._count_label)
        toolbar.addStretch()

        self._regenerate_btn = QPushButton("重新生成")
        self._regenerate_btn.setObjectName("regenerate_btn")
        self._regenerate_btn.clicked.connect(self._on_regenerate)
        toolbar.addWidget(self._regenerate_btn)

        self._clear_btn = QPushButton("清空选择")
        self._clear_btn.setObjectName("clear_selection_btn")
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)

        layout.addLayout(toolbar)

        grid = QGridLayout()
        cols = 8
        for i, p in enumerate(self._paths):
            btn = QToolButton()
            self._set_button_icon(btn, p)
            btn.setIconSize(QSize(120, 68))
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, idx=i: self._on_pick(idx))
            self._buttons.append(btn)
            grid.addWidget(btn, i // cols, i % cols)

        layout.addLayout(grid)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._refresh_highlight()

    def _set_button_icon(self, btn: QToolButton, path: str) -> None:
        pm = QPixmap(path)
        if not pm.isNull():
            scaled = pm.scaled(
                120,
                68,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            btn.setIcon(QIcon(scaled))

    def _update_count_label(self) -> None:
        self._count_label.setText(f"Selected {len(self._selected)}/{self.FRAME_COUNT}")

    def _on_pick(self, idx: int) -> None:
        if idx in self._selected:
            self._selected.discard(idx)
        else:
            self._selected.add(idx)
        self._refresh_highlight()
        self._update_count_label()

    def _on_clear(self) -> None:
        self._selected.clear()
        self._refresh_highlight()
        self._update_count_label()

    def _on_regenerate(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            regenerate_unselected_preview_frames(
                self._video_path,
                self._preview_dir,
                sorted(self._selected),
                frame_count=self.FRAME_COUNT,
            )
        finally:
            QApplication.restoreOverrideCursor()
        self._reload_thumbnails()

    def _reload_thumbnails(self) -> None:
        paths = sorted(glob.glob(os.path.join(self._preview_dir, "frame_*.png")))
        self._paths = [os.path.abspath(p) for p in paths]
        for i, btn in enumerate(self._buttons):
            if i < len(self._paths):
                self._set_button_icon(btn, self._paths[i])
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _refresh_highlight(self) -> None:
        for i, b in enumerate(self._buttons):
            b.setChecked(i in self._selected)

    def selected_frame_indices(self) -> list[int]:
        return sorted(self._selected)
