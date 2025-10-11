
from typing import List, Dict, Optional
from enum import Enum
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QGridLayout
)
from PyQt6.QtCore import Qt

from core_functions.quran.types import Surah
from core_functions.Reciters import RecitersManager, SurahReciter, AyahReciter
from core_functions.downloader import DownloadManager
from core_functions.downloader.status import DownloadStatus, DownloadProgress
from utils.logger import LoggerManager
from utils.const import data_folder
from utils.settings import Config

logger = LoggerManager.get_logger(__name__)


class DownloadMode(Enum):
    SURAH = "surah"
    AYAH = "ayah"


class DownloadManagerDialog(QDialog):
    """Dialog to manage and monitor Quran downloads."""

    def __init__(self, parent, surah_manager: DownloadManager, ayah_manager: DownloadManager):
        super().__init__(parent)
        self.parent = parent
        self.surah_manager = surah_manager
        self.ayah_manager = ayah_manager
        self.item_map: Dict[str, QListWidgetItem] = {}

        self.setWindowTitle("مدير التنزيلات")
        self.setMinimumWidth(520)

        self._setup_ui()
        self._connect_signals()
        self.update_list()
        

    # === UI SETUP ===
    def _setup_ui(self):
        layout = QVBoxLayout()

        # === Top controls ===
        top_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("بحث...")

        self.section_label = QLabel("القسم:")
        self.section_combo = QComboBox()
        for manager, label in [(self.surah_manager, "السور"), (self.ayah_manager, "الآيات")]:
            if manager:
                self.section_combo.addItem(label, manager)

        self.filter_label = QLabel("تصفية:")
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("الكل", None)
        for status in DownloadStatus:
            self.filter_combo.addItem(status.label, status)

        top_layout.addWidget(self.search_box)
        top_layout.addWidget(self.section_label)
        top_layout.addWidget(self.section_combo)
        top_layout.addWidget(self.filter_label)
        top_layout.addWidget(self.filter_combo)
        layout.addLayout(top_layout)

        # === List Widget ===
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.list_widget)

        # === Buttons ===
        btn_layout = QHBoxLayout()
        self.btn_download = QPushButton("تنزيل")
        self.btn_delete = QPushButton("حذف")
        self.btn_close = QPushButton("إغلاق")

        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _connect_signals(self):
        self.section_combo.currentIndexChanged.connect(self.update_list)
        self.filter_combo.currentIndexChanged.connect(self.update_list)
        self.search_box.textChanged.connect(self.update_list)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)

        self.btn_download.clicked.connect(self.show_download_menu)
        self.btn_delete.clicked.connect(self.show_delete_menu)
        self.btn_close.clicked.connect(self.close)
        self.surah_manager.download_progress.connect(self.update_progress)
        self.ayah_manager.download_progress.connect(self.update_progress)

    def current_manager(self) -> DownloadManager:
        return self.section_combo.currentData()

    def get_current_filter_status(self) -> Optional[DownloadStatus]:
        return self.filter_combo.currentData()

    def update_progress(self, progress: DownloadProgress):
        """Fast update for a specific item's progress."""
        item = self.item_map.get(progress.download_id)
        if not item:
            return
        progress_text = (
            f"{progress.percentage}%, "
            f"تم تنزيل {progress.downloaded_str} من {progress.total_str}\n"
            f"السرعة: {progress.speed_str} | الوقت المنقضي: {progress.elapsed_time_str} | الوقت المتبقي: {progress.remaining_time_str}"
            )

        item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, progress_text)
        item.setToolTip(progress_text)

    def update_list(self):
        """Rebuild the visible list based on filters and search."""
        manager = self.current_manager()
        if not manager:
            return

        self.list_widget.clear()
        self.item_map.clear()

        status = self.get_current_filter_status()
        search_text = self.search_box.text().strip().lower()

        download_items = manager.get_downloads(status)

        for item_data in download_items:
            if search_text and search_text not in item_data["filename"].lower():
                continue

            progress = (
                f"{(item_data['downloaded_bytes'] / item_data['total_bytes'] * 100):.1f}%"
                if item_data["total_bytes"] > 0 else "0%"
            )
            display_text = f"{item_data['filename']}, {item_data['status'].label}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, item_data['id'])
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, progress)
            item.setToolTip(progress)
            self.list_widget.addItem(item)
            self.item_map[item_data['id']] = item

    def show_context_menu(self, pos):
        menu = QMenu(self)
        action_delete = menu.addAction("حذف العنصر المحدد")
        action_delete.triggered.connect(self.delete_selected_item)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def delete_selected_item(self):
        """Delete the currently selected download item."""
        manager = self.current_manager()
        item = self.list_widget.currentItem()
        if not item:
            return
        download_id = item.data(Qt.ItemDataRole.UserRole)
        manager.db.delete(download_id)
        self.list_widget.takeItem(self.list_widget.row(item))
        self.item_map.pop(download_id, None)

    def delete_by_status(self, status):
        manager = self.current_manager()
        manager.delete_by_status(status)
        self.update_list()

    def delete_all(self):
        manager = self.current_manager()
        manager.delete_all()
        self.update_list()

    def show_delete_menu(self):
        menu = QMenu(self)
        menu.addAction("حذف الكل", self.delete_all)
        menu.addAction("حذف المكتمل", lambda: self.delete_by_status(DownloadStatus.COMPLETED))
        menu.addAction(
            "حذف غير المكتمل",
            lambda: self.delete_by_status([
                DownloadStatus.PENDING, DownloadStatus.DOWNLOADING,
                DownloadStatus.PAUSED, DownloadStatus.CANCELLED,
                DownloadStatus.ERROR
            ])
        )
        menu.setAccessibleName("قائمة حذف")
        menu.setActiveAction(menu.actions()[0])
        menu.exec(self.btn_delete.mapToGlobal(self.btn_delete.rect().bottomLeft()))

    def download_surahs(self):
        reciters_manager = SurahReciter(data_folder / "quran" / "reciters.db")
        surahs = self.parent.quran_manager.get_surahs()

        dialog = NewDownloadDialog(self, DownloadMode.SURAH, surahs, reciters_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selection = dialog.get_selection()
            reciter = selection["reciter"]
            from_surah = selection["from_surah"]
            to_surah = selection["to_surah"]

            new_downloads = [
                {
                    "reciter_id": reciter["id"],
                    "surah_number": num,
                    "url": reciters_manager.get_url(reciter["id"], num),
                }
                for num in range(from_surah.number, to_surah.number + 1)
            ]

            path = f"{Config.downloading.download_path}/{reciter['name']}"
            self.surah_manager.add_new_downloads(new_downloads, path)
            self.surah_manager.start()
            self.update_list()

    def show_download_menu(self):
        menu = QMenu(self)
        menu.addAction("تنزيل سور", self.download_surahs)
        menu.addAction("تنزيل آيات")
        menu.setAccessibleName("قائمة تنزيل جديد")
        menu.setActiveAction(menu.actions()[0])
        menu.exec(self.btn_download.mapToGlobal(self.btn_download.rect().bottomLeft()))


class NewDownloadDialog(QDialog):
    """Dialog for downloading Surahs or Ayahs."""

    def __init__(
            self, 
            parent, 
            mode:  DownloadMode, 
            surahs: List[Surah],
            reciters_manager: RecitersManager
            ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.surahs = surahs
        self.reciters_manager = reciters_manager

        # Window settings
        self.setWindowTitle("تحميل سور" if mode == DownloadMode.SURAH else "تحميل آيات")
        self.setAccessibleName("نافذة التحميل")

        layout = QVBoxLayout()
        grid = QGridLayout()

        # Reciter selection
        self.reciter_label = QLabel("القارئ:")
        self.reciter_combo = QComboBox()
        self.reciter_combo.setAccessibleName(self.reciter_label.text())
        for reciter in self.reciters_manager.get_reciters():
            self.reciter_combo.addItem(reciter["display_text"], reciter)

        grid.addWidget(self.reciter_label, 0, 0)
        grid.addWidget(self.reciter_combo, 0, 1)

        # From Surah
        self.from_surah_label = QLabel("من سورة:")
        self.from_surah_combo = QComboBox()
        self.from_surah_combo.setAccessibleName(self.from_surah_label.text())
        grid.addWidget(self.from_surah_label, 1, 0)
        grid.addWidget(self.from_surah_combo, 1, 1)

        row = 2

        # From Ayah (only in Ayah mode)
        if self.mode == DownloadMode.AYAH:
            self.from_ayah_label = QLabel("من آية:")
            self.from_ayah_combo = QComboBox()
            self.from_ayah_combo.setAccessibleName(self.from_ayah_label.text())

            grid.addWidget(self.from_ayah_label, row, 0)
            grid.addWidget(self.from_ayah_combo, row, 1)
            row += 1

            self.from_surah_combo.currentIndexChanged.connect(
                lambda _: self._populate_ayahs(self.from_surah_combo, self.from_ayah_combo)
            )

        # To Surah
        self.to_surah_label = QLabel("إلى سورة:")
        self.to_surah_combo = QComboBox()
        self.to_surah_combo.setAccessibleName(self.to_surah_label.text())
        grid.addWidget(self.to_surah_label, row, 0)
        grid.addWidget(self.to_surah_combo, row, 1)
        row += 1

        # To Ayah (only in Ayah mode)
        if self.mode == DownloadMode.AYAH:
            self.to_ayah_label = QLabel("إلى آية:")
            self.to_ayah_combo = QComboBox()
            self.to_ayah_combo.setAccessibleName(self.to_ayah_label.text())

            grid.addWidget(self.to_ayah_label, row, 0)
            grid.addWidget(self.to_ayah_combo, row, 1)
            row += 1

            self.to_surah_combo.currentIndexChanged.connect(
                lambda _: self._populate_ayahs(self.to_surah_combo, self.to_ayah_combo)
            )

        layout.addLayout(grid)

        # Control buttons
        btn_layout = QHBoxLayout()
        btn_download = QPushButton("تحميل")
        btn_download.clicked.connect(self.accept)
        btn_close = QPushButton("إغلاق")
        btn_close.clicked.connect(self.close)

        btn_layout.addWidget(btn_download)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # Initial population
        self.reciter_combo.currentIndexChanged.connect(self._on_reciter_changed)
        self._on_reciter_changed()

    def _on_reciter_changed(self):
        """Update Surah and Ayah combos when reciter changes."""
        reciter = self.reciter_combo.currentData()
        if not reciter:
            return
        
        if self.mode == DownloadMode.SURAH:
            self._populate_surahs(reciter, self.from_surah_combo)
            self._populate_surahs(reciter, self.to_surah_combo)
        elif self.mode == DownloadMode.AYAH:
            self._populate_ayahs(self.from_surah_combo, self.from_ayah_combo)
            self._populate_ayahs(self.to_surah_combo, self.to_ayah_combo)

    def _populate_surahs(self, reciter, combo: QComboBox):
        """Fill Surah combo with only available Surahs for the selected reciter."""
        combo.clear()
        available = set(reciter["available_suras"])

        for sura in self.surahs:
            if sura.number in available:
                combo.addItem(sura.name, sura)

    def _populate_ayahs(self, surah_combo: QComboBox, ayah_combo: QComboBox):
        """Fill Ayah combo based on selected Surah."""
        sura: Surah = surah_combo.currentData()
        if not sura:
            return

        ayah_combo.clear()
        for i in range(sura.ayah_count):
            ayah_number = sura.first_ayah_number + i
            ayah_combo.addItem(str(i + 1), ayah_number)

    def get_selection(self) -> dict:
        """Return user selections as a dictionary with auto-correction."""
        reciter = self.reciter_combo.currentData()
        from_surah: Surah = self.from_surah_combo.currentData()
        to_surah: Surah = self.to_surah_combo.currentData()

        # Auto-correct surah range
        if from_surah.number > to_surah.number:
            to_surah = from_surah

        data = {
            "reciter": reciter,
            "from_surah": from_surah,
            "to_surah": to_surah,
        }

        if self.mode == DownloadMode.AYAH:
            from_ayah = self.from_ayah_combo.currentData()
            to_ayah = self.to_ayah_combo.currentData()

            # Auto-correct ayah range (only if same surah)
            if from_surah.number == to_surah.number and from_ayah > to_ayah:
                to_ayah = from_ayah

            data["from_ayah"] = from_ayah
            data["to_ayah"] = to_ayah

        return data
