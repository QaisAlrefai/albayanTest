
import os
import requests
from typing import Callable, Dict
from PyQt6.QtCore import QRunnable, pyqtSlot, QThread
from .status import DownloadStatus, DownloadProgress
from .db import DownloadDB
from utils.func import calculate_sha256
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class DownloadWorker(QRunnable):
    def __init__(self, item_data: dict, callbacks: Dict[str, Callable], manager):
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
        downloaded_bytes = os.path.getsize(self.temp_path) if os.path.exists(self.temp_path) else 0
        file_mode = "ab" if downloaded_bytes > 0 else "wb"

        if downloaded_bytes > 0:
            resume_header["Range"] = f"bytes={downloaded_bytes}-"

        with requests.get(self.url, stream=True, headers=resume_header, timeout=10) as r:
            r.raise_for_status()
            content_length = int(r.headers.get("content-length", 0))
            total_bytes = downloaded_bytes + content_length

            progress = DownloadProgress(
                download_id=self.download_id,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes
            )

            self.callbacks["status"](self.download_id, DownloadStatus.DOWNLOADING)

            with open(self.temp_path, file_mode) as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if self._cancelled or self.manager._cancel_all:
                        logger.info(f"[Cancelled] ID={self.download_id}")
                        self.callbacks["status"](self.download_id, DownloadStatus.CANCELLED)
                        return

                    while self._paused or self.manager._pause_all:
                        QThread.msleep(100)
                        progress.reset_start_time()  # Reset timer when resumed

                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        progress.update(downloaded_bytes)

                        self.callbacks["progress"](progress)
                        self.callbacks["status"](self.download_id, DownloadStatus.DOWNLOADING)

                        if self.db:
                            self.db.upsert({
                                **self.item,
                                "downloaded_bytes": downloaded_bytes,
                                "total_bytes": total_bytes,
                                "status": DownloadStatus.DOWNLOADING
                            })

        if not self._cancelled and not self.manager._cancel_all:
            os.replace(self.temp_path, self.final_path)
            logger.info(f"[Download Completed] ID={self.download_id}")
            self.callbacks["status"](self.download_id, DownloadStatus.COMPLETED)
            self.callbacks["finished"](self.download_id, self.final_path)

            if self.db:
                file_hash = calculate_sha256(self.final_path)
                self.db.upsert({
                    **self.item,
                    "downloaded_bytes": downloaded_bytes,
                    "total_bytes": total_bytes,
                    "file_hash": file_hash,
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
