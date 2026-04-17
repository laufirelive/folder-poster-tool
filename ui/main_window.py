import os
import shutil
import threading
import uuid

from PyQt6.QtCore import QThread, QUrl
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import QDialog, QMainWindow, QMessageBox, QStackedWidget

from core.model_manager import ModelManager, is_model_missing_error
from core.material_paths import resolve_material_raster_path
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
from ui.pages.model_download_page import ModelDownloadPage
from ui.widgets.video_frames_modal import VideoFramesModal
from ui.workers.matting_worker import MattingWorker
from ui.workers.psd_export_worker import PsdExportWorker
from ui.workers.scanner_worker import ScannerWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder Poster")
        self.resize(800, 600)

        self._state_manager = StateManager()
        self._model_manager = ModelManager()
        self._cache_dir = os.path.expanduser("~/.folder-poster/cache")
        self._project_state: ProjectState | None = None
        self._materials_page: MaterialsPage | None = None
        self._matting_page: MattingPage | None = None
        self._export_page: ExportPage | None = None
        self._model_download_page: ModelDownloadPage | None = None

        self._matting_thread: QThread | None = None
        self._matting_worker: MattingWorker | None = None
        self._cancel_event: threading.Event | None = None
        self._matting_records: list[MatteRecord] = []
        self._matting_row_data: list[tuple[str, str, Material]] = []
        self._matting_total: int = 0
        self._matting_cancel_requested: bool = False
        self._matting_any_failure: bool = False
        self._matting_model_missing: bool = False

        self._psd_thread: QThread | None = None
        self._psd_worker: PsdExportWorker | None = None
        self._pending_psd_export_path: str | None = None
        self._scan_thread: QThread | None = None
        self._scan_worker: ScannerWorker | None = None

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.home_page = HomePage(self.handle_start_scan)
        self.stacked_widget.addWidget(self.home_page)
        self._apply_model_gate()

    def _apply_model_gate(self) -> None:
        if self._model_manager.is_installed():
            self.stacked_widget.setCurrentWidget(self.home_page)
            return
        self._show_model_download_page()

    def _show_model_download_page(self) -> None:
        if self._model_download_page is None:
            self._model_download_page = ModelDownloadPage(self._model_manager, self)
            self._model_download_page.model_ready.connect(self._on_model_download_ready)
            self.stacked_widget.addWidget(self._model_download_page)
        self.stacked_widget.setCurrentWidget(self._model_download_page)

    def _on_model_download_ready(self) -> None:
        if not self._model_manager.is_installed():
            if self._model_download_page is not None:
                QMessageBox.warning(self, "模型检查失败", "模型下载完成，但关键文件缺失，请重试下载。")
            return
        self.stacked_widget.setCurrentWidget(self.home_page)

    def handle_start_scan(self, path: str, mode: str, depth: int) -> None:
        if not self._model_manager.is_installed():
            self._show_model_download_page()
            return

        path = path.strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "无效路径", "请选择存在的文件夹路径。")
            return
        if self._scan_thread is not None and self._scan_thread.isRunning():
            QMessageBox.information(self, "请稍候", "正在扫描中…")
            return

        # Enter materials page immediately, then stream scan results asynchronously.
        project_id = uuid.uuid4().hex
        state = ProjectState(
            project_id=project_id,
            input_path=os.path.abspath(path),
            mode=mode,
            depth=depth,
            scanned_files=[],
            current_step="materials",
        )
        self._state_manager.save_state(state)
        self._project_state = state

        if self._materials_page is None:
            self._materials_page = MaterialsPage(state, self)
            self._materials_page.image_toggle_requested.connect(self._on_image_toggle)
            self._materials_page.video_pick_requested.connect(self._on_video_pick)
            self._materials_page.next_requested.connect(self._on_materials_next)
            self._materials_page.back_requested.connect(self._on_materials_back)
            self.stacked_widget.addWidget(self._materials_page)
        else:
            self._materials_page.set_state(state)
        self._materials_page.set_scan_loading(True)
        self.stacked_widget.setCurrentWidget(self._materials_page)

        self.home_page.set_scanning(True)
        self._scan_thread = QThread(self)
        self._scan_worker = ScannerWorker(path, mode, depth)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.batch_ready.connect(self._on_scan_batch_ready)
        self._scan_worker.finished_ok.connect(self._on_scan_finished_ok)
        self._scan_worker.finished_err.connect(self._on_scan_finished_err)
        self._scan_worker.finished_ok.connect(self._scan_thread.quit)
        self._scan_worker.finished_err.connect(self._scan_thread.quit)
        self._scan_worker.finished_ok.connect(self._scan_worker.deleteLater)
        self._scan_worker.finished_err.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.finished.connect(self._on_scan_thread_finished)
        self._scan_thread.start()

    def _on_scan_batch_ready(self, files) -> None:
        if self._project_state is None or self._materials_page is None:
            return
        self._materials_page.append_scanned_files(files)

    def _on_scan_finished_ok(self, path: str, mode: str, depth: int, total: int) -> None:
        if total == 0:
            QMessageBox.warning(self, "无文件", "该文件夹下没有匹配的文件。")
            self.stacked_widget.setCurrentWidget(self.home_page)
            return
        if self._materials_page is not None:
            self._materials_page.set_scan_loading(False)
        if self._project_state is not None:
            self._state_manager.save_state(self._project_state)

    def _on_scan_finished_err(self, err: str) -> None:
        QMessageBox.critical(self, "扫描失败", err or "未知错误")
        if self._materials_page is not None:
            self._materials_page.set_scan_loading(False)
        self.stacked_widget.setCurrentWidget(self.home_page)

    def _on_scan_thread_finished(self) -> None:
        self._scan_thread = None
        self._scan_worker = None
        self.home_page.set_scanning(False)

    def _on_materials_back(self) -> None:
        self.stacked_widget.setCurrentWidget(self.home_page)

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

        import glob

        existing_frames = sorted(glob.glob(os.path.join(out_dir, "frame_*.png")))
        self._show_video_frames_modal(sf, source_id, out_dir, existing_frames)

    def _show_video_frames_modal(self, sf, source_id, out_dir, paths) -> None:
        if paths:
            pm = QPixmap(paths[0])
            if self._materials_page is not None and not pm.isNull():
                self._materials_page.set_video_thumbnail(source_id, pm)

        initial_selected_indices = sorted(
            m.frame_idx
            for m in self._project_state.selected_materials
            if m.selected
            and m.frame_idx is not None
            and scanned_file_source_id_for_material(m) == source_id
        )

        modal = VideoFramesModal(
            paths,
            sf.path,
            out_dir,
            initial_selected_indices=initial_selected_indices,
            parent=self,
        )
        if modal.exec() != QDialog.DialogCode.Accepted:
            return

        indices = modal.selected_frame_indices()
        mats = [
            m
            for m in self._project_state.selected_materials
            if scanned_file_source_id_for_material(m) != source_id
        ]
        for idx in sorted(indices):
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
        if not self._model_manager.is_installed():
            self._show_model_download_page()
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
        self._matting_page.back_requested.connect(self._on_matting_back)
        self._matting_page.cancel_requested.connect(self._on_matting_cancel)
        self._matting_page.retry_all_failed_requested.connect(self._on_retry_all_matting_failed)
        self._matting_page.next_requested.connect(self._on_matting_next)
        self.stacked_widget.addWidget(self._matting_page)
        self.stacked_widget.setCurrentWidget(self._matting_page)
        self._matting_page.set_ready_for_next(False)

        self._matting_row_data = row_work
        self._matting_total = len(row_work)
        self._matting_records = []
        self._matting_cancel_requested = False
        self._matting_any_failure = False
        self._matting_model_missing = False
        self._cancel_event = threading.Event()

        self._matting_thread = QThread()
        self._matting_worker = MattingWorker(
            row_work,
            self._state_manager.base_dir,
            self._project_state.project_id,
            self._cancel_event,
            list(self._project_state.matte_map),
        )
        self._matting_worker.moveToThread(self._matting_thread)
        self._matting_thread.started.connect(self._matting_worker.run)
        self._matting_worker.progress.connect(self._on_matting_progress)
        self._matting_worker.row_done.connect(self._on_matting_row_done)
        self._matting_worker.finished.connect(self._on_matting_worker_finished)
        self._matting_worker.finished.connect(self._matting_thread.quit)
        self._matting_worker.finished.connect(self._matting_worker.deleteLater)
        self._matting_thread.finished.connect(self._matting_thread.deleteLater)
        self._matting_thread.finished.connect(self._on_matting_thread_finished)
        self._matting_thread.start()
        self._matting_page.set_worker_running(True)

    def _on_retry_all_matting_failed(self) -> None:
        if self._matting_thread is not None and self._matting_thread.isRunning():
            QMessageBox.information(self, "请稍候", "抠像任务仍在运行中。")
            return
        self._on_materials_next()

    def _on_matting_progress(self, index: int, total: int, _source_path: str, name: str) -> None:
        if self._matting_page is None:
            return
        self._matting_page.set_row_status(index, MattingRowStatus.RUNNING)
        pct = int(100 * index / total) if total else 0
        self._matting_page.set_overall_progress(pct)
        self._matting_page.set_current_label(name, (total - index, total))

    def _on_matting_row_done(
        self,
        index: int,
        matte_path: str,
        mask_path: str,
        ok: bool,
        err: str,
    ) -> None:
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
                        mask_path=mask_path,
                        is_active=True,
                    )
                )
        else:
            self._matting_any_failure = True
            if is_model_missing_error(err):
                self._matting_model_missing = True
                if self._cancel_event is not None:
                    self._cancel_event.set()
            self._matting_page.set_row_status(index, MattingRowStatus.ERROR, None)
        pct = int(100 * (index + 1) / total) if total else 100
        self._matting_page.set_overall_progress(pct)

    def _on_matting_cancel(self) -> None:
        if self._matting_thread is None or not self._matting_thread.isRunning():
            return
        self._matting_cancel_requested = True
        if self._cancel_event is not None:
            self._cancel_event.set()

    def _on_matting_back(self) -> None:
        if self._project_state is None:
            return
        if self._matting_thread is not None and self._matting_thread.isRunning():
            QMessageBox.information(self, "处理中", "抠像仍在进行中，请先点击“停止抠像”。")
            return
        self._project_state.current_step = "materials"
        self._state_manager.save_state(self._project_state)
        if self._materials_page is not None:
            self._materials_page.set_state(self._project_state)
            self.stacked_widget.setCurrentWidget(self._materials_page)

    def _on_matting_next(self) -> None:
        if self._project_state is None:
            return
        if self._matting_thread is not None and self._matting_thread.isRunning():
            return
        self._project_state.current_step = "export"
        self._state_manager.save_state(self._project_state)
        self._ensure_export_page()
        self.stacked_widget.setCurrentWidget(self._export_page)

    def _on_matting_worker_finished(self) -> None:
        if self._matting_model_missing:
            QMessageBox.warning(self, "模型不可用", "模型文件缺失或损坏，请先重新下载模型。")
            self._show_model_download_page()
            self._matting_worker = None
            return
        if self._project_state is not None:
            self._project_state.matte_map = list(self._matting_records)
            self._state_manager.save_state(self._project_state)
        if self._matting_cancel_requested and self._project_state is not None:
            self._project_state.current_step = "materials"
            self._state_manager.save_state(self._project_state)
            if self._materials_page is not None:
                self._materials_page.set_state(self._project_state)
            self.stacked_widget.setCurrentWidget(self._materials_page)
        elif (
            self._project_state is not None
            and not self._matting_cancel_requested
            and self._matting_any_failure
        ):
            self._project_state.current_step = "matting"
            self._state_manager.save_state(self._project_state)
            if self._matting_page is not None:
                self._matting_page.set_failures_present(True)
                self._matting_page.set_worker_running(False)
        elif self._project_state is not None and not self._matting_cancel_requested:
            self._project_state.current_step = "matting"
            self._state_manager.save_state(self._project_state)
            if self._matting_page is not None:
                self._matting_page.set_failures_present(False)
                self._matting_page.set_ready_for_next(True)
                self._matting_page.set_worker_running(False)
        self._matting_worker = None

    def _on_matting_thread_finished(self) -> None:
        if self._matting_page is not None:
            self._matting_page.set_worker_running(False)
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
        source_path_by_source_id: dict[str, str] = {}
        base = self._state_manager.base_dir
        for m in self._project_state.selected_materials:
            if not m.selected:
                continue
            src_path = resolve_material_raster_path(base, self._project_state, m)
            if src_path:
                source_path_by_source_id[m.source_id] = src_path
        if self._export_page is not None:
            self._export_page.set_exporting(True)
        self._pending_psd_export_path = path
        self._psd_thread = QThread()
        self._psd_worker = PsdExportWorker(
            self._project_state.matte_map,
            source_path_by_source_id,
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
        if self._export_page is not None:
            self._export_page.set_exporting(False)
        QMessageBox.information(self, "导出成功", "PSD 已保存。")
        if path:
            folder = os.path.dirname(path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _on_psd_export_err(self, err: str) -> None:
        self._pending_psd_export_path = None
        if self._export_page is not None:
            self._export_page.set_exporting(False)
        QMessageBox.critical(self, "导出失败", err)

    def _on_psd_thread_finished_export(self) -> None:
        self._psd_thread = None
        self._psd_worker = None

    def _cleanup_runtime_cache(self) -> None:
        shutil.rmtree(self._cache_dir, ignore_errors=True)

        base_dir = os.path.expanduser(self._state_manager.base_dir)
        if not os.path.isdir(base_dir):
            return
        for name in os.listdir(base_dir):
            project_dir = os.path.join(base_dir, name)
            if not os.path.isdir(project_dir):
                continue
            for child in ("previews", "mattes"):
                shutil.rmtree(os.path.join(project_dir, child), ignore_errors=True)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        try:
            self._cleanup_runtime_cache()
        finally:
            super().closeEvent(event)
