from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    ensure_resume_columns()


def ensure_resume_columns():
    inspector = inspect(engine)
    if "resumes" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("resumes")}
    if "file_url" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE resumes ADD COLUMN file_url VARCHAR(1000) NULL"))
