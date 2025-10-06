
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from .models import Base, DownloadTableBase
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

class DownloadDB:
    def __init__(self, db_url: str, download_table: DownloadTableBase):
        logger.debug(f"Initializing DownloadDB with db_url: {db_url}")
        self.download_table = download_table
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        download_table.metadata.create_all(self.engine)
        logger.info("DownloadDB initialized successfully with %s table.", download_table.__tablename__)

    def upsert(self, item_data: dict):
        logger.debug(f"Upserting item data: {item_data}")
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
        logger.debug("Fetching all download items")
        with self.Session() as session:
            try:
                return session.query(self.download_table).all()
            except SQLAlchemyError as e:
                logger.error(f"Error fetching all download items: {e}")
                return []

    def delete(self, download_id: str):
        logger.debug(f"Deleting download item with id: {download_id}")
        with self.Session() as session:
            try:
                session.query(self.download_table) \
                       .filter_by(id=download_id) \
                       .delete()
                session.commit()
                logger.info(f"Download item with id {download_id} deleted successfully.")
            except SQLAlchemyError as e:
                logger.error(f"Error deleting download item with id {download_id}: {e}")
                session.rollback()
