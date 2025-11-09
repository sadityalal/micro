from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
import jwt
from passlib.context import CryptContext
import logging
from shared.database import get_db
from shared.schemas import UserRegister, UserLogin, Token, UserResponse
from shared.models import User, UserSession
from shared.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer()

# Password hashing with Argon2
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, settings):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token():
    return str(uuid.uuid4())


@router.post("/register", response_model=UserResponse)
async def register(
        user_data: UserRegister,
        request: Request,
        db: Session = Depends(get_db)
):
    """Register a new user"""
    try:
        tenant_id = request.state.tenant_id
        settings = get_settings(tenant_id)

        # Check if user already exists
        existing_user = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.email == user_data.email
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            tenant_id=tenant_id,
            email=user_data.email,
            password_hash=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            role_id=5,  # Default customer role
            email_verified=False
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"New user registered: {user_data.email} for tenant {tenant_id}")

        return UserResponse(
            id=new_user.id,
            email=new_user.email,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            phone=new_user.phone,
            email_verified=new_user.email_verified,
            role_id=new_user.role_id
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token)
async def login(
        login_data: UserLogin,
        request: Request,
        db: Session = Depends(get_db)
):
    """User login"""
    try:
        tenant_id = request.state.tenant_id
        settings = get_settings(tenant_id)

        # Find user
        user = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.email == login_data.email,
            User.status == 'active'
        ).first()

        if not user or not verify_password(login_data.password, user.password_hash):
            # Update failed login attempts
            if user:
                user.failed_login_attempts += 1
                user.last_failed_login = datetime.utcnow()

                # Lock account if too many failed attempts
                if user.failed_login_attempts >= 5:
                    user.is_locked = True
                    user.locked_until = datetime.utcnow() + timedelta(minutes=30)

                db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Check if account is locked
        if user.is_locked and user.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked due to too many failed attempts"
            )

        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.is_locked = False
        user.last_login = datetime.utcnow()
        user.last_activity = datetime.utcnow()

        # Create session
        access_token = create_access_token(
            {"user_id": user.id, "tenant_id": tenant_id, "email": user.email},
            settings
        )
        refresh_token = create_refresh_token()

        # Save session to database
        user_session = UserSession(
            tenant_id=tenant_id,
            user_id=user.id,
            session_token=access_token,
            refresh_token=refresh_token,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes),
            refresh_token_expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
        )

        db.add(user_session)
        db.commit()

        logger.info(f"User logged in: {user.email} for tenant {tenant_id}")

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/logout")
async def logout(
        request: Request,
        db: Session = Depends(get_db)
):
    """User logout"""
    try:
        tenant_id = request.state.tenant_id
        auth_header = request.headers.get("authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

            # Invalidate session
            session = db.query(UserSession).filter(
                UserSession.tenant_id == tenant_id,
                UserSession.session_token == token,
                UserSession.is_active == True
            ).first()

            if session:
                session.is_active = False
                db.commit()
                logger.info(f"User logged out: session {session.id}")

        return {"message": "Logged out successfully"}

    except Exception as e:
        db.rollback()
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(
        request: Request,
        db: Session = Depends(get_db)
):
    """Refresh access token"""
    try:
        tenant_id = request.state.tenant_id
        settings = get_settings(tenant_id)
        refresh_token = request.headers.get("x-refresh-token")

        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token required"
            )

        # Find active session with refresh token
        session = db.query(UserSession).filter(
            UserSession.tenant_id == tenant_id,
            UserSession.refresh_token == refresh_token,
            UserSession.is_active == True,
            UserSession.refresh_token_expires_at > datetime.utcnow()
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        user = db.query(User).filter(User.id == session.user_id).first()
        if not user or user.status != 'active':
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Create new tokens
        new_access_token = create_access_token(
            {"user_id": user.id, "tenant_id": tenant_id, "email": user.email},
            settings
        )
        new_refresh_token = create_refresh_token()

        # Update session
        session.session_token = new_access_token
        session.refresh_token = new_refresh_token
        session.expires_at = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        session.refresh_token_expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
        session.last_used_at = datetime.utcnow()

        db.commit()

        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
        request: Request,
        db: Session = Depends(get_db)
):
    """Get current user info"""
    try:
        tenant_id = request.state.tenant_id
        auth_header = request.headers.get("authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        token = auth_header.split(" ")[1]
        settings = get_settings(tenant_id)

        # Verify token
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("user_id")
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        # Check session
        session = db.query(UserSession).filter(
            UserSession.tenant_id == tenant_id,
            UserSession.session_token == token,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session"
            )

        # Get user
        user = db.query(User).filter(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.status == 'active'
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Update last activity
        user.last_activity = datetime.utcnow()
        session.last_used_at = datetime.utcnow()
        db.commit()

        return UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            email_verified=user.email_verified,
            role_id=user.role_id
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Get user failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user info"
        )