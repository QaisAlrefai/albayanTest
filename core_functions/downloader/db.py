from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, DownloadItem
from datetime import datetime

class DownloadDB:
    def __init__(self, db_url="sqlite:///downloads.db"):
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def upsert(self, item_data: dict):
        session = self.Session()
        try:
            obj = session.query(DownloadItem).filter_by(id=item_data["id"]).first()
            if obj:
                for key, value in item_data.items():
                    setattr(obj, key, value)
            else:
                item_data.setdefault("created_at", datetime.utcnow())
                obj = DownloadItem(**item_data)
                session.add(obj)
            session.commit()
        finally:
            session.close()

    def all(self):
        session = self.Session()
        try:
            return session.query(DownloadItem).all()
        finally:
            session.close()

    def delete(self, download_id: str):
        session = self.Session()
        try:
            session.query(DownloadItem).filter_by(id=download_id).delete()
            session.commit()
        finally:
            session.close()