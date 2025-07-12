from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime

Base = declarative_base()

class DownloadItem(Base):
    __tablename__ = "downloads"

    id = Column(String, primary_key=True)
    url = Column(String, nullable=False)
    filename = Column(String)
    folder_path = Column(String)
    status = Column(String)
    downloaded_bytes = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    file_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)