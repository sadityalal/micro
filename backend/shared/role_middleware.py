from functools import wraps
from typing import List, Set
from fastapi import Request, HTTPException, status
import asyncio
from .infrastructure_service import infra_service
from .logger_middleware import get_logger

logger = get_logger(__name__)

_permission_cache = {}
_cache_lock = asyncio.Lock()


async def get_cached_permissions(tenant_id: int, user_id: int) -> Set[str]:
    cache_key = f"{tenant_id}:{user_id}"
    async with _cache_lock:
        if cache_key in _permission_cache:
            permissions, expiry = _permission_cache[cache_key]
            if asyncio.get_event_loop().time() < expiry:
                return permissions

        permissions = await _fetch_user_permissions(tenant_id, user_id)
        _permission_cache[cache_key] = (
            permissions,
            asyncio.get_event_loop().time() + 300
        )
        return permissions


async def _fetch_user_permissions(tenant_id: int, user_id: int) -> Set[str]:
    try:
        async with infra_service.get_db_session(tenant_id) as db:
            # FIXED QUERY
            result = await db.execute(
                "SELECT p.name FROM permissions p JOIN role_permissions rp ON p.id = rp.permission_id JOIN user_role_assignments ura ON rp.role_id = ura.role_id WHERE ura.user_id = :user_id",
                {"user_id": user_id}
            )
            return {row.name for row in result.fetchall()}
    except Exception as e:
        logger.error(f"Failed to fetch permissions for user {user_id} (tenant {tenant_id}): {e}")
        return set()


def require_permission(permission: str, allow_superuser: bool = True):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(*args, **kwargs)
            user = getattr(request.state, "user", None)
            tenant_id = getattr(request.state, "tenant_id", 1)
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

            if allow_superuser and _is_superuser(user):
                return await func(*args, **kwargs)

            user_permissions = await get_cached_permissions(tenant_id, user["id"])
            if permission not in user_permissions:
                logger.warning(
                    f"Permission denied: user {user.get('email', user['id'])} "
                    f"(tenant {tenant_id}) missing permission: {permission}"
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
    roles_set = set(roles)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(*args, **kwargs)
            user = getattr(request.state, "user", None)
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

            if allow_superuser and _is_superuser(user):
                return await func(*args, **kwargs)

            user_roles = {role["name"] for role in user.get("roles", [])}
            if not roles_set.intersection(user_roles):
                logger.warning(
                    f"Role denied: user {user.get('email', user['id'])} "
                    f"has roles {user_roles}, required {roles_set}"
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
    permissions_set = set(permissions)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = _extract_request(*args, **kwargs)
            user = getattr(request.state, "user", None)
            tenant_id = getattr(request.state, "tenant_id", 1)
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

            if allow_superuser and _is_superuser(user):
                return await func(*args, **kwargs)

            user_permissions = await get_cached_permissions(tenant_id, user["id"])
            if not permissions_set.intersection(user_permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions (any of required)"
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _extract_request(*args, **kwargs) -> Request:
    for arg in args:
        if isinstance(arg, Request):
            return arg
    for value in kwargs.values():
        if isinstance(value, Request):
            return value
    raise HTTPException(status_code=500, detail="Request object not found")


def _is_superuser(user: dict) -> bool:
    user_roles = {role["name"] for role in user.get("roles", [])}
    return "super_admin" in user_roles or "root" in user_roles


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


async def clear_permission_cache(tenant_id: int, user_id: int = None):
    async with _cache_lock:
        if user_id:
            _permission_cache.pop(f"{tenant_id}:{user_id}", None)
        else:
            keys = [k for k in _permission_cache if k.startswith(f"{tenant_id}:")]
            for k in keys:
                _permission_cache.pop(k, None)