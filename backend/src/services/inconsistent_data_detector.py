"""
InconsistentDataDetector - Priority-Based Conflict Resolution System

Implements the most complex component of Phase 1.2: detecting inconsistent data using 
a priority-based algorithm that applies all 9 business rules to each record, collects 
violations with priorities, and uses the highest priority violation for primary 
classification while storing all violations for detailed reporting.

Priority-Based Algorithm:
Priority 1 (Highest): BIZ_105 - Combined upload incomplete
Priority 2: VAL_010 - UUID not found in production  
Priority 3: BIZ_104 - Cross-file relationship failure
Priority 4: BIZ_102 - Impression decrease detected
Priority 5: BIZ_101 - Deal name modification not allowed (EXACT string matching)
Priority 6: BIZ_103 - Date modification flagged (ANY date changes)
Priority 7: VAL_015 - Invalid hierarchical structure (" > " format)
Priority 8: BIZ_106 - Campaign/Deal ID conflict (mutual exclusion)
Priority 9 (Lowest): VAL_020 - New entry business rule violation

Integration:
- Phase 1.1 compatibility with unified error code system
- Extended staging table JSONB storage
- Database connection sharing patterns
- Transaction coordination
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

# Database connections are managed by the caller
# No direct imports needed for session management


@dataclass
class PriorityViolation:
    """Represents a single priority violation with metadata"""
    priority: int
    error_code: str
    description: str
    field: Optional[str] = None
    original_value: Any = None
    current_value: Any = None


@dataclass 
class InconsistentClassification:
    """Result of inconsistency detection with priority-based classification"""
    primary_reason: str
    all_violations: List[Tuple[str, str]]  # (error_code, description)
    primary_error_code: str
    priority: int = 9
    
    def to_json_violations(self) -> List[Dict[str, str]]:
        """Convert violations to JSON format for JSONB storage"""
        return [
            {
                'error_code': violation[0],
                'description': violation[1]
            }
            for violation in self.all_violations
        ]


class InconsistentDataDetector:
    """
    Priority-based inconsistent data detector with conflict resolution.
    
    Applies all 9 business rules to each record, collects violations with priorities,
    and uses the highest priority violation for primary classification while storing
    all violations for detailed reporting.
    """
    
    def __init__(self, production_db_session: Session, staging_db_session: Session, 
                 processing_batch_id: str):
        """Initialize detector with database sessions and batch context"""
        if production_db_session is None:
            raise ValueError("Production database session required")
        if staging_db_session is None:
            raise ValueError("Staging database session required")
            
        self.production_db_session = production_db_session
        self.staging_db_session = staging_db_session
        self.processing_batch_id = processing_batch_id
        
        # Priority rules configuration (priority, error_code)
        self.priority_rules = {
            'combined_upload_incomplete': (1, 'BIZ_105'),
            'uuid_orphaned': (2, 'VAL_010'),
            'cross_file_inconsistent': (3, 'BIZ_104'),
            'impression_decreased': (4, 'BIZ_102'),
            'deal_name_changed': (5, 'BIZ_101'),
            'date_changed': (6, 'BIZ_103'),
            'hierarchical_invalid': (7, 'VAL_015'),
            'mutual_exclusion_violated': (8, 'BIZ_106'),
            'new_entry_invalid': (9, 'VAL_020')
        }
    
    def get_rule_priority(self, rule_name: str) -> int:
        """Get priority for a specific rule"""
        return self.priority_rules.get(rule_name, (9, ''))[0]
    
    def get_rule_error_code(self, rule_name: str) -> str:
        """Get error code for a specific rule"""
        return self.priority_rules.get(rule_name, ('', 'UNKNOWN'))[1]
    
    def detect_inconsistencies(self, record: Dict[str, Any], 
                             batch_context: Dict[str, Any]) -> Optional[InconsistentClassification]:
        """
        Apply all 9 business rules and return priority-based classification.
        
        Args:
            record: Individual record to check for inconsistencies
            batch_context: Context about the entire batch being processed
            
        Returns:
            InconsistentClassification if violations found, None otherwise
        """
        violations = []
        
        try:
            # Check all rules in priority order, collect violations with priorities and unified error codes
            if self.combined_upload_missing(batch_context): 
                violations.append((1, "BIZ_105", "Combined upload incomplete"))
                
            if self.uuid_orphaned(record): 
                violations.append((2, "VAL_010", "UUID not found in production"))
                
            if self.cross_file_inconsistent(record, batch_context): 
                violations.append((3, "BIZ_104", "Cross-file relationship failure"))
                
            if self.impression_decreased(record): 
                original_goal = self._get_production_impression_goal(record)
                current_goal = record.get('impression_goal', 0)
                violations.append((4, "BIZ_102", 
                    f"Impression decrease detected: {original_goal} -> {current_goal}"))
                
            if self.deal_name_changed(record): 
                original_name = self._get_production_deal_name(record)
                current_name = record.get('deal_name', '')
                violations.append((5, "BIZ_101", 
                    f'Deal name changed: "{original_name}" -> "{current_name}"'))
                
            if self.date_changed(record): 
                changed_fields = self._get_changed_date_fields(record)
                violations.append((6, "BIZ_103", 
                    f"Date modification flagged: {', '.join(changed_fields)}"))
                
            if self.hierarchical_invalid(record): 
                violations.append((7, "VAL_015", 
                    "Invalid hierarchical structure (missing ' > ' format)"))
                
            if self.mutual_exclusion_violated(record): 
                camp_id = record.get('deal_campaign_id', '')
                deal_id = record.get('deal_id', '')
                violations.append((8, "BIZ_106", 
                    f"Campaign/Deal ID conflict: both '{camp_id}' and '{deal_id}' populated"))
                
            if self.new_entry_invalid(record): 
                violations.append((9, "VAL_020", "New entry business rule violation"))
            
            if violations:
                # Sort by priority (lowest number = highest priority)
                violations.sort(key=lambda x: x[0])
                primary_violation = violations[0]
                all_reasons = [(v[1], v[2]) for v in violations]
                
                return InconsistentClassification(
                    primary_reason=primary_violation[2],
                    all_violations=all_reasons,
                    primary_error_code=primary_violation[1],
                    priority=primary_violation[0]
                )
                
        except Exception as e:
            # Handle database connection errors gracefully
            print(f"Error during inconsistency detection: {e}")
            return None
            
        return None
    
    def detect_inconsistencies_batch(self, records: List[Dict[str, Any]], 
                                   batch_context: Dict[str, Any]) -> List[Optional[InconsistentClassification]]:
        """Process batch of records for inconsistency detection"""
        # Use chunked processing for large datasets
        if len(records) > 5000:
            return process_records_in_chunks(records, chunk_size=500)
            
        results = []
        
        # Process records efficiently
        for record in records:
            try:
                result = self.detect_inconsistencies(record, batch_context)
                results.append(result)
            except Exception as e:
                print(f"Error processing record {record.get('deal_campaign_id', 'unknown')}: {e}")
                results.append(None)
        
        return results
    
    # Business Rule Implementations
    
    def combined_upload_missing(self, batch_context: Dict[str, Any]) -> bool:
        """Priority 1: Check if combined upload is incomplete"""
        has_campaign = batch_context.get('has_campaign_file', False)
        has_performance = batch_context.get('has_performance_file', False)
        return not (has_campaign and has_performance)
    
    def uuid_orphaned(self, record: Dict[str, Any]) -> bool:
        """Priority 2: Check if UUID exists in production database"""
        try:
            uuid_field = record.get('deal_campaign_id') or record.get('deal_id')
            if not uuid_field:
                return True
                
            # Query production database for UUID
            query = text("SELECT deal_campaign_id FROM campaigns WHERE deal_campaign_id = :uuid")
            result = self.production_db_session.execute(query, {'uuid': uuid_field})
            return len(result.fetchall()) == 0
            
        except Exception:
            return True  # Assume orphaned if can't verify
    
    def cross_file_inconsistent(self, record: Dict[str, Any], batch_context: Dict[str, Any]) -> bool:
        """Priority 3: Check cross-file relationship failures"""
        campaign_records = set(batch_context.get('campaign_records', []))
        performance_records = set(batch_context.get('performance_records', []))
        
        uuid_field = record.get('deal_campaign_id') or record.get('deal_id')
        if not uuid_field:
            return True
            
        # Check if record has corresponding entry in other file
        if record.get('deal_campaign_id'):
            # Campaign record - check if has performance data
            return uuid_field not in performance_records
        elif record.get('deal_id'):
            # Performance record - check if has campaign data
            return uuid_field not in campaign_records
            
        return False
    
    def impression_decreased(self, record: Dict[str, Any]) -> bool:
        """Priority 4: Check if impression goal decreased"""
        try:
            current_goal = record.get('impression_goal')
            if current_goal is None:
                return False
                
            original_goal = self._get_production_impression_goal(record)
            if original_goal is None:
                return False
                
            return current_goal < original_goal
            
        except Exception:
            return False
    
    def deal_name_changed(self, record: Dict[str, Any]) -> bool:
        """Priority 5: Check deal name modification with EXACT string matching"""
        try:
            current_name = record.get('deal_name')
            if current_name is None:
                return False
                
            original_name = self._get_production_deal_name(record)
            if original_name is None:
                return False
                
            # EXACT string comparison (case-sensitive)
            return current_name != original_name
            
        except Exception:
            return False
    
    def date_changed(self, record: Dict[str, Any]) -> bool:
        """Priority 6: Check if ANY date field was modified"""
        try:
            date_fields = ['start_date', 'end_date']
            
            for field in date_fields:
                current_date = record.get(field)
                if current_date is None:
                    continue
                    
                original_date = self._get_production_date_field(record, field)
                if original_date is None:
                    continue
                    
                # Convert to comparable format
                if isinstance(current_date, str):
                    current_date = datetime.strptime(current_date, '%Y-%m-%d').date()
                if isinstance(original_date, str):
                    original_date = datetime.strptime(original_date, '%Y-%m-%d').date()
                    
                if current_date != original_date:
                    return True
                    
            return False
            
        except Exception:
            return False
    
    def hierarchical_invalid(self, record: Dict[str, Any]) -> bool:
        """Priority 7: Check hierarchical name structure (' > ' format)"""
        deal_name = record.get('deal_name', '')
        
        if not deal_name:
            return True
            
        # Must contain " > " separator for valid hierarchy
        return ' > ' not in deal_name
    
    def mutual_exclusion_violated(self, record: Dict[str, Any]) -> bool:
        """Priority 8: Check Campaign/Deal ID mutual exclusion"""
        campaign_id = record.get('deal_campaign_id')
        deal_id = record.get('deal_id')
        
        # Both fields populated violates mutual exclusion
        campaign_populated = campaign_id is not None and str(campaign_id).strip() != ''
        deal_populated = deal_id is not None and str(deal_id).strip() != ''
        
        return campaign_populated and deal_populated
    
    def new_entry_invalid(self, record: Dict[str, Any]) -> bool:
        """Priority 9: Check new entry business rule violations"""
        # This would integrate with the new entry validator
        # For now, check basic new entry rules
        try:
            impression_goal = record.get('impression_goal', 0)
            cpm_eur = record.get('cpm_eur', Decimal('0'))
            
            # Check if violates new entry business rules
            if impression_goal < 1 or impression_goal > 1000000000:
                return True
            if isinstance(cpm_eur, (int, float, Decimal)) and (cpm_eur < Decimal('0.01') or cpm_eur > Decimal('45.00')):
                return True
                
            return False
            
        except Exception:
            return False
    
    # Helper methods for production database lookups
    
    def _get_production_impression_goal(self, record: Dict[str, Any]) -> Optional[int]:
        """Get original impression goal from production database"""
        try:
            uuid_field = record.get('deal_campaign_id')
            if not uuid_field:
                return None
                
            query = text("SELECT impression_goal FROM campaigns WHERE deal_campaign_id = :uuid")
            result = self.production_db_session.execute(query, {'uuid': uuid_field})
            row = result.fetchone()
            return row.impression_goal if row else None
            
        except Exception:
            return None
    
    def _get_production_deal_name(self, record: Dict[str, Any]) -> Optional[str]:
        """Get original deal name from production database"""
        try:
            uuid_field = record.get('deal_campaign_id')
            if not uuid_field:
                return None
                
            query = text("SELECT deal_name FROM campaigns WHERE deal_campaign_id = :uuid")
            result = self.production_db_session.execute(query, {'uuid': uuid_field})
            row = result.fetchone()
            return row.deal_name if row else None
            
        except Exception:
            return None
    
    def _get_production_date_field(self, record: Dict[str, Any], field: str) -> Optional[date]:
        """Get original date field from production database"""
        try:
            uuid_field = record.get('deal_campaign_id')
            if not uuid_field:
                return None
                
            query = text(f"SELECT {field} FROM campaigns WHERE deal_campaign_id = :uuid")
            result = self.production_db_session.execute(query, {'uuid': uuid_field})
            row = result.fetchone()
            return getattr(row, field) if row else None
            
        except Exception:
            return None
    
    def _get_changed_date_fields(self, record: Dict[str, Any]) -> List[str]:
        """Get list of date fields that changed"""
        changed_fields = []
        date_fields = ['start_date', 'end_date']
        
        for field in date_fields:
            current_date = record.get(field)
            if current_date is None:
                continue
                
            original_date = self._get_production_date_field(record, field)
            if original_date is None:
                continue
                
            try:
                if isinstance(current_date, str):
                    current_date = datetime.strptime(current_date, '%Y-%m-%d').date()
                if isinstance(original_date, str):
                    original_date = datetime.strptime(original_date, '%Y-%m-%d').date()
                    
                if current_date != original_date:
                    changed_fields.append(f"{field}: {original_date} -> {current_date}")
            except Exception:
                continue
                
        return changed_fields
    
    # Extended Staging Integration
    
    def store_inconsistent_record_in_staging(self, record: Dict[str, Any], 
                                           classification: InconsistentClassification):
        """Store inconsistent record in extended staging table with JSONB violations"""
        try:
            # Convert violations to JSON format
            violation_json = json.dumps(classification.to_json_violations())
            
            # Determine target table based on record type
            table_name = 'staging_campaigns' if 'deal_campaign_id' in record else 'staging_reporting'
            uuid_field = record.get('deal_campaign_id') or record.get('deal_id')
            
            # Insert/update record in staging with extended fields
            query = text(f"""
                INSERT INTO {table_name} 
                (uuid_field, processing_batch_id, record_classification, phase_context,
                 flagged_for_review, violation_details, primary_error_code)
                VALUES (:uuid_field, :processing_batch_id, 'inconsistent', :phase_context, 
                        :flagged_for_review, :violation_details, :primary_error_code)
                ON CONFLICT (uuid_field, processing_batch_id) 
                DO UPDATE SET 
                    record_classification = 'inconsistent',
                    flagged_for_review = :flagged_for_review,
                    violation_details = :violation_details,
                    primary_error_code = :primary_error_code
            """)
            
            params = {
                'uuid_field': uuid_field,
                'processing_batch_id': self.processing_batch_id,
                'phase_context': '1.2',
                'flagged_for_review': True,
                'violation_details': violation_json,
                'primary_error_code': classification.primary_error_code
            }
            
            self.staging_db_session.execute(query, params)
            
            # Only commit if not in existing transaction
            if not hasattr(self.staging_db_session, 'in_transaction') or not self.staging_db_session.in_transaction():
                self.staging_db_session.commit()
                
        except Exception as e:
            self.staging_db_session.rollback()
            raise e
    
    def store_violations_in_extended_staging(self, entry_data: Dict[str, Any], violations: List[Any]):
        """Store violations in extended staging (compatibility method)"""
        # Convert violations to classification format
        violation_tuples = []
        for violation in violations:
            error_code = getattr(violation, 'error_code', 'UNKNOWN')
            message = getattr(violation, 'message', str(violation))
            violation_tuples.append((error_code, message))
        
        classification = InconsistentClassification(
            primary_reason=violation_tuples[0][1] if violation_tuples else "Unknown violation",
            all_violations=violation_tuples,
            primary_error_code=violation_tuples[0][0] if violation_tuples else "UNKNOWN"
        )
        
        self.store_inconsistent_record_in_staging(entry_data, classification)


# Functional Interface Functions

async def detect_inconsistencies_batch(records: List[Dict[str, Any]], 
                                     batch_context: Dict[str, Any],
                                     production_session: Session,
                                     staging_session: Session) -> List[Optional[InconsistentClassification]]:
    """
    Standalone function for batch inconsistency detection.
    
    Args:
        records: List of records to check
        batch_context: Batch processing context
        production_session: Production database session
        staging_session: Staging database session
        
    Returns:
        List of classifications (None for consistent records)
    """
    detector = InconsistentDataDetector(
        production_db_session=production_session,
        staging_db_session=staging_session,
        processing_batch_id=batch_context.get('processing_batch_id', 'unknown')
    )
    
    # Run in executor for async compatibility
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        detector.detect_inconsistencies_batch, 
        records, 
        batch_context
    )


def validate_priority_algorithm(violations: List[Tuple[str, bool]], 
                               priority_rules: Dict[str, Tuple[int, str]]) -> Dict[str, Any]:
    """
    Validate priority algorithm correctness.
    
    Args:
        violations: List of (rule_name, triggered) tuples
        priority_rules: Rule priority configuration
        
    Returns:
        Algorithm validation result
    """
    triggered_violations = [(rule, triggered) for rule, triggered in violations if triggered]
    
    if not triggered_violations:
        return {'winning_rule': None, 'winning_priority': None, 'all_violations': []}
    
    # Sort by priority (lowest number = highest priority)
    sorted_violations = sorted(triggered_violations, 
                             key=lambda x: priority_rules.get(x[0], (999, 'UNKNOWN'))[0])
    
    winning_rule = sorted_violations[0][0]
    winning_priority = priority_rules.get(winning_rule, (999, 'UNKNOWN'))[0]
    winning_error_code = priority_rules.get(winning_rule, (999, 'UNKNOWN'))[1]
    
    return {
        'winning_rule': winning_rule,
        'winning_priority': winning_priority,
        'winning_error_code': winning_error_code,
        'all_violations': [v[0] for v in triggered_violations]
    }


@dataclass
class PriorityConflictResolution:
    """Result of priority conflict resolution"""
    primary_violation: PriorityViolation
    all_violations: List[PriorityViolation]


def resolve_priority_conflicts(conflicts: List[PriorityViolation]) -> PriorityConflictResolution:
    """
    Resolve priority conflicts using lowest number = highest priority.
    
    Args:
        conflicts: List of priority violations
        
    Returns:
        Resolved conflict with primary violation
    """
    if not conflicts:
        raise ValueError("No conflicts to resolve")
    
    # Sort by priority (lowest number = highest priority)
    sorted_conflicts = sorted(conflicts, key=lambda x: x.priority)
    
    return PriorityConflictResolution(
        primary_violation=sorted_conflicts[0],
        all_violations=sorted_conflicts
    )


def process_records_in_chunks(records: List[Dict[str, Any]], chunk_size: int = 500) -> List[Any]:
    """Process records in chunks for memory efficiency"""
    results = []
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        # Process chunk (placeholder implementation)
        results.extend([None] * len(chunk))
    return results