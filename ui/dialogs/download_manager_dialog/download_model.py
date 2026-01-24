
from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, QObject
from core_functions.downloader.status import DownloadStatus, DownloadProgress
from core_functions.downloader.manager import DownloadManager
from core_functions.Reciters import ReciterManager
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

    def __init__(
            self,
            parent: QObject,
            manager: DownloadManager,
            reciter_manager: ReciterManager,
            ):
        super().__init__(parent)
        self.manager = manager
        self.reciter_manager = reciter_manager
        self._download_ids: List[int] = [] 
        self._initialize_from_manager()

        # Connect signals
        self.manager.downloads_added.connect(self.on_downloads_added)
        self.manager.download_progress.connect(self.on_download_progress)
        self.manager.status_changed.connect(self.on_status_changed)
        self.manager.download_finished.connect(self.on_download_finished)
        self.manager.error.connect(self.on_download_error)
        self.manager.cancelled_all.connect(self.on_cancelled_all)
        self.manager.download_deleted.connect(self.on_download_deleted)
        self.manager.downloads_cleared.connect(self.on_downloads_cleared)

        # Cache for transient progress data (speed, eta, etc.) which isn't in main storage
        self._progress_cache: Dict[int, DownloadProgress] = {}

        
    def _initialize_from_manager(self):
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
            
        elif role == Qt.ItemDataRole.ToolTipRole:
            progress = self._progress_cache.get(download_id)
            if progress:
                return progress.tooltip_text

        elif role == Qt.ItemDataRole.AccessibleDescriptionRole:
            status_label = item_data["status"].label if item_data.get("status") else "Unknown"
            base_text = f"{status_label}"
            
            progress = self._progress_cache.get(download_id)
            if progress:
                return f"{base_text}. {progress.accessible_text}"
            return base_text

        elif role == Qt.ItemDataRole.AccessibleTextRole:
            # Accessibility: Main item text (Title + brief status)
            # Keeping it simple as requested, or matching previous behavior
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
        # Update cache
        self._progress_cache[progress.download_id] = progress
        
        # Find row for this download_id
        try:
            row = self._download_ids.index(progress.download_id)
            index = self.index(row, 0)
            
            # Emit dataChanged for Roles that might affect appearance and accessibility
            # AccessibleDescriptionRole needs to be updated for screen readers to catch the change
            roles = [
                self.ProgressRole, 
                Qt.ItemDataRole.ToolTipRole,
                Qt.ItemDataRole.AccessibleDescriptionRole
                # AccessibleTextRole usually doesn't need constant updates if it's just name + status
                # but if it includes %, it might. Kept strictly necessary ones to avoid spamming.
            ]
            self.dataChanged.emit(index, index, roles)
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

    def on_cancelled_all(self):
        self._download_ids.clear()
        self._progress_cache.clear()
        
    def on_download_deleted(self, download_id: int):
        try:
            row = self._download_ids.index(download_id)
            self.beginRemoveRows(QModelIndex(), row, row)
            self._download_ids.pop(row)
            if download_id in self._progress_cache:
                del self._progress_cache[download_id]
            self.endRemoveRows()
        except ValueError:
            pass

    def on_downloads_cleared(self):
        self.beginResetModel()
        self._download_ids.clear()
        self._progress_cache.clear()
        self.endResetModel()
