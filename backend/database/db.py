"""
Database connection and session management
"""

import os
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Database file location
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"

# Ensure data directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# SQLite connection string
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
# For SQLite, we use:
# - check_same_thread=False to allow use in async contexts
# - StaticPool for testing, NullPool for production
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # Set to True for SQL query logging
)

# Enable foreign key support for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database by creating all tables"""
    print(f"Initializing database at: {DB_PATH}")
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully")


def get_db() -> Session:
    """
    Get database session (for FastAPI dependency injection)
    
    Usage in FastAPI:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Get database session as context manager
    
    Usage:
        with get_db_session() as db:
            profile = db.query(Profile).filter_by(id='123').first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_backup(backup_path: Path = None):
    """
    Create a backup of the SQLite database
    
    Args:
        backup_path: Optional custom backup path
    """
    import shutil
    from datetime import datetime
    
    if not DB_PATH.exists():
        print("⚠️  Database file does not exist, nothing to backup")
        return
    
    if backup_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = PROJECT_ROOT / "data" / "backups" / f"srs4autism_{timestamp}.db"
    
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Database backup created: {backup_path}")
    return backup_path


def restore_backup(backup_path: Path):
    """
    Restore database from a backup
    
    Args:
        backup_path: Path to backup file
    """
    import shutil
    
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")
    
    # Create a backup of current database before restoring
    if DB_PATH.exists():
        create_backup(DB_PATH.parent / f"{DB_PATH.stem}_before_restore{DB_PATH.suffix}")
    
    shutil.copy2(backup_path, DB_PATH)
    print(f"✅ Database restored from: {backup_path}")


# For testing: create in-memory database
def get_test_db():
    """Get an in-memory SQLite database for testing"""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Enable foreign keys
    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(bind=test_engine)
    
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    return TestSessionLocal()


if __name__ == "__main__":
    # Initialize database if run directly
    init_db()


