
import os
from typing import List, Dict, Optional, Union
from pathlib import Path
from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from .worker import DownloadWorker
from .status import DownloadStatus, DownloadProgress
from .db import DownloadDB
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

class DownloadManager(QObject):
    download_progress = pyqtSignal(DownloadProgress)
    download_finished = pyqtSignal(int, str)                      # id, file_path
    error = pyqtSignal(int, str)                         # id, error message
    status_changed = pyqtSignal(int, DownloadStatus)     # id, new status

    def __init__(
        self,
        max_workers: int = 3,
        load_history: bool = False,
        save_history: bool = False,
        download_db: Optional[DownloadDB] = None,
    ):
        super().__init__()
        logger.debug("Initializing DownloaderManager")
        self.save_history = save_history
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

        logger.debug("DownloaderManager initialized with max_workers=%d, load_history=%s, save_history=%s", max_workers, load_history, save_history)

    def _load_history(self):
        """Load download history from the database."""
        logger.debug("Loading download history from database")

        if not self.db:
            logger.warning("No database instance available to load history.")
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
            self._downloads[item.id]["size_text"] = size_text = f"{item.total_bytes / (1024 * 1024):.2f} MB" if item.total_bytes > 1024 * 1024 else f"{item.total_bytes / 1024:.2f} KB"

            # Include any additional fields that might exist in the DB model
            other_keys = set(item.__dict__.keys())- set(self.db.download_table.__table__.c)
            for key in other_keys:
                self._downloads[item.id][key] = getattr(item, key)

        logger.info("Loaded %d download items from history", len(self._downloads))

    def add_new_downloads(self, download_items: List[Dict], download_folder: str):
        """Add multiple download items."""
        logger.debug("Adding new download items, count=%d", len(download_items))

        if not isinstance(download_items, list):
            raise ValueError("download_items must be a list of dictionaries.")

        for entry in download_items:
            filename = os.path.basename(entry["url"])
            item_data = {
                "filename": filename,
                "folder_path": download_folder,
                "status": DownloadStatus.PENDING,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                **entry,
            }

            if self.db and self.save_history:
                download_id = self.db.upsert(item_data)
            else:
                download_id = len(self._downloads) + 1

            item_data["id"] = download_id
            self._downloads[download_id] = item_data
        logger.info("Added %d new download items", len(download_items))

    def add_download(self, url: str, download_folder: str, **extra_data):
        """
        Add a single download item.
        Optionally accepts extra_data like metadata to be stored with the download.
        """
        logger.debug("Adding single download item: %s", url)
        item = {"url": url}
        item.update(extra_data)
        self.add_new_downloads([item], download_folder)
        logger.info("Added download item: %s", url)

    def start(self):
        """Start processing the download queue."""
        logger.info("Starting downloading process")

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

    def _on_progress(self, progress: DownloadProgress):
        self.download_progress.emit(progress)

    def _on_status(self, download_id: int, new_status: DownloadStatus):
        if download_id  not in  self._downloads:
            logger.warning("Received status update for unknown download ID: %d", download_id)
            return

        self._downloads[download_id]["status"] = new_status
        self.status_changed.emit(download_id, new_status)

        if self.db and self.save_history:
            self.db.update_status(download_id, new_status)

    def _on_error(self, download_id: int, message: str):
        logger.error("Download error (ID: %d): %s", download_id, message)
        self.error.emit(download_id, message)

    def _on_finished(self, download_id: int, filename: str):
        logger.debug("Download finished (ID: %d): %s", download_id, filename)
        self.download_finished.emit(download_id, filename)

    def pause(self, download_id: int):
        logger.debug("Pausing download ID: %d", download_id)
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.pause()

    def resume(self, download_id: int):
        logger.debug("Resuming download ID: %d", download_id)
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.resume()

    def cancel(self, download_id: int):
        logger.debug("Cancelling download ID: %d", download_id)
        if worker := self._downloads.get(download_id, {}).get("worker"):
            worker.cancel()            

    def restart(self, download_id: int):
        logger.debug("Restarting download ID: %d", download_id)
        if download_id in self._downloads:
            self._downloads[download_id]["status"] = DownloadStatus.PENDING
            self._downloads[download_id]["downloaded_bytes"] = 0
            if self.db and self.save_history:
                self.db.update_status(download_id, DownloadStatus.PENDING)
            self._downloads[download_id]["worker"] = DownloadWorker(
                self._downloads[download_id],
                callbacks={
                    "progress": self._on_progress,
                    "finished": self._on_finished,
                    "status": self._on_status,
                    "error": self._on_error
                },
                manager=self
            )
            self.pool.start(self._downloads[download_id]["worker"])
        else:
            logger.warning("Attempted to restart non-existent download ID: %d", download_id)

    def pause_all(self):
        logger.info("Pausing all downloads")
        self._pause_all = True
        for download_id in self._downloads:
            self.pause(download_id)

    def resume_all(self):
        logger.info("Resuming all downloads")
        self._pause_all = False
        for download_id in self._downloads:
            self.resume(download_id)

    def cancel_all(self):
        logger.info("Cancelling all downloads")
        self._cancel_all = True
        for download_id in self._downloads:
            self.cancel(download_id)

    def delete(self, download_id: int, delete_file: bool = True):
        logger.debug("Deleting download ID: %d", download_id)
        if download_id in self._downloads:
            if worker := self._downloads[download_id].get("worker"):
                worker.cancel()
            if self.db and self.save_history:
                self.db.delete(download_id)
            if delete_file:
                file_path = Path(self._downloads[download_id]["folder_path"]) / self._downloads[download_id]["filename"]
                file_path.unlink(missing_ok=True)
                logger.info("Deleted file: %s", file_path)
            del self._downloads[download_id]
            logger.info("Deleted download ID: %d", download_id)
        else:
            logger.warning("Attempted to delete non-existent download ID: %d", download_id)

    def delete_by_status(self, status: Union[DownloadStatus, List[DownloadStatus]]):
        logger.info("Deleting downloads with status: %s", status)
        for download_item in self.get_downloads(status):
            self.delete(download_item["id"])
        logger.info("Deleted downloads with status: %s", status)

    def delete_all(self):
        logger.debug("Deleting all downloads")
        self.db.delete_all()
        self._downloads.clear()
        logger.info("All downloads deleted")

    def get_download(self, download_id: int) -> Optional[Dict]:
        """Return the download item by ID, or None if not found."""
        return self._downloads.get(download_id)

    def get_downloads(
        self,
        status: Optional[Union[DownloadStatus, List[DownloadStatus]]] = None
    ) -> List[Dict]:
        """
        Return a list of downloads filtered by status.
        - If `status` is None → return all downloads.
        - If `status` is a single DownloadStatus → return matching downloads.
        - If `status` is a list → return downloads matching any of the statuses.
        """
        if status is None:
            logger.debug("Fetching all downloads (no status filter applied)")
            return list(self._downloads.values())

        if not isinstance(status, list):
            status = [status]

        logger.debug("Fetching downloads with statuses: %s", [s.name for s in status])
        return [
            info
            for info in self._downloads.values()
            if info["status"] in status
        ]
