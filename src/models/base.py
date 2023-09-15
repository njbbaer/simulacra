import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

Base = declarative_base()

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./development.db')
engine = create_engine(DATABASE_URL)
Session = scoped_session(sessionmaker(bind=engine))


def initialize_db():
    Base.metadata.create_all(bind=engine)


def _set_sqlite_pragma(dbapi_connection, _):
    """Set PRAGMA for SQLite to enforce ForeignKey constraint."""
    if DATABASE_URL.startswith("sqlite:"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


event.listens_for(engine, "connect")(_set_sqlite_pragma)
