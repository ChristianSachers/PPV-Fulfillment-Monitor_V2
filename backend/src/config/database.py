"""
PostgreSQL database configuration utility.
Centralized database configuration replacing SQLite usage.
"""
import os
import json
from typing import Dict, Any
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool


class DatabaseConfig:
    """Database configuration management class."""
    
    def __init__(self):
        """Initialize database configuration from config.json."""
        # Go up from src/config/database.py to project root, then to database/config.json
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'database', 'config.json'
        )
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.development = self.config['development']
        self.test = self.config['test'] 
        self.production = self.config['production']


def get_environment() -> str:
    """Get current environment (development/test/production)."""
    return os.getenv('ENVIRONMENT', 'development').lower()


def get_database_url() -> str:
    """Generate PostgreSQL database URL based on environment."""
    config = DatabaseConfig()
    env = get_environment()
    
    if env == 'production':
        # Validate required production environment variables
        required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variable(s): {', '.join(missing_vars)}")
        
        host = os.getenv('DB_HOST')
        port = os.getenv('DB_PORT', '5432')
        database = os.getenv('DB_NAME')
        username = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')
        
        # Add SSL for production
        url = f"postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=require"
        
    elif env == 'test':
        db_config = config.test
        if db_config['password']:
            url = f"postgresql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        else:
            url = f"postgresql://{db_config['username']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        
    else:  # development (default)
        db_config = config.development
        if db_config['password']:
            url = f"postgresql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        else:
            url = f"postgresql://{db_config['username']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    
    return url


def get_database_engine() -> Engine:
    """Create and configure SQLAlchemy engine with connection pooling."""
    database_url = get_database_url()
    
    # Configure connection pool
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,   # Recycle connections every hour
        echo=get_environment() == 'development'  # Log SQL in development
    )
    
    return engine


def get_session_local() -> sessionmaker:
    """Create sessionmaker configured for the current environment."""
    engine = get_database_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Global instances
_engine = None
_session_local = None


def get_db() -> Session:
    """
    Database dependency for FastAPI.
    Yields a database session and ensures proper cleanup.
    """
    global _session_local
    
    if _session_local is None:
        _session_local = get_session_local()
    
    db = _session_local()
    try:
        yield db
    finally:
        db.close()


def initialize_database():
    """Initialize database engine and create tables if needed."""
    global _engine, _session_local
    
    _engine = get_database_engine()
    _session_local = get_session_local()
    
    return _engine, _session_local