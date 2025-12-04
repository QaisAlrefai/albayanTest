
from typing import List, Union
from PyQt6.QtWidgets import QProgressBar
from core_functions.downloader.status import DownloadStatus
from core_functions.downloader.manager import DownloadManager  # افترض اسم الكلاس

class SessionProgressBar(QProgressBar):
    """
    A QProgressBar that tracks the overall download progress across one or more DownloadManager instances.
    - Considers only PENDING and DOWNLOADING as in-progress.
    - PAUSED files decrease the in-progress count.
    """

    def __init__(self, parent: Union[None, 'QWidget'] = None) -> None:
        super().__init__(parent)
        self._managers: List[DownloadManager] = []
        self._total_files: int = 0
        self._completed_files: int = 0

        self.setMinimum(0)
        self.setValue(0)
        self.setFormat("Completed %v of %m")

    def set_managers(self, managers: Union[DownloadManager, List[DownloadManager]]) -> None:
        """
        Assign one or multiple DownloadManager instances to track.
        :param managers: DownloadManager or list of DownloadManager
        """
        if not isinstance(managers, list):
            managers = [managers]
        self._managers = managers
        self._recalculate_totals()

        # Connect signals for automatic updates
        for mgr in self._managers:
            mgr.download_finished.connect(self._on_file_finished)
            mgr.status_changed.connect(self._on_status_changed)

    def _recalculate_totals(self) -> None:
        """Recompute total files in-progress for the session."""
        self._total_files = 0

        for mgr in self._managers:
            self._total_files += len(mgr.get_downloads([DownloadStatus.PENDING, DownloadStatus.DOWNLOADING]))

        self.setMaximum(self._total_files + self._completed_files)
        self.setValue(self._completed_files)

    def increment(self, count: int = 1) -> None:
        """Manually increment completed files count."""
        self._completed_files += count
        self.setValue(self._completed_files)

    def decrement(self, count: int = 1) -> None:
        """Manually decrease completed files count (e.g., when a file is paused/cancelled)."""
        self._completed_files = max(0, self._completed_files - count)
        self.setValue(self._completed_files)

    def finish_session(self) -> None:
        """Reset the session progress when all files are done."""
        self._completed_files = 0
        self._total_files = 0
        self.setMaximum(0)
        self.setValue(0)

    def _on_file_finished(self, download_id: int) -> None:
        """Slot for download_finished signal."""
        self.increment()

    def _on_status_changed(self, download_id: int, status: DownloadStatus) -> None:
        """Slot for status_changed signal."""
        # If file is paused, decrease in-progress count
        if status in (DownloadStatus.PAUSED, DownloadStatus.CANCELLED, DownloadStatus.ERROR):
            self.decrement()
