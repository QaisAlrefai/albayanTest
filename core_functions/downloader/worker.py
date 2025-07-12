import os
import requests
from PyQt6.QtCore import QRunnable, pyqtSlot
from .enums import DownloadStatus
from .db import DownloadDB

class DownloadWorker(QRunnable):
    def __init__(self, item_data: dict, signals, manager):
        super().__init__()
        self.item = item_data
        self.signals = signals
        self.manager = manager
        self.db = DownloadDB()

        self.filename = self.item["filename"]
        self.folder_path = self.item["folder_path"]
        self.final_path = os.path.join(self.folder_path, self.filename)
        self.temp_path = self.final_path + ".part"
        self.url = self.item["url"]
        self.download_id = self.item["id"]

        self._paused = False
        self._cancelled = False

    @pyqtSlot()
    def run(self):
        try:
            self._download_file()
        except Exception as e:
            self.signals["status"].emit(self.download_id, DownloadStatus.ERROR)
            self.signals["error"].emit(self.download_id, str(e))

    def _download_file(self):
        os.makedirs(self.folder_path, exist_ok=True)
        resume_header = {}
        file_mode = "ab" if os.path.exists(self.temp_path) else "wb"
        downloaded_size = os.path.getsize(self.temp_path) if os.path.exists(self.temp_path) else 0

        if downloaded_size > 0:
            resume_header["Range"] = f"bytes={downloaded_size}-"

        with requests.get(self.url, stream=True, headers=resume_header) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0)) + downloaded_size

            with open(self.temp_path, file_mode) as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if self._cancelled or self.manager._cancel_all:
                        self.signals["status"].emit(self.download_id, DownloadStatus.CANCELLED)
                        return
                    while self._paused or self.manager._pause_all:
                        self.manager.msleep(100)

                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        percent = int((downloaded_size / total_size) * 100) if total_size else 0
                        self.signals["progress"].emit(
                            self.download_id, self.filename, downloaded_size, total_size, percent
                        )
                        self.db.upsert({
                            **self.item,
                            "downloaded_bytes": downloaded_size,
                            "total_bytes": total_size,
                            "status": DownloadStatus.RESUMED.value
                        })

        if not self._cancelled and not self.manager._cancel_all:
            os.replace(self.temp_path, self.final_path)
            self.signals["status"].emit(self.download_id, DownloadStatus.COMPLETED)
            self.signals["finished"].emit(self.download_id, self.filename)
            self.db.upsert({**self.item, "downloaded_bytes": downloaded_size, "total_bytes": total_size, "status": DownloadStatus.COMPLETED.value})

    def pause(self):
        self._paused = True
        self.signals["status"].emit(self.download_id, DownloadStatus.PAUSED)

    def resume(self):
        self._paused = False
        self.signals["status"].emit(self.download_id, DownloadStatus.RESUMED)

    def cancel(self):
        self._cancelled = True