"""
Priority-Based Business Rule Framework for Phase 1.2
Implements sophisticated business rule validation with priority-based execution
and integration with the unified error code system.
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime
from uuid import UUID


class BusinessRulePriority(Enum):
    """Business rule execution priorities - lower number = higher priority."""
    COMBINED_UPLOAD_ENFORCEMENT = 1      # Priority 1 - Highest
    UUID_ORPHANING_DETECTION = 2         # Priority 2
    CROSS_FILE_RELATIONSHIP_CONSISTENCY = 3  # Priority 3
    IMPRESSION_DECREASE_DETECTION = 4    # Priority 4
    DEAL_NAME_EXACT_MATCHING = 5        # Priority 5
    DATE_CHANGE_INCONSISTENCY = 6       # Priority 6
    HIERARCHICAL_NAME_STRUCTURE = 7     # Priority 7
    MUTUAL_EXCLUSION_VIOLATIONS = 8     # Priority 8
    NEW_ENTRY_BUSINESS_RULES = 9        # Priority 9 - Lowest

    def __lt__(self, other):
        """Enable priority comparison - lower values are higher priority."""
        if isinstance(other, BusinessRulePriority):
            return self.value < other.value
        return NotImplemented


@dataclass
class BusinessRuleViolation:
    """Represents a business rule violation with comprehensive context."""
    rule_priority: BusinessRulePriority
    error_code: str
    message: str
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    affected_records: List[str]
    context: Optional[Dict[str, Any]] = None
    suggested_action: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BusinessRuleResult:
    """Result of business rule execution."""
    success: bool
    violations: List[BusinessRuleViolation]
    processed_records: int
    flagged_records: int
    execution_time_ms: float = 0.0
    rule_priority: Optional[BusinessRulePriority] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RuleExecutionContext:
    """Context for business rule execution."""
    phase: str  # '1.1', '1.2'
    upload_type: str  # 'single', 'combined'
    campaign_data: List[Dict[str, Any]]
    reporting_data: List[Dict[str, Any]]
    processing_batch_id: str
    existing_production_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
    user_id: Optional[str] = None
    request_timestamp: Optional[datetime] = None
    validation_mode: Optional[str] = None  # 'strict', 'permissive'
    metadata: Optional[Dict[str, Any]] = None


class BusinessRuleEngine:
    """Priority-based business rule execution engine."""
    
    def __init__(self):
        """Initialize the business rule engine."""
        self._rules: List[Dict[str, Any]] = []
        self._registered_rules: Dict[BusinessRulePriority, List[Dict[str, Any]]] = {}
    
    def register_rule(
        self, 
        priority: BusinessRulePriority, 
        rule_function: Callable[[RuleExecutionContext], BusinessRuleResult],
        description: str,
        enabled: bool = True
    ) -> None:
        """
        Register a business rule with the engine.
        
        Args:
            priority: Rule execution priority
            rule_function: Function that implements the rule logic
            description: Human-readable rule description
            enabled: Whether the rule is enabled for execution
        """
        rule_entry = {
            'priority': priority,
            'function': rule_function,
            'description': description,
            'enabled': enabled,
            'registered_at': datetime.now()
        }
        
        self._rules.append(rule_entry)
        
        if priority not in self._registered_rules:
            self._registered_rules[priority] = []
        self._registered_rules[priority].append(rule_entry)
        
        # Keep rules sorted by priority
        self._rules.sort(key=lambda r: r['priority'].value)
    
    def get_rules_by_priority(self, priority: Optional[BusinessRulePriority] = None) -> List[Dict[str, Any]]:
        """
        Get rules by priority level.
        
        Args:
            priority: Specific priority to filter by, or None for all rules
            
        Returns:
            List of rule entries sorted by priority
        """
        if priority is not None:
            return self._registered_rules.get(priority, [])
        
        return sorted(self._rules, key=lambda r: r['priority'].value)
    
    def execute_rules(self, context: RuleExecutionContext) -> List[BusinessRuleResult]:
        """
        Execute all registered rules in priority order.
        
        Args:
            context: Rule execution context
            
        Returns:
            List of business rule results
        """
        results = []
        
        for rule_entry in self.get_rules_by_priority():
            if not rule_entry['enabled']:
                continue
            
            start_time = time.time()
            try:
                result = rule_entry['function'](context)
                result.execution_time_ms = (time.time() - start_time) * 1000
                result.rule_priority = rule_entry['priority']
                results.append(result)
            except Exception as e:
                # Create error result for failed rule execution
                error_result = BusinessRuleResult(
                    success=False,
                    violations=[
                        BusinessRuleViolation(
                            rule_priority=rule_entry['priority'],
                            error_code='RULE_EXECUTION_ERROR',
                            message=f"Rule execution failed: {str(e)}",
                            severity='CRITICAL',
                            affected_records=[],
                            context={'error': str(e), 'rule': rule_entry['description']}
                        )
                    ],
                    processed_records=0,
                    flagged_records=0,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    rule_priority=rule_entry['priority']
                )
                results.append(error_result)
        
        return results


# Global business rule engine instance
_global_engine = BusinessRuleEngine()


def validate_combined_upload(context: RuleExecutionContext) -> BusinessRuleResult:
    """
    Validate that combined uploads have both campaign and reporting data.
    Priority: COMBINED_UPLOAD_ENFORCEMENT (1)
    """
    start_time = time.time()
    violations = []
    
    if context.upload_type == 'combined':
        if not context.campaign_data:
            violations.append(BusinessRuleViolation(
                rule_priority=BusinessRulePriority.COMBINED_UPLOAD_ENFORCEMENT,
                error_code='BIZ_105',
                message='Combined upload incomplete',
                severity='CRITICAL',
                affected_records=[],
                context={'missing': 'campaign_data'},
                suggested_action='Upload both campaign and reporting files together'
            ))
        
        if not context.reporting_data:
            violations.append(BusinessRuleViolation(
                rule_priority=BusinessRulePriority.COMBINED_UPLOAD_ENFORCEMENT,
                error_code='BIZ_105',
                message='Combined upload incomplete',
                severity='CRITICAL',
                affected_records=[],
                context={'missing': 'reporting_data'},
                suggested_action='Upload both campaign and reporting files together'
            ))
    
    return BusinessRuleResult(
        success=len(violations) == 0,
        violations=violations,
        processed_records=len(context.campaign_data) + len(context.reporting_data),
        flagged_records=len(violations),
        execution_time_ms=(time.time() - start_time) * 1000
    )


def detect_impression_decrease(context: RuleExecutionContext) -> BusinessRuleResult:
    """
    Detect impression goal decreases that require review.
    Priority: IMPRESSION_DECREASE_DETECTION (4)
    """
    start_time = time.time()
    violations = []
    
    if not context.existing_production_data or 'campaigns' not in context.existing_production_data:
        return BusinessRuleResult(
            success=True,
            violations=[],
            processed_records=len(context.campaign_data),
            flagged_records=0,
            execution_time_ms=(time.time() - start_time) * 1000
        )
    
    existing_campaigns = {
        str(camp.get('deal_campaign_id')): camp 
        for camp in context.existing_production_data['campaigns']
    }
    
    for campaign in context.campaign_data:
        campaign_id = str(campaign.get('deal_campaign_id'))
        if campaign_id in existing_campaigns:
            existing_campaign = existing_campaigns[campaign_id]
            
            current_impressions = campaign.get('impression_goal', 0)
            existing_impressions = existing_campaign.get('impression_goal', 0)
            
            if current_impressions < existing_impressions:
                violations.append(BusinessRuleViolation(
                    rule_priority=BusinessRulePriority.IMPRESSION_DECREASE_DETECTION,
                    error_code='BIZ_102',
                    message='Impression decrease detected',
                    severity='HIGH',
                    affected_records=[campaign_id],
                    context={
                        'original_impressions': existing_impressions,
                        'new_impressions': current_impressions,
                        'decrease_amount': existing_impressions - current_impressions
                    },
                    suggested_action='Verify impression decrease is intentional or correct the value'
                ))
    
    return BusinessRuleResult(
        success=len(violations) == 0,
        violations=violations,
        processed_records=len(context.campaign_data),
        flagged_records=len(violations),
        execution_time_ms=(time.time() - start_time) * 1000
    )


def check_deal_name_modification(context: RuleExecutionContext) -> BusinessRuleResult:
    """
    Check for deal name modifications in Phase 1.2 strict mode.
    Priority: DEAL_NAME_EXACT_MATCHING (5)
    """
    start_time = time.time()
    violations = []
    
    if context.phase != '1.2' or not context.existing_production_data or 'campaigns' not in context.existing_production_data:
        return BusinessRuleResult(
            success=True,
            violations=[],
            processed_records=len(context.campaign_data),
            flagged_records=0,
            execution_time_ms=(time.time() - start_time) * 1000
        )
    
    existing_campaigns = {
        str(camp.get('deal_campaign_id')): camp 
        for camp in context.existing_production_data['campaigns']
    }
    
    for campaign in context.campaign_data:
        campaign_id = str(campaign.get('deal_campaign_id'))
        if campaign_id in existing_campaigns:
            existing_campaign = existing_campaigns[campaign_id]
            
            current_name = campaign.get('deal_campaign_name', '').strip()
            existing_name = existing_campaign.get('deal_campaign_name', '').strip()
            
            if current_name != existing_name:
                violations.append(BusinessRuleViolation(
                    rule_priority=BusinessRulePriority.DEAL_NAME_EXACT_MATCHING,
                    error_code='BIZ_101',
                    message='Deal name modification not allowed',
                    severity='CRITICAL',
                    affected_records=[campaign_id],
                    context={
                        'original_name': existing_name,
                        'new_name': current_name
                    },
                    suggested_action='Revert deal name to original value or request approval for modification'
                ))
    
    return BusinessRuleResult(
        success=len(violations) == 0,
        violations=violations,
        processed_records=len(context.campaign_data),
        flagged_records=len(violations),
        execution_time_ms=(time.time() - start_time) * 1000
    )


def validate_cross_file_relationships(context: RuleExecutionContext) -> BusinessRuleResult:
    """
    Validate cross-file relationships between campaign and reporting data.
    Priority: CROSS_FILE_RELATIONSHIP_CONSISTENCY (3)
    """
    start_time = time.time()
    violations = []
    
    if context.upload_type != 'combined':
        return BusinessRuleResult(
            success=True,
            violations=[],
            processed_records=len(context.reporting_data),
            flagged_records=0,
            execution_time_ms=(time.time() - start_time) * 1000
        )
    
    # Create set of valid campaign IDs
    campaign_ids = {
        str(camp.get('deal_campaign_id')) 
        for camp in context.campaign_data 
        if camp.get('deal_campaign_id')
    }
    
    # Check reporting data references
    for report in context.reporting_data:
        deal_id = str(report.get('deal_id'))
        if deal_id and deal_id not in campaign_ids:
            violations.append(BusinessRuleViolation(
                rule_priority=BusinessRulePriority.CROSS_FILE_RELATIONSHIP_CONSISTENCY,
                error_code='BIZ_104',
                message='Cross-file relationship failure',
                severity='CRITICAL',
                affected_records=[deal_id],
                context={
                    'orphaned_deal_id': deal_id,
                    'available_campaign_ids': list(campaign_ids)
                },
                suggested_action='Ensure all campaign IDs in reporting data have corresponding campaign entries'
            ))
    
    return BusinessRuleResult(
        success=len(violations) == 0,
        violations=violations,
        processed_records=len(context.reporting_data),
        flagged_records=len(violations),
        execution_time_ms=(time.time() - start_time) * 1000
    )


def apply_business_rules(context: RuleExecutionContext) -> BusinessRuleResult:
    """
    Apply all business rules to the execution context.
    
    Args:
        context: Rule execution context
        
    Returns:
        Consolidated business rule result
    """
    # Register default rules if not already registered
    if not _global_engine._rules:
        _register_default_rules()
    
    # Execute all rules
    individual_results = _global_engine.execute_rules(context)
    
    # Consolidate results
    all_violations = []
    total_processed = 0
    total_flagged = 0
    total_execution_time = 0.0
    overall_success = True
    
    for result in individual_results:
        all_violations.extend(result.violations)
        total_processed += result.processed_records
        total_flagged += result.flagged_records
        total_execution_time += result.execution_time_ms
        
        if not result.success:
            overall_success = False
    
    return BusinessRuleResult(
        success=overall_success,
        violations=all_violations,
        processed_records=total_processed,
        flagged_records=total_flagged,
        execution_time_ms=total_execution_time
    )


def get_rule_by_priority(priority: Optional[BusinessRulePriority] = None) -> List[Dict[str, Any]]:
    """
    Get rules by priority level.
    
    Args:
        priority: Specific priority to filter by, or None for all rules
        
    Returns:
        List of rule entries sorted by priority
    """
    # Register default rules if not already registered
    if not _global_engine._rules:
        _register_default_rules()
    
    return _global_engine.get_rules_by_priority(priority)


def _register_default_rules():
    """Register default business rules with the global engine."""
    _global_engine.register_rule(
        priority=BusinessRulePriority.COMBINED_UPLOAD_ENFORCEMENT,
        rule_function=validate_combined_upload,
        description='Validate combined upload completeness'
    )
    
    _global_engine.register_rule(
        priority=BusinessRulePriority.CROSS_FILE_RELATIONSHIP_CONSISTENCY,
        rule_function=validate_cross_file_relationships,
        description='Validate cross-file relationship consistency'
    )
    
    _global_engine.register_rule(
        priority=BusinessRulePriority.IMPRESSION_DECREASE_DETECTION,
        rule_function=detect_impression_decrease,
        description='Detect impression goal decreases'
    )
    
    _global_engine.register_rule(
        priority=BusinessRulePriority.DEAL_NAME_EXACT_MATCHING,
        rule_function=check_deal_name_modification,
        description='Check for deal name modifications'
    )


def reset_global_engine():
    """Reset the global engine (for testing purposes)."""
    global _global_engine
    _global_engine = BusinessRuleEngine()


def get_engine_stats() -> Dict[str, Any]:
    """Get statistics about the global rule engine."""
    return {
        'total_rules': len(_global_engine._rules),
        'enabled_rules': len([r for r in _global_engine._rules if r['enabled']]),
        'priorities_in_use': list(set(r['priority'] for r in _global_engine._rules)),
        'last_registered': max([r['registered_at'] for r in _global_engine._rules]) if _global_engine._rules else None
    }