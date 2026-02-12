#!/usr/bin/env python3
"""
Tenant Isolation Test Suite
Comprehensive tests for multi-tenant data isolation.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import logging

# Import the modules we want to test
import sys
sys.path.insert(0, "D:\\verified-digital-twin-brains\\backend")

from modules.tenant_guard import TenantGuard, TenantIsolationError, TenantAuditLogger
from modules.embeddings_delphi import PineconeDelphiClient


# Configure logging for tests
logging.basicConfig(level=logging.INFO)


class TestTenantGuard:
    """Test the TenantGuard isolation enforcement."""
    
    def test_user_can_access_own_creator(self):
        """User should be able to access their own creator."""
        user = {
            "id": "user_123",
            "email": "sainath@example.com",
            "creator_ids": ["sainath.no.1"],
            "role": "user"
        }
        
        guard = TenantGuard(user)
        
        # Should not raise
        result = guard.validate_creator_access("sainath.no.1")
        assert result is True
    
    def test_user_cannot_access_other_creator(self):
        """User should NOT be able to access another creator's data."""
        user = {
            "id": "user_123",
            "email": "sainath@example.com",
            "creator_ids": ["sainath.no.1"],
            "role": "user"
        }
        
        guard = TenantGuard(user)
        
        with pytest.raises(TenantIsolationError) as exc_info:
            guard.validate_creator_access("other.user")
        
        assert "Access denied" in str(exc_info.value)
        assert "other.user" in str(exc_info.value)
    
    def test_admin_can_access_any_creator(self):
        """Admin should be able to access any creator (with audit)."""
        admin = {
            "id": "admin_123",
            "email": "admin@digitalbrains.com",
            "creator_ids": [],
            "role": "admin"
        }
        
        guard = TenantGuard(admin)
        
        # Should not raise for any creator
        result = guard.validate_creator_access("any.creator")
        assert result is True
        
        # Check is_admin flag
        assert guard.is_admin is True
    
    def test_namespace_parsing(self):
        """Test parsing creator_id from namespace."""
        user = {
            "id": "user_123",
            "email": "sainath@example.com",
            "creator_ids": ["sainath.no.1"],
            "role": "user"
        }
        
        guard = TenantGuard(user)
        
        # Valid namespace - should succeed
        result = guard.validate_namespace_access("creator_sainath.no.1_twin_coach")
        assert result is True
        
        # Invalid namespace - should raise
        with pytest.raises(TenantIsolationError):
            guard.validate_namespace_access("creator_other.user_twin_coach")
    
    def test_namespace_parsing_with_underscores(self):
        """Test parsing creator_ids that contain underscores."""
        user = {
            "id": "user_123",
            "email": "test@example.com",
            "creator_ids": ["user_test_123"],
            "role": "user"
        }
        
        guard = TenantGuard(user)
        
        # Creator ID with underscores
        result = guard.validate_namespace_access("creator_user_test_123_twin_coach")
        assert result is True
    
    def test_get_allowed_namespaces(self):
        """Test getting allowed namespace patterns."""
        user = {
            "id": "user_123",
            "email": "sainath@example.com",
            "creator_ids": ["sainath.no.1", "sainath.no.2"],
            "role": "user"
        }
        
        guard = TenantGuard(user)
        patterns = guard.get_allowed_namespaces()
        
        assert len(patterns) == 2
        assert "creator_sainath.no.1_*" in patterns
        assert "creator_sainath.no.2_*" in patterns
    
    def test_filter_results_by_tenant(self):
        """Test filtering query results by tenant."""
        user = {
            "id": "user_123",
            "email": "sainath@example.com",
            "creator_ids": ["sainath.no.1"],
            "role": "user"
        }
        
        guard = TenantGuard(user)
        
        # Mock results
        mock_match_own = Mock()
        mock_match_own.metadata = {"creator_id": "sainath.no.1"}
        mock_match_own.id = "vec_1"
        
        mock_match_other = Mock()
        mock_match_other.metadata = {"creator_id": "other.user"}
        mock_match_other.id = "vec_2"
        
        results = [mock_match_own, mock_match_other]
        
        # Should filter out other user's data
        filtered = guard.filter_results_by_tenant(results)
        
        assert len(filtered) == 1
        assert filtered[0].id == "vec_1"
    
    def test_user_with_no_creators(self):
        """Test user with no creator access."""
        user = {
            "id": "user_123",
            "email": "new@example.com",
            "creator_ids": [],
            "role": "user"
        }
        
        guard = TenantGuard(user)
        
        with pytest.raises(TenantIsolationError):
            guard.validate_creator_access("any.creator")


class TestTenantAuditLogger:
    """Test the audit logging functionality."""
    
    def test_log_vector_query(self, caplog):
        """Test logging vector queries."""
        logger = TenantAuditLogger()
        
        with caplog.at_level(logging.INFO):
            logger.log_vector_query(
                user_id="user_123",
                creator_id="sainath.no.1",
                twin_id="coach",
                top_k=10,
                result_count=5,
                latency_ms=45.5,
                ip_address="192.168.1.1"
            )
        
        assert "vector_query" in caplog.text
        assert "user_123" in caplog.text
        assert "sainath.no.1" in caplog.text
    
    def test_log_isolation_violation(self, caplog):
        """Test logging isolation violations."""
        logger = TenantAuditLogger()
        
        with caplog.at_level(logging.WARNING):
            logger.log_isolation_violation(
                user_id="user_123",
                email="attacker@example.com",
                attempted_creator_id="victim.creator",
                authorized_creators=["attacker.creator"],
                endpoint="/query",
                ip_address="10.0.0.1"
            )
        
        assert "isolation_violation" in caplog.text
        assert "severity" in caplog.text
        assert "HIGH" in caplog.text
        assert "blocked" in caplog.text
    
    def test_log_data_deletion(self, caplog):
        """Test logging data deletions."""
        logger = TenantAuditLogger()
        
        with caplog.at_level(logging.INFO):
            logger.log_data_deletion(
                user_id="user_123",
                creator_id="sainath.no.1",
                twin_id="coach",
                vector_count=100,
                gdpr_request=True
            )
        
        assert "data_deletion" in caplog.text
        assert "gdpr_request" in caplog.text
        assert "true" in caplog.text


