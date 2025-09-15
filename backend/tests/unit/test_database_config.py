"""
Unit tests for PostgreSQL database configuration utility.
Following TDD RED phase - write failing tests first.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from src.config.database import (
    get_database_url,
    get_database_engine,
    get_session_local,
    get_db,
    DatabaseConfig
)


class TestDatabaseConfig:
    """Test database configuration utility."""
    
    def test_get_database_url_development(self):
        """Test database URL generation for development environment."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=True):
            url = get_database_url()
            expected = "postgresql://christiansachers@localhost:5432/ppv_fulfillment_dev"
            assert url == expected
    
    def test_get_database_url_test(self):
        """Test database URL generation for test environment."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'test'}, clear=True):
            url = get_database_url()
            expected = "postgresql://christiansachers@localhost:5432/ppv_fulfillment_test"
            assert url == expected
    
    def test_get_database_url_production(self):
        """Test database URL generation for production environment."""
        env_vars = {
            'ENVIRONMENT': 'production',
            'DB_HOST': 'prod-host',
            'DB_PORT': '5432',
            'DB_NAME': 'prod_db',
            'DB_USER': 'prod_user',
            'DB_PASSWORD': 'prod_pass'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            url = get_database_url()
            expected = "postgresql://prod_user:prod_pass@prod-host:5432/prod_db?sslmode=require"
            assert url == expected
    
    def test_get_database_url_default_environment(self):
        """Test database URL defaults to development when no environment set."""
        with patch.dict(os.environ, {}, clear=True):
            url = get_database_url()
            expected = "postgresql://christiansachers@localhost:5432/ppv_fulfillment_dev"
            assert url == expected
    
    def test_get_database_engine_returns_engine(self):
        """Test database engine creation returns SQLAlchemy Engine."""
        engine = get_database_engine()
        assert isinstance(engine, Engine)
        assert "postgresql" in str(engine.url)
    
    def test_get_session_local_returns_sessionmaker(self):
        """Test session local returns configured sessionmaker."""
        session_local = get_session_local()
        assert isinstance(session_local, sessionmaker)
    
    def test_get_db_dependency_yields_session(self):
        """Test database dependency function yields session and closes it."""
        # Reset global session_local to ensure clean test state
        with patch('src.config.database._session_local', None):
            with patch('src.config.database.get_session_local') as mock_session_local:
                mock_session = MagicMock()
                mock_session_local.return_value = MagicMock(return_value=mock_session)
                
                db_gen = get_db()
                session = next(db_gen)
                
                assert session == mock_session
                
                # Test cleanup
                try:
                    next(db_gen)
                except StopIteration:
                    pass
                
                mock_session.close.assert_called_once()
    
    def test_database_config_class_loads_config(self):
        """Test DatabaseConfig class loads configuration from JSON."""
        config = DatabaseConfig()
        assert hasattr(config, 'development')
        assert hasattr(config, 'test')
        assert hasattr(config, 'production')
        assert config.development['database'] == 'ppv_fulfillment_dev'
    
    def test_missing_production_env_vars_raises_error(self):
        """Test missing production environment variables raises appropriate error."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}, clear=True):
            with pytest.raises(ValueError, match="Missing required environment variable"):
                get_database_url()
    
    def test_database_connection_pool_configuration(self):
        """Test database engine has proper connection pool settings."""
        engine = get_database_engine()
        assert engine.pool.size() >= 5  # Minimum pool size
        assert engine.pool._max_overflow >= 10  # Connection overflow
    
    def test_database_ssl_configuration_production(self):
        """Test SSL configuration is enabled for production environment."""
        env_vars = {
            'ENVIRONMENT': 'production',
            'DB_HOST': 'prod-host',
            'DB_NAME': 'prod_db',
            'DB_USER': 'prod_user',
            'DB_PASSWORD': 'prod_pass'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            url = get_database_url()
            assert "sslmode=require" in url