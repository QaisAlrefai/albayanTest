
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

    def all(self) -> list[DownloadTableBase]:
        logger.debug("Fetching all download items")
        with self.Session() as session:
            try:
                return session.query(self.download_table).all()
            except SQLAlchemyError as e:
                logger.error(f"Error fetching all download items: {e}")
                return []

    def get(self, download_id: str) -> DownloadTableBase:
        logger.debug(f"Fetching download item with id: {download_id}")
        with self.Session() as session:
            try:
                return session.query(self.download_table).filter_by(id=download_id).first()
            except SQLAlchemyError as e:
                logger.error(f"Error fetching download item with id {download_id}: {e}")
                return None

    def update_status(self, download_id: str, new_status: int):
        logger.debug(f"Updating status for download_id {download_id} to {new_status}")
        with self.Session() as session:
            try:
                obj = session.query(self.download_table).filter_by(id=download_id).first()
                if obj:
                    obj.status = new_status
                    session.commit()
                    logger.info(f"Status for download_id {download_id} updated to {new_status}")
                else:
                    logger.warning(f"No download item found with id: {download_id}")
            except SQLAlchemyError as e:
                logger.error(f"Error updating status for download_id {download_id}: {e}")
                session.rollback()

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

    def delete_all(self):
        logger.debug("Deleting all download items")
        with self.Session() as session:
            try:
                num_deleted = session.query(self.download_table).delete()
                session.commit()
                logger.info(f"All download items deleted successfully. Total deleted: {num_deleted}")
            except SQLAlchemyError as e:
                logger.error(f"Error deleting all download items: {e}")
                session.rollback()
