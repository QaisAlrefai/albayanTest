import os
from typing import List, Dict, Optional, Type
from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from .worker import DownloadWorker
from .status import DownloadStatus
from .db import DownloadDB


class DownloaderManager(QObject):
    download_progress = pyqtSignal(int, str, int, int, int)       # id, filename, downloaded, total, percent
    download_finished = pyqtSignal(int, str)                      # id, file_path
    error = pyqtSignal(int, str)                         # id, error message
    status_changed = pyqtSignal(int, DownloadStatus)     # id, new status

    def __init__(
        self,
        urls: Optional[List[str]] = None,
        download_folder: str = "downloads",
        max_workers: int = 3,
        load_history: bool = False,
        save_history: bool = False,
        download_db: Optional[DownloadDB] = None,
    ):
        super().__init__()
        self.urls = [urls ]if isinstance(urls, str) else urls or []
        self.save_history = save_history
        self.download_folder = download_folder
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(max_workers)

        self._downloads: Dict[int, Dict] = {}
        self._pause_all = False
        self._cancel_all = False
        self.db = download_db

        if not self.db and (save_history or load_history):
            raise ValueError("DownloadDB instance is required for saving or loading history.")

        if load_history and self.db:
            self._load_history()

        if self.urls:
            self._add_new_downloads(self.urls)

    def _load_history(self):
        if not self.db:
            return
        for item in self.db.all():
            self._downloads[item.id] = {
                "id": item.id,
                "url": item.url,
                "filename": item.filename,
                "folder_path": item.folder_path,
                "status": item.status,
                "downloaded_bytes": item.downloaded_bytes,
                "total_bytes": item.total_bytes,
                "file_hash": item.file_hash,
            }

    def _add_new_downloads(self, urls: List[str]):
        for url in urls:
            filename = os.path.basename(url)
            folder = self.download_folder

            if self.db and self.save_history:
                item_data = {
                    "url": url,
                    "filename": filename,
                    "folder_path": folder,
                    "status": DownloadStatus.PENDING,
                    "downloaded_bytes": 0,
                    "total_bytes": 0
                }
                download_id = self.db.upsert(item_data)
            else:
                download_id = len(self._downloads) + 1

            self._downloads[download_id] = {
                "id": download_id,
                "url": url,
                "filename": filename,
                "folder_path": folder,
                "status": DownloadStatus.PENDING,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "file_hash": None,
            }

    def start(self):
        for download_id, info in self._downloads.items():
            if info["status"] in (DownloadStatus.COMPLETED, DownloadStatus.CANCELLED):
                continue

            worker = DownloadWorker(
                info,
                callbacks={
                    "progress": self._on_progress,
                    "finished": self._on_finished,
                    "status": self._on_status,
                    "error": self._on_error
                },
                manager=self
            )
            self._downloads[download_id]["worker"] = worker
            self.pool.start(worker)

    def _on_progress(self, download_id: int, filename: str, downloaded: int, total: int, percent: int):
        self.download_progress.emit(download_id, filename, downloaded, total, percent)

    def _on_status(self, download_id: int, new_status: DownloadStatus):
        self._downloads[download_id]["status"] = new_status
        self.status_changed.emit(download_id, new_status)

        if self.db and self.save_history:
            self.db.update_status(download_id, new_status)

    def _on_error(self, download_id: int, message: str):
        self.error.emit(download_id, message)

    def _on_finished(self, download_id: int, filename: str):
        self.download_finished.emit(download_id, filename)
    def pause(self, download_id: int):
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.pause()

    def resume(self, download_id: int):
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.resume()

    def cancel(self, download_id: int):
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.cancel()

    def pause_all(self):
        self._pause_all = True
        for download_id in self._downloads:
            self.pause(download_id)

    def resume_all(self):
        self._pause_all = False
        for download_id in self._downloads:
            self.resume(download_id)

    def cancel_all(self):
        self._cancel_all = True
        for download_id in self._downloads:
            self.cancel(download_id)

    def get_download_map(self) -> Dict[int, Dict]:
        return {
            download_id: {
                "url": data["url"],
                "filename": data["filename"],
                "folder_path": data["folder_path"],
                "status": data["status"]
            }
            for download_id, data in self._downloads.items()
        }
