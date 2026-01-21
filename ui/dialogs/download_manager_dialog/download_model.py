
from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, QObject
from core_functions.downloader.status import DownloadStatus, DownloadProgress
from core_functions.downloader.manager import DownloadManager
from typing import List, Dict, Any, Optional
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

class DownloadListModel(QAbstractListModel):
    """
    Model that wraps DownloadManager data for a QListView.
    Ensures efficiency with large lists and provides accessibility support.
    """

    ItemRole = Qt.ItemDataRole.UserRole
    ProgressRole = Qt.ItemDataRole.UserRole + 1
    StatusRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self, manager: DownloadManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.manager = manager
        # We keep a local list of download IDs to map row index -> download ID
        # This list must be kept in sync with the manager's internal state
        self._download_ids: List[int] = [] 
        
        # We can initialize from existing downloads in the manager
        self._initialize_from_manager()

        # Connect signals
        self.manager.downloads_added.connect(self.on_downloads_added)
        self.manager.download_progress.connect(self.on_download_progress)
        self.manager.status_changed.connect(self.on_status_changed)
        self.manager.download_finished.connect(self.on_download_finished)
        self.manager.error.connect(self.on_download_error)

        # Connect to a signal for deletions if you implement one in manager.
        # Currently manager doesn't seem to have a dedicated bulk delete signal other than careful manual management,
        # but for now we assume additions are the main bottleneck. 
        # Ideally manager should emit `downloads_removed` or similar. I'll stick to what's available or safe.
    
    def _initialize_from_manager(self):
        # Initial load
        all_downloads = self.manager.get_downloads()
        self._download_ids = [d["id"] for d in all_downloads]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._download_ids)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        
        row = index.row()
        if row < 0 or row >= len(self._download_ids):
            return None
            
        download_id = self._download_ids[row]
        item_data = self.manager.get_download(download_id)
        
        if not item_data:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return item_data["filename"]
            
        elif role == Qt.ItemDataRole.AccessibleTextRole:
            # Accessibility: Descriptive text for screen readers
            status_text = item_data["status"].label if item_data.get("status") else "Unknown"
            progress_val = 0
            if item_data["total_bytes"] > 0:
                progress_val = int((item_data["downloaded_bytes"] / item_data["total_bytes"]) * 100)
            
            return f"{item_data['filename']}, {status_text}, {progress_val}%"
            
        elif role == self.ItemRole:
            return item_data
            
        elif role == self.StatusRole:
            return item_data["status"]
            
        elif role == self.ProgressRole:
            # Return a simple dict or object with progress info
            return {
                "downloaded": item_data["downloaded_bytes"],
                "total": item_data["total_bytes"],
                "percentage": int((item_data["downloaded_bytes"] / item_data["total_bytes"]) * 100) if item_data["total_bytes"] > 0 else 0
            }

        return None

    def on_downloads_added(self, new_items: List[Dict]):
        if not new_items:
            return

        first_row = len(self._download_ids)
        last_row = first_row + len(new_items) - 1
        
        self.beginInsertRows(QModelIndex(), first_row, last_row)
        for item in new_items:
            self._download_ids.append(item["id"])
        self.endInsertRows()

    def on_download_progress(self, progress: DownloadProgress):
        # Find row for this download_id
        try:
            row = self._download_ids.index(progress.download_id)
            index = self.index(row, 0)
            # Emit dataChanged for Roles that might affect appearance
            # Note: For strict performance, only emit roles that actually changed.
            # But Progress is usually visually represented by a custom delegate using UserRoles.
            self.dataChanged.emit(index, index, [self.ProgressRole, Qt.ItemDataRole.AccessibleTextRole])
        except ValueError:
            pass # ID not in our list (maybe deleted or filtered?)

    def on_status_changed(self, download_id: int, new_status: DownloadStatus):
        try:
            row = self._download_ids.index(download_id)
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.StatusRole, Qt.ItemDataRole.AccessibleTextRole])
        except ValueError:
            pass

    def on_download_finished(self, download_id: int, file_path: str):
        try:
            row = self._download_ids.index(download_id)
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.StatusRole, self.ProgressRole, Qt.ItemDataRole.AccessibleTextRole])
        except ValueError:
            pass

    def on_download_error(self, download_id: int, error_msg: str):
        try:
            row = self._download_ids.index(download_id)
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.StatusRole, Qt.ItemDataRole.AccessibleTextRole])
        except ValueError:
            pass
