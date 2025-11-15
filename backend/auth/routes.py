from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
import time
import jwt
import bcrypt
import secrets
from typing import Dict, Any

from shared import (
    auth_middleware, create_session, destroy_session,
    set_session_cookie, delete_session_cookie, require_permission,
    get_logger, infra_service, password_policy, get_tenant_config
)

logger = get_logger(__name__)
router = APIRouter()


@router.post("/register")
async def register_user(request: Request):
    try:
        body = await request.json()
        email = body.get("email")
        password = body.get("password")
        first_name = body.get("first_name")
        last_name = body.get("last_name")
        tenant_id = request.headers.get("x-tenant-id", 1)

        if not all([email, password, first_name, last_name]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Validate password
        password_validation = await password_policy.validate_password(
            password, tenant_id, {
                'email': email,
                'first_name': first_name,
                'last_name': last_name
            }
        )
        if not password_validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail={"error": "password_validation_failed", "issues": password_validation["errors"]}
            )

        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        async with infra_service.get_db_session(tenant_id) as db:
            # Check if user exists
            result = await db.execute(
                "SELECT id FROM users WHERE email = :email",
                {"email": email}
            )
            if result.fetchone():
                raise HTTPException(status_code=400, detail="User already exists")

            # Create user
            result = await db.execute(
                "INSERT INTO users (email, password_hash, first_name, last_name, tenant_id) "
                "VALUES (:email, :password_hash, :first_name, :last_name, :tenant_id) "
                "RETURNING id",
                {
                    "email": email,
                    "password_hash": password_hash,
                    "first_name": first_name,
                    "last_name": last_name,
                    "tenant_id": tenant_id
                }
            )
            user_id = result.fetchone().id

            # Assign default role (customer)
            await db.execute(
                "INSERT INTO user_role_assignments (user_id, role_id, assigned_by) "
                "VALUES (:user_id, (SELECT id FROM user_roles WHERE name = 'customer'), :user_id)",
                {"user_id": user_id}
            )

            await db.commit()

        logger.info(f"User registered: {email} (tenant: {tenant_id})")
        return {"message": "User registered successfully", "user_id": user_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login")
async def login_user(request: Request):
    try:
        body = await request.json()
        email = body.get("email")
        password = body.get("password")
        tenant_id = request.headers.get("x-tenant-id", 1)

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")

        async with infra_service.get_db_session(tenant_id) as db:
            # Get user with password
            result = await db.execute(
                "SELECT id, email, password_hash, first_name, last_name FROM users WHERE email = :email",
                {"email": email}
            )
            user = result.fetchone()

            if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            # Get user roles
            roles_result = await db.execute(
                "SELECT r.name FROM user_roles r JOIN user_role_assignments ura ON r.id = ura.role_id WHERE ura.user_id = :user_id",
                {"user_id": user.id}
            )
            roles = [row.name for row in roles_result.fetchall()]

            # Create session
            session_data = await create_session(
                tenant_id=tenant_id,
                user_id=user.id,
                user_agent=request.headers.get("user-agent", ""),
                ip_address=request.client.host
            )

            # Generate JWT token
            tenant_config = await get_tenant_config(tenant_id)
            jwt_secret = tenant_config.get("security", {}).get("jwt_secret_key", "fallback-secret")

            token_payload = {
                "sub": str(user.id),
                "email": user.email,
                "roles": roles,
                "exp": time.time() + 3600,  # 1 hour
                "type": "access",
                "jti": secrets.token_urlsafe(16)
            }
            access_token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")

            response_data = {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "roles": roles
                }
            }

            # Set session cookie
            response = Response(content=response_data)
            set_session_cookie(response, session_data["id"])

            logger.info(f"User logged in: {email} (tenant: {tenant_id})")
            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/logout")
async def logout_user(request: Request):
    try:
        tenant_id = getattr(request.state, "tenant_id", 1)
        session = getattr(request.state, "session", None)

        if session and session.get("id"):
            await destroy_session(tenant_id, session["id"])

        # Revoke JWT token if present
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                tenant_config = await get_tenant_config(tenant_id)
                jwt_secret = tenant_config.get("security", {}).get("jwt_secret_key", "fallback-secret")
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                jti = payload.get("jti")
                if jti:
                    redis_client = await infra_service.get_redis_client(tenant_id, "cache")
                    await redis_client.setex(f"revoked_token:{jti}", 3600, "1")
            except:
                pass

        response = Response(content={"message": "Logged out successfully"})
        delete_session_cookie(response)

        logger.info(f"User logged out (tenant: {tenant_id})")
        return response

    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


@router.get("/me")
async def get_current_user(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {"user": user}


@router.post("/refresh")
async def refresh_token(request: Request):
    # Implementation for token refresh
    return {"message": "Token refresh endpoint"}