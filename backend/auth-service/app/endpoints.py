from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shared.database.connection import get_db, get_redis
from shared.database.repositories.user_repository import UserRepository
from shared.database.repositories.tenant_repository import TenantRepository
from shared.schemas.auth import (
    UserLogin, UserCreate, Token, UserResponse,
    PasswordResetRequest, PasswordResetConfirm, ChangePassword
)
from .auth import AuthService
from shared.logger import auth_service_logger
from sqlalchemy.orm import Session
import redis

router = APIRouter()
security = HTTPBearer()

def get_auth_service(db: Session = Depends(get_db), redis_client: redis.Redis = Depends(get_redis)) -> AuthService:
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    return AuthService(user_repo, tenant_repo, redis_client)

@router.post("/login", response_model=Token)
async def login(
        user_login: UserLogin,
        request: Request,
        auth_service: AuthService = Depends(get_auth_service),
        db: Session = Depends(get_db)
):
    auth_service_logger.info(
        "Login attempt started",
        extra={
            "email": user_login.email,
            "tenant_domain": user_login.tenant_domain,
            "client_ip": request.client.host
        }
    )
    
    tenant_id = None
    if user_login.tenant_domain:
        tenant_repo = TenantRepository(db)
        tenant = tenant_repo.get_tenant_by_domain(user_login.tenant_domain)
        if not tenant:
            auth_service_logger.warning(
                "Login failed - tenant not found",
                extra={"domain": user_login.tenant_domain}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        tenant_id = tenant.id

    user_repo = UserRepository(db)
    user = user_repo.get_user_by_email(user_login.email, tenant_id)
    
    user_data = auth_service.authenticate_user(
        user_login.email,
        user_login.password,
        tenant_id
    )
    
    if not user_data:
        user_repo.log_login_attempt({
            "user_id": user.id if user else None,
            "attempted_email": user_login.email,
            "tenant_id": tenant_id,
            "ip_address": request.client.host,
            "device_info": {"user_agent": request.headers.get("user-agent")},
            "status": "failed"
        })
        auth_service_logger.warning(
            "Login failed - invalid credentials",
            extra={
                "email": user_login.email,
                "tenant_id": tenant_id,
                "client_ip": request.client.host
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_repo.log_login_attempt({
        "user_id": user_data["id"],
        "attempted_email": user_login.email,
        "tenant_id": tenant_id,
        "ip_address": request.client.host,
        "device_info": {"user_agent": request.headers.get("user-agent")},
        "status": "success"
    })
    
    tokens = await auth_service.create_tokens(user_data, tenant_id or user_data["tenant_id"], request)
    
    auth_service_logger.info(
        "Login successful",
        extra={
            "user_id": user_data["id"],
            "email": user_data["email"],
            "tenant_id": tenant_id,
            "roles": user_data["roles"],
            "permissions": user_data["permissions"]
        }
    )
    
    return tokens

@router.post("/register", response_model=UserResponse)
async def register(
        user_create: UserCreate,
        auth_service: AuthService = Depends(get_auth_service),
        db: Session = Depends(get_db)
):
    auth_service_logger.info(
        "User registration attempt",
        extra={
            "email": user_create.email,
            "tenant_domain": user_create.tenant_domain,
            "first_name": user_create.first_name
        }
    )
    
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    
    existing_user = user_repo.get_user_by_email(user_create.email)
    if existing_user:
        auth_service_logger.warning(
            "Registration failed - user already exists",
            extra={"email": user_create.email}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    tenant_id = None
    if user_create.tenant_domain:
        tenant = tenant_repo.get_tenant_by_domain(user_create.tenant_domain)
        if not tenant:
            auth_service_logger.warning(
                "Registration failed - tenant not found",
                extra={"domain": user_create.tenant_domain}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        tenant_id = tenant.id
    
    hashed_password = auth_service.get_password_hash(user_create.password)
    user_data = {
        "first_name": user_create.first_name,
        "last_name": user_create.last_name,
        "email": user_create.email,
        "phone": user_create.phone,
        "password_hash": hashed_password,
        "tenant_id": tenant_id
    }
    
    user = user_repo.create_user(user_data)
    
    if tenant_id:
        user_repo.add_to_tenant(tenant_id, user.id, 4)
    
    auth_service_logger.info(
        "User registration successful",
        extra={
            "user_id": user.id,
            "email": user.email,
            "tenant_id": tenant_id
        }
    )
    
    return UserResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        tenant_id=user.tenant_id,
        created_at=user.created_at
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(
        refresh_token: str = Body(...),
        tenant_id: int = Body(...),
        auth_service: AuthService = Depends(get_auth_service)
):
    auth_service_logger.info(
        "Token refresh attempt",
        extra={"tenant_id": tenant_id}
    )
    
    token_data = auth_service.validate_refresh_token(refresh_token, tenant_id)
    if not token_data:
        auth_service_logger.warning(
            "Token refresh failed - invalid refresh token",
            extra={"tenant_id": tenant_id}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    db = next(get_db())
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(token_data.user_id)
    if not user:
        auth_service_logger.warning(
            "Token refresh failed - user not found",
            extra={"user_id": token_data.user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user_data = {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "tenant_id": user.tenant_id,
        "roles": token_data.roles,
        "permissions": token_data.permissions
    }
    
    tokens = await auth_service.create_tokens(user_data, tenant_id)
    
    auth_service_logger.info(
        "Token refresh successful",
        extra={
            "user_id": user.id,
            "tenant_id": tenant_id
        }
    )
    
    return tokens

@router.post("/verify")
async def verify_token(
        token: str = Body(...),
        tenant_id: int = Body(...),
        auth_service: AuthService = Depends(get_auth_service)
):
    auth_service_logger.info(
        "Token verification attempt",
        extra={"tenant_id": tenant_id}
    )
    
    token_data = auth_service.verify_token(token, tenant_id)
    if not token_data:
        auth_service_logger.warning(
            "Token verification failed - invalid token",
            extra={"tenant_id": tenant_id}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    db = next(get_db())
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(token_data.user_id)
    if not user:
        auth_service_logger.warning(
            "Token verification failed - user not found",
            extra={"user_id": token_data.user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    auth_service_logger.info(
        "Token verification successful",
        extra={
            "user_id": user.id,
            "email": user.email,
            "tenant_id": tenant_id
        }
    )
    
    return {
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "tenant_id": user.tenant_id,
        "roles": token_data.roles,
        "permissions": token_data.permissions
    }

@router.post("/logout")
async def logout(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        auth_service: AuthService = Depends(get_auth_service),
        db: Session = Depends(get_db),
        response: Response = None
):
    token = credentials.credentials
    auth_service_logger.info("Logout attempt")
    
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    token_data = None
    
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        auth_service_logger.warning("Logout failed - invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    await auth_service.logout_user(token_data.user_id, token_data.tenant_id, token)
    
    auth_service_logger.info(
        "Logout successful",
        extra={
            "user_id": token_data.user_id,
            "tenant_id": token_data.tenant_id
        }
    )
    
    # Return proper JSON response instead of empty response
    return {"message": "Successfully logged out"}

@router.get("/admin/management")
async def admin_management(
        request: Request,
        db: Session = Depends(get_db),
        credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    auth_service_logger.info("Admin management access attempt")
    
    tenant_repo = TenantRepository(db)
    tenants = tenant_repo.get_all_active_tenants()
    token_data = None
    
    for tenant in tenants:
        auth_service = get_auth_service(db, get_redis())
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break
    
    if not token_data:
        auth_service_logger.warning("Admin access denied - invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_roles = token_data.roles
    if "admin" in user_roles or "super_admin" in user_roles:
        auth_service_logger.info(
            "Admin management access granted",
            extra={
                "user_id": token_data.user_id,
                "tenant_id": token_data.tenant_id,
                "roles": user_roles
            }
        )
        return {
            "message": "Admin Management Panel",
            "user_id": token_data.user_id,
            "tenant_id": token_data.tenant_id,
            "roles": user_roles,
            "management_data": {
                "user_management": True,
                "content_management": True,
                "reports_access": True
            }
        }
    else:
        auth_service_logger.warning(
            "Admin management access denied - insufficient permissions",
            extra={
                "user_id": token_data.user_id,
                "roles": user_roles
            }
        )
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Admin or Super Admin access required."
        )

@router.get("/health")
async def health_check():
    auth_service_logger.debug("Health check performed")
    return {"status": "healthy", "service": "auth-service"}
