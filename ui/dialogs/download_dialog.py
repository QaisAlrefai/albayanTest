from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QComboBox, QListWidget, QPushButton, QMenu, QLabel, QGridLayout
)
from PyQt6.QtCore import Qt
import sys


class DownloadVersesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تنزيل آيات")
        self.setAccessibleName("نافذة تنزيل آيات")

        layout = QVBoxLayout()
        grid = QGridLayout()

        self.reader_combo = QComboBox()
        self.reader_combo.addItems(["القارئ 1", "القارئ 2"])
        grid.addWidget(QLabel("القارئ:"), 0, 0)
        grid.addWidget(self.reader_combo, 0, 1)

        self.from_surah_combo = QComboBox()
        self.from_surah_combo.addItems(["الفاتحة", "البقرة", "آل عمران"])
        grid.addWidget(QLabel("من السورة:"), 1, 0)
        grid.addWidget(self.from_surah_combo, 1, 1)

        self.from_ayah_combo = QComboBox()
        self.from_ayah_combo.addItems([str(i) for i in range(1, 21)])
        grid.addWidget(QLabel("من الآية:"), 2, 0)
        grid.addWidget(self.from_ayah_combo, 2, 1)

        self.to_surah_combo = QComboBox()
        self.to_surah_combo.addItems(["الفاتحة", "البقرة", "آل عمران"])
        grid.addWidget(QLabel("إلى السورة:"), 3, 0)
        grid.addWidget(self.to_surah_combo, 3, 1)

        self.to_ayah_combo = QComboBox()
        self.to_ayah_combo.addItems([str(i) for i in range(1, 21)])
        grid.addWidget(QLabel("إلى الآية:"), 4, 0)
        grid.addWidget(self.to_ayah_combo, 4, 1)

        layout.addLayout(grid)

        btn_layout = QHBoxLayout()
        btn_download = QPushButton("تنزيل")
        btn_close = QPushButton("إغلاق")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_download)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
        self.setLayout(layout)


class DownloadSurahsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تنزيل سور")
        self.setAccessibleName("نافذة تنزيل سور")

        layout = QVBoxLayout()
        grid = QGridLayout()

        self.reader_combo = QComboBox()
        self.reader_combo.addItems(["القارئ 1", "القارئ 2"])
        grid.addWidget(QLabel("القارئ:"), 0, 0)
        grid.addWidget(self.reader_combo, 0, 1)

        self.from_surah_combo = QComboBox()
        self.from_surah_combo.addItems(["الفاتحة", "البقرة", "آل عمران"])
        grid.addWidget(QLabel("من السورة:"), 1, 0)
        grid.addWidget(self.from_surah_combo, 1, 1)

        self.to_surah_combo = QComboBox()
        self.to_surah_combo.addItems(["الفاتحة", "البقرة", "آل عمران"])
        grid.addWidget(QLabel("إلى السورة:"), 2, 0)
        grid.addWidget(self.to_surah_combo, 2, 1)

        layout.addLayout(grid)

        btn_layout = QHBoxLayout()
        btn_download = QPushButton("تنزيل")
        btn_close = QPushButton("إغلاق")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_download)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
        self.setLayout(layout)


class MainDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("إدارة التنزيلات")
        self.setAccessibleName("نافذة إدارة التنزيلات")

        layout = QVBoxLayout()

        # مربع البحث + الفلتر
        top_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("بحث...")
        self.search_box.setAccessibleName("مربع البحث")

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["الكل", "قيد التنزيل", "المكتمل"])
        self.filter_combo.setAccessibleName("فلتر العرض")

        top_layout.addWidget(self.search_box)
        top_layout.addWidget(self.filter_combo)
        layout.addLayout(top_layout)

        # القائمة
        self.list_widget = QListWidget()
        self.list_widget.setAccessibleName("قائمة العناصر")
        self.list_widget.addItems([
            "عنصر 1 - مكتمل",
            "عنصر 2 - قيد التنزيل",
            "عنصر 3 - مكتمل",
            "عنصر 4 - قيد التنزيل"
        ])
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.list_widget)

        # الأزرار
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

    def show_context_menu(self, pos):
        menu = QMenu(self)
        delete_action = menu.addAction("حذف العنصر المحدد")
        delete_action.triggered.connect(self.delete_selected_item)

        download_menu = menu.addMenu("تنزيل")
        download_menu.addAction("تنزيل سور", self.open_download_surahs)
        download_menu.addAction("تنزيل آيات", self.open_download_verses)

        menu.exec(self.list_widget.mapToGlobal(pos))

    def delete_selected_item(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.list_widget.takeItem(current_row)

    def show_delete_menu(self):
        menu = QMenu(self)
        menu.addAction("حذف الكل", self.delete_all)
        menu.addAction("حذف المكتمل", lambda: self.delete_by_filter("المكتمل"))
        menu.addAction("حذف غير المكتمل", lambda: self.delete_by_filter("قيد التنزيل"))
        menu.exec(self.btn_delete.mapToGlobal(self.btn_delete.rect().bottomLeft()))

    def delete_all(self):
        self.list_widget.clear()

    def delete_by_filter(self, filter_text):
        for i in reversed(range(self.list_widget.count())):
            item_text = self.list_widget.item(i).text()
            if filter_text in item_text:
                self.list_widget.takeItem(i)

    def show_download_menu(self):
        menu = QMenu(self)
        menu.addAction("تنزيل سور", self.open_download_surahs)
        menu.addAction("تنزيل آيات", self.open_download_verses)
        menu.exec(self.btn_download.mapToGlobal(self.btn_download.rect().bottomLeft()))

    def open_download_surahs(self):
        dlg = DownloadSurahsDialog(self)
        dlg.exec()

    def open_download_verses(self):
        dlg = DownloadVersesDialog(self)
        dlg.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)  # دعم الاتجاه العربي
    dlg = MainDialog()
    dlg.resize(500, 400)
    dlg.show()
    sys.exit(app.exec())
