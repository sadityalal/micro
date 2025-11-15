# backend/shared/permissions.py
from functools import wraps
from typing import List, Set, Optional
from fastapi import Request, HTTPException, status
import asyncio
from ..logger import get_logger

logger = get_logger(__name__)

# Cache for permission sets (tenant_id -> permission_set)
_permission_cache = {}
_cache_lock = asyncio.Lock()


async def get_cached_permissions(tenant_id: int, user_id: int) -> Set[str]:
    """Cache user permissions to reduce database load"""
    cache_key = f"{tenant_id}:{user_id}"

    async with _cache_lock:
        if cache_key in _permission_cache:
            permissions, expiry = _permission_cache[cache_key]
            if asyncio.get_event_loop().time() < expiry:
                return permissions

        # Fetch from database (simplified - you'd join with your actual tables)
        permissions = await _fetch_user_permissions(tenant_id, user_id)

        # Cache for 5 minutes
        _permission_cache[cache_key] = (
            permissions,
            asyncio.get_event_loop().time() + 300
        )

        return permissions


async def _fetch_user_permissions(tenant_id: int, user_id: int) -> Set[str]:
    """Fetch user permissions from database"""
    # This would be your actual database query
    # For now, return a mock set
    return {"users:read", "products:read"}  # Replace with actual DB call


def require_permission(permission: str, allow_superuser: bool = True):
    """
    Decorator to require specific permission

    Args:
        permission: The permission string required
        allow_superuser: Whether superusers bypass permission checks
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(*args, **kwargs)
            user = getattr(request.state, "user", None)
            tenant_id = getattr(request.state, "tenant_id", 1)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Superuser bypass (if enabled)
            if allow_superuser and _is_superuser(user):
                return await func(*args, **kwargs)

            # Check permission
            user_permissions = await get_cached_permissions(tenant_id, user["id"])
            if permission not in user_permissions:
                logger.warning(
                    f"Permission denied: user {user['email']} (tenant {tenant_id}) "
                    f"tried to access {permission}. Has: {user_permissions}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "insufficient_permissions",
                        "required": permission,
                        "has": list(user_permissions)
                    }
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(roles: List[str], allow_superuser: bool = True):
    """
    Decorator to require specific role

    Args:
        roles: List of role names that can access
        allow_superuser: Whether superusers bypass role checks
    """
    roles_set = set(roles)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(*args, **kwargs)
            user = getattr(request.state, "user", None)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Superuser bypass (if enabled)
            if allow_superuser and _is_superuser(user):
                return await func(*args, **kwargs)

            # Check role
            user_roles = {role["name"] for role in user.get("roles", [])}
            if not roles_set.intersection(user_roles):
                logger.warning(
                    f"Role denied: user {user['email']} with roles {user_roles} "
                    f"tried to access {roles_set}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "insufficient_roles",
                        "required": list(roles_set),
                        "has": list(user_roles)
                    }
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(permissions: List[str], allow_superuser: bool = True):
    """Require any one of the given permissions"""
    permissions_set = set(permissions)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(*args, **kwargs)
            user = getattr(request.state, "user", None)
            tenant_id = getattr(request.state, "tenant_id", 1)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if allow_superuser and _is_superuser(user):
                return await func(*args, **kwargs)

            user_permissions = await get_cached_permissions(tenant_id, user["id"])
            if not permissions_set.intersection(user_permissions):
                logger.warning(
                    f"Any-permission denied: user {user['email']} "
                    f"tried to access any of {permissions_set}. Has: {user_permissions}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions (any of required)"
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _extract_request(*args, **kwargs) -> Request:
    """Extract Request object from function arguments"""
    for arg in args:
        if isinstance(arg, Request):
            return arg
    for value in kwargs.values():
        if isinstance(value, Request):
            return value
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Request object not found in endpoint arguments"
    )


def _is_superuser(user: dict) -> bool:
    """Check if user has superuser privileges"""
    user_roles = {role["name"] for role in user.get("roles", [])}
    return "super_admin" in user_roles or "root" in user_roles


# Permission groups (now as examples - should come from database in production)
ADMIN_PERMISSIONS = {
    "users:create", "users:read", "users:update", "users:delete",
    "products:create", "products:update", "products:delete",
    "orders:read_all", "orders:update_status", "analytics:view"
}

CUSTOMER_PERMISSIONS = {
    "products:read", "orders:create", "orders:read_own",
    "profile:read", "profile:update", "cart:manage"
}

MANAGER_PERMISSIONS = {
    "products:read", "products:update",
    "orders:read_all", "orders:update_status",
    "analytics:view", "reports:generate"
}


# Clear cache utility (call this when user permissions change)
async def clear_permission_cache(tenant_id: int, user_id: int = None):
    """Clear permission cache for user or entire tenant"""
    async with _cache_lock:
        if user_id:
            cache_key = f"{tenant_id}:{user_id}"
            _permission_cache.pop(cache_key, None)
        else:
            # Clear all for tenant
            keys_to_remove = [k for k in _permission_cache.keys() if k.startswith(f"{tenant_id}:")]
            for key in keys_to_remove:
                _permission_cache.pop(key, None)