from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QMessageBox,
    QPushButton, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu
)
from PyQt6.QtCore import Qt

from core_functions.downloader import DownloadManager
from core_functions.downloader.status import DownloadStatus, DownloadProgress
from core_functions.Reciters import RecitersManager
from utils.logger import LoggerManager
from utils.settings import Config

from .models import DownloadMode
from .new_download_dialog import NewDownloadDialog
from .progress_tracker import SessionProgressBar

logger = LoggerManager.get_logger(__name__)

class DownloadManagerDialog(QDialog):
    """Dialog to manage and monitor Quran downloads."""

    def __init__(
            self, 
                 parent, 
                 surah_manager: DownloadManager, 
                 ayah_manager: DownloadManager,
                 surah_reciters: RecitersManager,
                    ayah_reciters: RecitersManager
                 ):
        super().__init__(parent)
        self.parent = parent
        self.surah_manager = surah_manager
        self.ayah_manager = ayah_manager
        self.surah_reciters = surah_reciters
        self.ayah_reciters = ayah_reciters
        self.item_map: Dict[str, QListWidgetItem] = {}

        self.setWindowTitle("مدير التنزيلات")
        self.setMinimumWidth(520)

        self._setup_ui()
        self.session_progress.set_managers([self.surah_manager, self.ayah_manager])
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
        self.section_combo.setAccessibleName(self.section_label.text())
        for manager, reciters_manager, label in [
            (self.surah_manager, self.surah_reciters, "السور"), 
            (self.ayah_manager, self.ayah_reciters, "الآيات")
            ]:
            if manager:
                self.section_combo.addItem(label, (manager, reciters_manager))

        self.filter_label = QLabel("تصفية:")
        self.filter_combo = QComboBox()
        self.filter_combo.setAccessibleName(self.filter_label.text())
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

        # === Session Progress ===
        self.session_progress = SessionProgressBar(self)
        layout.addWidget(self.session_progress)

        # === Buttons ===
        btn_layout = QHBoxLayout()
        self.btn_download = QPushButton("تنزيل جديد")
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
        self.surah_manager.status_changed.connect(self.update_status)
        self.ayah_manager.status_changed.connect(self.update_status)
        self.surah_manager.download_finished.connect(self.on_finished)
        self.ayah_manager.download_finished.connect(self.on_finished)

    @property
    def current_manager(self) -> DownloadManager:
        return self.section_combo.currentData()[0]
    
    @property
    def current_reciters_manager(self) -> RecitersManager:
        return self.section_combo.currentData()[1]

    @property
    def current_filter_status(self) -> Optional[DownloadStatus]:
        return self.filter_combo.currentData()

    @property
    def current_download_item(self) -> Optional[QListWidgetItem]:
        return self.list_widget.currentItem()
    
    @property
    def current_download_id(self) -> Optional[int]:
        item = self.current_download_item
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

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

    def update_status(self, download_id: str, status: DownloadStatus):
        """Update the status of a specific item."""
        item = self.item_map.get(download_id)
        if not item:
            logger.warning(f"Item with ID {download_id} not found in item_map.")
            return
        
        text = item.text()
        if ", " in text:
            base_text = ", ".join(text.split(", ")[:-1])
            new_text = f"{base_text}, {status.label}"
            item.setText(new_text)

    def on_finished(self, download_id: str):
        """Handle when a download is finished."""
        item = self.item_map.get(download_id)
        if not item:
            logger.warning(f"Item with ID {download_id} not found in item_map.")
            return
        
        download_item = self.current_manager.get_download(download_id)
        text = f"100%, الحجم {download_item['size_text'] or 'غير معروف'}"
        item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, text)
        item.setToolTip(text)

    def update_list(self):
        """Rebuild the visible list based on filters and search."""
        manager = self.current_manager
        if not manager:
            logger.warning("No download manager selected.")
            return

        self.list_widget.clear()
        self.item_map.clear()

        status = self.current_filter_status
        search_text = self.search_box.text().strip().lower()
        download_items = manager.get_downloads(status)
        surahs = self.parent.quran_manager.get_surahs()

        for item_data in download_items:
            if search_text and search_text not in item_data["filename"].lower():
                continue

            progress = (
                f"{(item_data['downloaded_bytes'] / item_data['total_bytes'] * 100):.1f}%, " if item_data["total_bytes"] > 0 else "0%, "
            ) + f", الحجم {item_data.get('size_text') or 'غير معروف'}"

            surah = surahs[item_data["surah_number"] - 1]
            reciter_display_text = self.current_reciters_manager.get_reciter(item_data["reciter_id"]).get("display_text", "قارئ غير معروف")
            display_text = f"{item_data['filename']}, {surah.name}, {reciter_display_text}, {item_data['status'].label}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, item_data['id'])
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, progress)
            item.setToolTip(progress)
            self.list_widget.addItem(item)
            self.item_map[item_data['id']] = item

    def show_context_menu(self, pos):
        """Show context menu for the selected download item."""
        if not self.current_download_item:
            logger.warning("No download item selected for context menu.")
            return
        
        menu = QMenu(self)
        current_status = self.current_manager.get_download(self.current_download_id)["status"]

        # Pause / Resume depending on state
        if current_status == DownloadStatus.DOWNLOADING:
            menu.addAction("إيقاف مؤقت", lambda: self.current_manager.pause(self.current_download_id))
        elif current_status == DownloadStatus.PAUSED:
            menu.addAction("استئناف", lambda: self.current_manager.resume(self.current_download_id))

        # Cancel option if active
        if current_status not in [DownloadStatus.COMPLETED, DownloadStatus.CANCELLED, DownloadStatus.ERROR]:
            menu.addAction("إلغاء التحميل",
            lambda: self.current_manager.cancel(self.current_download_id) 
            if self.confirm_cancel_item(self.current_download_id) else None)
            menu.addAction("إلغاء تحميل الكل",
            lambda: self.current_manager.cancel_all() 
            if self.confirm_cancel_all() else None)
        elif current_status == DownloadStatus.CANCELLED:
            menu.addAction("بدء التحميل", lambda: self.current_manager.restart(self.current_download_id))
            menu.addAction("بدء تحميل الكل", self.current_manager.restart_all)
        elif current_status == DownloadStatus.ERROR:
            menu.addAction("إعادة المحاولة", lambda: self.current_manager.restart(self.current_download_id))
                
        # Delete option
        menu.addSeparator()
        action_delete = menu.addAction("حذف العنصر المحدد", self.delete_selected_item)

        menu.setAccessibleName("الإجراءات")
        menu.setFocus()
        menu.exec(self.list_widget.mapToGlobal(pos))

    def delete_selected_item(self):
        """Delete the currently selected download item."""
        if not self.current_download_item:
            return

        download_id = self.current_download_id
        data = self.current_manager.get_download(download_id)
        surahs = self.parent.quran_manager.get_surahs()
        surah = surahs[data["surah_number"] - 1]
        reciter = self.current_reciters_manager.get_reciter(data["reciter_id"])
        reciter_name = reciter.get("display_text", "قارئ غير معروف")

        item_name = data["filename"]
        surah_name = surah.name

        full_title = f"{item_name} - {surah_name} - {reciter_name}"


        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("تأكيد الحذف")
        msg_box.setText(
            f"هل أنت متأكد من حذف العنصر التالي؟\n\n{full_title}"
        )

        yes_button = msg_box.addButton("نعم", QMessageBox.ButtonRole.AcceptRole)
        no_button = msg_box.addButton("لا", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()


        if msg_box.clickedButton() != yes_button:
            return


        self.current_manager.delete(download_id)

        self.item_map.pop(download_id, None)
        self.update_list()



    def delete_by_status(self, status, status_label):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("تأكيد الحذف")
        msg_box.setText(f"هل تريد حذف العناصر {status_label}؟")

        yes_button = msg_box.addButton("نعم", QMessageBox.ButtonRole.AcceptRole)
        msg_box.addButton("لا", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        if msg_box.clickedButton() != yes_button:
            return


        if status == "incomplete":
            statuses = {
                DownloadStatus.PENDING,
                DownloadStatus.DOWNLOADING,
                DownloadStatus.PAUSED,
                DownloadStatus.CANCELLED,
                DownloadStatus.ERROR
            }
            for st in statuses:
                self.current_manager.delete_by_status(st)
        else:
            self.current_manager.delete_by_status(status)

        self.update_list()



    def confirm_cancel_item(self, download_id: int) -> bool:
        """Show a confirmation dialog before cancelling a specific download."""
        data = self.current_manager.get_download(download_id)
        surahs = self.parent.quran_manager.get_surahs()
        surah = surahs[data["surah_number"] - 1]
        reciter = self.current_reciters_manager.get_reciter(data["reciter_id"])
        reciter_name = reciter.get("display_text", "قارئ غير معروف")
        full_title = f"{data['filename']} - {surah.name} - {reciter_name}"

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("تأكيد إلغاء التحميل")
        msg_box.setText(f"هل أنت متأكد من إلغاء تحميل العنصر التالي؟\n\n{full_title}")
        yes_button = msg_box.addButton("نعم", QMessageBox.ButtonRole.AcceptRole)
        no_button =msg_box.addButton("لا", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()
        return msg_box.clickedButton() == yes_button





    def confirm_cancel_all(self) -> bool:
        """Show a confirmation dialog before cancelling all downloads."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("تأكيد إلغاء الكل")
        msg_box.setText("هل أنت متأكد من إلغاء جميع التنزيلات؟")
        yes_button = msg_box.addButton("نعم", QMessageBox.ButtonRole.AcceptRole)
        no_button = msg_box.addButton("لا", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()
        return msg_box.clickedButton() == yes_button



    def delete_all(self):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("تأكيد حذف الكل")
        msg_box.setText("هل أنت متأكد من حذف جميع العناصر؟")

        yes_button = msg_box.addButton("نعم", QMessageBox.ButtonRole.AcceptRole)
        no_button = msg_box.addButton("لا", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        if msg_box.clickedButton() != yes_button:
            return

        self.current_manager.delete_all()
        self.update_list()


    def show_delete_menu(self):
        menu = QMenu(self)
        menu.addAction("حذف الكل", self.delete_all)
        menu.addAction("حذف المكتمل",
        lambda: self.delete_by_status(DownloadStatus.COMPLETED, "المكتمل"))

        menu.addAction("حذف غير المكتمل",
        lambda: self.delete_by_status("incomplete", "غير المكتمل"))

        
        menu.setAccessibleName("قائمة حذف")
        menu.setFocus()
        menu.exec(self.btn_delete.mapToGlobal(self.btn_delete.rect().bottomLeft()))



    def download_surahs(self):
        surahs = self.parent.quran_manager.get_surahs()

        dialog = NewDownloadDialog(self, DownloadMode.SURAH, surahs, self.surah_reciters)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selection = dialog.get_selection()
            reciter = selection["reciter"]
            from_surah = selection["from_surah"]
            to_surah = selection["to_surah"]

            new_downloads = [
                {
                    "reciter_id": reciter["id"],
                    "surah_number": num,
                    "url": self.surah_reciters.get_url(reciter["id"], num),
                }
                for num in range(from_surah.number, to_surah.number + 1)
                if num in reciter["available_suras"]
            ]

            path = F"{Config.downloading.download_path}/{reciter['id']}"
            self.surah_manager.add_new_downloads(new_downloads, path)
            self.surah_manager.start()
            self.update_list()
            self.session_progress.recalculate_totals()
            self.list_widget.setFocus()

    def download_ayahs(self):
        surahs = self.parent.quran_manager.get_surahs()

        dialog = NewDownloadDialog(self, DownloadMode.AYAH, surahs, self.ayah_reciters)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selection = dialog.get_selection()
            reciter = selection["reciter"]
            from_surah = selection["from_surah"]
            to_surah = selection["to_surah"]
            from_ayah_global = selection["from_ayah"]
            to_ayah_global = selection["to_ayah"]

            new_downloads = []
            
            # Iterate through the range of surahs
            for surah in surahs[from_surah.number - 1 : to_surah.number]:
                start_ayah = 1
                end_ayah = surah.ayah_count

                if                 from_ayah_global >= surah.first_ayah_number and                 from_ayah_global <= surah.last_ayah_number:
                    start_ayah = from_ayah_global - surah.first_ayah_number + 1

                if                 to_ayah_global >= surah.first_ayah_number and                 to_ayah_global <= surah.last_ayah_number:
                    end_ayah = to_ayah_global - surah.first_ayah_number + 1

                for ayah_num in range(start_ayah, end_ayah + 1):
                    url = self.ayah_reciters.get_url(reciter["id"], surah.number, ayah_num)
                    if url:
                        new_downloads.append({
                            "reciter_id": reciter["id"],
                            "surah_number": surah.number,
                            "ayah_number": ayah_num,
                            "url": url,
                        })

            if new_downloads:
                path = F"{Config.downloading.download_path}/{reciter['id']}"
                self.ayah_manager.add_new_downloads(new_downloads, path)
                self.ayah_manager.start()
                self.update_list()
                self.session_progress.recalculate_totals()
                self.list_widget.setFocus()

    def show_download_menu(self):
        menu = QMenu(self)
        menu.addAction("تنزيل سور", self.download_surahs)
        menu.addAction("تنزيل آيات", self.download_ayahs)
        menu.setAccessibleName("قائمة تنزيل جديد")
        menu.setFocus()
        menu.exec(self.btn_download.mapToGlobal(self.btn_download.rect().bottomLeft()))
