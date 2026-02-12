#!/bin/bash

# middleware.py
cat > auth/middleware.py << 'EOF'
"""
FastAPI authentication middleware.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import jwt as pyjwt
from auth.jwt_handler import jwt_handler


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки JWT токенов."""
    
    # Публичные эндпоинты без auth
    PUBLIC_PATHS = [
        "/api/health",
        "/",
        "/static",
        "/docs",
        "/openapi.json",
        "/redoc"
    ]
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and check authentication.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
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
                content={"detail": "Invalid Authorization header format. Use: Bearer <token>"}
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
        
        # Continue to next handler
        return await call_next(request)


if __name__ == "__main__":
    print("AuthMiddleware created successfully")
    print(f"Public paths: {AuthMiddleware.PUBLIC_PATHS}")
EOF

# permissions.py
cat > auth/permissions.py << 'EOF'
"""
RBAC permissions and role checking.
"""
from enum import Enum
from fastapi import Request, HTTPException, Depends


class Permission(str, Enum):
    """Доступные разрешения в системе."""
    READ_GRAPH = "read:graph"
    READ_DRIFT = "read:drift"
    READ_REPORT = "read:report"
    WRITE_FEEDBACK = "write:feedback"
    WRITE_WHITELIST = "write:whitelist"
    WRITE_POLICY = "write:policy"
    WRITE_GITOPS = "write:gitops"
    WRITE_INTEGRATIONS = "write:integrations"
    DELETE_WHITELIST = "delete:whitelist"


# Матрица разрешений для ролей
ROLE_PERMISSIONS = {
    "viewer": [
        Permission.READ_GRAPH,
        Permission.READ_DRIFT,
        Permission.READ_REPORT,
    ],
    "operator": [
        Permission.READ_GRAPH,
        Permission.READ_DRIFT,
        Permission.READ_REPORT,
        Permission.WRITE_FEEDBACK,
        Permission.WRITE_WHITELIST,
        Permission.WRITE_POLICY,
    ],
    "admin": [
        Permission.READ_GRAPH,
        Permission.READ_DRIFT,
        Permission.READ_REPORT,
        Permission.WRITE_FEEDBACK,
        Permission.WRITE_WHITELIST,
        Permission.WRITE_POLICY,
        Permission.WRITE_GITOPS,
        Permission.WRITE_INTEGRATIONS,
        Permission.DELETE_WHITELIST,
    ],
}


def check_permission(role: str, permission: Permission) -> bool:
    """
    Проверить есть ли у роли указанное разрешение.
    
    Args:
        role: Роль пользователя
        permission: Требуемое разрешение
        
    Returns:
        True если есть разрешение
    """
    permissions = ROLE_PERMISSIONS.get(role, [])
    return permission in permissions


def has_permission(user: dict, permission: Permission) -> bool:
    """
    Проверить есть ли у пользователя разрешение.
    
    Args:
        user: User dict из request.state.user
        permission: Требуемое разрешение
        
    Returns:
        True если есть разрешение
    """
    role = user.get("role", "")
    return check_permission(role, permission)


def require_role(required_role: str):
    """
    FastAPI dependency для проверки роли.
    
    Args:
        required_role: Минимально требуемая роль
        
    Returns:
        Dependency function
    """
    role_hierarchy = {"viewer": 0, "operator": 1, "admin": 2}
    required_level = role_hierarchy.get(required_role, 0)
    
    def dependency(request: Request):
        if not hasattr(request.state, "user"):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        user = request.state.user
        user_role = user.get("role", "")
        user_level = role_hierarchy.get(user_role, -1)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=403,
                detail=f"Required role: {required_role}, your role: {user_role}"
            )
        
        return user
    
    return dependency


def require_permission(permission: Permission):
    """
    FastAPI dependency для проверки разрешения.
    
    Args:
        permission: Требуемое разрешение
        
    Returns:
        Dependency function
    """
    def dependency(request: Request):
        if not hasattr(request.state, "user"):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        user = request.state.user
        if not has_permission(user, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {permission}"
            )
        
        return user
    
    return dependency


if __name__ == "__main__":
    # Test permissions
    print("Testing RBAC permissions...")
    
    # Viewer permissions
    assert check_permission("viewer", Permission.READ_GRAPH) is True
    assert check_permission("viewer", Permission.WRITE_POLICY) is False
    
    # Operator permissions
    assert check_permission("operator", Permission.WRITE_POLICY) is True
    assert check_permission("operator", Permission.WRITE_GITOPS) is False
    
    # Admin permissions
    assert check_permission("admin", Permission.WRITE_GITOPS) is True
    assert check_permission("admin", Permission.DELETE_WHITELIST) is True
    
    print("All permission tests passed!")
EOF

chmod +x create_week10_files.sh
bash create_week10_files.sh
