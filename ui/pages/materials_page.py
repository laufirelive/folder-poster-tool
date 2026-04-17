from PyQt6 import sip
from PyQt6.QtCore import QSize, Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
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
        self._current_card_width = 240
        self._card_min_width = 180
        self._card_max_width = 420
        self._card_target_width = 240
        self._waterfall_mode = True
        self._card_widgets: list[QFrame] = []
        self._card_index_by_source: dict[str, int] = {}
        self._card_refs: dict[str, dict] = {}
        self._thumb_aspect: dict[str, float] = {}
        self._render_next_index = 0
        self._render_batch_size = 48
        self._render_budget = 0
        self._initial_render_limit = 240
        self._render_expand_step = 180
        self._thumb_worker = None
        self._thumb_thread = None
        self._scan_loading = False
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(1)
        self._render_timer.timeout.connect(self._render_next_batch)

        self.setStyleSheet("""
            QFrame#MaterialCard {
                background-color: #ffffff;
                border: 2px solid #dde2e8;
                border-radius: 8px;
            }
            QFrame#MaterialCard:hover {
                border-color: #8ab8ff;
            }
            QFrame#MaterialCard[selected="true"] {
                border-color: #1677ff;
                background-color: #f6faff;
            }
            QFrame#MaterialCard[selected="true"]:hover {
                border-color: #0f63d6;
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
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._grid_layout = QGridLayout(self._container)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setContentsMargins(20, 20, 20, 20)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._scroll.setWidget(self._container)
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_for_lazy_render)

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
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet("font-size: 14px; color: #555;")
        self._update_stats_label()

        # Toolbar (View controls)
        toolbar_layout = QHBoxLayout()
        self._view_btn = QPushButton("瀑布流 ▼")
        self._view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view_btn.clicked.connect(self._toggle_view_mode)
        size_lbl = QLabel("大小:")
        size_lbl.setStyleSheet("color: #666;")
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(self._card_min_width, self._card_max_width)
        self._size_slider.setValue(self._card_target_width)
        self._size_slider.setFixedWidth(180)
        self._size_slider.valueChanged.connect(self._on_size_changed)
        toolbar_layout.addWidget(self._view_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(size_lbl)
        toolbar_layout.addWidget(self._size_slider)
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
        self._start_progressive_render()

    def _start_thumbnail_worker(self):
        video_paths = []
        for sf in self._state.scanned_files:
            if sf.type == "video" and sf.source_id not in self._thumb_cache:
                video_paths.append((sf.source_id, sf.path))
        
        if not video_paths:
            return

        # Need a place to store thumbs temporarily
        cache_dir = os.path.expanduser("~/.folder-poster/cache/thumbs")
        
        if self._thumb_thread is not None and self._thumb_thread.isRunning():
            return
        self._thumb_thread = QThread()
        self._thumb_worker = ThumbnailWorker(video_paths, cache_dir)
        self._thumb_worker.moveToThread(self._thumb_thread)
        
        self._thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumb_thread.started.connect(self._thumb_worker.run)
        
        self._thumb_worker.finished.connect(self._thumb_thread.quit)
        self._thumb_worker.finished.connect(self._thumb_worker.deleteLater)
        self._thumb_thread.finished.connect(self._thumb_thread.deleteLater)
        self._thumb_thread.finished.connect(self._on_thumb_thread_finished)
        self._thumb_thread.start()

    def _on_thumb_thread_finished(self):
        self._thumb_worker = None
        self._thumb_thread = None
        # Scan may still be streaming new files; pick up any newly discovered videos.
        self._start_thumbnail_worker()

    def _on_thumbnail_ready(self, source_id: str, path: str):
        pm = QPixmap(path)
        if not pm.isNull():
            self._thumb_cache[source_id] = pm
            self._update_video_thumb(source_id)

    def _toggle_view_mode(self) -> None:
        self._waterfall_mode = not self._waterfall_mode
        self._view_btn.setText("瀑布流 ▼" if self._waterfall_mode else "等宽等高 ▼")
        self._adjust_columns(force=True)
        self._refresh_visible_thumbnails()

    def _on_size_changed(self, value: int) -> None:
        self._card_target_width = int(value)
        self._adjust_columns(force=True)
        self._refresh_visible_thumbnails()

    def _toggle_image_selection(self, source_id: str) -> None:
        selected = self._is_image_selected(source_id)
        self.image_toggle_requested.emit(source_id, not selected)

    def set_state(self, state: ProjectState) -> None:
        old_ids = [sf.source_id for sf in self._state.scanned_files]
        new_ids = [sf.source_id for sf in state.scanned_files]
        self._state = state
        self._update_stats_label()
        if old_ids == new_ids:
            self._refresh_visible_selection_state()
            self._update_footer_and_next_button()
            return
        self._start_thumbnail_worker()
        self._start_progressive_render()

    def set_scan_loading(self, loading: bool) -> None:
        self._scan_loading = loading
        self._update_stats_label()

    def append_scanned_files(self, new_files: list) -> None:
        if not new_files:
            return
        start_count = len(self._state.scanned_files)
        self._state.scanned_files.extend(new_files)
        self._start_thumbnail_worker()
        for i, sf in enumerate(self._state.scanned_files[start_count:], start=start_count):
            self._card_index_by_source[sf.source_id] = i
        self._update_stats_label()
        if self._render_budget == 0:
            self._render_budget = min(len(self._state.scanned_files), self._initial_render_limit)
        if self._near_bottom():
            self._render_budget = min(
                len(self._state.scanned_files),
                self._render_budget + self._render_expand_step,
            )
        if not self._render_timer.isActive():
            self._render_timer.start()

    def set_video_thumbnail(self, source_id: str, pixmap: QPixmap) -> None:
        self._thumb_cache[source_id] = pixmap
        self._update_video_thumb(source_id)

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
        self._render_timer.stop()
        self._card_widgets.clear()
        self._card_index_by_source.clear()
        self._card_refs.clear()
        self._thumb_aspect.clear()
        self._render_next_index = 0
        self._render_budget = 0
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w is not None and not sip.isdeleted(w):
                w.setParent(None)
                w.deleteLater()

    def _start_progressive_render(self) -> None:
        self._clear_grid()
        self._update_footer_and_next_button()
        self._render_budget = min(len(self._state.scanned_files), self._initial_render_limit)
        self._render_next_batch()
        if self._render_next_index < self._render_budget:
            self._render_timer.start()

    @staticmethod
    def _load_thumb_quick(path: str, size: QSize) -> QPixmap:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        src_size = reader.size()
        if src_size.isValid() and src_size.width() > 0 and src_size.height() > 0:
            scale = min(
                size.width() / src_size.width(),
                size.height() / src_size.height(),
            )
            if scale < 1.0:
                reader.setScaledSize(
                    QSize(
                        max(1, int(src_size.width() * scale)),
                        max(1, int(src_size.height() * scale)),
                    )
                )
        img = reader.read()
        pm = QPixmap.fromImage(img)
        return pm if not pm.isNull() else QPixmap()

    def _thumbnail_for_display(self, src: QPixmap, thumb_size) -> QPixmap:
        if src.isNull():
            return QPixmap()
        if self._waterfall_mode:
            return src.scaled(
                thumb_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        # Fill + center-crop for uniform cards.
        return src.scaled(
            thumb_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _set_thumb_pixmap(self, thumb: QLabel, src: QPixmap) -> None:
        shown = self._thumbnail_for_display(src, thumb.size())
        if shown.isNull():
            return
        thumb.setPixmap(shown)
        thumb.setText("")

    def _build_card_widget(self, sf, card_width: int) -> QFrame:
        card = QFrame()
        card.setObjectName("MaterialCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setProperty("sourceType", sf.type)
        card.setFixedWidth(card_width)
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 10, 10, 10)

        thumb_width = max(140, card_width - 20)
        thumb_height = self._thumb_height_for_source(sf, thumb_width)
        thumb = QLabel()
        thumb.setFixedSize(thumb_width, thumb_height)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("background: #f0f0f0; color: #888888; border-radius: 4px;")

        if sf.type == "image":
            pm = self._load_thumb_quick(sf.path, thumb.size())
            if not pm.isNull():
                self._thumb_aspect[sf.source_id] = max(0.1, pm.width() / max(1, pm.height()))
                self._set_thumb_pixmap(thumb, pm)
            else:
                thumb.setText("图片")
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.mousePressEvent = (
                lambda _e, sid=sf.source_id: self._toggle_image_selection(sid)
            )
        else:
            cached = self._thumb_cache.get(sf.source_id)
            if cached is not None and not cached.isNull():
                self._set_thumb_pixmap(thumb, cached)
            else:
                thumb.setText("视频 (提取中...)")

        name = QLabel()
        metrics = name.fontMetrics()
        elided_name = metrics.elidedText(sf.name, Qt.TextElideMode.ElideRight, thumb_width)
        name.setText(elided_name)
        name.setStyleSheet("font-size: 12px; color: #333;")
        name.setWordWrap(False)
        name.setToolTip(sf.path)

        v.addWidget(thumb)
        v.addWidget(name)

        cb = None
        btn = None
        if sf.type == "image":
            cb = QCheckBox("选用")
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(
                "QCheckBox { padding: 4px 0; } "
                "QCheckBox::indicator { width: 20px; height: 20px; }"
            )
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

        self._card_refs[sf.source_id] = {
            "card": card,
            "thumb": thumb,
            "checkbox": cb,
            "pick_btn": btn,
            "source_id": sf.source_id,
        }
        self._apply_card_selected_style(sf.source_id)
        return card

    def _thumb_height_for_source(self, sf, thumb_width: int) -> int:
        if not self._waterfall_mode:
            return max(96, min(260, int(thumb_width * 0.72)))
        aspect = self._thumb_aspect.get(sf.source_id)
        if aspect is None and sf.type == "image":
            reader = QImageReader(sf.path)
            size = reader.size()
            if size.isValid() and size.height() > 0:
                aspect = size.width() / size.height()
                self._thumb_aspect[sf.source_id] = aspect
        if aspect is None or aspect <= 0:
            aspect = 16 / 9
        return max(96, min(420, int(thumb_width / aspect)))

    def _render_next_batch(self) -> None:
        total = len(self._state.scanned_files)
        if self._render_next_index >= total:
            self._render_timer.stop()
            return
        if self._render_next_index >= self._render_budget:
            self._render_timer.stop()
            return
        cols, card_width = self._compute_layout_metrics(self._scroll.viewport().width())
        self._current_cols = cols
        self._current_card_width = card_width

        end = min(total, self._render_budget, self._render_next_index + self._render_batch_size)
        for i in range(self._render_next_index, end):
            sf = self._state.scanned_files[i]
            card = self._build_card_widget(sf, card_width)
            self._card_widgets.append(card)
            self._card_index_by_source[sf.source_id] = i
            self._grid_layout.addWidget(card, i // cols, i % cols)

        self._render_next_index = end
        if self._render_next_index >= total or self._render_next_index >= self._render_budget:
            self._render_timer.stop()

    def _near_bottom(self) -> bool:
        sb = self._scroll.verticalScrollBar()
        return (sb.maximum() - sb.value()) < 900

    def _on_scroll_for_lazy_render(self, _value: int) -> None:
        if self._render_next_index >= len(self._state.scanned_files):
            return
        if not self._near_bottom():
            return
        self._render_budget = min(
            len(self._state.scanned_files),
            self._render_budget + self._render_expand_step,
        )
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _apply_card_selected_style(self, source_id: str) -> None:
        ref = self._card_refs.get(source_id)
        if ref is None:
            return
        card = ref["card"]
        sf = next((x for x in self._state.scanned_files if x.source_id == source_id), None)
        if sf is None:
            return
        if sf.type == "image":
            selected = self._is_image_selected(source_id)
            cb = ref["checkbox"]
            if cb is not None:
                cb.blockSignals(True)
                cb.setChecked(selected)
                cb.blockSignals(False)
        else:
            n_frames = self._selected_video_frame_count(source_id)
            selected = n_frames > 0
            btn = ref["pick_btn"]
            if btn is not None:
                btn.setText("选择帧" if n_frames == 0 else f"已选 {n_frames} 帧")
                btn.setStyleSheet(
                    "background-color: #e6f2ff; color: #007bff; border: 1px solid #007bff;"
                    if n_frames > 0
                    else ""
                )
        card.setProperty("selected", selected)
        card.style().unpolish(card)
        card.style().polish(card)

    def _refresh_visible_selection_state(self) -> None:
        for sid in self._card_refs:
            self._apply_card_selected_style(sid)

    def _update_video_thumb(self, source_id: str) -> None:
        ref = self._card_refs.get(source_id)
        if ref is None:
            return
        thumb = ref["thumb"]
        pm = self._thumb_cache.get(source_id)
        if pm is None or pm.isNull():
            return
        self._thumb_aspect[source_id] = max(0.1, pm.width() / max(1, pm.height()))
        sf = next((x for x in self._state.scanned_files if x.source_id == source_id), None)
        if sf is not None:
            new_h = self._thumb_height_for_source(sf, thumb.width())
            thumb.setFixedSize(thumb.width(), new_h)
        self._set_thumb_pixmap(thumb, pm)

    def _refresh_visible_thumbnails(self) -> None:
        for sf in self._state.scanned_files:
            ref = self._card_refs.get(sf.source_id)
            if ref is None:
                continue
            thumb = ref["thumb"]
            if sf.type == "video":
                cached = self._thumb_cache.get(sf.source_id)
                if cached is not None and not cached.isNull():
                    self._set_thumb_pixmap(thumb, cached)
            else:
                pm = self._load_thumb_quick(sf.path, thumb.size())
                if not pm.isNull():
                    self._set_thumb_pixmap(thumb, pm)

    def _update_footer_and_next_button(self) -> None:
        n_selected = len([m for m in self._state.selected_materials if m.selected])
        self._next_btn.setEnabled(n_selected >= 1)
        if self._state.mode == "video":
            vid_ids = {scanned_file_source_id_for_material(m) for m in self._state.selected_materials if m.selected}
            self._footer_label.setText(f"已选素材: {n_selected} 帧（来自 {len(vid_ids)} 个视频）")
        else:
            self._footer_label.setText(f"已选素材: {n_selected} 张")

    def _update_stats_label(self) -> None:
        file_type_str = "视频" if self._state.mode == "video" else "图片"
        count = len(self._state.scanned_files)
        if self._scan_loading:
            self._stats_label.setText(
                f"扫描中… 已发现 {count} 个{file_type_str}文件（递归 {self._state.depth} 层）"
            )
        else:
            self._stats_label.setText(
                f"已找到 {count} 个{file_type_str}文件（递归 {self._state.depth} 层）"
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_columns()

    def _adjust_columns(self, *, force: bool = False):
        if not self._state or not self._state.scanned_files:
            return
        cols, card_width = self._compute_layout_metrics(self._scroll.viewport().width())
        if force or self._current_cols != cols or self._current_card_width != card_width:
            self._current_cols = cols
            self._current_card_width = card_width
            # Reflow existing cards only; avoid expensive full rebuild.
            while self._grid_layout.count():
                item = self._grid_layout.takeAt(0)
                if item.widget() is not None:
                    item.widget().setParent(self._container)
            for i, card in enumerate(self._card_widgets):
                card.setFixedWidth(card_width)
                if i < len(self._state.scanned_files):
                    sf = self._state.scanned_files[i]
                    ref = self._card_refs.get(sf.source_id)
                    if ref is not None:
                        thumb = ref["thumb"]
                        thumb_w = max(140, card_width - 20)
                        thumb_h = self._thumb_height_for_source(sf, thumb_w)
                        thumb.setFixedSize(thumb_w, thumb_h)
                self._grid_layout.addWidget(card, i // cols, i % cols)
            self._refresh_visible_thumbnails()

    def _compute_layout_metrics(self, viewport_width: int) -> tuple[int, int]:
        spacing = self._grid_layout.horizontalSpacing()
        if spacing < 0:
            spacing = 16

        margins = self._grid_layout.contentsMargins()
        available = viewport_width - margins.left() - margins.right()
        if available <= 0:
            return self._current_cols, self._card_min_width

        max_cols = max(1, (available + spacing) // (self._card_min_width + spacing))
        min_cols = max(1, (available + spacing + self._card_max_width - 1) // (self._card_max_width + spacing))

        target = max(self._card_min_width, min(self._card_max_width, self._card_target_width))
        desired_cols = max(1, int(round((available + spacing) / (target + spacing))))
        cols = max(min_cols, min(max_cols, desired_cols))

        card_width = (available - spacing * (cols - 1)) // cols
        card_width = max(self._card_min_width, min(self._card_max_width, card_width))
        return cols, card_width
