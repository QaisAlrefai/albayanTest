from enum import Enum

class DownloadStatus(Enum):
    PAUSED = "paused"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ERROR = "error"
    PENDING = "pending"