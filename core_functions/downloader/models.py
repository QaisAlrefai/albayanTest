from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Enum as SqlEnum
from .status import DownloadStatus

# Base for declarative models
Base = declarative_base()


class DownloadTableBase(Base):
    """Abstract base class for shared download fields (not mapped to DB)."""
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    folder_path = Column(String, nullable=False)

    status = Column(
        SqlEnum(DownloadStatus, name="download_status", native_enum=False),
        nullable=False,
        default=DownloadStatus.PENDING,
    )

    downloaded_bytes = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    file_hash = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DownloadSurahs(DownloadTableBase):
    __tablename__ = "download_surahs"

    reciter_id = Column(Integer, nullable=False)
    surah_number = Column(Integer, nullable=False)


class DownloadAyahs(DownloadTableBase):
    __tablename__ = "download_ayahs"

    reciter_id = Column(Integer, nullable=False)
    surah_number = Column(Integer, nullable=False)
    ayah_number = Column(Integer, nullable=False)
