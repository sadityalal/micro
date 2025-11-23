from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from shared.database.connection import get_db, get_redis
from shared.database.repositories.user_repository import UserRepository
from shared.database.repositories.tenant_repository import TenantRepository
from shared.security.session_manager import SessionManager, SessionData
from shared.logger import auth_service_logger
from .auth import AuthService

router = APIRouter()
security = HTTPBearer()

# Pydantic models for admin requests/responses
class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class RoleAssignmentRequest(BaseModel):
    user_id: int
    role_id: int

class UserResponseExtended(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    tenant_id: Optional[int]
    is_active: bool
    created_at: str
    last_login: Optional[str]
    roles: List[str]

class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_sessions: int
    login_attempts_24h: int
    failed_logins_24h: int

class SessionResponse(BaseModel):
    session_id: str
    user_id: int
    tenant_id: int
    created_at: str
    last_accessed: str
    expires_at: str
    user_agent: Optional[str]
    ip_address: Optional[str]
    roles: List[str]

def get_admin_auth_service(
    db: Session = Depends(get_db), 
    redis_client = Depends(get_redis)
) -> AuthService:
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    return AuthService(user_repo, tenant_repo, redis_client)

@router.get("/admin/users", response_model=List[UserResponseExtended])
async def get_all_users(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_admin_auth_service)
):
    auth_service_logger.info("Admin users list access attempt")
    
    # Verify admin access
    token = credentials.credentials
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    
    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user_repo = UserRepository(db)
    users = user_repo.get_all_users(skip=skip, limit=limit)
    
    extended_users = []
    for user in users:
        roles = user_repo.get_user_roles(user.id)
        extended_users.append(UserResponseExtended(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone=user.phone,
            tenant_id=user.tenant_id,
            is_active=True,
            created_at=user.created_at.isoformat() if user.created_at else "",
            last_login=None,
            roles=roles
        ))
    
    auth_service_logger.info(
        "Admin users list accessed",
        extra={
            "admin_user_id": token_data.user_id,
            "users_returned": len(extended_users)
        }
    )
    
    return extended_users

@router.get("/admin/users/{user_id}", response_model=UserResponseExtended)
async def get_user_details(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_admin_auth_service)
):
    auth_service_logger.info(f"Admin user details access attempt for user {user_id}")
    
    token = credentials.credentials
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    
    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    roles = user_repo.get_user_roles(user.id)
    
    auth_service_logger.info(
        "Admin user details accessed",
        extra={
            "admin_user_id": token_data.user_id,
            "target_user_id": user_id
        }
    )
    
    return UserResponseExtended(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        tenant_id=user.tenant_id,
        is_active=True,
        created_at=user.created_at.isoformat() if user.created_at else "",
        last_login=None,
        roles=roles
    )

@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: int,
    user_update: UserUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_admin_auth_service)
):
    auth_service_logger.info(f"Admin user update attempt for user {user_id}")
    
    token = credentials.credentials
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    
    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user fields
    update_data = {}
    if user_update.first_name is not None:
        update_data["first_name"] = user_update.first_name
    if user_update.last_name is not None:
        update_data["last_name"] = user_update.last_name
    if user_update.email is not None:
        update_data["email"] = user_update.email
    if user_update.phone is not None:
        update_data["phone"] = user_update.phone
    
    if update_data:
        user_repo.update_user(user_id, update_data)
    
    auth_service_logger.info(
        "Admin user updated",
        extra={
            "admin_user_id": token_data.user_id,
            "target_user_id": user_id,
            "updated_fields": list(update_data.keys())
        }
    )
    
    return {"message": "User updated successfully"}

@router.post("/admin/users/{user_id}/roles")
async def assign_role_to_user(
    user_id: int,
    role_assignment: RoleAssignmentRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_admin_auth_service)
):
    auth_service_logger.info(f"Admin role assignment attempt for user {user_id}")
    
    token = credentials.credentials
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    
    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user_repo = UserRepository(db)
    
    # Check if user exists
    user = user_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if role exists
    role = user_repo.get_role_by_id(role_assignment.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Assign role to user
    user_repo.assign_role_to_user(user_id, role_assignment.role_id, token_data.user_id)
    
    auth_service_logger.info(
        "Admin role assigned to user",
        extra={
            "admin_user_id": token_data.user_id,
            "target_user_id": user_id,
            "role_id": role_assignment.role_id
        }
    )
    
    return {"message": "Role assigned successfully"}

@router.get("/admin/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_admin_auth_service)
):
    auth_service_logger.info("Admin stats access attempt")
    
    token = credentials.credentials
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    
    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user_repo = UserRepository(db)
    
    # Get basic stats
    total_users = user_repo.get_total_users_count()
    active_users = user_repo.get_active_users_count()
    login_attempts_24h = user_repo.get_login_attempts_count(hours=24)
    failed_logins_24h = user_repo.get_failed_login_attempts_count(hours=24)
    
    # Get session count from Redis
    redis_client = get_redis()
    session_keys = redis_client.keys("session:*")
    total_sessions = len(session_keys) if session_keys else 0
    
    auth_service_logger.info(
        "Admin stats accessed",
        extra={
            "admin_user_id": token_data.user_id
        }
    )
    
    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_sessions=total_sessions,
        login_attempts_24h=login_attempts_24h,
        failed_logins_24h=failed_logins_24h
    )

@router.get("/admin/login-history")
async def get_login_history(
    user_id: Optional[int] = None,
    hours: int = 24,
    skip: int = 0,
    limit: int = 100,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_admin_auth_service)
):
    auth_service_logger.info("Admin login history access attempt")
    
    token = credentials.credentials
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    
    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user_repo = UserRepository(db)
    login_history = user_repo.get_login_history(
        user_id=user_id,
        hours=hours,
        skip=skip,
        limit=limit
    )
    
    auth_service_logger.info(
        "Admin login history accessed",
        extra={
            "admin_user_id": token_data.user_id,
            "user_id_filter": user_id,
            "hours": hours
        }
    )
    
    return login_history

@router.get("/admin/users/{user_id}/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_admin_auth_service)
):
    auth_service_logger.info(f"Admin user sessions access attempt for user {user_id}")
    
    token = credentials.credentials
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    
    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user sessions
    sessions = await auth_service.get_user_sessions(user_id, user.tenant_id or 1)
    
    session_responses = []
    for session in sessions:
        session_responses.append(SessionResponse(
            session_id=session.session_id,
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            created_at=datetime.fromtimestamp(session.created_at).isoformat(),
            last_accessed=datetime.fromtimestamp(session.last_accessed).isoformat(),
            expires_at=datetime.fromtimestamp(session.expires_at).isoformat(),
            user_agent=session.user_agent,
            ip_address=session.ip_address,
            roles=session.roles
        ))
    
    auth_service_logger.info(
        "Admin user sessions accessed",
        extra={
            "admin_user_id": token_data.user_id,
            "target_user_id": user_id,
            "sessions_count": len(session_responses)
        }
    )
    
    return session_responses

@router.delete("/admin/users/{user_id}/sessions")
async def terminate_user_sessions(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_admin_auth_service)
):
    auth_service_logger.info(f"Admin terminate user sessions attempt for user {user_id}")
    
    token = credentials.credentials
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    
    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Terminate all user sessions
    await auth_service.session_manager.delete_user_sessions(user_id, user.tenant_id or 1)
    
    auth_service_logger.info(
        "Admin terminated user sessions",
        extra={
            "admin_user_id": token_data.user_id,
            "target_user_id": user_id
        }
    )
    
    return {"message": "All user sessions terminated successfully"}
