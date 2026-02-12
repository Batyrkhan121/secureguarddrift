"""
Week 10 tests: Authentication, RBAC, and production features.
"""
import pytest
from datetime import timedelta
import jwt as pyjwt
from auth.jwt_handler import JWTHandler
from auth.permissions import Permission, check_permission, ROLE_PERMISSIONS


def test_jwt_generation_and_validation():
    """Test JWT token creation and validation."""
    handler = JWTHandler(secret="test-secret-key")
    
    # Create token
    token = handler.create_token(
        user_id="user123",
        email="test@example.com",
        role="operator",
        tenant_id="tenant1"
    )
    
    assert token is not None
    assert isinstance(token, str)
    
    # Verify token
    payload = handler.verify_token(token)
    assert payload["user_id"] == "user123"
    assert payload["email"] == "test@example.com"
    assert payload["role"] == "operator"
    assert payload["tenant_id"] == "tenant1"
    assert "exp" in payload


def test_jwt_expired_token():
    """Test that expired tokens are rejected."""
    handler = JWTHandler(secret="test-secret-key")
    
    # Create expired token
    expired_token = handler.create_token(
        user_id="user123",
        email="test@example.com",
        role="viewer",
        tenant_id="tenant1",
        expires_delta=timedelta(seconds=-1)
    )
    
    # Should raise ExpiredSignatureError
    with pytest.raises(pyjwt.ExpiredSignatureError):
        handler.verify_token(expired_token)


def test_jwt_invalid_token():
    """Test that invalid tokens are rejected."""
    handler = JWTHandler(secret="test-secret-key")
    
    # Invalid token
    invalid_token = "invalid.token.here"
    
    with pytest.raises(pyjwt.InvalidTokenError):
        handler.verify_token(invalid_token)


def test_viewer_permissions():
    """Test viewer role permissions."""
    # Viewer can read
    assert check_permission("viewer", Permission.READ_GRAPH) is True
    assert check_permission("viewer", Permission.READ_DRIFT) is True
    assert check_permission("viewer", Permission.READ_REPORT) is True
    
    # Viewer cannot write
    assert check_permission("viewer", Permission.WRITE_POLICY) is False
    assert check_permission("viewer", Permission.WRITE_FEEDBACK) is False
    assert check_permission("viewer", Permission.WRITE_GITOPS) is False


def test_operator_permissions():
    """Test operator role permissions."""
    # Operator can read
    assert check_permission("operator", Permission.READ_GRAPH) is True
    
    # Operator can write some things
    assert check_permission("operator", Permission.WRITE_POLICY) is True
    assert check_permission("operator", Permission.WRITE_FEEDBACK) is True
    assert check_permission("operator", Permission.WRITE_WHITELIST) is True
    
    # Operator cannot write gitops
    assert check_permission("operator", Permission.WRITE_GITOPS) is False
    assert check_permission("operator", Permission.DELETE_WHITELIST) is False


def test_admin_permissions():
    """Test admin role has all permissions."""
    # Admin has all permissions
    for permission in Permission:
        assert check_permission("admin", permission) is True


def test_role_permissions_matrix():
    """Test that role permissions matrix is correctly defined."""
    assert "viewer" in ROLE_PERMISSIONS
    assert "operator" in ROLE_PERMISSIONS
    assert "admin" in ROLE_PERMISSIONS
    
    # Viewer has 3 permissions
    assert len(ROLE_PERMISSIONS["viewer"]) == 3
    
    # Operator has 6 permissions
    assert len(ROLE_PERMISSIONS["operator"]) == 6
    
    # Admin has 9 permissions (all)
    assert len(ROLE_PERMISSIONS["admin"]) == 9


def test_unknown_role():
    """Test that unknown role has no permissions."""
    assert check_permission("unknown_role", Permission.READ_GRAPH) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
