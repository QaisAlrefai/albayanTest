
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject

# Add project root to path
sys.path.append(os.getcwd())

from core_functions.downloader.manager import DownloadManager
from ui.dialogs.download_manager_dialog.download_model import DownloadListModel

def verify_signals():
    app = QApplication(sys.argv)
    
    print("Initializing Manager and Model...")
    manager = DownloadManager(save_history=False)
    model = DownloadListModel(manager)
    
    # Test Addition
    print("Adding a download...")
    manager.add_download("http://example.com/file1.mp3", "/tmp")
    
    assert model.rowCount() == 1
    print("Model row count is 1 (Passed)")
    
    download_id = model._download_ids[0]
    
    # Test Deletion
    print("Deleting download...")
    manager.delete(download_id, delete_file=False)
    
    assert model.rowCount() == 0
    print("Model row count is 0 (Passed)")
    
    # Test Clear
    print("Adding multiple downloads...")
    manager.add_download("http://example.com/file2.mp3", "/tmp")
    manager.add_download("http://example.com/file3.mp3", "/tmp")
    assert model.rowCount() == 2
    
    print("Clearing all downloads...")
    manager.delete_all(delete_files=False)
    
    assert model.rowCount() == 0
    print("Model row count is 0 after clearing (Passed)")
    
    print("Verification Successful!")

if __name__ == "__main__":
    verify_signals()
