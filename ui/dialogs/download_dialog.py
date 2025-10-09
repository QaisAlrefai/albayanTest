
from typing import List
from enum import Enum

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, 
    QPushButton, QLabel, QGridLayout, QLineEdit, 
    QListWidget, QListWidgetItem, QMenu
)
from PyQt6.QtCore import Qt

from core_functions.quran.types import Surah
from core_functions.Reciters import RecitersManager, AyahReciter, SurahReciter
from core_functions.downloader import DownloadManager
from core_functions.downloader.status import DownloadStatus, DownloadProgress
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class DownloadMode(Enum):
    SURAH = "surah"
    AYAH = "ayah"

 
class DownloadManagerDialog(QDialog):
    def __init__(
        self,
        parent,
        surah_manager: DownloadManager,
        ayah_manager: DownloadManager,
    ):
        super().__init__(parent)
        self.parent = parent
        self.surah_manager = surah_manager
        self.ayah_manager = ayah_manager

        self.setWindowTitle("مدير التنزيلات")
        self.setMinimumWidth(500)

        layout = QVBoxLayout()

        # === Top Controls ===
        top_layout = QHBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("بحث...")

        self.section_label = QLabel("القسم:")
        self.section_combo = QComboBox()
        for download_manager, section in [
            (self.surah_manager, "السور"),
            (self.ayah_manager, "الآيات"),
        ]:
            if download_manager is not None:
                self.section_combo.addItem(section, download_manager)
        self.section_combo.currentIndexChanged.connect(self.update_list)
        self.section_combo.setAccessibleName(self.section_label.text())

        self.filter_label = QLabel("تصفية:")
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("الكل", None)
        for status in DownloadStatus:
            self.filter_combo.addItem(status.label, status)
        self.filter_combo.setAccessibleName(self.filter_label.text())
        self.filter_combo.currentIndexChanged.connect(self.update_list)

        top_layout.addWidget(self.search_box)
        top_layout.addWidget(self.section_label)
        top_layout.addWidget(self.section_combo)
        top_layout.addWidget(self.filter_label)
        top_layout.addWidget(self.filter_combo)
        layout.addLayout(top_layout)

        # === Downloads List ===
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.list_widget)

        # === Buttons ===
        btn_layout = QHBoxLayout()
        self.btn_download = QPushButton("تنزيل")
        self.btn_delete = QPushButton("حذف")
        self.btn_close = QPushButton("إغلاق")

        self.btn_download.clicked.connect(self.show_download_menu)
        self.btn_delete.clicked.connect(self.show_delete_menu)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # Load initial data
        self.update_list()

    def current_manager(self) -> DownloadManager:
        return self.section_combo.currentData()

    def update_list(self):
        """Refresh the list view based on section and filter."""
        manager = self.current_manager()
        self.list_widget.clear()

        status = self.filter_combo.currentData()
        downloads = manager.get_downloads(status)

        for  download_item in downloads:
            display_text = f"{download_item['name']} - {download_item['status'].label}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, download_item['id'])
            self.list_widget.addItem(item)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        delete_action = menu.addAction("حذف العنصر المحدد")
        delete_action.triggered.connect(self.delete_selected_item)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def delete_selected_item(self):
        manager = self.current_manager()
        download_id = self.list_widget.currentItem().data(Qt.ItemDataRole.UserRole)
        if download_id:
            manager.db.delete(download_id)
            self.update_list()

    def delete_by_status(self, status: DownloadStatus):
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
        menu.addAction("حذف غير المكتمل", lambda: self.delete_by_status([DownloadStatus.PENDING, DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED, DownloadStatus.CANCELLED, DownloadStatus.ERROR]))
        menu.exec(self.btn_delete.mapToGlobal(self.btn_delete.rect().bottomLeft()))

    def show_download_menu(self):
        menu = QMenu(self)
        menu.addAction("تنزيل سور")
        menu.addAction("تنزيل آيات")
        menu.exec(self.btn_download.mapToGlobal(self.btn_download.rect().bottomLeft()))


class NewDownloadDialog(QDialog):
    """Dialog for downloading Surahs or Ayahs."""

    def __init__(self, parent, mode: DownloadMode, surahs: List[Surah], reciters_manager: RecitersManager):
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
            self.reciter_combo.addItem(reciter["display_text"], reciter["id"])

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
        available = set(reciter["available_surahs"])
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
