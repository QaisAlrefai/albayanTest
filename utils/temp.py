
import os
from pathlib import Path
from .const import program_english_name, author

try:
    from winrt.windows.storage import ApplicationData
except ImportError:
    ApplicationData = None


class PathManager:
    def __init__(self, app_name, author):
        self.app_name = app_name
        self.author = author

        # detect environment (MSIX vs external)
        self.base_dir = self._detect_base_dir()

        # main folders
        self.app_folder = self.base_dir / self.author / app_name
        self.app_folder.mkdir(parents=True, exist_ok=True)

        # standard paths
        self.user_db = self.app_folder / "user_data.db"
        self.download_db_path = self.app_folder / "download_data.db"
        self.config_file = self.app_folder / "config.ini"
        self.log_file = self.app_folder / f"{app_name.lower()}.log"
        self.data_folder = Path("database")  # bundled data
        self.reciters_db = self.data_folder / "quran" / "reciters.db"


        # athkar
        self.athkar_db = self.app_folder / "athkar.db"
        self.athkar_audio = self.app_folder / "audio" / "athkar"
        self.athkar_audio.mkdir(parents=True, exist_ok=True)

        # temp
        self.temp_folder = Path(os.getenv("TEMP", "/tmp")) / app_name
        self.temp_folder.mkdir(parents=True, exist_ok=True)

        # documents
        self.documents_dir = Path.home() / "Documents" / app_name
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def _detect_base_dir(self) -> Path:
        """Detects base directory depending on app context."""
        # MSIX environment
        if ApplicationData:
            try:
                return Path(ApplicationData.current.local_folder.path)
            except Exception:
                pass
        # fallback: external exe
        return Path(os.getenv("APPDATA", Path.home()))

    def __repr__(self):
        """Pretty multi-line representation for debugging/printing."""
        paths = {
            "BaseDir": self.base_dir,
            "AppFolder": self.app_folder,
            "UserDB": self.user_db,
            "Config": self.config_file,
            "Log": self.log_file,
            "AthkarDB": self.athkar_db,
            "AthkarAudio": self.athkar_audio,
            "Temp": self.temp_folder,
            "Documents": self.documents_dir,
        }
        lines = [f"<PathManager app='{self.app_name}'>"]
        lines += [f"  {key}: {val}" for key, val in paths.items()]
        return "\n".join(lines)
    
# create a singleton instance
paths = PathManager(program_english_name, author)
