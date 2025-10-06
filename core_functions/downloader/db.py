
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from .models import Base, DownloadTableBase
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

class DownloadDB:
    def __init__(self, db_url: str, download_table: DownloadTableBase):
        self.download_table = download_table
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        download_table.metadata.create_all(self.engine)

    def upsert(self, item_data: dict):
        with self.Session() as session:
            try:
                obj = session.query(self.download_table).filter_by(id=item_data.get("id")).first()
                if obj:
                    for key, value in item_data.items():
                        setattr(obj, key, value)
                else:
                    obj = self.download_table(**item_data)
                    session.add(obj)
                session.commit()
                return obj.id
            except SQLAlchemyError as e:
                logger.error(f"Error upserting download item: {e}")
                session.rollback()
                return None

    def all(self):
        with self.Session() as session:
            try:
                return session.query(self.download_table).all()
            except SQLAlchemyError as e:
                logger.error(f"Error fetching all download items: {e}")
                return []

    def delete(self, download_id: str):
        with self.Session() as session:
            try:
                session.query(self.download_table) \
                       .filter_by(id=download_id) \
                       .delete()
                session.commit()
            except SQLAlchemyError as e:
                logger.error(f"Error deleting download item with id {download_id}: {e}")
                session.rollback()
