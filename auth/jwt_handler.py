"""
JWT token generation and validation.
"""
import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt

logger = logging.getLogger(__name__)


class JWTHandler:
    """Handles JWT token creation and validation."""
    
    def __init__(self, secret: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize JWT handler.
        
        Args:
            secret: JWT secret key (from env if not provided)
            algorithm: JWT algorithm (default HS256)
        """
        self.secret = self._get_validated_secret(secret)
        self.algorithm = algorithm
    
    def _get_validated_secret(self, provided_secret: Optional[str]) -> str:
        """
        Get and validate JWT secret.
        
        Args:
            provided_secret: Provided secret (or None)
            
        Returns:
            Validated secret string
            
        Raises:
            ValueError: If secret is missing/invalid in production mode
        """
        # Get environment mode
        env_mode = os.getenv("SECUREGUARD_ENV", "development").lower()
        is_production = env_mode == "production"
        
        # Get secret from various sources
        secret = provided_secret or os.getenv("JWT_SECRET")
        
        # Validate secret length
        MIN_SECRET_LENGTH = 32
        
        if not secret:
            if is_production:
                raise ValueError(
                    "JWT_SECRET is required in production mode. "
                    "Set SECUREGUARD_ENV=production and JWT_SECRET environment variable."
                )
            # Auto-generate in development
            secret = secrets.token_hex(32)
            logger.warning(
                "JWT_SECRET not provided. Auto-generated secret for development. "
                "DO NOT use in production!"
            )
        elif len(secret) < MIN_SECRET_LENGTH:
            if is_production:
                raise ValueError(
                    f"JWT_SECRET must be at least {MIN_SECRET_LENGTH} characters long. "
                    f"Current length: {len(secret)}"
                )
            # Warn in development
            logger.warning(
                f"JWT_SECRET is too short ({len(secret)} chars, minimum {MIN_SECRET_LENGTH}). "
                f"This is acceptable in development but INSECURE for production!"
            )
        
        return secret
    
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
        
        expire = datetime.now(timezone.utc) + expires_delta
        
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
