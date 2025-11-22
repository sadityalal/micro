from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shared.database.connection import get_db, get_redis
from shared.database.repositories.user_repository import UserRepository
from shared.database.repositories.tenant_repository import TenantRepository
from shared.schemas.auth import (
    UserLogin, UserCreate, Token, UserResponse,
    PasswordResetRequest, PasswordResetConfirm, ChangePassword
)
from .auth import AuthService
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
    # Determine tenant ID
    tenant_id = None
    if user_login.tenant_domain:
        tenant_repo = TenantRepository(db)
        tenant = tenant_repo.get_tenant_by_domain(user_login.tenant_domain)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        tenant_id = tenant.id

    # First, check if user exists to get user_id for logging
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_email(user_login.email, tenant_id)

    # Authenticate user
    user_data = auth_service.authenticate_user(
        user_login.email,
        user_login.password,
        tenant_id
    )

    if not user_data:
        # Log failed login attempt - we know the attempted email and user_id if user exists
        user_repo.log_login_attempt({
            "user_id": user.id if user else None,  # user.id if user exists, None if not
            "attempted_email": user_login.email,  # Always log the attempted email
            "tenant_id": tenant_id,
            "ip_address": request.client.host,
            "device_info": {"user_agent": request.headers.get("user-agent")},
            "status": "failed"
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log successful login
    user_repo.log_login_attempt({
        "user_id": user_data["id"],
        "attempted_email": user_login.email,  # Log email for successful attempts too
        "tenant_id": tenant_id,
        "ip_address": request.client.host,
        "device_info": {"user_agent": request.headers.get("user-agent")},
        "status": "success"
    })

    # Create tokens
    tokens = auth_service.create_tokens(user_data, tenant_id or user_data["tenant_id"])
    return tokens


@router.post("/register", response_model=UserResponse)
async def register(
        user_create: UserCreate,
        auth_service: AuthService = Depends(get_auth_service),
        db: Session = Depends(get_db)
):
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)

    # Check if user already exists
    existing_user = user_repo.get_user_by_email(user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Determine tenant
    tenant_id = None
    if user_create.tenant_domain:
        tenant = tenant_repo.get_tenant_by_domain(user_create.tenant_domain)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        tenant_id = tenant.id

    # Create user
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

    # Add user to tenant with default role (customer)
    if tenant_id:
        user_repo.add_to_tenant(tenant_id, user.id, 4)  # 4 = customer role ID

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
        refresh_token: str,
        tenant_id: int,
        auth_service: AuthService = Depends(get_auth_service)
):
    token_data = auth_service.validate_refresh_token(refresh_token, tenant_id)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get fresh user data
    db = next(get_db())
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(token_data.user_id)
    if not user:
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

    # Create new tokens
    tokens = auth_service.create_tokens(user_data, tenant_id)
    return tokens


@router.post("/verify")
async def verify_token(
    token: str = Body(...),      # Get from JSON body
    tenant_id: int = Body(...),  # Get from JSON body
    auth_service: AuthService = Depends(get_auth_service)
):
    """Verify JWT token and return user data"""
    token_data = auth_service.verify_token(token, tenant_id)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    # Get fresh user data
    db = next(get_db())
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(token_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
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
        db: Session = Depends(get_db)
):
    token = credentials.credentials
    tenant_repo = TenantRepository(db)

    # For simplicity, we'll get tenant_id from token
    # In production, you might want to pass tenant_id explicitly
    tenants = tenant_repo.get_all_active_tenants()

    token_data = None
    for tenant in tenants:
        token_data = auth_service.verify_token(token, tenant.id)
        if token_data:
            break

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # Revoke refresh token
    auth_service.revoke_refresh_token(token_data.user_id, token_data.tenant_id)

    return {"message": "Successfully logged out"}


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auth-service"}