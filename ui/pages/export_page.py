"""
完成页 (export): summary, save folder, canvas presets, export PSD / back.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# Running `python ui/pages/export_page.py` adds project root for imports.
if __name__ == "__main__":
    _proj_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_proj_root))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from models import ProjectState

_DEFAULT_PSD_NAME = "folder_poster_export.psd"

_PRESET_4K = (4000, 6000)
_PRESET_2K = (2000, 3000)


class ExportPage(QWidget):
    export_requested = pyqtSignal(str, int, int)
    back_requested = pyqtSignal()

    def __init__(
        self,
        project_state: ProjectState,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._state = project_state

        header = QHBoxLayout()
        back_btn = QPushButton("← 返回", self)
        back_btn.clicked.connect(self.back_requested.emit)
        title = QLabel("Folder Poster", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(back_btn)
        header.addWidget(title, stretch=1)

        self._summary_title = QLabel("✅ 抠像完成", self)
        self._summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._summary_count = QLabel(self)
        self._summary_count.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._path_edit = QLineEdit(self)
        self._path_edit.setText(project_state.input_path or "")
        browse_btn = QPushButton("浏览", self)
        browse_btn.clicked.connect(self._browse_directory)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("保存位置:", self))
        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(browse_btn)

        hint = QLabel("默认: 输入文件夹路径", self)
        hint.setStyleSheet("color: #888888;")

        self._size_combo = QComboBox(self)
        self._size_combo.addItem("4000 × 6000 (推荐)", _PRESET_4K)
        self._size_combo.addItem("2000 × 3000", _PRESET_2K)
        self._size_combo.addItem("自定义", None)
        self._size_combo.currentIndexChanged.connect(self._on_preset_changed)

        self._custom_label = QLabel("须保持 2:3", self)
        self._width_spin = QSpinBox(self)
        self._height_spin = QSpinBox(self)
        for sp in (self._width_spin, self._height_spin):
            sp.setRange(2, 30000)
        self._width_spin.setValue(_PRESET_4K[0])
        self._height_spin.setValue(_PRESET_4K[1])
        self._width_spin.valueChanged.connect(self._on_width_changed)
        self._height_spin.valueChanged.connect(self._on_height_changed)

        custom_row = QHBoxLayout()
        custom_row.addWidget(self._custom_label)
        custom_row.addWidget(QLabel("宽:", self))
        custom_row.addWidget(self._width_spin)
        custom_row.addWidget(QLabel("高:", self))
        custom_row.addWidget(self._height_spin)
        custom_row.addStretch()

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("画布尺寸:", self))
        size_row.addWidget(self._size_combo)
        size_row.addWidget(QLabel("px（2:3）", self))
        size_row.addStretch()

        export_btn = QPushButton("导出 PSD", self)
        export_btn.clicked.connect(self._on_export_clicked)

        outer = QVBoxLayout(self)
        outer.addLayout(header)
        outer.addSpacing(12)
        outer.addWidget(self._summary_title)
        outer.addWidget(self._summary_count)
        outer.addSpacing(16)
        outer.addLayout(path_row)
        outer.addWidget(hint)
        outer.addSpacing(8)
        outer.addLayout(size_row)
        outer.addLayout(custom_row)
        outer.addStretch()
        outer.addWidget(export_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._refresh_summary()
        self._on_preset_changed(self._size_combo.currentIndex())

    def set_state(self, state: ProjectState) -> None:
        self._state = state
        if not self._path_edit.text().strip():
            self._path_edit.setText(state.input_path or "")
        self._refresh_summary()

    def _active_matte_count(self) -> int:
        return sum(1 for r in self._state.matte_map if r.is_active)

    def _refresh_summary(self) -> None:
        n = self._active_matte_count()
        self._summary_count.setText(f"共 {n} 张素材已抠像")

    def _browse_directory(self) -> None:
        start = self._path_edit.text().strip() or self._state.input_path or ""
        path = QFileDialog.getExistingDirectory(self, "选择保存文件夹", start)
        if path:
            self._path_edit.setText(path)

    def _on_preset_changed(self, index: int) -> None:
        data = self._size_combo.itemData(index)
        custom = data is None
        self._custom_label.setVisible(custom)
        self._width_spin.setVisible(custom)
        self._height_spin.setVisible(custom)
        if not custom and data is not None:
            w, h = data
            self._width_spin.blockSignals(True)
            self._height_spin.blockSignals(True)
            self._width_spin.setValue(w)
            self._height_spin.setValue(h)
            self._width_spin.blockSignals(False)
            self._height_spin.blockSignals(False)

    def _on_width_changed(self, value: int) -> None:
        if self._size_combo.currentData() is None:
            new_h = max(2, value * 3 // 2)
            if new_h != self._height_spin.value():
                self._height_spin.blockSignals(True)
                self._height_spin.setValue(new_h)
                self._height_spin.blockSignals(False)

    def _on_height_changed(self, value: int) -> None:
        if self._size_combo.currentData() is None:
            new_w = max(2, value * 2 // 3)
            if new_w != self._width_spin.value():
                self._width_spin.blockSignals(True)
                self._width_spin.setValue(new_w)
                self._width_spin.blockSignals(False)

    def _canvas_size(self) -> tuple[int, int]:
        data = self._size_combo.currentData()
        if data is not None:
            w, h = data
            return int(w), int(h)
        return self._width_spin.value(), self._height_spin.value()

    def _on_export_clicked(self) -> None:
        raw = self._path_edit.text().strip()
        if not raw:
            QMessageBox.warning(self, "保存位置", "请选择保存文件夹。")
            return
        directory = os.path.abspath(raw)
        if not os.path.isdir(directory):
            QMessageBox.warning(
                self,
                "保存位置",
                "保存路径不是有效的文件夹，请重新选择。",
            )
            return
        out_path = os.path.join(directory, _DEFAULT_PSD_NAME)
        w, h = self._canvas_size()
        self.export_requested.emit(out_path, w, h)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    from models import MatteRecord, ProjectState

    app = QApplication(sys.argv)
    state = ProjectState(
        project_id="demo_export",
        input_path=str(Path.home()),
        mode="image",
        matte_map=[
            MatteRecord("a", 0.0, "/tmp/x.png", True),
            MatteRecord("b", 0.0, "/tmp/y.png", True),
        ],
    )
    page = ExportPage(state)
    page.setWindowTitle("Export page demo")
    page.resize(520, 420)
    page.export_requested.connect(
        lambda p, w, h: print("export_requested:", p, w, h)
    )
    page.back_requested.connect(lambda: print("back_requested"))
    page.show()
    sys.exit(app.exec())
