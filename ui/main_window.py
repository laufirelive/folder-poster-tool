import os
import uuid

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QMainWindow, QMessageBox, QStackedWidget

from core.extractor import extract_preview_frames
from core.scanner import scan_directory
from core.state_manager import StateManager
from models import Material, ProjectState
from ui.pages.home_page import HomePage
from ui.pages.materials_page import MaterialsPage
from ui.widgets.video_frames_modal import VideoFramesModal


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder Poster")
        self.resize(800, 600)

        self._state_manager = StateManager()
        self._project_state: ProjectState | None = None
        self._materials_page: MaterialsPage | None = None

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.home_page = HomePage(self.handle_start_scan)
        self.stacked_widget.addWidget(self.home_page)

    def handle_start_scan(self, path: str, mode: str, depth: int) -> None:
        path = path.strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "无效路径", "请选择存在的文件夹路径。")
            return

        files = scan_directory(path, mode, depth)
        if not files:
            QMessageBox.warning(self, "无文件", "该文件夹下没有匹配的文件。")
            return

        project_id = uuid.uuid4().hex
        state = ProjectState(
            project_id=project_id,
            input_path=os.path.abspath(path),
            mode=mode,
            depth=depth,
            scanned_files=files,
            current_step="materials",
        )
        self._state_manager.save_state(state)
        self._project_state = state

        if self._materials_page is None:
            self._materials_page = MaterialsPage(state, self)
            self._materials_page.image_toggle_requested.connect(self._on_image_toggle)
            self._materials_page.video_pick_requested.connect(self._on_video_pick)
            self.stacked_widget.addWidget(self._materials_page)
        else:
            self._materials_page.set_state(state)

        self.stacked_widget.setCurrentWidget(self._materials_page)

    def _on_image_toggle(self, source_id: str, selected: bool) -> None:
        if self._project_state is None:
            return
        mats = [m for m in self._project_state.selected_materials if m.source_id != source_id]
        if selected:
            mats.append(Material(source_id=source_id, frame_idx=None, selected=True))
        self._project_state.selected_materials = mats
        self._state_manager.save_state(self._project_state)
        if self._materials_page is not None:
            self._materials_page.set_state(self._project_state)

    def _on_video_pick(self, source_id: str) -> None:
        if self._project_state is None:
            return
        sf = next((f for f in self._project_state.scanned_files if f.source_id == source_id), None)
        if sf is None:
            return

        out_dir = os.path.join(
            self._state_manager.base_dir,
            self._project_state.project_id,
            "previews",
            source_id,
        )
        try:
            paths = extract_preview_frames(sf.path, out_dir, 32)
        except Exception as exc:
            QMessageBox.warning(self, "提取失败", str(exc))
            return

        pm = QPixmap(paths[0])
        if self._materials_page is not None and not pm.isNull():
            self._materials_page.set_video_thumbnail(source_id, pm)

        modal = VideoFramesModal(paths, initial_index=0, parent=self)
        if modal.exec() != QDialog.DialogCode.Accepted:
            return

        idx = modal.selected_frame_index()
        mats = [m for m in self._project_state.selected_materials if m.source_id != source_id]
        mats.append(Material(source_id=source_id, frame_idx=idx, selected=True))
        self._project_state.selected_materials = mats
        self._state_manager.save_state(self._project_state)
        if self._materials_page is not None:
            self._materials_page.set_state(self._project_state)
