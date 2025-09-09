"""Database connection utilities for staging operations."""
import os
from typing import Generator
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from src.models.staging import Base, CampaignsStaging, ReportingStaging


def get_staging_database_url() -> str:
    """Get the staging database URL from environment or default configuration."""
    # Check for environment variables first (production)
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'ppv_fulfillment_dev')
    db_user = os.getenv('DB_USER', '')
    db_password = os.getenv('DB_PASSWORD', '')
    
    # Build connection URL
    if db_user and db_password:
        url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        # For local development without authentication
        url = f"postgresql://{db_host}:{db_port}/{db_name}"
    
    return url


def create_staging_engine(database_url: str = None) -> Engine:
    """Create SQLAlchemy engine for staging database operations."""
    if database_url is None:
        database_url = get_staging_database_url()
    
    # Engine configuration for staging operations
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,   # Recycle connections after 1 hour
    )
    
    return engine


def get_staging_session(engine: Engine = None) -> Generator[Session, None, None]:
    """Get a staging database session with proper cleanup."""
    if engine is None:
        engine = create_staging_engine()
    
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_staging_tables(engine: Engine = None) -> None:
    """Initialize staging tables in the database."""
    if engine is None:
        engine = create_staging_engine()
    
    try:
        # Create all staging tables
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        with engine.connect() as connection:
            # Check if campaigns_staging exists
            result = connection.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_staging')")
            )
            campaigns_exists = result.fetchone()[0]
            
            # Check if reporting_staging exists
            result = connection.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'reporting_staging')")
            )
            reporting_exists = result.fetchone()[0]
            
            if not campaigns_exists or not reporting_exists:
                raise OperationalError(
                    "Failed to create staging tables",
                    params=None,
                    orig=None
                )
                
    except OperationalError as e:
        raise OperationalError(
            f"Failed to initialize staging tables: {str(e)}",
            params=None,
            orig=e
        )


def drop_staging_tables(engine: Engine = None) -> None:
    """Drop staging tables from the database (for testing/cleanup)."""
    if engine is None:
        engine = create_staging_engine()
    
    try:
        # Drop all staging tables
        Base.metadata.drop_all(bind=engine)
    except OperationalError as e:
        raise OperationalError(
            f"Failed to drop staging tables: {str(e)}",
            params=None,
            orig=e
        )


def test_staging_connection(database_url: str = None) -> bool:
    """Test the staging database connection."""
    try:
        engine = create_staging_engine(database_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            return result.fetchone()[0] == 1
    except Exception:
        return False
    finally:
        if 'engine' in locals():
            engine.dispose()