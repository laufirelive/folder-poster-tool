from PyQt6 import sip
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models import ProjectState, scanned_file_source_id_for_material


class MaterialsPage(QWidget):
    image_toggle_requested = pyqtSignal(str, bool)
    video_pick_requested = pyqtSignal(str)
    next_requested = pyqtSignal()

    def __init__(self, project_state: ProjectState, parent=None):
        super().__init__(parent)
        self._state = project_state
        self._thumb_cache: dict[str, QPixmap] = {}

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._grid_layout = QGridLayout(self._container)
        self._grid_layout.setSpacing(12)
        self._scroll.setWidget(self._container)

        self._next_btn = QPushButton("下一步", self)
        self._next_btn.clicked.connect(self.next_requested.emit)

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self._next_btn)

        outer = QVBoxLayout(self)
        outer.addWidget(self._scroll)
        outer.addLayout(footer)
        self._rebuild_grid()

    def set_state(self, state: ProjectState) -> None:
        self._state = state
        self._rebuild_grid()

    def set_video_thumbnail(self, source_id: str, pixmap: QPixmap) -> None:
        self._thumb_cache[source_id] = pixmap
        self._rebuild_grid()

    def _is_image_selected(self, source_id: str) -> bool:
        for m in self._state.selected_materials:
            if m.source_id == source_id and m.selected:
                return True
        return False

    def _selected_video_frame_count(self, video_source_id: str) -> int:
        n = 0
        for m in self._state.selected_materials:
            if not m.selected or m.frame_idx is None:
                continue
            if scanned_file_source_id_for_material(m) == video_source_id:
                n += 1
        return n

    def _clear_grid(self) -> None:
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w is not None and not sip.isdeleted(w):
                sip.delete(w)

    def _rebuild_grid(self) -> None:
        self._clear_grid()
        cols = 3
        for i, sf in enumerate(self._state.scanned_files):
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            v = QVBoxLayout(card)
            thumb = QLabel()
            thumb.setFixedSize(160, 90)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet("background: #222222; color: #aaaaaa;")

            if sf.type == "image":
                pm = QPixmap(sf.path)
                if not pm.isNull():
                    thumb.setPixmap(
                        pm.scaled(
                            thumb.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    thumb.setText("图片")
            else:
                cached = self._thumb_cache.get(sf.source_id)
                if cached is not None and not cached.isNull():
                    thumb.setPixmap(
                        cached.scaled(
                            thumb.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    thumb.setText("视频")

            name = QLabel(sf.name)
            name.setWordWrap(False)
            name.setToolTip(sf.path)

            v.addWidget(thumb)
            v.addWidget(name)

            if sf.type == "image":
                cb = QCheckBox("选用")
                cb.setChecked(self._is_image_selected(sf.source_id))
                cb.toggled.connect(
                    lambda checked, sid=sf.source_id: self.image_toggle_requested.emit(sid, checked)
                )
                v.addWidget(cb)
            else:
                n_frames = self._selected_video_frame_count(sf.source_id)
                btn_text = "选择帧" if n_frames == 0 else f"已选 {n_frames} 帧"
                btn = QPushButton(btn_text)
                btn.clicked.connect(
                    lambda checked=False, sid=sf.source_id: self.video_pick_requested.emit(sid)
                )
                v.addWidget(btn)

            self._grid_layout.addWidget(card, i // cols, i % cols)

        n_selected = len([m for m in self._state.selected_materials if m.selected])
        self._next_btn.setEnabled(n_selected >= 1)
