"""
Comprehensive TDD Test Suite for InconsistentDataDetector - RED PHASE
Tests MUST fail initially since inconsistent_data_detector doesn't exist yet.

Priority-Based Conflict Resolution Algorithm:
Priority 1 (Highest): BIZ_105 - Combined upload incomplete
Priority 2: VAL_010 - UUID not found in production  
Priority 3: BIZ_104 - Cross-file relationship failure
Priority 4: BIZ_102 - Impression decrease detected
Priority 5: BIZ_101 - Deal name modification not allowed (EXACT string matching)
Priority 6: BIZ_103 - Date modification flagged (ANY date changes)
Priority 7: VAL_015 - Invalid hierarchical structure (" > " format)
Priority 8: BIZ_106 - Campaign/Deal ID conflict (mutual exclusion)
Priority 9 (Lowest): VAL_020 - New entry business rule violation

Business Rules Integration:
- All 9 rules applied to each record
- Highest priority violation determines primary classification
- All violations stored for detailed reporting
- JSONB storage in extended staging tables
- Phase 1.1 compatibility maintained
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, date
from typing import List, Dict, Any, Optional

# Import the inconsistent data detector that doesn't exist yet (TDD RED phase)
from src.services.inconsistent_data_detector import (
    InconsistentDataDetector,
    InconsistentClassification,
    PriorityViolation,
    detect_inconsistencies_batch,
    validate_priority_algorithm,
    resolve_priority_conflicts
)


class TestInconsistentDataDetectorInitialization:
    """Test InconsistentDataDetector class initialization and configuration"""
    
    @pytest.fixture
    def mock_production_session(self):
        """Mock production database session"""
        session = Mock()
        session.execute = Mock()
        session.close = Mock()
        return session
    
    @pytest.fixture
    def mock_staging_session(self):
        """Mock staging database session"""
        session = Mock()
        session.execute = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session
    
    @pytest.fixture
    def detector(self, mock_production_session, mock_staging_session):
        """Create InconsistentDataDetector instance"""
        return InconsistentDataDetector(
            production_db_session=mock_production_session,
            staging_db_session=mock_staging_session,
            processing_batch_id="batch-001"
        )
    
    def test_detector_initialization_with_sessions(self, detector):
        """Test detector initializes with correct database sessions"""
        assert detector.production_db_session is not None
        assert detector.staging_db_session is not None
        assert detector.processing_batch_id == "batch-001"
        
        # Verify priority configuration
        assert detector.priority_rules is not None
        assert len(detector.priority_rules) == 9
    
    def test_priority_rule_configuration(self, detector):
        """Test priority rules are correctly configured"""
        expected_priorities = {
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
        
        for rule_name, (priority, error_code) in expected_priorities.items():
            assert detector.get_rule_priority(rule_name) == priority
            assert detector.get_rule_error_code(rule_name) == error_code
    
    def test_detector_requires_database_sessions(self):
        """Test detector requires both production and staging sessions"""
        with pytest.raises(ValueError, match="Production database session required"):
            InconsistentDataDetector(production_db_session=None, staging_db_session=Mock())
        
        with pytest.raises(ValueError, match="Staging database session required"):
            InconsistentDataDetector(production_db_session=Mock(), staging_db_session=None)


class TestPriorityBasedDetectionAlgorithm:
    """Test priority-based detection algorithm for all 9 business rules"""
    
    @pytest.fixture
    def detector(self):
        return InconsistentDataDetector(Mock(), Mock(), "batch-001")
    
    @pytest.fixture
    def sample_record(self):
        """Sample record for testing"""
        return {
            'deal_campaign_id': 'camp-001',
            'deal_name': 'Original Campaign > Sub Campaign',
            'start_date': date(2024, 1, 1),
            'end_date': date(2024, 1, 31),
            'impression_goal': 50000,
            'budget_eur': Decimal('1000.00'),
            'cpm_eur': Decimal('5.50')
        }
    
    @pytest.fixture
    def batch_context(self):
        """Sample batch context for testing"""
        return {
            'has_campaign_file': True,
            'has_performance_file': True,
            'campaign_records': ['camp-001', 'camp-002'],
            'performance_records': ['perf-001', 'perf-002'],
            'processing_batch_id': 'batch-001'
        }
    
    def test_priority_1_combined_upload_incomplete_highest_priority(self, detector, sample_record):
        """Test Priority 1 (BIZ_105): Combined upload incomplete has highest priority"""
        batch_context = {'has_campaign_file': True, 'has_performance_file': False}
        
        # Mock other rules to also trigger violations
        detector.uuid_orphaned = Mock(return_value=True)
        detector.deal_name_changed = Mock(return_value=True)
        detector.combined_upload_missing = Mock(return_value=True)
        
        result = detector.detect_inconsistencies(sample_record, batch_context)
        
        # Should prioritize BIZ_105 despite other violations
        assert result is not None
        assert result.primary_error_code == 'BIZ_105'
        assert result.primary_reason == "Combined upload incomplete"
        assert result.priority == 1
        
        # Should still capture all violations
        assert len(result.all_violations) >= 3
        violation_codes = [v[0] for v in result.all_violations]
        assert 'BIZ_105' in violation_codes
        assert 'VAL_010' in violation_codes
        assert 'BIZ_101' in violation_codes
    
    def test_priority_2_uuid_orphaned_detection(self, detector, sample_record, batch_context):
        """Test Priority 2 (VAL_010): UUID not found in production"""
        # Mock production lookup to return no results
        detector.production_db_session.execute.return_value.fetchall.return_value = []
        detector.combined_upload_missing = Mock(return_value=False)
        
        result = detector.detect_inconsistencies(sample_record, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'VAL_010'
        assert "UUID not found in production" in result.primary_reason
        assert result.priority == 2
    
    def test_priority_3_cross_file_inconsistent_detection(self, detector, sample_record, batch_context):
        """Test Priority 3 (BIZ_104): Cross-file relationship failure"""
        # Mock no higher priority violations
        detector.combined_upload_missing = Mock(return_value=False)
        detector.uuid_orphaned = Mock(return_value=False)
        
        # Mock cross-file inconsistency
        detector.cross_file_inconsistent = Mock(return_value=True)
        
        result = detector.detect_inconsistencies(sample_record, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'BIZ_104'
        assert "Cross-file relationship failure" in result.primary_reason
        assert result.priority == 3
    
    def test_priority_4_impression_decrease_detection(self, detector, sample_record, batch_context):
        """Test Priority 4 (BIZ_102): Impression decrease detected"""
        # Mock production record with higher impression goal
        production_record = Mock()
        production_record.impression_goal = 75000  # Higher than sample_record (50000)
        detector.production_db_session.execute.return_value.fetchall.return_value = [production_record]
        
        # Mock no higher priority violations
        detector.combined_upload_missing = Mock(return_value=False)
        detector.uuid_orphaned = Mock(return_value=False)
        detector.cross_file_inconsistent = Mock(return_value=False)
        
        result = detector.detect_inconsistencies(sample_record, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'BIZ_102'
        assert "Impression decrease detected" in result.primary_reason
        assert result.priority == 4
        
        # Should include specific decrease information
        assert "75000" in str(result.all_violations) and "50000" in str(result.all_violations)
    
    def test_priority_5_deal_name_exact_string_matching(self, detector, batch_context):
        """Test Priority 5 (BIZ_101): Deal name modification - EXACT string matching"""
        # Test exact string matching (case-sensitive)
        original_record = {
            'deal_campaign_id': 'camp-001',
            'deal_name': 'Original Campaign Name'
        }
        
        modified_record = {
            'deal_campaign_id': 'camp-001',
            'deal_name': 'original campaign name'  # Case change
        }
        
        # Mock production record
        production_record = Mock()
        production_record.deal_name = 'Original Campaign Name'
        detector.production_db_session.execute.return_value.fetchall.return_value = [production_record]
        
        # Mock no higher priority violations
        detector.combined_upload_missing = Mock(return_value=False)
        detector.uuid_orphaned = Mock(return_value=False)
        detector.cross_file_inconsistent = Mock(return_value=False)
        detector.impression_decreased = Mock(return_value=False)
        
        result = detector.detect_inconsistencies(modified_record, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'BIZ_101'
        assert "Deal name modification not allowed" in result.primary_reason
        assert result.priority == 5
        
        # Should capture exact original and modified names
        violation_details = str(result.all_violations)
        assert 'Original Campaign Name' in violation_details
        assert 'original campaign name' in violation_details
    
    def test_priority_6_any_date_modification_flagged(self, detector, batch_context):
        """Test Priority 6 (BIZ_103): ANY date modification flagged"""
        record_with_date_change = {
            'deal_campaign_id': 'camp-001',
            'start_date': date(2024, 1, 15),  # Changed from original
            'end_date': date(2024, 1, 31)
        }
        
        # Mock production record with different dates
        production_record = Mock()
        production_record.start_date = date(2024, 1, 1)  # Original date
        production_record.end_date = date(2024, 1, 31)
        detector.production_db_session.execute.return_value.fetchall.return_value = [production_record]
        
        # Mock no higher priority violations
        for method in ['combined_upload_missing', 'uuid_orphaned', 'cross_file_inconsistent', 
                      'impression_decreased', 'deal_name_changed']:
            setattr(detector, method, Mock(return_value=False))
        
        result = detector.detect_inconsistencies(record_with_date_change, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'BIZ_103'
        assert "Date modification flagged" in result.primary_reason
        assert result.priority == 6
        
        # Should capture which date field changed
        violation_details = str(result.all_violations)
        assert 'start_date' in violation_details
    
    def test_priority_7_hierarchical_structure_validation(self, detector, batch_context):
        """Test Priority 7 (VAL_015): Invalid hierarchical structure (" > " format)"""
        record_with_invalid_hierarchy = {
            'deal_campaign_id': 'camp-001',
            'deal_name': 'Invalid Campaign Name Without Hierarchy'  # Missing " > " structure
        }
        
        # Mock no higher priority violations
        for method in ['combined_upload_missing', 'uuid_orphaned', 'cross_file_inconsistent', 
                      'impression_decreased', 'deal_name_changed', 'date_changed']:
            setattr(detector, method, Mock(return_value=False))
        
        result = detector.detect_inconsistencies(record_with_invalid_hierarchy, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'VAL_015'
        assert "Invalid hierarchical structure" in result.primary_reason
        assert result.priority == 7
        
        # Should validate " > " structure requirement
        violation_details = str(result.all_violations)
        assert '" > "' in violation_details or 'hierarchical' in violation_details.lower()
    
    def test_priority_8_mutual_exclusion_violation(self, detector, batch_context):
        """Test Priority 8 (BIZ_106): Campaign/Deal ID conflict (mutual exclusion)"""
        record_with_both_ids = {
            'deal_campaign_id': 'camp-001',  # Both fields populated
            'deal_id': 'deal-001',           # This violates mutual exclusion
            'deal_name': 'Test Campaign'
        }
        
        # Mock no higher priority violations
        for method in ['combined_upload_missing', 'uuid_orphaned', 'cross_file_inconsistent', 
                      'impression_decreased', 'deal_name_changed', 'date_changed', 'hierarchical_invalid']:
            setattr(detector, method, Mock(return_value=False))
        
        result = detector.detect_inconsistencies(record_with_both_ids, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'BIZ_106'
        assert "Campaign/Deal ID conflict" in result.primary_reason
        assert result.priority == 8
        
        # Should capture both conflicting IDs
        violation_details = str(result.all_violations)
        assert 'camp-001' in violation_details
        assert 'deal-001' in violation_details
    
    def test_priority_9_new_entry_business_rule_violation(self, detector, batch_context):
        """Test Priority 9 (VAL_020): New entry business rule violation (lowest priority)"""
        new_entry_record = {
            'deal_campaign_id': 'new-camp-001',
            'impression_goal': 0,  # Violates new entry business rules
            'cpm_eur': Decimal('0.005')  # Below minimum
        }
        
        # Mock no higher priority violations
        for method in ['combined_upload_missing', 'uuid_orphaned', 'cross_file_inconsistent', 
                      'impression_decreased', 'deal_name_changed', 'date_changed', 
                      'hierarchical_invalid', 'mutual_exclusion_violated']:
            setattr(detector, method, Mock(return_value=False))
        
        # Mock new entry validation to return violations
        detector.new_entry_invalid = Mock(return_value=True)
        
        result = detector.detect_inconsistencies(new_entry_record, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'VAL_020'
        assert "New entry business rule violation" in result.primary_reason
        assert result.priority == 9


class TestConflictResolutionAlgorithm:
    """Test priority-based conflict resolution when multiple rules apply"""
    
    @pytest.fixture
    def detector(self):
        return InconsistentDataDetector(Mock(), Mock(), "batch-001")
    
    def test_multiple_violations_priority_resolution(self, detector):
        """Test conflict resolution when all 9 rules apply simultaneously"""
        record = {
            'deal_campaign_id': 'camp-001',
            'deal_id': 'deal-001',  # Mutual exclusion violation
            'deal_name': 'Invalid Name',  # No hierarchy + name change
            'start_date': date(2024, 2, 1),  # Date change
            'impression_goal': 30000  # Impression decrease
        }
        
        batch_context = {
            'has_campaign_file': True,
            'has_performance_file': False  # Missing file
        }
        
        # Mock all rules to return violations
        detector.combined_upload_missing = Mock(return_value=True)  # Priority 1
        detector.uuid_orphaned = Mock(return_value=True)  # Priority 2
        detector.cross_file_inconsistent = Mock(return_value=True)  # Priority 3
        detector.impression_decreased = Mock(return_value=True)  # Priority 4
        detector.deal_name_changed = Mock(return_value=True)  # Priority 5
        detector.date_changed = Mock(return_value=True)  # Priority 6
        detector.hierarchical_invalid = Mock(return_value=True)  # Priority 7
        detector.mutual_exclusion_violated = Mock(return_value=True)  # Priority 8
        detector.new_entry_invalid = Mock(return_value=True)  # Priority 9
        
        result = detector.detect_inconsistencies(record, batch_context)
        
        # Should prioritize by lowest priority number (highest priority)
        assert result is not None
        assert result.primary_error_code == 'BIZ_105'  # Priority 1 wins
        assert result.primary_reason == "Combined upload incomplete"
        assert result.priority == 1
        
        # Should capture ALL violations for detailed reporting
        assert len(result.all_violations) == 9
        
        # Verify all error codes are present
        violation_codes = [v[0] for v in result.all_violations]
        expected_codes = ['BIZ_105', 'VAL_010', 'BIZ_104', 'BIZ_102', 'BIZ_101', 
                         'BIZ_103', 'VAL_015', 'BIZ_106', 'VAL_020']
        for code in expected_codes:
            assert code in violation_codes
    
    def test_priority_ordering_correctness(self, detector):
        """Test that priority ordering is correctly maintained"""
        # Create scenario with priorities 3, 6, and 8 violations
        record = {'deal_campaign_id': 'camp-001'}
        batch_context = {}
        
        detector.combined_upload_missing = Mock(return_value=False)  # Priority 1
        detector.uuid_orphaned = Mock(return_value=False)  # Priority 2
        detector.cross_file_inconsistent = Mock(return_value=True)  # Priority 3 - Should win
        detector.impression_decreased = Mock(return_value=False)  # Priority 4
        detector.deal_name_changed = Mock(return_value=False)  # Priority 5
        detector.date_changed = Mock(return_value=True)  # Priority 6
        detector.hierarchical_invalid = Mock(return_value=False)  # Priority 7
        detector.mutual_exclusion_violated = Mock(return_value=True)  # Priority 8
        detector.new_entry_invalid = Mock(return_value=False)  # Priority 9
        
        result = detector.detect_inconsistencies(record, batch_context)
        
        # Priority 3 should win over 6 and 8
        assert result.primary_error_code == 'BIZ_104'
        assert result.priority == 3
        
        # Should still capture all three violations
        assert len(result.all_violations) == 3
        violation_codes = [v[0] for v in result.all_violations]
        assert 'BIZ_104' in violation_codes  # Priority 3
        assert 'BIZ_103' in violation_codes  # Priority 6
        assert 'BIZ_106' in violation_codes  # Priority 8
    
    def test_single_violation_handling(self, detector):
        """Test handling when only one rule applies"""
        record = {'deal_campaign_id': 'camp-001'}
        batch_context = {}
        
        # Only priority 7 violation
        for i, method in enumerate(['combined_upload_missing', 'uuid_orphaned', 'cross_file_inconsistent', 
                                   'impression_decreased', 'deal_name_changed', 'date_changed'], 1):
            if i != 7:
                setattr(detector, method, Mock(return_value=False))
        
        detector.hierarchical_invalid = Mock(return_value=True)  # Priority 7
        detector.mutual_exclusion_violated = Mock(return_value=False)  # Priority 8
        detector.new_entry_invalid = Mock(return_value=False)  # Priority 9
        
        result = detector.detect_inconsistencies(record, batch_context)
        
        assert result is not None
        assert result.primary_error_code == 'VAL_015'
        assert result.priority == 7
        assert len(result.all_violations) == 1
    
    def test_no_violations_returns_none(self, detector):
        """Test that no violations returns None classification"""
        record = {'deal_campaign_id': 'camp-001'}
        batch_context = {}
        
        # Mock all rules to return no violations
        for method in ['combined_upload_missing', 'uuid_orphaned', 'cross_file_inconsistent', 
                      'impression_decreased', 'deal_name_changed', 'date_changed', 
                      'hierarchical_invalid', 'mutual_exclusion_violated', 'new_entry_invalid']:
            setattr(detector, method, Mock(return_value=False))
        
        result = detector.detect_inconsistencies(record, batch_context)
        
        assert result is None


class TestSpecificRuleImplementations:
    """Test specific implementations of each business rule"""
    
    @pytest.fixture
    def detector(self):
        return InconsistentDataDetector(Mock(), Mock(), "batch-001")
    
    def test_deal_name_exact_string_comparison(self, detector):
        """Test deal name change detection with exact string comparison"""
        # Mock production record
        production_record = Mock()
        production_record.deal_name = "Exact Campaign Name"
        detector.production_db_session.execute.return_value.fetchall.return_value = [production_record]
        
        # Test exact match (should not trigger)
        record_exact = {'deal_campaign_id': 'camp-001', 'deal_name': 'Exact Campaign Name'}
        assert not detector.deal_name_changed(record_exact)
        
        # Test case change (should trigger)
        record_case = {'deal_campaign_id': 'camp-001', 'deal_name': 'exact campaign name'}
        assert detector.deal_name_changed(record_case)
        
        # Test whitespace change (should trigger)
        record_space = {'deal_campaign_id': 'camp-001', 'deal_name': 'Exact  Campaign Name'}
        assert detector.deal_name_changed(record_space)
        
        # Test character addition (should trigger)
        record_addition = {'deal_campaign_id': 'camp-001', 'deal_name': 'Exact Campaign Name Updated'}
        assert detector.deal_name_changed(record_addition)
    
    def test_date_change_detection_any_modification(self, detector):
        """Test date change detection flags ANY date modification"""
        production_record = Mock()
        production_record.start_date = date(2024, 1, 1)
        production_record.end_date = date(2024, 1, 31)
        detector.production_db_session.execute.return_value.fetchall.return_value = [production_record]
        
        # Test no date change
        record_same = {
            'deal_campaign_id': 'camp-001',
            'start_date': date(2024, 1, 1),
            'end_date': date(2024, 1, 31)
        }
        assert not detector.date_changed(record_same)
        
        # Test start_date change
        record_start = {
            'deal_campaign_id': 'camp-001',
            'start_date': date(2024, 1, 2),  # Changed
            'end_date': date(2024, 1, 31)
        }
        assert detector.date_changed(record_start)
        
        # Test end_date change
        record_end = {
            'deal_campaign_id': 'camp-001',
            'start_date': date(2024, 1, 1),
            'end_date': date(2024, 2, 1)  # Changed
        }
        assert detector.date_changed(record_end)
        
        # Test both dates change
        record_both = {
            'deal_campaign_id': 'camp-001',
            'start_date': date(2024, 1, 5),  # Changed
            'end_date': date(2024, 2, 5)   # Changed
        }
        assert detector.date_changed(record_both)
    
    def test_impression_decrease_detection(self, detector):
        """Test impression decrease detection (all decreases suspicious)"""
        production_record = Mock()
        production_record.impression_goal = 50000
        detector.production_db_session.execute.return_value.fetchall.return_value = [production_record]
        
        # Test no change
        record_same = {'deal_campaign_id': 'camp-001', 'impression_goal': 50000}
        assert not detector.impression_decreased(record_same)
        
        # Test increase (should not trigger)
        record_increase = {'deal_campaign_id': 'camp-001', 'impression_goal': 60000}
        assert not detector.impression_decreased(record_increase)
        
        # Test small decrease (should trigger)
        record_small_decrease = {'deal_campaign_id': 'camp-001', 'impression_goal': 49999}
        assert detector.impression_decreased(record_small_decrease)
        
        # Test large decrease (should trigger)
        record_large_decrease = {'deal_campaign_id': 'camp-001', 'impression_goal': 25000}
        assert detector.impression_decreased(record_large_decrease)
        
        # Test zero impressions (should trigger)
        record_zero = {'deal_campaign_id': 'camp-001', 'impression_goal': 0}
        assert detector.impression_decreased(record_zero)
    
    def test_hierarchical_name_structure_validation(self, detector):
        """Test hierarchical name structure validation (" > " format)"""
        # Valid hierarchical structures
        valid_names = [
            'Parent Campaign > Child Campaign',
            'Brand > Product > Variant',
            'Category > Subcategory > Item',
            'Level1 > Level2 > Level3 > Level4'
        ]
        
        for name in valid_names:
            record = {'deal_name': name}
            assert not detector.hierarchical_invalid(record), f"Should be valid: {name}"
        
        # Invalid hierarchical structures
        invalid_names = [
            'Single Level Campaign',
            'Parent Campaign-Child Campaign',  # Wrong separator
            'Parent Campaign | Child Campaign',  # Wrong separator
            'Parent Campaign>Child Campaign',  # No spaces
            '> Child Campaign',  # Starts with separator
            'Parent Campaign >',  # Ends with separator
            '',  # Empty string
            'Parent Campaign >>Child Campaign'  # Double separator
        ]
        
        for name in invalid_names:
            record = {'deal_name': name}
            assert detector.hierarchical_invalid(record), f"Should be invalid: {name}"
    
    def test_mutual_exclusion_violation_detection(self, detector):
        """Test mutual exclusion violation (Campaign/Deal ID conflict)"""
        # Valid cases (only one ID populated)
        valid_records = [
            {'deal_campaign_id': 'camp-001', 'deal_id': None},
            {'deal_campaign_id': 'camp-001'},  # deal_id not present
            {'deal_id': 'deal-001', 'deal_campaign_id': None},
            {'deal_id': 'deal-001'},  # deal_campaign_id not present
        ]
        
        for record in valid_records:
            assert not detector.mutual_exclusion_violated(record)
        
        # Invalid cases (both IDs populated)
        invalid_records = [
            {'deal_campaign_id': 'camp-001', 'deal_id': 'deal-001'},
            {'deal_campaign_id': '', 'deal_id': 'deal-001'},  # Empty string still counts
            {'deal_campaign_id': 'camp-001', 'deal_id': ''},  # Empty string still counts
        ]
        
        for record in invalid_records:
            assert detector.mutual_exclusion_violated(record)
    
    def test_cross_file_consistency_validation(self, detector):
        """Test cross-file consistency validation"""
        batch_context = {
            'campaign_records': ['camp-001', 'camp-002', 'camp-003'],
            'performance_records': ['camp-001', 'camp-002', 'camp-004']  # camp-003 missing, camp-004 extra
        }
        
        # Records with matching UUIDs across files
        consistent_record = {'deal_campaign_id': 'camp-001'}
        assert not detector.cross_file_inconsistent(consistent_record, batch_context)
        
        # Campaign record without corresponding performance
        orphaned_campaign = {'deal_campaign_id': 'camp-003'}
        assert detector.cross_file_inconsistent(orphaned_campaign, batch_context)
        
        # Performance record without corresponding campaign
        orphaned_performance = {'deal_id': 'camp-004'}
        assert detector.cross_file_inconsistent(orphaned_performance, batch_context)


class TestExtendedStagingIntegration:
    """Test integration with extended staging tables and JSONB storage"""
    
    @pytest.fixture
    def detector(self):
        staging_session = Mock()
        return InconsistentDataDetector(Mock(), staging_session, "batch-001")
    
    def test_violation_storage_in_jsonb_format(self, detector):
        """Test violation details stored in JSONB format"""
        record = {'deal_campaign_id': 'camp-001'}
        classification = InconsistentClassification(
            primary_reason="Deal name modification not allowed",
            all_violations=[
                ('BIZ_101', 'Deal name changed: "Old Name" -> "New Name"'),
                ('BIZ_103', 'Start date changed: 2024-01-01 -> 2024-01-05')
            ],
            primary_error_code='BIZ_101',
            priority=5
        )
        
        detector.store_inconsistent_record_in_staging(record, classification)
        
        # Verify JSONB storage format
        call_args = detector.staging_db_session.execute.call_args
        query_params = call_args[1] if len(call_args) > 1 else {}
        
        assert 'violation_details' in query_params
        
        # Parse and verify JSON structure
        import json
        violation_json = json.loads(query_params['violation_details'])
        assert isinstance(violation_json, list)
        assert len(violation_json) == 2
        
        # Verify first violation
        assert violation_json[0]['error_code'] == 'BIZ_101'
        assert 'Deal name changed' in violation_json[0]['description']
        
        # Verify second violation
        assert violation_json[1]['error_code'] == 'BIZ_103'
        assert 'Start date changed' in violation_json[1]['description']
    
    def test_flagged_for_review_setting(self, detector):
        """Test flagged_for_review is set to true for inconsistent records"""
        record = {'deal_campaign_id': 'camp-001'}
        classification = InconsistentClassification(
            primary_reason="Test violation",
            all_violations=[('BIZ_101', 'Test description')],
            primary_error_code='BIZ_101'
        )
        
        detector.store_inconsistent_record_in_staging(record, classification)
        
        call_args = detector.staging_db_session.execute.call_args
        query = str(call_args[0][0])
        params = call_args[1] if len(call_args) > 1 else {}
        
        # Verify flagged_for_review is set
        assert 'flagged_for_review' in query
        assert params.get('flagged_for_review') is True
    
    def test_phase_context_setting(self, detector):
        """Test phase_context is set to '1.2' for inconsistent records"""
        record = {'deal_campaign_id': 'camp-001'}
        classification = InconsistentClassification(
            primary_reason="Test violation",
            all_violations=[('BIZ_101', 'Test description')],
            primary_error_code='BIZ_101'
        )
        
        detector.store_inconsistent_record_in_staging(record, classification)
        
        call_args = detector.staging_db_session.execute.call_args
        params = call_args[1] if len(call_args) > 1 else {}
        
        assert params.get('phase_context') == '1.2'


class TestPhase11IntegrationCompatibility:
    """Test integration compatibility with Phase 1.1 components"""
    
    @pytest.fixture
    def detector(self):
        return InconsistentDataDetector(Mock(), Mock(), "batch-001")
    
    def test_unified_error_code_system_integration(self, detector):
        """Test integration with unified error code system from Phase 1.1"""
        # Verify error codes match Phase 1.1 system
        expected_error_codes = {
            'BIZ_101', 'BIZ_102', 'BIZ_103', 'BIZ_104', 'BIZ_105', 'BIZ_106',
            'VAL_010', 'VAL_015', 'VAL_020'
        }
        
        for rule_name in detector.priority_rules:
            error_code = detector.get_rule_error_code(rule_name)
            assert error_code in expected_error_codes
    
    def test_database_session_sharing_with_phase_1_1(self, detector):
        """Test database session sharing patterns from Phase 1.1"""
        # Should use the same session instances
        assert detector.production_db_session is not None
        assert detector.staging_db_session is not None
        
        # Should not create new connections
        detector.detect_inconsistencies({'deal_campaign_id': 'test'}, {})
        
        # Should use existing sessions without closing them
        detector.production_db_session.close.assert_not_called()
        detector.staging_db_session.close.assert_not_called()
    
    def test_processing_batch_id_consistency(self, detector):
        """Test processing_batch_id consistency with Phase 1.1"""
        record = {'deal_campaign_id': 'camp-001'}
        classification = InconsistentClassification(
            primary_reason="Test violation",
            all_violations=[('BIZ_101', 'Test description')],
            primary_error_code='BIZ_101'
        )
        
        detector.store_inconsistent_record_in_staging(record, classification)
        
        call_args = detector.staging_db_session.execute.call_args
        params = call_args[1] if len(call_args) > 1 else {}
        
        # Should use the same processing_batch_id pattern
        assert params.get('processing_batch_id') == 'batch-001'


class TestBatchProcessingAndPerformance:
    """Test batch processing capabilities and performance requirements"""
    
    @pytest.fixture
    def detector(self):
        return InconsistentDataDetector(Mock(), Mock(), "batch-001")
    
    def test_batch_inconsistency_detection(self, detector):
        """Test batch processing of multiple records for inconsistency detection"""
        records = [
            {'deal_campaign_id': 'camp-001', 'deal_name': 'Campaign 1'},
            {'deal_campaign_id': 'camp-002', 'deal_name': 'Campaign 2'},
            {'deal_campaign_id': 'camp-003', 'deal_name': 'Invalid Name'}  # Missing hierarchy
        ]
        
        batch_context = {'has_campaign_file': True, 'has_performance_file': True}
        
        # Mock different violations for different records
        detector.hierarchical_invalid = Mock(side_effect=[False, False, True])
        for method in ['combined_upload_missing', 'uuid_orphaned', 'cross_file_inconsistent', 
                      'impression_decreased', 'deal_name_changed', 'date_changed', 
                      'mutual_exclusion_violated', 'new_entry_invalid']:
            setattr(detector, method, Mock(return_value=False))
        
        results = detector.detect_inconsistencies_batch(records, batch_context)
        
        assert len(results) == 3
        assert results[0] is None  # No violations
        assert results[1] is None  # No violations
        assert results[2] is not None  # Has violation
        assert results[2].primary_error_code == 'VAL_015'
    
    def test_large_dataset_performance(self, detector):
        """Test performance with large datasets (1000+ records)"""
        import time
        
        # Create large dataset
        large_records = [
            {'deal_campaign_id': f'camp-{i:04d}', 'deal_name': f'Campaign {i}'}
            for i in range(1000)
        ]
        
        batch_context = {}
        
        # Mock all rules to return no violations for performance test
        for method in ['combined_upload_missing', 'uuid_orphaned', 'cross_file_inconsistent', 
                      'impression_decreased', 'deal_name_changed', 'date_changed', 
                      'hierarchical_invalid', 'mutual_exclusion_violated', 'new_entry_invalid']:
            setattr(detector, method, Mock(return_value=False))
        
        start_time = time.time()
        results = detector.detect_inconsistencies_batch(large_records, batch_context)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should process 1000 records in reasonable time (< 5 seconds)
        assert processing_time < 5
        assert len(results) == 1000
        assert all(result is None for result in results)  # No violations
    
    def test_memory_efficiency_with_large_batches(self, detector):
        """Test memory efficiency with large batches"""
        # This test ensures the detector doesn't load entire datasets into memory
        large_batch_size = 5000
        
        # Mock memory-efficient processing
        with patch('src.services.inconsistent_data_detector.process_records_in_chunks') as mock_process:
            mock_process.return_value = [None] * large_batch_size
            
            large_records = [
                {'deal_campaign_id': f'camp-{i:06d}'}
                for i in range(large_batch_size)
            ]
            
            results = detector.detect_inconsistencies_batch(large_records, {})
            
            # Should use chunked processing for memory efficiency
            mock_process.assert_called_once()
            assert len(results) == large_batch_size


class TestErrorHandlingAndRobustness:
    """Test error handling and system robustness"""
    
    @pytest.fixture
    def detector(self):
        return InconsistentDataDetector(Mock(), Mock(), "batch-001")
    
    def test_production_database_connection_error_handling(self, detector):
        """Test graceful handling of production database connection errors"""
        detector.production_db_session.execute.side_effect = Exception("Connection failed")
        
        record = {'deal_campaign_id': 'camp-001'}
        batch_context = {}
        
        # Should handle database errors gracefully
        result = detector.detect_inconsistencies(record, batch_context)
        
        # Should still attempt other validations that don't require database
        assert result is not None or result is None  # Either way, should not crash
    
    def test_staging_database_rollback_on_error(self, detector):
        """Test staging database rollback when storage errors occur"""
        detector.staging_db_session.execute.side_effect = Exception("Storage failed")
        
        record = {'deal_campaign_id': 'camp-001'}
        classification = InconsistentClassification(
            primary_reason="Test violation",
            all_violations=[('BIZ_101', 'Test description')],
            primary_error_code='BIZ_101'
        )
        
        with pytest.raises(Exception):
            detector.store_inconsistent_record_in_staging(record, classification)
        
        # Should trigger rollback on error
        detector.staging_db_session.rollback.assert_called_once()
    
    def test_invalid_record_data_handling(self, detector):
        """Test handling of invalid or malformed record data"""
        invalid_records = [
            {},  # Empty record
            {'invalid_field': 'value'},  # Missing required fields
            {'deal_campaign_id': None},  # Null ID
            {'deal_campaign_id': ''},  # Empty ID
        ]
        
        batch_context = {}
        
        # Should handle invalid records without crashing
        for record in invalid_records:
            try:
                result = detector.detect_inconsistencies(record, batch_context)
                # Either returns a result or None, but should not crash
                assert result is None or isinstance(result, InconsistentClassification)
            except Exception as e:
                # If an exception is raised, it should be a validation error, not a crash
                assert "validation" in str(e).lower() or "invalid" in str(e).lower()


class TestInconsistentClassificationModel:
    """Test InconsistentClassification data model"""
    
    def test_inconsistent_classification_creation(self):
        """Test InconsistentClassification model creation"""
        classification = InconsistentClassification(
            primary_reason="Deal name modification not allowed",
            all_violations=[
                ('BIZ_101', 'Deal name changed'),
                ('BIZ_103', 'Date changed')
            ],
            primary_error_code='BIZ_101',
            priority=5
        )
        
        assert classification.primary_reason == "Deal name modification not allowed"
        assert classification.primary_error_code == 'BIZ_101'
        assert classification.priority == 5
        assert len(classification.all_violations) == 2
    
    def test_violation_json_serialization(self):
        """Test violation serialization to JSON format"""
        classification = InconsistentClassification(
            primary_reason="Multiple violations detected",
            all_violations=[
                ('BIZ_101', 'Deal name changed: "Old" -> "New"'),
                ('BIZ_103', 'Start date changed: 2024-01-01 -> 2024-01-05'),
                ('VAL_015', 'Invalid hierarchical structure')
            ],
            primary_error_code='BIZ_101'
        )
        
        json_violations = classification.to_json_violations()
        
        assert isinstance(json_violations, list)
        assert len(json_violations) == 3
        
        # Verify first violation
        assert json_violations[0]['error_code'] == 'BIZ_101'
        assert 'Deal name changed' in json_violations[0]['description']
        
        # Verify structure consistency
        for violation in json_violations:
            assert 'error_code' in violation
            assert 'description' in violation
            assert isinstance(violation['error_code'], str)
            assert isinstance(violation['description'], str)


class TestFunctionalInterfaceTests:
    """Test functional interface functions"""
    
    @pytest.mark.asyncio
    async def test_detect_inconsistencies_batch_function(self):
        """Test standalone detect_inconsistencies_batch function"""
        records = [
            {'deal_campaign_id': 'camp-001'},
            {'deal_campaign_id': 'camp-002'}
        ]
        batch_context = {}
        
        with patch('src.services.inconsistent_data_detector.InconsistentDataDetector') as mock_detector:
            detector_instance = mock_detector.return_value
            detector_instance.detect_inconsistencies.side_effect = [None, None]
            
            results = await detect_inconsistencies_batch(records, batch_context, Mock(), Mock())
            
            assert len(results) == 2
            assert all(result is None for result in results)
    
    def test_validate_priority_algorithm_function(self):
        """Test priority algorithm validation function"""
        # Test that priority algorithm validation works correctly
        priority_rules = {
            'rule1': (1, 'BIZ_101'),
            'rule2': (2, 'BIZ_102'),
            'rule3': (3, 'BIZ_103')
        }
        
        violations = [
            ('rule3', True),  # Priority 3
            ('rule1', True),  # Priority 1 (should win)
            ('rule2', True)   # Priority 2
        ]
        
        result = validate_priority_algorithm(violations, priority_rules)
        
        assert result['winning_rule'] == 'rule1'
        assert result['winning_priority'] == 1
        assert result['winning_error_code'] == 'BIZ_101'
        assert len(result['all_violations']) == 3

    def test_resolve_priority_conflicts_function(self):
        """Test priority conflict resolution function"""
        conflicts = [
            PriorityViolation(priority=3, error_code='BIZ_104', description='Cross-file issue'),
            PriorityViolation(priority=1, error_code='BIZ_105', description='Upload incomplete'),
            PriorityViolation(priority=5, error_code='BIZ_101', description='Name changed')
        ]
        
        resolved = resolve_priority_conflicts(conflicts)
        
        assert resolved.primary_violation.priority == 1
        assert resolved.primary_violation.error_code == 'BIZ_105'
        assert len(resolved.all_violations) == 3


# Performance and Integration Test Data
@pytest.fixture
def large_test_dataset():
    """Generate large test dataset for performance testing"""
    return [
        {
            'deal_campaign_id': f'camp-{i:06d}',
            'deal_name': f'Campaign {i} > Subcampaign {i}',
            'start_date': date(2024, 1, 1),
            'end_date': date(2024, 1, 31),
            'impression_goal': 50000 + i,
            'budget_eur': Decimal(f'{1000 + i}.00'),
            'cpm_eur': Decimal('5.50')
        }
        for i in range(1000)
    ]


@pytest.fixture
def complex_batch_context():
    """Generate complex batch context for integration testing"""
    return {
        'has_campaign_file': True,
        'has_performance_file': True,
        'campaign_records': [f'camp-{i:06d}' for i in range(500)],
        'performance_records': [f'camp-{i:06d}' for i in range(450)],  # Some missing
        'processing_batch_id': 'complex-batch-001',
        'upload_session_id': 'session-001',
        'user_id': 'test-user',
        'upload_timestamp': datetime.now()
    }