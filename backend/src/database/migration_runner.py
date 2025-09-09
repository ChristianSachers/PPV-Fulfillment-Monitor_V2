"""
Database migration runner utility.

Provides centralized migration management with:
- Schema versioning and tracking
- Forward and rollback execution control
- Migration history logging
- Integration with existing staging_connection.py
- Production-ready error handling and validation

Usage:
    from src.database.migration_runner import MigrationRunner
    
    runner = MigrationRunner()
    result = runner.run_forward_migration('001_create_staging_tables')
    if result.success:
        print(f"Migration completed in {result.execution_time_seconds}s")
"""

import os
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import Engine, text, create_engine
from sqlalchemy.exc import OperationalError, IntegrityError

from src.database.staging_connection import (
    create_staging_engine, 
    get_staging_database_url,
    test_staging_connection
)


class MigrationDirection(str, Enum):
    """Migration direction enumeration."""
    FORWARD = "forward"
    ROLLBACK = "rollback"


class MigrationStatus(str, Enum):
    """Migration execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class MigrationResult:
    """Migration execution result with metadata."""
    success: bool
    migration_id: str
    migration_name: str
    direction: MigrationDirection
    schema_version_from: str
    schema_version_to: str
    execution_time_seconds: float
    executed_at: str
    error_message: Optional[str] = None
    tables_affected: List[str] = None
    indexes_affected: int = 0
    enums_affected: List[str] = None
    
    def __post_init__(self):
        """Initialize list fields if None."""
        if self.tables_affected is None:
            self.tables_affected = []
        if self.enums_affected is None:
            self.enums_affected = []


class MigrationError(Exception):
    """Enhanced exception for migration errors with context support."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
    
    def __str__(self):
        return self.message


