"""
FastAPI authentication middleware.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import jwt as pyjwt
from auth.jwt_handler import jwt_handler


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки JWT токенов."""
    
    # Публичные эндпоинты без auth
    PUBLIC_PATHS = [
        "/api/health",
        "/api/auth/login",
        "/",
        "/static",
        "/docs",
        "/openapi.json",
        "/redoc"
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request and check authentication."""
        # Check if path is public
        path = request.url.path
        if any(path.startswith(p) for p in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"}
            )
        
        # Check Bearer format
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Authorization header format"}
            )
        
        token = parts[1]
        
        # Verify token
        try:
            payload = jwt_handler.verify_token(token)
        except pyjwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired"}
            )
        except pyjwt.InvalidTokenError as e:
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid token: {str(e)}"}
            )
        
        # Add user to request state
        request.state.user = {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "tenant_id": payload.get("tenant_id")
        }
        
        return await call_next(request)
