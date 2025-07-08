import os
import uuid
from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from .worker import DownloadWorker
from .enums import DownloadStatus
from .db import DownloadDB

class DownloaderManager(QObject):
    progress = pyqtSignal(str, str, int, int, int)
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str, str)
    status = pyqtSignal(str, DownloadStatus)

    def __init__(self, urls=None, default_folder="downloads", max_workers=3):
        super().__init__()
        self.default_folder = default_folder
        self._pause_all = False
        self._cancel_all = False
        self.db = DownloadDB()
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(max_workers)

        self._downloads = {}  # id → metadata
        self._load_state()
        if urls:
            self._add_new_downloads(urls)

    def _load_state(self):
        for item in self.db.all():
            self._downloads[item.id] = {
                "id": item.id,
                "url": item.url,
                "filename": item.filename,
                "folder_path": item.folder_path,
                "status": item.status,
                "downloaded_bytes": item.downloaded_bytes,
                "total_bytes": item.total_bytes,
                "file_hash": item.file_hash
            }

    def _add_new_downloads(self, urls):
        for url in urls:
            filename = os.path.basename(url)
            folder = self.default_folder
            download_id = str(uuid.uuid4())
            new_entry = {
                "id": download_id,
                "url": url,
                "filename": filename,
                "folder_path": folder,
                "status": DownloadStatus.PENDING.value
            }
            self.db.upsert(new_entry)
            self._downloads[download_id] = new_entry

    def start(self):
        for download_id, info in self._downloads.items():
            if info["status"] in (DownloadStatus.COMPLETED.value, DownloadStatus.CANCELLED.value):
                continue
            worker = DownloadWorker(info, {
                "progress": self._on_progress,
                "finished": self._on_finished,
                "status": self._on_status,
                "error": self._on_error,
            }, manager=self)
            self._downloads[download_id]["worker"] = worker
            self.pool.start(worker)

    def _on_progress(self, download_id, filename, downloaded, total, percent):
        self.progress.emit(download_id, filename, downloaded, total, percent)

    def _on_status(self, download_id, status):
        self._downloads[download_id]["status"] = status.value
        self.status.emit(download_id, status)

    def _on_error(self, download_id, message):
        self.error.emit(download_id, message)

    def _on_finished(self, download_id, filename):
        self.finished.emit(download_id, filename)

    def pause(self, download_id):
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.pause()

    def resume(self, download_id):
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.resume()

    def cancel(self, download_id):
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.cancel()

    def pause_all(self):
        self._pause_all = True
        for info in self._downloads.values():
            if info.get("worker"):
                info["worker"].pause()

    def resume_all(self):
        self._pause_all = False
        for info in self._downloads.values():
            if info.get("worker"):
                info["worker"].resume()

    def cancel_all(self):
        self._cancel_all = True
        for info in self._downloads.values():
            if info.get("worker"):
                info["worker"].cancel()

    def get_download_map(self):
        return {
            download_id: {
                "url": data["url"],
                "filename": data["filename"],
                "folder_path": data["folder_path"],
                "status": data["status"]
            }
            for download_id, data in self._downloads.items()
        }