class TestDelphiClientIsolation:
    """Test that DelphiClient maintains tenant isolation."""
    
    @pytest.fixture
    def mock_pinecone(self):
        """Create a mock Pinecone client."""
        with patch('modules.embeddings_delphi.Pinecone') as mock:
            mock_index = Mock()
            mock_instance = Mock()
            mock_instance.Index.return_value = mock_index
            mock.return_value = mock_instance
            yield mock, mock_index
    
    def test_namespace_generation(self, mock_pinecone):
        """Test correct namespace naming."""
        _, _ = mock_pinecone
        client = PineconeDelphiClient()
        
        # Twin-specific namespace
        ns = client._get_namespace("sainath.no.1", "coach")
        assert ns == "creator_sainath.no.1_twin_coach"
        
        # Creator-wide namespace
        ns = client._get_namespace("sainath.no.1")
        assert ns == "creator_sainath.no.1"
    
    def test_upsert_adds_metadata(self, mock_pinecone):
        """Test that upsert adds creator/twin metadata."""
        _, mock_index = mock_pinecone
        client = PineconeDelphiClient()
        
        vectors = [
            {
                "id": "doc_1",
                "values": [0.1] * 3072,
                "metadata": {"text": "test"}
            }
        ]
        
        client.upsert_vectors(
            vectors=vectors,
            creator_id="sainath.no.1",
            twin_id="coach"
        )
        
        # Verify upsert was called
        mock_index.upsert.assert_called_once()
        
        # Verify metadata was enriched
        call_args = mock_index.upsert.call_args
        upserted_vectors = call_args[1]["vectors"]
        
        assert upserted_vectors[0]["metadata"]["creator_id"] == "sainath.no.1"
        assert upserted_vectors[0]["metadata"]["twin_id"] == "coach"
    
    def test_query_uses_correct_namespace(self, mock_pinecone):
        """Test that query uses the correct tenant namespace."""
        _, mock_index = mock_pinecone
        client = PineconeDelphiClient()
        
        client.query(
            vector=[0.1] * 3072,
            creator_id="sainath.no.1",
            twin_id="coach",
            top_k=10
        )
        
        # Verify query was called with correct namespace
        mock_index.query.assert_called_once()
        call_args = mock_index.query.call_args
        
        assert call_args[1]["namespace"] == "creator_sainath.no.1_twin_coach"
        assert call_args[1]["top_k"] == 10
    
    def test_delete_twin_deletes_correct_namespace(self, mock_pinecone):
        """Test twin deletion targets correct namespace."""
        _, mock_index = mock_pinecone
        client = PineconeDelphiClient()
        
        client.delete_twin("sainath.no.1", "coach")
        
        # Verify delete was called with correct namespace
        mock_index.delete.assert_called_once_with(
            delete_all=True,
            namespace="creator_sainath.no.1_twin_coach"
        )
    
    def test_delete_creator_deletes_all_namespaces(self, mock_pinecone):
        """Test creator deletion removes all twin namespaces."""
        _, mock_index = mock_pinecone
        client = PineconeDelphiClient()
        
        # Mock the stats to show multiple namespaces
        mock_index.describe_index_stats.return_value = Mock(
            namespaces={
                "creator_sainath.no.1": Mock(vector_count=100),
                "creator_sainath.no.1_twin_coach": Mock(vector_count=50),
                "creator_sainath.no.1_twin_assistant": Mock(vector_count=75),
                "creator_other.user_twin_coach": Mock(vector_count=200),
            }
        )
        
        result = client.delete_creator_data("sainath.no.1")
        
        # Should succeed
        assert result is True
        
        # Should delete 3 namespaces (creator + 2 twins)
        assert mock_index.delete.call_count == 3


class TestIntegrationScenarios:
    """Integration tests for complete tenant isolation flow."""
    
    def test_cross_tenant_query_blocked(self):
        """Complete flow: User A tries to query User B's data."""
        # User A
        user_a = {
            "id": "user_a",
            "email": "a@example.com",
            "creator_ids": ["creator.a"],
            "role": "user"
        }
        
        guard = TenantGuard(user_a)
        
        # Try to access creator B's data
        with pytest.raises(TenantIsolationError):
            guard.validate_creator_access("creator.b")
    
    def test_admin_access_logged(self, caplog):
        """Admin access should be allowed but logged."""
        admin = {
            "id": "admin_1",
            "email": "admin@digitalbrains.com",
            "creator_ids": [],
            "role": "admin"
        }
        
        with caplog.at_level(logging.INFO):
            guard = TenantGuard(admin)
            guard.validate_creator_access("any.creator")
        
        # Should log admin access
        assert "Admin access granted" in caplog.text
    
    def test_gdpr_deletion_flow(self):
        """Test complete GDPR deletion flow."""
        # This would test the actual deletion endpoints
        # For now, just verify the logic
        
        user = {
            "id": "user_123",
            "email": "sainath@example.com",
            "creator_ids": ["sainath.no.1"],
            "role": "user"
        }
        
        guard = TenantGuard(user)
        
        # User can request deletion of their own data
        assert guard.validate_creator_access("sainath.no.1") is True
        
        # But not someone else's
        with pytest.raises(TenantIsolationError):
            guard.validate_creator_access("other.user")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
