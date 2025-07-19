import os
import requests
from typing import Callable, Dict
from PyQt6.QtCore import QRunnable, pyqtSlot, QThread
from .enums import DownloadStatus
from .db import DownloadDB
from .manager import DownloaderManager
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class DownloadWorker(QRunnable):
    def __init__(self, item_data: dict, callbacks: Dict[str, Callable], manager: DownloaderManager):
        super().__init__()
        self.item = item_data
        self.callbacks = callbacks
        self.manager = manager
        self.db: DownloadDB = self.manager.db

        self.filename = item_data["filename"]
        self.folder_path = item_data["folder_path"]
        self.final_path = os.path.join(self.folder_path, self.filename)
        self.temp_path = self.final_path + ".part"
        self.url = item_data["url"]
        self.download_id = item_data["id"]

        self._paused = False
        self._cancelled = False

        logger.debug(f"[Worker Init] ID={self.download_id}, URL={self.url}")

    @pyqtSlot()
    def run(self) -> None:
        logger.debug(f"[Download Start] ID={self.download_id}")
        try:
            self._download_file()
        except Exception as e:
            logger.exception(f"[Download Error] ID={self.download_id}")
            self.callbacks["status"](self.download_id, DownloadStatus.ERROR)
            self.callbacks["error"](self.download_id, str(e))

    def _download_file(self) -> None:
        os.makedirs(self.folder_path, exist_ok=True)

        resume_header = {}
        downloaded_size = os.path.getsize(self.temp_path) if os.path.exists(self.temp_path) else 0
        file_mode = "ab" if downloaded_size > 0 else "wb"

        if downloaded_size > 0:
            resume_header["Range"] = f"bytes={downloaded_size}-"

        with requests.get(self.url, stream=True, headers=resume_header, timeout=10) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0)) + downloaded_size
            self.callbacks["status"](self.download_id, DownloadStatus.DOWNLOADING)

            with open(self.temp_path, file_mode) as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if self._cancelled or self.manager._cancel_all:
                        logger.info(f"[Cancelled] ID={self.download_id}")
                        self.callbacks["status"](self.download_id, DownloadStatus.CANCELLED)
                        return

                    while self._paused or self.manager._pause_all:
                        QThread.msleep(100)

                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        percent = int((downloaded_size / total_size) * 100) if total_size else 0

                        self.callbacks["progress"](
                            self.download_id, self.filename, downloaded_size, total_size, percent
                        )
                        self.callbacks["status"](
                            self.download_id, DownloadStatus.DOWNLOADING
                        )

                        self.db.upsert({
                            **self.item,
                            "downloaded_bytes": downloaded_size,
                            "total_bytes": total_size,
                            "status": DownloadStatus.DOWNLOADING
                        })

        if not self._cancelled and not self.manager._cancel_all:
            os.replace(self.temp_path, self.final_path)
            logger.info(f"[Completed] ID={self.download_id}")
            self.callbacks["status"](self.download_id, DownloadStatus.COMPLETED)
            self.callbacks["finished"](self.download_id, self.filename)

            self.db.upsert({
                **self.item,
                "downloaded_bytes": downloaded_size,
                "total_bytes": total_size,
                "status": DownloadStatus.COMPLETED
            })

    def pause(self) -> None:
        logger.debug(f"[Paused] ID={self.download_id}")
        self._paused = True
        self.callbacks["status"](self.download_id, DownloadStatus.PAUSED)

    def resume(self) -> None:
        logger.debug(f"[Resumed] ID={self.download_id}")
        self._paused = False
        self.callbacks["status"](self.download_id, DownloadStatus.DOWNLOADING)

    def cancel(self) -> None:
        logger.debug(f"[Cancel Requested] ID={self.download_id}")
        self._cancelled = True
        self.callbacks["status"](self.download_id, DownloadStatus.CANCELLED)