class MigrationRunner:
    """
    Database migration runner with schema versioning and history tracking.
    
    Features:
    - Forward and rollback migration execution
    - Schema version management
    - Migration history tracking
    - Integration with existing database connection
    - Production-ready error handling
    """
    
    def __init__(self, engine: Optional[Engine] = None, migrations_path: Optional[str] = None):
        """
        Initialize migration runner.
        
        Args:
            engine: SQLAlchemy engine (uses staging connection if None)
            migrations_path: Path to migration scripts directory
        """
        self.engine = engine if engine else create_staging_engine()
        
        # Set migrations path relative to project root
        if migrations_path is None:
            backend_dir = Path(__file__).parent.parent.parent  # Go up from src/database/
            project_root = backend_dir.parent
            self.migrations_path = project_root / "database" / "migrations"
        else:
            self.migrations_path = Path(migrations_path)
        
        # Initialize migration tracking table
        self._init_migration_tracking()
    
    def _init_migration_tracking(self) -> None:
        """Initialize migration tracking infrastructure."""
        try:
            with self.engine.connect() as connection:
                # Create migration_history table if it doesn't exist
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS migration_history (
                        id SERIAL PRIMARY KEY,
                        migration_id VARCHAR(50) NOT NULL,
                        migration_name VARCHAR(200) NOT NULL,
                        direction VARCHAR(20) NOT NULL,
                        schema_version_from VARCHAR(20) NOT NULL,
                        schema_version_to VARCHAR(20) NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        execution_time_seconds DECIMAL(10, 6) NOT NULL,
                        executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        error_message TEXT NULL,
                        metadata JSONB NULL
                    )
                """))
                
                # Create schema_version table if it doesn't exist
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        current_version VARCHAR(20) NOT NULL DEFAULT '0',
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT single_version_row CHECK (id = 1)
                    )
                """))
                
                # Insert initial version if table is empty
                connection.execute(text("""
                    INSERT INTO schema_version (id, current_version) 
                    SELECT 1, '0' 
                    WHERE NOT EXISTS (SELECT 1 FROM schema_version)
                """))
                
                connection.commit()
                
        except Exception as e:
            raise MigrationError(
                f"Failed to initialize migration tracking: {str(e)}",
                context={'engine_url': str(self.engine.url)}
            )
    
    def get_current_version(self) -> str:
        """Get current schema version."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT current_version FROM schema_version WHERE id = 1"))
                row = result.fetchone()
                return row[0] if row else "0"
        except Exception as e:
            raise MigrationError(
                f"Failed to get current schema version: {str(e)}",
                context={'table': 'schema_version'}
            )
    
    def _update_schema_version(self, version: str) -> None:
        """Update schema version."""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("""
                    UPDATE schema_version 
                    SET current_version = :version, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = 1
                """), {'version': version})
                connection.commit()
        except Exception as e:
            raise MigrationError(
                f"Failed to update schema version to {version}: {str(e)}",
                context={'target_version': version}
            )
    
    def get_migration_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get migration history.
        
        Args:
            limit: Maximum number of history records to return
            
        Returns:
            List of migration history records
        """
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("""
                    SELECT migration_id, migration_name, direction, schema_version_from, 
                           schema_version_to, status, execution_time_seconds, executed_at,
                           error_message, metadata
                    FROM migration_history 
                    ORDER BY executed_at DESC 
                    LIMIT :limit
                """), {'limit': limit})
                
                return [
                    {
                        'migration': row[0],
                        'name': row[1],
                        'direction': row[2],
                        'version_from': row[3],
                        'version_to': row[4],
                        'status': row[5],
                        'execution_time': float(row[6]),
                        'executed_at': row[7].isoformat() if row[7] else None,
                        'error_message': row[8],
                        'metadata': row[9]
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            raise MigrationError(
                f"Failed to get migration history: {str(e)}",
                context={'limit': limit}
            )
    
    def _log_migration(self, result: MigrationResult) -> None:
        """Log migration execution to history."""
        try:
            with self.engine.connect() as connection:
                metadata = {
                    'tables_affected': result.tables_affected,
                    'indexes_affected': result.indexes_affected,
                    'enums_affected': result.enums_affected
                }
                
                connection.execute(text("""
                    INSERT INTO migration_history 
                    (migration_id, migration_name, direction, schema_version_from, 
                     schema_version_to, status, execution_time_seconds, executed_at,
                     error_message, metadata)
                    VALUES 
                    (:migration_id, :migration_name, :direction, :version_from,
                     :version_to, :status, :execution_time, :executed_at,
                     :error_message, :metadata)
                """), {
                    'migration_id': result.migration_id,
                    'migration_name': result.migration_name,
                    'direction': result.direction.value,
                    'version_from': result.schema_version_from,
                    'version_to': result.schema_version_to,
                    'status': MigrationStatus.SUCCESS.value if result.success else MigrationStatus.FAILED.value,
                    'execution_time': result.execution_time_seconds,
                    'executed_at': result.executed_at,
                    'error_message': result.error_message,
                    'metadata': str(metadata)  # Convert to JSON string
                })
                connection.commit()
        except Exception as e:
            # Don't fail migration on logging error, but warn
            print(f"Warning: Failed to log migration history: {str(e)}")
    
    def _load_migration_module(self, migration_file: str):
        """Dynamically load migration module."""
        migration_path = self.migrations_path / migration_file
        
        if not migration_path.exists():
            raise MigrationError(
                f"Migration file not found: {migration_file}",
                context={'path': str(migration_path)}
            )
        
        try:
            spec = importlib.util.spec_from_file_location(
                f"migration_{migration_file[:-3]}", 
                migration_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            raise MigrationError(
                f"Failed to load migration module {migration_file}: {str(e)}",
                context={'path': str(migration_path)}
            )
    
    def run_forward_migration(self, migration_name: str) -> MigrationResult:
        """
        Execute forward migration.
        
        Args:
            migration_name: Name of migration file without .py extension
            
        Returns:
            MigrationResult with execution details
        """
        migration_file = f"{migration_name}.py"
        
        # Validate database connection
        if not test_staging_connection(str(self.engine.url)):
            raise MigrationError(
                "Database connection failed",
                context={'database_url': str(self.engine.url)}
            )
        
        try:
            # Load migration module
            migration_module = self._load_migration_module(migration_file)
            
            # Check if migration function exists
            if not hasattr(migration_module, 'run_forward_migration'):
                raise MigrationError(
                    f"Migration {migration_file} missing run_forward_migration function",
                    context={'migration_file': migration_file}
                )
            
            # Get current version for validation
            current_version = self.get_current_version()
            
            # Execute migration
            execution_start = datetime.utcnow()
            migration_result = migration_module.run_forward_migration(self.engine)
            execution_end = datetime.utcnow()
            
            # Convert to MigrationResult if it's a dict
            if isinstance(migration_result, dict):
                result = MigrationResult(
                    success=migration_result.get('success', False),
                    migration_id=migration_result.get('migration_id', migration_name),
                    migration_name=migration_result.get('migration_name', migration_name),
                    direction=MigrationDirection.FORWARD,
                    schema_version_from=migration_result.get('schema_version_from', current_version),
                    schema_version_to=migration_result.get('schema_version_to', ''),
                    execution_time_seconds=migration_result.get('execution_time_seconds', 
                                                                (execution_end - execution_start).total_seconds()),
                    executed_at=migration_result.get('executed_at', execution_start.isoformat()),
                    error_message=migration_result.get('error_message'),
                    tables_affected=migration_result.get('tables_created', []),
                    indexes_affected=migration_result.get('indexes_created', 0),
                    enums_affected=migration_result.get('enums_created', [])
                )
            else:
                result = migration_result
            
            # Update schema version if migration succeeded
            if result.success and result.schema_version_to:
                self._update_schema_version(result.schema_version_to)
            
            # Log migration
            self._log_migration(result)
            
            return result
            
        except Exception as e:
            error_result = MigrationResult(
                success=False,
                migration_id=migration_name,
                migration_name=migration_name,
                direction=MigrationDirection.FORWARD,
                schema_version_from=self.get_current_version(),
                schema_version_to='',
                execution_time_seconds=0.0,
                executed_at=datetime.utcnow().isoformat(),
                error_message=str(e)
            )
            
            self._log_migration(error_result)
            return error_result
    
    def run_rollback_migration(self, migration_name: str) -> MigrationResult:
        """
        Execute rollback migration.
        
        Args:
            migration_name: Name of rollback migration file without .py extension
            
        Returns:
            MigrationResult with execution details
        """
        migration_file = f"{migration_name}.py"
        
        # Validate database connection
        if not test_staging_connection(str(self.engine.url)):
            raise MigrationError(
                "Database connection failed",
                context={'database_url': str(self.engine.url)}
            )
        
        try:
            # Load migration module
            migration_module = self._load_migration_module(migration_file)
            
            # Check if rollback function exists
            if not hasattr(migration_module, 'run_rollback_migration'):
                raise MigrationError(
                    f"Migration {migration_file} missing run_rollback_migration function",
                    context={'migration_file': migration_file}
                )
            
            # Get current version for validation
            current_version = self.get_current_version()
            
            # Execute rollback
            execution_start = datetime.utcnow()
            migration_result = migration_module.run_rollback_migration(self.engine)
            execution_end = datetime.utcnow()
            
            # Convert to MigrationResult if it's a dict
            if isinstance(migration_result, dict):
                result = MigrationResult(
                    success=migration_result.get('success', False),
                    migration_id=migration_result.get('migration_id', migration_name),
                    migration_name=migration_result.get('migration_name', migration_name),
                    direction=MigrationDirection.ROLLBACK,
                    schema_version_from=migration_result.get('schema_version_from', current_version),
                    schema_version_to=migration_result.get('schema_version_to', '0'),
                    execution_time_seconds=migration_result.get('execution_time_seconds',
                                                                (execution_end - execution_start).total_seconds()),
                    executed_at=migration_result.get('executed_at', execution_start.isoformat()),
                    error_message=migration_result.get('error_message'),
                    tables_affected=migration_result.get('tables_dropped', []),
                    indexes_affected=migration_result.get('indexes_dropped', 0),
                    enums_affected=migration_result.get('enums_dropped', [])
                )
            else:
                result = migration_result
            
            # Update schema version if rollback succeeded
            if result.success and result.schema_version_to:
                self._update_schema_version(result.schema_version_to)
            
            # Log migration
            self._log_migration(result)
            
            return result
            
        except Exception as e:
            error_result = MigrationResult(
                success=False,
                migration_id=migration_name,
                migration_name=migration_name,
                direction=MigrationDirection.ROLLBACK,
                schema_version_from=self.get_current_version(),
                schema_version_to='',
                execution_time_seconds=0.0,
                executed_at=datetime.utcnow().isoformat(),
                error_message=str(e)
            )
            
            self._log_migration(error_result)
            return error_result
    
    def list_available_migrations(self) -> List[str]:
        """List available migration files."""
        if not self.migrations_path.exists():
            return []
        
        migration_files = []
        for file_path in self.migrations_path.glob("*.py"):
            if not file_path.name.startswith("__"):
                migration_files.append(file_path.stem)
        
        return sorted(migration_files)
    
    def validate_migration_integrity(self) -> Dict[str, Any]:
        """
        Validate migration system integrity.
        
        Returns:
            Dict with validation results
        """
        validation_results = {
            'database_connection': False,
            'tracking_tables_exist': False,
            'current_version_valid': False,
            'migration_files_found': 0,
            'errors': []
        }
        
        try:
            # Test database connection
            validation_results['database_connection'] = test_staging_connection(str(self.engine.url))
            
            # Check tracking tables exist
            with self.engine.connect() as connection:
                result = connection.execute(text("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_name IN ('migration_history', 'schema_version')
                """))
                validation_results['tracking_tables_exist'] = result.fetchone()[0] == 2
                
                # Check current version is valid
                current_version = self.get_current_version()
                validation_results['current_version_valid'] = current_version is not None
                validation_results['current_version'] = current_version
                
            # Count available migration files
            validation_results['migration_files_found'] = len(self.list_available_migrations())
            
        except Exception as e:
            validation_results['errors'].append(str(e))
        
        return validation_results


# Utility functions for CLI and external usage
def create_migration_runner(database_url: Optional[str] = None) -> MigrationRunner:
    """Create migration runner with optional custom database URL."""
    if database_url:
        engine = create_engine(database_url)
    else:
        engine = create_staging_engine()
    
    return MigrationRunner(engine=engine)


def run_staging_migration(migration_name: str, direction: str = "forward") -> MigrationResult:
    """
    Convenience function to run staging migration.
    
    Args:
        migration_name: Name of migration to run
        direction: 'forward' or 'rollback'
        
    Returns:
        MigrationResult with execution details
    """
    runner = create_migration_runner()
    
    if direction.lower() == "forward":
        return runner.run_forward_migration(migration_name)
    elif direction.lower() == "rollback":
        return runner.run_rollback_migration(migration_name)
    else:
        raise ValueError(f"Invalid direction: {direction}. Must be 'forward' or 'rollback'")


# CLI integration (if needed)
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python migration_runner.py <migration_name> <forward|rollback>")
        sys.exit(1)
    
    migration_name = sys.argv[1]
    direction = sys.argv[2]
    
    try:
        result = run_staging_migration(migration_name, direction)
        
        if result.success:
            print(f"Migration {migration_name} ({direction}) completed successfully")
            print(f"Execution time: {result.execution_time_seconds:.3f}s")
            print(f"Schema version: {result.schema_version_from} → {result.schema_version_to}")
        else:
            print(f"Migration {migration_name} ({direction}) failed: {result.error_message}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Migration runner error: {str(e)}")
        sys.exit(1)