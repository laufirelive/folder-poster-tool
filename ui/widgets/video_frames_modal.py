from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QToolButton, QVBoxLayout


class VideoFramesModal(QDialog):
    def __init__(self, frame_paths: list[str], initial_index: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择视频帧")
        self.resize(1100, 520)

        self._paths = list(frame_paths)
        if self._paths:
            self._selected = max(0, min(initial_index, len(self._paths) - 1))
        else:
            self._selected = 0

        self._buttons: list[QToolButton] = []

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        cols = 8
        for i, p in enumerate(self._paths):
            btn = QToolButton()
            pm = QPixmap(p)
            if not pm.isNull():
                scaled = pm.scaled(
                    120,
                    68,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                btn.setIcon(QIcon(scaled))
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

        self._highlight(self._selected)

    def _on_pick(self, idx: int) -> None:
        self._selected = idx
        self._highlight(idx)

    def _highlight(self, idx: int) -> None:
        for i, b in enumerate(self._buttons):
            b.setChecked(i == idx)

    def selected_frame_index(self) -> int:
        return self._selected
