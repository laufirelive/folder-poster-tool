from PyQt6 import sip
from PyQt6.QtCore import Qt, pyqtSignal, QThread
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

import os
from models import ProjectState, scanned_file_source_id_for_material
from ui.workers.thumbnail_worker import ThumbnailWorker


class MaterialsPage(QWidget):
    image_toggle_requested = pyqtSignal(str, bool)
    video_pick_requested = pyqtSignal(str)
    next_requested = pyqtSignal()
    back_requested = pyqtSignal()

    def __init__(self, project_state: ProjectState, parent=None):
        super().__init__(parent)
        self._state = project_state
        self._thumb_cache: dict[str, QPixmap] = {}
        self._current_cols = 3

        self.setStyleSheet("""
            QFrame#MaterialCard {
                background-color: #ffffff;
                border: 1px solid #dddddd;
                border-radius: 8px;
            }
            QFrame#MaterialCard:hover {
                border: 1px solid #007bff;
            }
            QLabel {
                font-family: sans-serif;
            }
            QPushButton#NextButton {
                padding: 10px 30px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#NextButton:hover {
                background-color: #0056b3;
            }
            QPushButton#NextButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
            QPushButton#PickButton {
                padding: 6px;
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QPushButton#PickButton:hover {
                background-color: #e0e0e0;
            }
        """)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._grid_layout = QGridLayout(self._container)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setContentsMargins(20, 20, 20, 20)
        self._scroll.setWidget(self._container)

        # Header
        header_layout = QHBoxLayout()
        self._back_btn = QPushButton("← 返回")
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._back_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #007bff;
                font-weight: bold;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)

        title_label = QLabel("Folder Poster")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")

        self._next_btn = QPushButton("下一步")
        self._next_btn.setObjectName("NextButton")
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self.next_requested.emit)

        header_layout.addWidget(self._back_btn)
        header_layout.addStretch()
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self._next_btn)

        # Stats Label
        file_type_str = "视频" if self._state.mode == "video" else "图片"
        self._stats_label = QLabel(f"已找到 {len(self._state.scanned_files)} 个{file_type_str}文件（递归 {self._state.depth} 层）")
        self._stats_label.setStyleSheet("font-size: 14px; color: #555;")

        # Toolbar (View controls)
        toolbar_layout = QHBoxLayout()
        view_btn = QPushButton("瀑布流 ▼")
        view_btn.setEnabled(False)
        size_lbl = QLabel("大小: ████████░░")
        size_lbl.setStyleSheet("color: #888;")
        toolbar_layout.addWidget(view_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(size_lbl)
        toolbar_layout.addStretch()

        # Footer
        self._footer_label = QLabel("已选素材: 0")
        self._footer_label.setStyleSheet("font-size: 14px; color: #333; font-weight: bold;")
        
        footer_layout = QHBoxLayout()
        footer_layout.addWidget(self._footer_label)
        footer_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addLayout(header_layout)
        outer.addSpacing(10)
        outer.addWidget(self._stats_label)
        outer.addSpacing(5)
        outer.addLayout(toolbar_layout)
        outer.addSpacing(10)
        outer.addWidget(self._scroll)
        outer.addSpacing(10)
        outer.addLayout(footer_layout)

        self._start_thumbnail_worker()
        self._rebuild_grid()

    def _start_thumbnail_worker(self):
        video_paths = []
        for sf in self._state.scanned_files:
            if sf.type == "video" and sf.source_id not in self._thumb_cache:
                video_paths.append((sf.source_id, sf.path))
        
        if not video_paths:
            return

        # Need a place to store thumbs temporarily
        cache_dir = os.path.expanduser("~/.folder-poster/cache/thumbs")
        
        self._thumb_thread = QThread()
        self._thumb_worker = ThumbnailWorker(video_paths, cache_dir)
        self._thumb_worker.moveToThread(self._thumb_thread)
        
        self._thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumb_thread.started.connect(self._thumb_worker.run)
        
        self._thumb_thread.start()

    def _on_thumbnail_ready(self, source_id: str, path: str):
        pm = QPixmap(path)
        if not pm.isNull():
            self.set_video_thumbnail(source_id, pm)

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
                w.setParent(None)
                w.deleteLater()

    def _rebuild_grid(self) -> None:
        self._clear_grid()
        cols = self._current_cols
        for i, sf in enumerate(self._state.scanned_files):
            card = QFrame()
            card.setObjectName("MaterialCard")
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setFixedWidth(200)
            v = QVBoxLayout(card)
            v.setContentsMargins(10, 10, 10, 10)

            thumb = QLabel()
            thumb.setFixedSize(180, 120)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet("background: #f0f0f0; color: #888888; border-radius: 4px;")

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
                    thumb.setText("视频 (提取中...)")

            name = QLabel()
            metrics = name.fontMetrics()
            elided_name = metrics.elidedText(sf.name, Qt.TextElideMode.ElideRight, 180)
            name.setText(elided_name)
            name.setStyleSheet("font-size: 12px; color: #333;")
            name.setWordWrap(False)
            name.setToolTip(sf.path)

            v.addWidget(thumb)
            v.addWidget(name)

            if sf.type == "image":
                cb = QCheckBox("选用")
                cb.setCursor(Qt.CursorShape.PointingHandCursor)
                cb.setChecked(self._is_image_selected(sf.source_id))
                cb.toggled.connect(
                    lambda checked, sid=sf.source_id: self.image_toggle_requested.emit(sid, checked)
                )
                v.addWidget(cb)
            else:
                n_frames = self._selected_video_frame_count(sf.source_id)
                btn_text = "选择帧" if n_frames == 0 else f"已选 {n_frames} 帧"
                btn = QPushButton(btn_text)
                btn.setObjectName("PickButton")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(
                    lambda checked=False, sid=sf.source_id: self.video_pick_requested.emit(sid)
                )
                if n_frames > 0:
                    btn.setStyleSheet("background-color: #e6f2ff; color: #007bff; border: 1px solid #007bff;")
                v.addWidget(btn)

            self._grid_layout.addWidget(card, i // cols, i % cols)

        n_selected = len([m for m in self._state.selected_materials if m.selected])
        self._next_btn.setEnabled(n_selected >= 1)

        if self._state.mode == "video":
            vid_ids = {scanned_file_source_id_for_material(m) for m in self._state.selected_materials if m.selected}
            self._footer_label.setText(f"已选素材: {n_selected} 帧（来自 {len(vid_ids)} 个视频）")
        else:
            self._footer_label.setText(f"已选素材: {n_selected} 张")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_columns()

    def _adjust_columns(self):
        if not self._state or not self._state.scanned_files:
            return
        # Get width of scroll area viewport
        width = self._scroll.viewport().width()
        # Card width = 180 (thumb) + 20 (margins) + 16 (spacing) = ~216, let's say 240
        cols = max(1, width // 240)
        
        if self._current_cols != cols:
            self._current_cols = cols
            
            # Reposition existing widgets without deleting them
            widgets = []
            while self._grid_layout.count():
                item = self._grid_layout.takeAt(0)
                if item.widget():
                    widgets.append(item.widget())
            
            for i, w in enumerate(widgets):
                self._grid_layout.addWidget(w, i // cols, i % cols)