from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os


DATA_DIR = "data"
DATABASE_FILE = os.path.join(DATA_DIR, "monitor.db")
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

os.makedirs(DATA_DIR, exist_ok=True)

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """
    Initialize the database by creating all tables.
    
    This function creates the database tables if they don't exist.
    Safe to call multiple times as it only creates missing tables.
    """
    Base.metadata.create_all(bind=engine)