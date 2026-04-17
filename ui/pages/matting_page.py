"""
Matting progress UI: dual-pane responsive card grids (source vs matte result).
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Union

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from models import ProjectState

# (display_name, source_image_path, material_key)
MattingRowSpec = Tuple[str, str, Tuple[str, Optional[int]]]

_THUMB_W, _THUMB_H = 220, 124


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
    pm.fill(Qt.GlobalColor.lightGray)
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
    back_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    retry_all_failed_requested = pyqtSignal()
    next_requested = pyqtSignal()

    def __init__(
        self,
        project_state: ProjectState,
        rows: List[MattingRowSpec],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._state = project_state
        self._rows: List[MattingRowSpec] = list(rows)
        self._left_cards: list[QFrame] = []
        self._right_cards: list[QFrame] = []
        self._row_widgets: List[dict] = []
        self._running_rows: set[int] = set()
        self._spinner_phase = 0
        self._current_cols = 1

        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(220)
        self._loading_timer.timeout.connect(self._on_loading_tick)

        self.setStyleSheet(
            """
            QFrame#MattingCard {
                background: #ffffff;
                border: 1px solid #dde3ea;
                border-radius: 10px;
            }
            QFrame#MattingCard[status="running"] {
                border-color: #6aa8ff;
                background: #f7fbff;
            }
            QFrame#MattingCard[status="done"] {
                border-color: #6dcf8b;
                background: #f6fff8;
            }
            QFrame#MattingCard[status="error"] {
                border-color: #f2a5a5;
                background: #fff7f7;
            }
            QToolButton#MattingThumb {
                border: 1px solid #e1e6ec;
                border-radius: 8px;
                background: #f3f5f7;
                padding: 4px;
                text-align: center;
            }
            QToolButton#MattingThumb:hover:enabled {
                border-color: #87b5ff;
            }
            """
        )

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)

        self._current_file_label = QLabel("当前文件：—", self)
        self._remaining_label = QLabel("剩余：—", self)
        info = QHBoxLayout()
        info.addWidget(self._current_file_label)
        info.addStretch()
        info.addWidget(self._remaining_label)

        self._left_scroll = QScrollArea(self)
        self._right_scroll = QScrollArea(self)
        for sc in (self._left_scroll, self._right_scroll):
            sc.setWidgetResizable(True)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sc.setFrameShape(QFrame.Shape.StyledPanel)

        left_host = QWidget()
        right_host = QWidget()
        self._left_grid = QGridLayout(left_host)
        self._right_grid = QGridLayout(right_host)
        for grid in (self._left_grid, self._right_grid):
            grid.setSpacing(12)
            grid.setContentsMargins(10, 10, 10, 10)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._left_scroll.setWidget(left_host)
        self._right_scroll.setWidget(right_host)

        titles = QHBoxLayout()
        titles.addWidget(QLabel("<b>原始</b>", self), stretch=1)
        titles.addWidget(QLabel("<b>抠像结果</b>", self), stretch=1)

        mid = QHBoxLayout()
        mid.addWidget(self._left_scroll, stretch=1)
        mid.addWidget(self._right_scroll, stretch=1)

        self._back_btn = QPushButton("← 返回上一步", self)
        self._back_btn.clicked.connect(self.back_requested.emit)

        self.retry_failed_button = QPushButton("重试失败项", self)
        self.retry_failed_button.setVisible(False)
        self.retry_failed_button.setEnabled(False)
        self.retry_failed_button.clicked.connect(self.retry_all_failed_requested.emit)

        self._stop_btn = QPushButton("停止抠像", self)
        self._stop_btn.clicked.connect(self.cancel_requested.emit)
        self._stop_btn.setEnabled(False)

        self._next_btn = QPushButton("下一步", self)
        self._next_btn.clicked.connect(self.next_requested.emit)
        self._next_btn.setEnabled(False)
        self._next_btn.setVisible(False)

        bottom = QHBoxLayout()
        bottom.addWidget(self._back_btn)
        bottom.addStretch()
        bottom.addWidget(self.retry_failed_button)
        bottom.addWidget(self._stop_btn)
        bottom.addWidget(self._next_btn)

        outer = QVBoxLayout(self)
        outer.addWidget(self._progress)
        outer.addLayout(info)
        outer.addLayout(titles)
        outer.addLayout(mid, stretch=1)
        outer.addLayout(bottom)

        self._build_rows()

    def set_failures_present(self, has_failures: bool) -> None:
        self.retry_failed_button.setVisible(has_failures)
        self.retry_failed_button.setEnabled(has_failures)

    def set_worker_running(self, running: bool) -> None:
        self._stop_btn.setEnabled(running)
        self._back_btn.setEnabled(not running)
        self._next_btn.setEnabled(not running and self._next_btn.isVisible())
        if self.retry_failed_button.isVisible():
            self.retry_failed_button.setEnabled(not running)
        if not running and not self._running_rows and self._loading_timer.isActive():
            self._loading_timer.stop()

    def set_ready_for_next(self, ready: bool) -> None:
        self._next_btn.setVisible(ready)
        self._next_btn.setEnabled(ready and not self._stop_btn.isEnabled())

    def set_state(self, state: ProjectState) -> None:
        self._state = state

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_cards()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._relayout_cards)

    def _build_rows(self) -> None:
        self._left_cards.clear()
        self._right_cards.clear()
        self._row_widgets.clear()

        for idx, (display_name, source_path, _key) in enumerate(self._rows):
            source_card = QFrame()
            source_card.setObjectName("MattingCard")
            source_card.setProperty("status", MattingRowStatus.PENDING.value)
            lv = QVBoxLayout(source_card)

            name_lbl = QLabel(display_name)
            name_lbl.setWordWrap(True)
            source_btn = QToolButton()
            source_btn.setObjectName("MattingThumb")
            source_btn.setIconSize(_placeholder_pixmap().size())
            source_btn.setToolTip("点击预览原图")
            source_btn.setFixedHeight(_THUMB_H + 18)
            source_btn.setIcon(QIcon(_load_thumb(source_path)))
            source_btn.clicked.connect(lambda checked=False, i=idx: self._preview_source(i))
            source_status = QLabel(_STATUS_LABEL[MattingRowStatus.PENDING])
            lv.addWidget(name_lbl)
            lv.addWidget(source_btn)
            lv.addWidget(source_status)

            matte_card = QFrame()
            matte_card.setObjectName("MattingCard")
            matte_card.setProperty("status", MattingRowStatus.PENDING.value)
            rv = QVBoxLayout(matte_card)
            matte_name = QLabel(display_name)
            matte_name.setWordWrap(True)
            matte_btn = QToolButton()
            matte_btn.setObjectName("MattingThumb")
            matte_btn.setIconSize(_placeholder_pixmap().size())
            matte_btn.setToolTip("点击预览抠像结果")
            matte_btn.setFixedHeight(_THUMB_H + 18)
            matte_btn.setIcon(QIcon(_placeholder_pixmap()))
            matte_btn.clicked.connect(lambda checked=False, i=idx: self._preview_matte(i))
            matte_status = QLabel(_STATUS_LABEL[MattingRowStatus.PENDING])
            rv.addWidget(matte_name)
            rv.addWidget(matte_btn)
            rv.addWidget(matte_status)

            self._left_cards.append(source_card)
            self._right_cards.append(matte_card)
            self._row_widgets.append(
                {
                    "source_path": source_path,
                    "matte_path": None,
                    "source_status": source_status,
                    "matte_status": matte_status,
                    "source_card": source_card,
                    "matte_card": matte_card,
                    "matte_btn": matte_btn,
                }
            )

        self._relayout_cards()

    def _compute_columns(self, viewport_width: int) -> int:
        spacing = self._left_grid.horizontalSpacing()
        if spacing < 0:
            spacing = 12
        if viewport_width <= 0:
            return self._current_cols
        min_card = 260
        cols = max(1, (viewport_width + spacing) // (min_card + spacing))
        return max(1, min(3, cols))

    def _relayout_cards(self) -> None:
        cols = min(
            self._compute_columns(self._left_scroll.viewport().width()),
            self._compute_columns(self._right_scroll.viewport().width()),
        )
        self._current_cols = cols

        for grid in (self._left_grid, self._right_grid):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget() is not None:
                    item.widget().setParent(grid.parentWidget())

        spacing = self._left_grid.horizontalSpacing()
        if spacing < 0:
            spacing = 12
        lm = self._left_grid.contentsMargins()
        rm = self._right_grid.contentsMargins()
        left_avail = self._left_scroll.viewport().width() - lm.left() - lm.right()
        right_avail = self._right_scroll.viewport().width() - rm.left() - rm.right()
        if cols > 0:
            left_w = (left_avail - spacing * (cols - 1)) // cols
            right_w = (right_avail - spacing * (cols - 1)) // cols
            card_w = max(220, min(left_w, right_w))
        else:
            card_w = 260

        for i, (left_card, right_card) in enumerate(zip(self._left_cards, self._right_cards)):
            left_card.setFixedWidth(card_w)
            right_card.setFixedWidth(card_w)
            self._left_grid.addWidget(left_card, i // cols, i % cols)
            self._right_grid.addWidget(right_card, i // cols, i % cols)

    def _set_card_status(self, row: dict, status: MattingRowStatus) -> None:
        status_val = status.value
        for key in ("source_card", "matte_card"):
            card = row[key]
            card.setProperty("status", status_val)
            card.style().unpolish(card)
            card.style().polish(card)

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
        label = _STATUS_LABEL.get(st, str(st))
        row["source_status"].setText(label)
        row["matte_status"].setText(label)
        self._set_card_status(row, st)

        matte_btn = row["matte_btn"]
        if st == MattingRowStatus.DONE and matte_preview_path:
            row["matte_path"] = matte_preview_path
            matte_btn.setIcon(QIcon(_load_thumb(matte_preview_path)))
            self._running_rows.discard(index)
        elif st == MattingRowStatus.RUNNING:
            row["matte_path"] = None
            self._running_rows.add(index)
            self._set_loading_indicator(matte_btn)
        elif st == MattingRowStatus.ERROR:
            row["matte_path"] = None
            self._running_rows.discard(index)
            pm = _placeholder_pixmap()
            matte_btn.setIcon(QIcon(pm))
            matte_btn.setText("失败")
        else:
            row["matte_path"] = None
            self._running_rows.discard(index)
            matte_btn.setIcon(QIcon(_placeholder_pixmap()))
            matte_btn.setText("")

        if self._running_rows and not self._loading_timer.isActive():
            self._loading_timer.start()
        if not self._running_rows and self._loading_timer.isActive():
            self._loading_timer.stop()

    def _set_loading_indicator(self, btn: QToolButton) -> None:
        pm = QPixmap(40, 40)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(Qt.GlobalColor.darkGray, 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        start = (self._spinner_phase * 30) * 16
        span = 280 * 16
        painter.drawArc(8, 8, 24, 24, start, span)
        painter.end()
        btn.setIcon(QIcon(pm))
        btn.setText("处理中...")

    def _on_loading_tick(self) -> None:
        if not self._running_rows:
            self._loading_timer.stop()
            return
        self._spinner_phase = (self._spinner_phase + 1) % 12
        for idx in list(self._running_rows):
            if 0 <= idx < len(self._row_widgets):
                self._set_loading_indicator(self._row_widgets[idx]["matte_btn"])

    def set_overall_progress(self, percent: int) -> None:
        self._progress.setValue(max(0, min(100, int(percent))))

    def set_current_label(self, name: str, remaining: Tuple[int, int]) -> None:
        rem, total = remaining
        self._current_file_label.setText(f"当前文件：{name}")
        self._remaining_label.setText(f"剩余 {rem}/{total}")

    @staticmethod
    def _detail_text(path: str, pm: QPixmap) -> str:
        return f"尺寸: {pm.width()} x {pm.height()}\n文件: {path}"

    def _open_preview(self, path: str, title: str) -> None:
        if not path or not os.path.isfile(path):
            return
        pm = QPixmap(path)
        if pm.isNull():
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
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
        detail = QLabel(self._detail_text(path, pm))
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(dlg.reject)
        box.accepted.connect(dlg.accept)
        layout.addWidget(image)
        layout.addWidget(detail)
        layout.addWidget(box)
        dlg.exec()

    def _preview_source(self, index: int) -> None:
        if 0 <= index < len(self._row_widgets):
            path = self._row_widgets[index]["source_path"]
            self._open_preview(path, "原图预览")

    def _preview_matte(self, index: int) -> None:
        if 0 <= index < len(self._row_widgets):
            path = self._row_widgets[index]["matte_path"]
            if path:
                self._open_preview(path, "抠像结果预览")
