import os
import threading
import uuid

from PyQt6.QtCore import QThread, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import QDialog, QMainWindow, QMessageBox, QStackedWidget

from core.extractor import extract_preview_frames
from core.material_paths import resolve_material_raster_path
from core.scanner import scan_directory
from core.state_manager import StateManager
from models import (
    Material,
    MatteRecord,
    ProjectState,
    material_source_id_for_video,
    scanned_file_source_id_for_material,
)
from ui.pages.export_page import ExportPage
from ui.pages.home_page import HomePage
from ui.pages.matting_page import MattingPage, MattingRowStatus
from ui.pages.materials_page import MaterialsPage
from ui.widgets.video_frames_modal import VideoFramesModal
from ui.workers.matting_worker import MattingWorker
from ui.workers.psd_export_worker import PsdExportWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder Poster")
        self.resize(800, 600)

        self._state_manager = StateManager()
        self._project_state: ProjectState | None = None
        self._materials_page: MaterialsPage | None = None
        self._matting_page: MattingPage | None = None
        self._export_page: ExportPage | None = None

        self._matting_thread: QThread | None = None
        self._matting_worker: MattingWorker | None = None
        self._cancel_event: threading.Event | None = None
        self._matting_records: list[MatteRecord] = []
        self._matting_row_data: list[tuple[str, str, Material]] = []
        self._matting_total: int = 0
        self._matting_cancel_requested: bool = False

        self._psd_thread: QThread | None = None
        self._psd_worker: PsdExportWorker | None = None
        self._pending_psd_export_path: str | None = None

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
            self._materials_page.next_requested.connect(self._on_materials_next)
            self.stacked_widget.addWidget(self._materials_page)
        else:
            self._materials_page.set_state(state)

        self.stacked_widget.setCurrentWidget(self._materials_page)

    def _on_image_toggle(self, source_id: str, selected: bool) -> None:
        if self._project_state is None:
            return
        mats = [
            m
            for m in self._project_state.selected_materials
            if scanned_file_source_id_for_material(m) != source_id
        ]
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
        mats = [
            m
            for m in self._project_state.selected_materials
            if scanned_file_source_id_for_material(m) != source_id
        ]
        mats.append(
            Material(
                source_id=material_source_id_for_video(source_id, idx),
                frame_idx=idx,
                selected=True,
            )
        )
        self._project_state.selected_materials = mats
        self._state_manager.save_state(self._project_state)
        if self._materials_page is not None:
            self._materials_page.set_state(self._project_state)

    def _on_materials_next(self) -> None:
        if self._project_state is None:
            return
        selected = [m for m in self._project_state.selected_materials if m.selected]
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择至少一个素材。")
            return

        base = self._state_manager.base_dir
        row_work: list[tuple[str, str, Material]] = []
        missing_labels: list[str] = []

        for m in selected:
            rpath = resolve_material_raster_path(base, self._project_state, m)
            sf = next(
                (
                    f
                    for f in self._project_state.scanned_files
                    if f.source_id == scanned_file_source_id_for_material(m)
                ),
                None,
            )
            if rpath is None or sf is None:
                label = sf.name if sf else m.source_id
                missing_labels.append(label)
                continue
            display = sf.name
            if m.frame_idx is not None:
                display = f"{sf.name} · 帧 {m.frame_idx + 1}"
            row_work.append((display, rpath, m))

        if missing_labels:
            QMessageBox.warning(
                self,
                "缺少预览文件",
                "以下素材缺少可用的源图或视频帧，请先完成选择：\n"
                + "\n".join(missing_labels),
            )
            return

        if not row_work:
            return

        self._project_state.current_step = "matting"
        self._state_manager.save_state(self._project_state)

        if self._matting_page is not None:
            self.stacked_widget.removeWidget(self._matting_page)
            self._matting_page.deleteLater()
            self._matting_page = None

        specs = [(d, p, (mat.source_id, mat.frame_idx)) for d, p, mat in row_work]
        self._matting_page = MattingPage(self._project_state, specs, self)
        self._matting_page.cancel_requested.connect(self._on_matting_cancel)
        self.stacked_widget.addWidget(self._matting_page)
        self.stacked_widget.setCurrentWidget(self._matting_page)

        self._matting_row_data = row_work
        self._matting_total = len(row_work)
        self._matting_records = []
        self._matting_cancel_requested = False
        self._cancel_event = threading.Event()

        self._matting_thread = QThread()
        self._matting_worker = MattingWorker(
            row_work,
            self._state_manager.base_dir,
            self._project_state.project_id,
            self._cancel_event,
        )
        self._matting_worker.moveToThread(self._matting_thread)
        self._matting_thread.started.connect(self._matting_worker.run)
        self._matting_worker.progress.connect(self._on_matting_progress)
        self._matting_worker.row_done.connect(self._on_matting_row_done)
        self._matting_worker.finished.connect(self._on_matting_worker_finished)
        self._matting_worker.finished.connect(self._matting_thread.quit)
        self._matting_worker.finished.connect(self._matting_worker.deleteLater)
        self._matting_thread.finished.connect(self._on_matting_thread_finished)
        self._matting_thread.start()

    def _on_matting_progress(self, index: int, total: int, _source_path: str, name: str) -> None:
        if self._matting_page is None:
            return
        self._matting_page.set_row_status(index, MattingRowStatus.RUNNING)
        pct = int(100 * index / total) if total else 0
        self._matting_page.set_overall_progress(pct)
        self._matting_page.set_current_label(name, (total - index, total))

    def _on_matting_row_done(self, index: int, matte_path: str, ok: bool, err: str) -> None:
        if self._matting_page is None:
            return
        total = self._matting_total
        if ok:
            self._matting_page.set_row_status(index, MattingRowStatus.DONE, matte_path)
            if 0 <= index < len(self._matting_row_data):
                _name, src_path, mat = self._matting_row_data[index]
                mtime = os.path.getmtime(src_path)
                self._matting_records.append(
                    MatteRecord(
                        source_id=mat.source_id,
                        source_mtime=mtime,
                        matte_path=matte_path,
                        is_active=True,
                    )
                )
        else:
            self._matting_page.set_row_status(index, MattingRowStatus.ERROR, None)
        pct = int(100 * (index + 1) / total) if total else 100
        self._matting_page.set_overall_progress(pct)

    def _on_matting_cancel(self) -> None:
        if self._matting_thread is None or not self._matting_thread.isRunning():
            return
        self._matting_cancel_requested = True
        if self._cancel_event is not None:
            self._cancel_event.set()

    def _on_matting_worker_finished(self) -> None:
        if self._project_state is not None:
            self._project_state.matte_map = list(self._matting_records)
            self._state_manager.save_state(self._project_state)
        if self._matting_cancel_requested and self._project_state is not None:
            self._project_state.current_step = "materials"
            self._state_manager.save_state(self._project_state)
            if self._materials_page is not None:
                self._materials_page.set_state(self._project_state)
            self.stacked_widget.setCurrentWidget(self._materials_page)
        elif self._project_state is not None and not self._matting_cancel_requested:
            self._project_state.current_step = "export"
            self._state_manager.save_state(self._project_state)
            self._ensure_export_page()
            self.stacked_widget.setCurrentWidget(self._export_page)
        self._matting_worker = None

    def _on_matting_thread_finished(self) -> None:
        self._matting_thread = None
        self._cancel_event = None

    def _ensure_export_page(self) -> None:
        assert self._project_state is not None
        if self._export_page is None:
            self._export_page = ExportPage(self._project_state, self)
            self._export_page.export_requested.connect(self._on_export_requested)
            self._export_page.back_requested.connect(self._on_export_back)
            self.stacked_widget.addWidget(self._export_page)
        else:
            self._export_page.set_state(self._project_state)

    def _on_export_back(self) -> None:
        if self._project_state is None:
            return
        self._project_state.current_step = "matting"
        self._state_manager.save_state(self._project_state)
        if self._matting_page is not None:
            self.stacked_widget.setCurrentWidget(self._matting_page)

    def _on_export_requested(self, path: str, width: int, height: int) -> None:
        if self._project_state is None:
            return
        if self._psd_thread is not None and self._psd_thread.isRunning():
            QMessageBox.information(self, "请稍候", "正在导出 PSD…")
            return
        self._pending_psd_export_path = path
        self._psd_thread = QThread()
        self._psd_worker = PsdExportWorker(
            self._project_state.matte_map,
            width,
            height,
            path,
        )
        self._psd_worker.moveToThread(self._psd_thread)
        self._psd_thread.started.connect(self._psd_worker.run)
        self._psd_worker.finished_ok.connect(self._on_psd_export_ok)
        self._psd_worker.finished_err.connect(self._on_psd_export_err)
        self._psd_worker.finished_ok.connect(self._psd_thread.quit)
        self._psd_worker.finished_err.connect(self._psd_thread.quit)
        self._psd_worker.finished_ok.connect(self._psd_worker.deleteLater)
        self._psd_worker.finished_err.connect(self._psd_worker.deleteLater)
        self._psd_thread.finished.connect(self._on_psd_thread_finished_export)
        self._psd_thread.start()

    def _on_psd_export_ok(self) -> None:
        path = self._pending_psd_export_path
        self._pending_psd_export_path = None
        QMessageBox.information(self, "导出成功", "PSD 已保存。")
        if path:
            folder = os.path.dirname(path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _on_psd_export_err(self, err: str) -> None:
        self._pending_psd_export_path = None
        QMessageBox.critical(self, "导出失败", err)

    def _on_psd_thread_finished_export(self) -> None:
        self._psd_thread = None
        self._psd_worker = None
