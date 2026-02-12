"""
RBAC permissions and role checking.
"""
from enum import Enum
from fastapi import Request, HTTPException


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
    """Проверить есть ли у роли указанное разрешение."""
    permissions = ROLE_PERMISSIONS.get(role, [])
    return permission in permissions


def has_permission(user: dict, permission: Permission) -> bool:
    """Проверить есть ли у пользователя разрешение."""
    role = user.get("role", "")
    return check_permission(role, permission)


def require_role(required_role: str):
    """FastAPI dependency для проверки роли."""
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
    """FastAPI dependency для проверки разрешения."""
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
