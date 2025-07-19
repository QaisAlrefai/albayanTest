from enum import Enum

class DownloadStatus(Enum):
    PAUSED = "paused"
    DOWNLOADING = "downloading"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ERROR = "error"
    PENDING = "pending"
    