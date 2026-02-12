"""
JWT token generation and validation.
"""
import os
from datetime import datetime, timedelta
from typing import Optional
import jwt


class JWTHandler:
    """Handles JWT token creation and validation."""
    
    def __init__(self, secret: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize JWT handler.
        
        Args:
            secret: JWT secret key (from env if not provided)
            algorithm: JWT algorithm (default HS256)
        """
        self.secret = secret or os.getenv("JWT_SECRET", "dev-secret-change-in-production")
        self.algorithm = algorithm
    
    def create_token(
        self,
        user_id: str,
        email: str,
        role: str,
        tenant_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a new JWT token.
        
        Args:
            user_id: User ID
            email: User email
            role: User role (admin/operator/viewer)
            tenant_id: Tenant ID
            expires_delta: Token expiration time (default 24h)
            
        Returns:
            JWT token string
        """
        if expires_delta is None:
            expires_delta = timedelta(hours=24)
        
        expire = datetime.utcnow() + expires_delta
        
        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "tenant_id": tenant_id,
            "exp": expire
        }
        
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return token
    
    def verify_token(self, token: str) -> dict:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload
            
        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise jwt.ExpiredSignatureError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")
    
    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode token without verification (for debugging).
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception:
            return None


# Global JWT handler instance
jwt_handler = JWTHandler()


if __name__ == "__main__":
    # Test JWT creation and validation
    handler = JWTHandler(secret="test-secret")
    
    # Create token
    token = handler.create_token(
        user_id="user123",
        email="test@example.com",
        role="operator",
        tenant_id="tenant1"
    )
    print(f"Token created: {token[:50]}...")
    
    # Verify token
    try:
        payload = handler.verify_token(token)
        print(f"Token verified: {payload}")
    except Exception as e:
        print(f"Verification failed: {e}")
    
    # Test expired token
    expired_token = handler.create_token(
        user_id="user123",
        email="test@example.com",
        role="viewer",
        tenant_id="tenant1",
        expires_delta=timedelta(seconds=-1)
    )
    try:
        handler.verify_token(expired_token)
    except jwt.ExpiredSignatureError:
        print("Expired token correctly rejected")
