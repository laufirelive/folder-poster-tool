"""
Matting progress UI: dual-pane thumbnails (source vs matte) with per-row status.

Row spec items are (display_name, source_image_path, material_key) where
material_key is typically (source_id, frame_idx) to correlate with Material / MatteRecord.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Union

# Running `python ui/pages/matting_page.py` adds `ui/pages` to sys.path; project root must come first.
if __name__ == "__main__":
    _proj_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_proj_root))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models import ProjectState

# (display_name, source_image_path, material_key)
MattingRowSpec = Tuple[str, str, Tuple[str, Optional[int]]]

_THUMB_W, _THUMB_H = 140, 79


class MattingRowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


_STATUS_LABEL = {
    MattingRowStatus.PENDING: "等待",
    MattingRowStatus.RUNNING: "处理中",
    MattingRowStatus.DONE: "完成",
    MattingRowStatus.ERROR: "失败",
}


def _status_from_value(status: Union[MattingRowStatus, str]) -> MattingRowStatus:
    if isinstance(status, MattingRowStatus):
        return status
    try:
        return MattingRowStatus(str(status).lower())
    except ValueError:
        return MattingRowStatus.PENDING


def _placeholder_pixmap() -> QPixmap:
    pm = QPixmap(_THUMB_W, _THUMB_H)
    pm.fill(Qt.GlobalColor.darkGray)
    return pm


def _load_thumb(path: str) -> QPixmap:
    p = Path(path)
    if not p.is_file():
        return _placeholder_pixmap()
    pm = QPixmap(str(p))
    if pm.isNull():
        return _placeholder_pixmap()
    return pm.scaled(
        _THUMB_W,
        _THUMB_H,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class MattingPage(QWidget):
    cancel_requested = pyqtSignal()

    def __init__(
        self,
        project_state: ProjectState,
        rows: List[MattingRowSpec],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._state = project_state
        self._rows: List[MattingRowSpec] = list(rows)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)

        self._current_file_label = QLabel("当前文件：—", self)
        self._remaining_label = QLabel("剩余：—", self)

        top = QHBoxLayout()
        top.addWidget(self._progress, stretch=1)
        top.addWidget(self._current_file_label)
        top.addWidget(self._remaining_label)

        self._left_scroll = QScrollArea(self)
        self._right_scroll = QScrollArea(self)
        for sc in (self._left_scroll, self._right_scroll):
            sc.setWidgetResizable(True)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sc.setFrameShape(QFrame.Shape.StyledPanel)

        left_host = QWidget()
        self._left_col = QVBoxLayout(left_host)
        self._left_col.setSpacing(8)
        right_host = QWidget()
        self._right_col = QVBoxLayout(right_host)
        self._right_col.setSpacing(8)

        self._left_scroll.setWidget(left_host)
        self._right_scroll.setWidget(right_host)

        self._row_widgets: List[dict] = []

        mid = QHBoxLayout()
        mid.addWidget(self._left_scroll, stretch=1)
        mid.addWidget(self._right_scroll, stretch=1)

        # Column titles above scroll areas
        titles = QHBoxLayout()
        titles.addWidget(QLabel("<b>原始</b>", self), stretch=1)
        titles.addWidget(QLabel("<b>抠像结果</b>", self), stretch=1)

        cancel_btn = QPushButton("取消", self)
        cancel_btn.clicked.connect(self.cancel_requested.emit)

        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(cancel_btn)

        outer = QVBoxLayout(self)
        outer.addLayout(top)
        outer.addLayout(titles)
        outer.addLayout(mid, stretch=1)
        outer.addLayout(bottom)

        self._build_rows()

    def set_state(self, state: ProjectState) -> None:
        self._state = state

    def _clear_row_layouts(self) -> None:
        for col in (self._left_col, self._right_col):
            while col.count():
                item = col.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        self._row_widgets.clear()

    def _build_rows(self) -> None:
        self._clear_row_layouts()
        for display_name, source_path, _key in self._rows:
            left_frame = QFrame()
            left_frame.setFrameShape(QFrame.Shape.StyledPanel)
            lv = QVBoxLayout(left_frame)
            name_lbl = QLabel(display_name)
            name_lbl.setWordWrap(True)
            thumb = QLabel()
            thumb.setFixedSize(_THUMB_W, _THUMB_H)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet("background: #222222;")
            thumb.setPixmap(_load_thumb(source_path))
            status_lbl = QLabel(_STATUS_LABEL[MattingRowStatus.PENDING])
            lv.addWidget(name_lbl)
            lv.addWidget(thumb)
            lv.addWidget(status_lbl)

            right_frame = QFrame()
            right_frame.setFrameShape(QFrame.Shape.StyledPanel)
            rv = QVBoxLayout(right_frame)
            matte_thumb = QLabel()
            matte_thumb.setFixedSize(_THUMB_W, _THUMB_H)
            matte_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            matte_thumb.setStyleSheet("background: #222222;")
            matte_thumb.setPixmap(_placeholder_pixmap())
            rv.addWidget(matte_thumb)

            self._left_col.addWidget(left_frame)
            self._right_col.addWidget(right_frame)
            self._row_widgets.append(
                {
                    "status_label": status_lbl,
                    "matte_thumb": matte_thumb,
                }
            )
        self._left_col.addStretch()
        self._right_col.addStretch()

    def set_row_status(
        self,
        index: int,
        status: Union[MattingRowStatus, str],
        matte_preview_path: Optional[str] = None,
    ) -> None:
        if index < 0 or index >= len(self._row_widgets):
            return
        st = _status_from_value(status)
        row = self._row_widgets[index]
        row["status_label"].setText(_STATUS_LABEL.get(st, str(st)))
        if matte_preview_path and st == MattingRowStatus.DONE:
            row["matte_thumb"].setPixmap(_load_thumb(matte_preview_path))
        elif st in (MattingRowStatus.PENDING, MattingRowStatus.RUNNING):
            row["matte_thumb"].setPixmap(_placeholder_pixmap())
        elif st == MattingRowStatus.ERROR:
            row["matte_thumb"].setPixmap(_placeholder_pixmap())

    def set_overall_progress(self, percent: int) -> None:
        self._progress.setValue(max(0, min(100, int(percent))))

    def set_current_label(self, name: str, remaining: Tuple[int, int]) -> None:
        rem, total = remaining
        self._current_file_label.setText(f"当前文件：{name}")
        self._remaining_label.setText(f"剩余 {rem}/{total}")


if __name__ == "__main__":
    import tempfile

    from PyQt6.QtWidgets import QApplication

    from models import ProjectState

    app = QApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp())
    sample = tmp / "demo.png"
    try:
        from PIL import Image

        Image.new("RGB", (64, 64), color=(200, 100, 50)).save(sample)
    except Exception:
        sample.write_bytes(b"")

    state = ProjectState(project_id="demo_matting", input_path=str(tmp), mode="image")
    specs: List[MattingRowSpec] = [
        ("demo.png", str(sample), ("src_a", None)),
        ("video frame", str(sample), ("src_b", 2)),
    ]
    w = MattingPage(state, specs)
    w.setWindowTitle("Matting page demo")
    w.resize(720, 520)
    w.set_overall_progress(40)
    w.set_current_label("demo.png", (1, 2))
    w.set_row_status(0, MattingRowStatus.DONE, str(sample))
    w.show()
    sys.exit(app.exec())
