# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings # Importing the initialized settings

# Engine setup
engine = create_engine(
    settings.DATABASE_URL, 
    echo=True, 
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# SQLAlchemy 2.0 Base
class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()