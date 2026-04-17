import os
from typing import Iterable

from PyQt6.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.workers.extractor_worker import ExtractorWorker


class FrameThumbButton(QToolButton):
    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


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
        self._min_thumb_w = 200
        self._thumb_size = QSize(220, 124)
        self._current_cols = 8

        self._video_path = video_path
        self._preview_dir = preview_dir
        self._paths: list[str | None] = [None] * self.FRAME_COUNT
        for p in frame_paths:
            slot = self._slot_index_from_path(p)
            if slot is None:
                continue
            self._paths[slot] = os.path.abspath(p)
        self._selected: set[int] = set()
        if initial_selected_indices is not None:
            for i in initial_selected_indices:
                if 0 <= i < self.FRAME_COUNT:
                    self._selected.add(i)

        self._buttons: list[QToolButton] = []
        self._selectors: list[QCheckBox] = []
        self._cards: list[QFrame] = []
        self._extractor_thread: QThread | None = None
        self._extractor_worker: ExtractorWorker | None = None
        self._spinner_phase = 0
        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(250)
        self._loading_timer.timeout.connect(self._on_loading_tick)
        self._loading_timer.start()
        self.setStyleSheet(
            """
            QFrame#FrameCard {
                background: #ffffff;
                border: 2px solid #d8dee6;
                border-radius: 10px;
            }
            QFrame#FrameCard[selected="true"] {
                border-color: #1677ff;
                background: #edf4ff;
            }
            QToolButton#FrameButton {
                background: #ffffff;
                border: 1px solid #e2e6ec;
                border-radius: 8px;
                padding: 4px;
                color: #555;
            }
            QToolButton#FrameButton:hover:enabled {
                border-color: #75a6ef;
                background: #f7fbff;
            }
            QToolButton#FrameButton:disabled {
                color: #8f98a3;
                background: #f5f6f8;
                border-color: #dfe4ea;
            }
            QCheckBox#FrameCheck {
                spacing: 6px;
                padding-left: 4px;
            }
            """
        )

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._count_label = QLabel()
        self._count_label.setObjectName("selected_count_label")
        self._status_label = QLabel()
        self._update_toolbar_labels()
        toolbar.addWidget(self._count_label)
        toolbar.addSpacing(12)
        toolbar.addWidget(self._status_label)
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

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll)

        for i in range(self.FRAME_COUNT):
            card = QFrame()
            card.setObjectName("FrameCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 8, 8, 8)
            card_layout.setSpacing(6)

            btn = FrameThumbButton()
            btn.setObjectName("FrameButton")
            btn.setIconSize(self._thumb_size)
            btn.setToolTip("单击选择，双击预览")
            btn.clicked.connect(
                lambda checked=False, idx=i: self._selectors[idx].setChecked(
                    not self._selectors[idx].isChecked()
                )
            )
            btn.doubleClicked.connect(lambda idx=i: self._open_frame_preview(idx))
            card_layout.addWidget(btn)

            check = QCheckBox(f"选中第 {i + 1} 帧")
            check.setObjectName("FrameCheck")
            check.setStyleSheet(
                "QCheckBox { padding: 4px 0; } "
                "QCheckBox::indicator { width: 20px; height: 20px; }"
            )
            check.toggled.connect(lambda checked, idx=i: self._on_toggle_select(idx, checked))
            card_layout.addWidget(check)

            self._buttons.append(btn)
            self._selectors.append(check)
            self._cards.append(card)
            self._refresh_slot(i)
        self._relayout_grid()

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._refresh_highlight()
        if not self._all_slots_ready():
            self._start_extraction(regenerate=False)

    def _slot_index_from_path(self, path: str) -> int | None:
        name = os.path.basename(path)
        if not name.startswith("frame_") or not name.endswith(".png"):
            return None
        num = name[len("frame_") : -len(".png")]
        if not num.isdigit():
            return None
        idx = int(num) - 1
        if 0 <= idx < self.FRAME_COUNT:
            return idx
        return None

    def _set_button_icon(self, btn: QToolButton, path: str) -> None:
        pm = QPixmap(path)
        if not pm.isNull():
            scaled = pm.scaled(
                self._thumb_size.width(),
                self._thumb_size.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            btn.setIcon(QIcon(scaled))
            btn.setText("")

    def _update_toolbar_labels(self) -> None:
        self._count_label.setText(f"已选 {len(self._selected)}/{self.FRAME_COUNT}")
        loaded = sum(1 for p in self._paths if p)
        if self._extractor_thread is not None and self._extractor_thread.isRunning():
            self._status_label.setText(f"加载中 {loaded}/{self.FRAME_COUNT}")
        else:
            self._status_label.setText(f"已加载 {loaded}/{self.FRAME_COUNT}")

    def _refresh_slot(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._buttons):
            return
        btn = self._buttons[idx]
        check = self._selectors[idx]
        path = self._paths[idx]
        if path and os.path.isfile(path):
            btn.setEnabled(True)
            check.setEnabled(True)
            self._set_button_icon(btn, path)
            return
        btn.setEnabled(False)
        check.setEnabled(False)
        self._set_loading_indicator(btn)
        if idx in self._selected:
            self._selected.discard(idx)

    def _set_loading_indicator(self, btn: QToolButton) -> None:
        pm = QPixmap(36, 36)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(Qt.GlobalColor.darkGray, 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        start = (self._spinner_phase * 30) * 16
        span = 270 * 16
        painter.drawArc(6, 6, 24, 24, start, span)
        painter.end()
        btn.setIcon(QIcon(pm))
        btn.setText("加载中")

    def _on_toggle_select(self, idx: int, checked: bool) -> None:
        if idx < 0 or idx >= len(self._paths) or not self._paths[idx]:
            return
        if checked:
            self._selected.add(idx)
        else:
            self._selected.discard(idx)
        self._refresh_highlight()
        self._update_toolbar_labels()

    def _on_clear(self) -> None:
        self._selected.clear()
        self._refresh_highlight()
        self._update_toolbar_labels()

    def _on_regenerate(self) -> None:
        if self._extractor_thread is not None and self._extractor_thread.isRunning():
            return
        for idx in range(self.FRAME_COUNT):
            if idx in self._selected:
                continue
            self._paths[idx] = None
            self._refresh_slot(idx)
        self._refresh_highlight()
        self._update_toolbar_labels()
        self._start_extraction(regenerate=True)

    def _all_slots_ready(self) -> bool:
        return all(path and os.path.isfile(path) for path in self._paths)

    def _start_extraction(self, *, regenerate: bool) -> None:
        self._regenerate_btn.setEnabled(False)
        self._extractor_thread = QThread(self)
        self._extractor_worker = ExtractorWorker(
            self._video_path,
            self._preview_dir,
            self.FRAME_COUNT,
            regenerate=regenerate,
            keep_indices=sorted(self._selected),
        )
        self._extractor_worker.moveToThread(self._extractor_thread)
        self._extractor_thread.started.connect(self._extractor_worker.run)
        self._extractor_worker.frame_ready.connect(self._on_frame_ready)
        self._extractor_worker.finished_ok.connect(self._on_extractor_finished_ok)
        self._extractor_worker.finished_err.connect(self._on_extractor_finished_err)
        self._extractor_worker.finished_ok.connect(self._extractor_thread.quit)
        self._extractor_worker.finished_err.connect(self._extractor_thread.quit)
        self._extractor_worker.finished_ok.connect(self._extractor_worker.deleteLater)
        self._extractor_worker.finished_err.connect(self._extractor_worker.deleteLater)
        self._extractor_thread.finished.connect(self._on_extractor_thread_finished)
        self._extractor_thread.finished.connect(self._extractor_thread.deleteLater)
        self._extractor_thread.start()
        self._update_toolbar_labels()

    def _on_frame_ready(self, slot: int, frame_path: str) -> None:
        if slot < 0 or slot >= self.FRAME_COUNT:
            return
        self._paths[slot] = os.path.abspath(frame_path)
        self._refresh_slot(slot)
        self._refresh_highlight()
        self._update_toolbar_labels()

    def _on_extractor_finished_ok(self, paths: list[str]) -> None:
        for p in paths:
            slot = self._slot_index_from_path(p)
            if slot is None:
                continue
            self._paths[slot] = os.path.abspath(p)
            self._refresh_slot(slot)
        self._refresh_highlight()
        self._update_toolbar_labels()

    def _on_extractor_finished_err(self, err: str) -> None:
        QMessageBox.warning(self, "提取失败", err)
        self._update_toolbar_labels()

    def _on_extractor_thread_finished(self) -> None:
        self._extractor_thread = None
        self._extractor_worker = None
        self._regenerate_btn.setEnabled(True)
        self._update_toolbar_labels()
        if self._all_slots_ready() and self._loading_timer.isActive():
            self._loading_timer.stop()

    def _on_loading_tick(self) -> None:
        self._spinner_phase = (self._spinner_phase + 1) % 12
        any_pending = False
        for idx, btn in enumerate(self._buttons):
            if self._paths[idx]:
                continue
            self._set_loading_indicator(btn)
            any_pending = True
        if not any_pending and self._loading_timer.isActive():
            self._loading_timer.stop()

    def _refresh_highlight(self) -> None:
        for i, b in enumerate(self._buttons):
            selected = i in self._selected and bool(self._paths[i])
            cb = self._selectors[i]
            card = self._cards[i]
            cb.blockSignals(True)
            cb.setChecked(selected)
            cb.blockSignals(False)
            card.setProperty("selected", selected)
            card.style().unpolish(card)
            card.style().polish(card)
            b.style().unpolish(b)
            b.style().polish(b)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Ensure viewport width is final after modal is shown.
        QTimer.singleShot(0, self._relayout_grid)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cols = self._compute_columns(self._scroll.viewport().width())
        if cols != self._current_cols:
            self._current_cols = cols
            self._relayout_grid()

    def _compute_columns(self, viewport_width: int) -> int:
        spacing = self._grid.horizontalSpacing()
        if spacing < 0:
            spacing = 10
        if viewport_width <= 0:
            return self._current_cols

        min_cell = self._min_thumb_w + 24
        cols = max(1, (viewport_width + spacing) // (min_cell + spacing))
        return max(2, min(6, cols))

    def _relayout_grid(self) -> None:
        cols = self._compute_columns(self._scroll.viewport().width())
        self._current_cols = cols
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(self._grid_container)
        for i, card in enumerate(self._cards):
            self._grid.addWidget(card, i // cols, i % cols)

    @staticmethod
    def _frame_detail_text(idx: int, path: str, pixmap: QPixmap) -> str:
        return (
            f"槽位: {idx + 1}/{VideoFramesModal.FRAME_COUNT}\n"
            f"尺寸: {pixmap.width()} x {pixmap.height()}\n"
            f"文件: {path}"
        )

    def _open_frame_preview(self, idx: int) -> None:
        if idx < 0 or idx >= self.FRAME_COUNT:
            return
        path = self._paths[idx]
        if not path or not os.path.isfile(path):
            return

        pm = QPixmap(path)
        if pm.isNull():
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"帧预览 #{idx + 1:02d}")
        dlg.resize(980, 680)

        layout = QVBoxLayout(dlg)
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setPixmap(
            pm.scaled(
                920,
                560,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        detail = QLabel(self._frame_detail_text(idx, path, pm))
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(dlg.reject)
        close_box.accepted.connect(dlg.accept)

        layout.addWidget(image)
        layout.addWidget(detail)
        layout.addWidget(close_box)
        dlg.exec()

    def selected_frame_indices(self) -> list[int]:
        return sorted(self._selected)

    def reject(self) -> None:
        self._stop_extractor()
        super().reject()

    def accept(self) -> None:
        self._stop_extractor()
        super().accept()

    def _stop_extractor(self) -> None:
        if self._extractor_worker is not None:
            self._extractor_worker.request_stop()
        if self._extractor_thread is not None and self._extractor_thread.isRunning():
            self._extractor_thread.quit()
            self._extractor_thread.wait(500)
        if self._loading_timer.isActive():
            self._loading_timer.stop()
