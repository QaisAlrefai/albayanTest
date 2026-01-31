from pathlib import Path
import os
import subprocess
from typing import List, Dict, Optional, Union

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QMessageBox,
    QPushButton, QLabel, QLineEdit, QListView,
    QAbstractItemView, QMenu
)
from PyQt6.QtCore import Qt, QUrl, QModelIndex
from PyQt6.QtGui import QDesktopServices
from django import shortcuts
from ui.dialogs.info_dialog import InfoDialog
from core_functions.downloader import DownloadManager
from core_functions.downloader.status import DownloadStatus, DownloadProgress
from core_functions.Reciters import RecitersManager
from utils.logger import LoggerManager
from utils.settings import Config
from  utils.universal_speech import UniversalSpeech

from ui.common.user_message import UserMessageService
from .models import DownloadMode
from .new_download_dialog import NewDownloadDialog
from .progress_tracker import SessionProgressBar
from .delegate import DownloadDelegate
from .download_model import DownloadListModel
from .proxy_model import DownloadProxyModel

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
        
        # Initialize Models
        self.surah_model = DownloadListModel(self, self.surah_manager, self.surah_reciters, self.parent.quran_manager.get_surahs())
        self.ayah_model = DownloadListModel(self, self.ayah_manager, self.ayah_reciters, self.parent.quran_manager.get_surahs())
        
        self.proxy_model = DownloadProxyModel(self)
        
        # Default to Surah Model
        self.proxy_model.setSourceModel(self.surah_model)

        self.user_message_service = UserMessageService(self)

        self.setWindowTitle("مدير التنزيلات")
        self.setMinimumWidth(520)

        self._setup_ui()
        self.set_shortcuts()
        self.session_progress.set_managers([self.surah_manager, self.ayah_manager])
        self._connect_signals()
        # No initial update_list needed, model handles it

    def _setup_ui(self):
        layout = QVBoxLayout()

        # === Top controls ===
        top_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("بحث...")

        self.section_label = QLabel("القسم:")
        self.section_combo = QComboBox()
        self.section_combo.setAccessibleName(self.section_label.text())
        
        # Add items with (Model, Manager, RecitersManager) as UserData
        if self.surah_manager:
            self.section_combo.addItem("السور", (self.surah_model, self.surah_manager, self.surah_reciters))
        if self.ayah_manager:
            self.section_combo.addItem("الآيات", (self.ayah_model, self.ayah_manager, self.ayah_reciters))

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

        # === ListView Widget ===
        self.list_view = QListView()
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.setModel(self.proxy_model)
        self.list_view.setItemDelegate(DownloadDelegate(self.list_view))
        self.list_view.setUniformItemSizes(True)
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.list_view)

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
        self.section_combo.currentIndexChanged.connect(self.on_section_changed)
        self.filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        self.search_box.textChanged.connect(self.on_search_text_changed)
        self.list_view.customContextMenuRequested.connect(self.show_context_menu)

        self.btn_download.clicked.connect(self.show_download_menu)
        self.btn_delete.clicked.connect(self.show_delete_menu)
        self.btn_close.clicked.connect(self.close)
        
        # Manager signals are handled by the models internally for data updates.
        # However, for SessionProgressBar, it might still need direct manager signals or we can hook them up.
        # The session progress bar likely connects to managers internally if passed in `set_managers`?
        # create `set_managers` in `main_dialog.__init__` handles it.
        # But we also have `on_finished` in original code that was updating tooltips. Model handles this now.
        
        # We still need to listen to add events effectively if session progress needs recalc, 
        # but `SessionProgressBar` implementation likely handles signals from managers directly.
        
        # Let's ensure session progress updates when new downloads are added via the dialog.

        # Let's ensure session progress updates when new downloads are added via the dialog.
        self.surah_manager.downloads_added.connect(lambda _: self.session_progress.recalculate_totals())
        self.ayah_manager.downloads_added.connect(lambda _: self.session_progress.recalculate_totals())
        
        # Ensure session progress updates when downloads are deleted
        self.surah_manager.download_deleted.connect(lambda _: self.session_progress.recalculate_totals())
        self.ayah_manager.download_deleted.connect(lambda _: self.session_progress.recalculate_totals())
        self.surah_manager.downloads_cleared.connect(self.session_progress.recalculate_totals)
        self.ayah_manager.downloads_cleared.connect(self.session_progress.recalculate_totals)

    def set_shortcuts(self):

        shortcuts = (
            (QKeySequence("P"), self.say_percentage),
            (QKeySequence("C"), self.say_status),
            (QKeySequence("S"), self.say_speed),
            (QKeySequence("D"), self.say_downloaded_size),
            (QKeySequence("E"), self.say_elapsed_time),
        )

        for seq, func in shortcuts:
            shortcut = QShortcut(seq, self)
            shortcut.activated.connect(func)

    def on_section_changed(self):
        data = self.section_combo.currentData()
        if data:
            model = data[0]
            self.proxy_model.setSourceModel(model)

    def on_filter_changed(self):
        status = self.filter_combo.currentData()
        self.proxy_model.set_status_filter(status)

    def on_search_text_changed(self, text):
        self.proxy_model.set_text_filter(text)

    @property
    def current_manager(self) -> DownloadManager:
        return self.section_combo.currentData()[1]
    
    @property
    def current_reciters_manager(self) -> RecitersManager:
        return self.section_combo.currentData()[2]

    @property
    def current_item_index(self) -> Optional[QModelIndex]:
        index = self.list_view.currentIndex()
        if not index.isValid():
            return None
        return index
    
    @property
    def current_download_id(self) -> Optional[int]:
        index = self.current_item_index
        if not index:
            return None
        return index.data(DownloadListModel.ItemRole)["id"]
    
    @property
    def current_download_title(self) -> str:
        index = self.current_item_index
        if not index.isValid():
            return ""
        return index.data(Qt.ItemDataRole.DisplayRole)

    def show_context_menu(self, pos):
        """Show context menu for the selected download item."""
        index = self.list_view.indexAt(pos)
        if not index.isValid():
            return

        item_data = index.data(DownloadListModel.ItemRole)
        if not item_data:
            return

        download_id = item_data["id"]
        current_status = item_data["status"]
        file_path = Path(item_data["folder_path"]) / item_data["filename"]

        menu = QMenu(self)
        open_file_action = menu.addAction("تشغيل في المشغل الافتراضي", lambda: self.open_in_default_player(file_path))
        open_folder = menu.addAction("فتح في المجلد", lambda: self.open_containing_folder(file_path))
        menu.addSeparator()
        pause_action = menu.addAction("إيقاف مؤقت", self.pause_current_item)
        pause_all_action = menu.addAction("إيقاف تنزيل الكل", self.pause_all)
        resume_action = menu.addAction("استئناف", lambda: self.current_manager.resume(download_id))
        resume_all = menu.addAction("استئناف تنزيل الكل", self.current_manager.resume_all)
        start_action = menu.addAction("إعادة المحاولة" if current_status == DownloadStatus.ERROR else "بدء التنزيل", self.restart_current_item)
        start_all = menu.addAction("بدء تنزيل الكل", self.restart_all)
        cancel_action = menu.addAction("إلغاء التنزيل", self.cancel_current_item)
        cancel_all_action = menu.addAction("إلغاء تنزيل الكل", self.cancel_all)
        menu.addSeparator()
        delete_action = menu.addAction("حذف العنصر المحدد", self.delete_selected_item)
        delete_all_action = menu.addAction("حذف الكل", self.delete_all)
        info_action = menu.addAction("معلومات العنصر المحدد", self.show_selected_item_info)

        # status of actions based on current status
        open_file_action.setEnabled(file_path.exists() and current_status == DownloadStatus.COMPLETED)
        open_folder.setEnabled(file_path.exists())
        pause_action.setEnabled(current_status == DownloadStatus.DOWNLOADING)
        pause_all_action.setEnabled(self.current_manager.has_active_downloads())
        resume_action.setEnabled(current_status == DownloadStatus.PAUSED)
        resume_all.setEnabled(len(self.current_manager.get_downloads([DownloadStatus.PAUSED])) > 0)
        start_action.setEnabled(current_status in {DownloadStatus.ERROR, DownloadStatus.CANCELLED})
        start_all.setEnabled(len(self.current_manager.get_downloads([DownloadStatus.CANCELLED, DownloadStatus.ERROR])) > 0)
        cancel_action.setEnabled(current_status in {DownloadStatus.PENDING, DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED})
        cancel_all_action.setEnabled(len(self.current_manager.get_downloads([DownloadStatus.PENDING, DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED])) > 0)
        delete_action.setEnabled(self.current_download_id is not None)
        delete_all_action.setEnabled(len(self.current_manager.get_downloads()) > 0)

        menu.setAccessibleName("الإجراءات")
        menu.setFocus()
        menu.exec(self.list_view.mapToGlobal(pos))

    def show_selected_item_info(self):
        download_id = self.current_download_id
        if download_id is None:
            logger.warning("No download selected.")
            return

        data = self.current_manager.get_download(download_id)
        if not data:
            logger.warning(f"No data found for download ID {download_id}")
            return
        formatted_text, window_title = self.format_download_info(data)
        InfoDialog(self, window_title, window_title, formatted_text).open()

    def format_download_info(self, data: dict) -> tuple[str, str]:
        """Format a download item (Surah or Ayah) into a clean text for display entirely inside f-strings."""

        surahs = self.parent.quran_manager.get_surahs()
        reciter = self.current_reciters_manager.get_reciter(data.get("reciter_id"))

        window_title = f"معلومات ملف {data.get('filename', 'غير معروف')}"

        return (
            "\n".join([
                f"نوع العنصر: {'آية' if data.get('ayah_number') else 'سورة'}.",
                f"اسم الملف: {data.get('filename', 'غير معروف')}.",
                *( [f"حجم الملف: {data.get('size_text')}." ] if data.get('size_text') and not str(data.get('size_text')).startswith('0') else [] ),
                f"مسار الملف: {data.get('folder_path', 'غير معروف')}.",
                f"تاريخ الإنشاء: {data.get('created_at').strftime('%Y-%m-%d %H:%M') if hasattr(data.get('created_at'), 'strftime') else (str(data.get('created_at'))[:16] if data.get('created_at') else 'غير معروف')}.",
                f"تاريخ آخر تعديل: {data.get('updated_at').strftime('%Y-%m-%d %H:%M') if hasattr(data.get('updated_at'), 'strftime') else (str(data.get('updated_at'))[:16] if data.get('updated_at') else 'غير معروف')}.",
                f"الحالة: {data.get('status').label if data.get('status') else 'غير معروف'}.",
                *( [f"رقم الآية: {data.get('ayah_number')}." ] if data.get('ayah_number') else [] ),
                f"رقم السورة: {data.get('surah_number', 'غير معروف')}.",
                f"اسم السورة: {surahs[data.get('surah_number') - 1].name if data.get('surah_number') and 0 < data.get('surah_number') <= len(surahs) else 'غير معروف'}.",
                f"القارئ: {reciter.get('display_text', 'غير معروف') if reciter else 'غير معروف'}.",
                f"الرابط: {data.get('url', 'غير معروف')}."
            ]),
            window_title
        )

    def open_in_default_player(self, file_path: Union[str, Path]):
        file_path = Path(file_path) if isinstance(file_path, str) else file_path
        if file_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))

    def open_containing_folder(self, file_path: Union[str, Path]):
        file_path = Path(file_path) if isinstance(file_path, str) else file_path
        folder_path = file_path.parent
        if folder_path.exists():
            subprocess.run(f'explorer /select,"{file_path}"', shell=True)

    def delete_selected_item(self):
        """Delete the currently selected download item."""
        download_id = self.current_download_id
        if not download_id:
            return
        
            if  self.user_message_service.confirm(
                "تأكيد الحذف", f"هل أنت متأكد من حذف العنصر التالي؟\n\n{self.current_download_title}"
            ):
                self.current_manager.delete(download_id)

    def delete_by_status(self, status, status_label):
        if not self.user_message_service.confirm(
            "تأكيد الحذف",
            f"هل تريد حذف العناصر {status_label}؟",
        ):
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

    def cancel_current_item(self):
        if self.user_message_service.confirm(
            "تأكيد إلغاء التنزيل",
            f"هل أنت متأكد من إلغاء تنزيل العنصر التالي؟\n\n{self.current_download_title}"
        ):
            self.current_manager.cancel(self.current_download_id)

    def pause_current_item(self):
        self.current_manager.pause(self.current_download_id)
        self.proxy_model.invalidateFilter()

    def pause_all(self):
        self.current_manager.pause_all()
        self.proxy_model.invalidateFilter()

    def restart_current_item(self):
        self.current_manager.restart(self.current_download_id)
        self.proxy_model.invalidateFilter()

    def restart_all(self):
        self.current_manager.restart_all()
        self.proxy_model.invalidateFilter()

    def cancel_all(self):
        if self.user_message_service.confirm(
            "تأكيد إلغاء الكل",
            "هل أنت متأكد من إلغاء جميع التنزيلات؟",
        ):
            self.current_manager.cancel_all()
            self.proxy_model.invalidateFilter()

    def delete_all(self):
        if self.user_message_service.confirm(
            "تأكيد حذف الكل",
            "هل أنت متأكد من حذف جميع العناصر؟",
        ):
            self.current_manager.delete_all()

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
            self.section_combo.setCurrentIndex(0)
            self.list_view.setFocus()

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

                for ayah_num in range(start_ayah if start_ayah > 1 else 0, end_ayah + 1):
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
                self.section_combo.setCurrentIndex(1)
                self.list_view.setFocus()

    def show_download_menu(self):
        menu = QMenu(self)
        menu.addAction("تنزيل سور", self.download_surahs)
        menu.addAction("تنزيل آيات", self.download_ayahs)
        menu.setAccessibleName("قائمة تنزيل جديد")
        menu.setFocus()
        menu.exec(self.btn_download.mapToGlobal(self.btn_download.rect().bottomLeft()))

    def say_percentage(self):
        """Use text-to-speech to announce the download percentage."""
        index = self.current_item_index
        if index:
            percentage = index.data(DownloadListModel.percentageRole)
            UniversalSpeech.say(percentage)

    def say_status(self):
        """Use text-to-speech to announce the download status."""
        index = self.current_item_index
        if index:
            status = index.data(DownloadListModel.StatusRole).label
            UniversalSpeech.say(status)

    def say_speed(self):
        """Use text-to-speech to announce the download speed."""
        index = self.current_item_index
        if index:
            speed = index.data(DownloadListModel.speedRole)
            UniversalSpeech.say(speed)

    def say_downloaded_size(self):
        """Use text-to-speech to announce the downloaded size."""
        index = self.current_item_index
        if index:
            size = index.data(DownloadListModel.downloadedSizeRole)
            UniversalSpeech.say(size)

    def say_elapsed_time(self):
        """Use text-to-speech to announce the elapsed time."""
        index = self.current_item_index
        if index:
            elapsed = index.data(DownloadListModel.elapsedTimeRole)
            UniversalSpeech.say(elapsed)
