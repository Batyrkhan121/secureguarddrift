# api/routes/__init__.py

from fastapi import Request


def get_tenant_id(request: Request) -> str | None:
    """Extract tenant_id from request set by auth middleware.

    Returns the tenant_id string, or None for super_admin.
    Falls back to None when the auth middleware is not active
    (e.g. during tests without authentication).
    """
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    return user.get("tenant_id")
