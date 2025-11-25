from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import redis
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from shared.database.connection import get_db, get_redis
from shared.database.repositories.user_repository import UserRepository
from shared.logger import setup_logger
from shared.security.session_manager import SessionManager
from .schemas import (
    UserProfileResponse, UserProfileUpdate, PasswordChangeRequest,
    AddressCreate, AddressResponse, AddressUpdate, UserPreferences,
    SessionResponse, LoginHistoryResponse, AccountDeactivationRequest,
    ConsentRequest, DataDeletionRequest, NotificationType, 
    NotificationPreference, UserNotificationPreferences
)
router = APIRouter()
security = HTTPBearer()
logger = setup_logger("user-routes")
ph = PasswordHasher()

def get_user_repository(db: Session = Depends(get_db)):
    return UserRepository(db)

def get_session_manager():
    redis_client = get_redis()
    return SessionManager(redis_client)

def get_client_ip(request: Request) -> str:
    return request.client.host

def get_user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "")

def log_audit_event(
    user_id: int,
    action: str,
    resource_type: str = None,
    resource_id: int = None,
    old_values: dict = None,
    new_values: dict = None,
    ip_address: str = None,
    user_agent: str = None
):
    logger.info(
        "Audit event",
        extra={
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "old_values": old_values,
            "new_values": new_values,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
    )

@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository)
):
    user_id = request.state.user_id
    user = user_repo.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found or account deactivated")
    logger.info("User profile retrieved", extra={"user_id": user_id})
    return UserProfileResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        username=user.username,
        phone=user.phone,
        tenant_id=user.tenant_id,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    request: Request,
    profile_update: UserProfileUpdate,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    user = user_repo.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found or account deactivated")
    old_values = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'phone': user.phone,
        'username': user.username
    }
    if profile_update.email and profile_update.email != user.email:
        existing_user = user_repo.get_user_by_email(profile_update.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=400, detail="Email already taken")
    if profile_update.username and profile_update.username != user.username:
        existing_user = user_repo.get_user_by_username(profile_update.username)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=400, detail="Username already taken")
    update_data = {}
    if profile_update.first_name is not None:
        update_data["first_name"] = profile_update.first_name
    if profile_update.last_name is not None:
        update_data["last_name"] = profile_update.last_name
    if profile_update.email is not None:
        update_data["email"] = profile_update.email
    if profile_update.phone is not None:
        update_data["phone"] = profile_update.phone
    if profile_update.username is not None:
        update_data["username"] = profile_update.username
    if update_data:
        user_repo.update_user(user_id, update_data)
        user = user_repo.get_user_by_id(user_id)
        log_audit_event(
            user_id=user_id,
            action="profile_update",
            resource_type="user",
            resource_id=user_id,
            old_values=old_values,
            new_values=update_data,
            ip_address=ip_address,
            user_agent=user_agent
        )
    logger.info("User profile updated", extra={"user_id": user_id, "updated_fields": list(update_data.keys())})
    return UserProfileResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        username=user.username,
        phone=user.phone,
        tenant_id=user.tenant_id,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

@router.put("/password")
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    user = user_repo.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found or account deactivated")
    new_hashed_password = ph.hash(password_data.new_password)
    user_repo.update_user_password(user_id, new_hashed_password)
    log_audit_event(
        user_id=user_id,
        action="password_change",
        resource_type="user",
        resource_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("Password changed successfully", extra={"user_id": user_id})
    return {"message": "Password changed successfully"}

@router.post("/deactivate")
async def deactivate_account(
    request: Request,
    deactivation_data: AccountDeactivationRequest,
    background_tasks: BackgroundTasks,
    user_repo: UserRepository = Depends(get_user_repository),
    session_manager: SessionManager = Depends(get_session_manager),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    tenant_id = request.state.tenant_id
    user_repo.update_user(user_id, {"is_active": False})
    session_manager.delete_user_sessions(user_id, tenant_id)
    reactivation_deadline = datetime.utcnow() + timedelta(days=30)
    log_audit_event(
        user_id=user_id,
        action="account_deactivated",
        resource_type="user",
        resource_id=user_id,
        new_values={"reason": deactivation_data.reason, "reactivation_deadline": reactivation_deadline.isoformat()},
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("User account deactivated", extra={
        "user_id": user_id,
        "reason": deactivation_data.reason,
        "reactivation_deadline": reactivation_deadline.isoformat()
    })
    return {
        "message": "Account deactivated successfully",
        "reactivation_possible_until": reactivation_deadline.isoformat()
    }

@router.post("/reactivate")
async def reactivate_account(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    user = user_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user_repo.update_user(user_id, {"is_active": True})
    log_audit_event(
        user_id=user_id,
        action="account_reactivated",
        resource_type="user",
        resource_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("User account reactivated", extra={"user_id": user_id})
    return {"message": "Account reactivated successfully"}

@router.post("/delete-account")
async def request_account_deletion(
    request: Request,
    deletion_request: DataDeletionRequest,
    background_tasks: BackgroundTasks,
    user_repo: UserRepository = Depends(get_user_repository),
    session_manager: SessionManager = Depends(get_session_manager),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    tenant_id = request.state.tenant_id
    scheduled_for = datetime.utcnow() + timedelta(days=14)
    deletion_req = user_repo.create_data_deletion_request(
        user_id=user_id,
        deletion_type=deletion_request.deletion_type,
        scheduled_for=scheduled_for,
        reason=deletion_request.reason
    )
    user_repo.update_user(user_id, {"is_active": False})
    session_manager.delete_user_sessions(user_id, tenant_id)
    log_audit_event(
        user_id=user_id,
        action="account_deletion_requested",
        resource_type="user",
        resource_id=user_id,
        new_values={
            "deletion_type": deletion_request.deletion_type,
            "scheduled_for": scheduled_for.isoformat(),
            "reason": deletion_request.reason
        },
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("Account deletion requested", extra={
        "user_id": user_id,
        "deletion_type": deletion_request.deletion_type,
        "scheduled_for": scheduled_for.isoformat()
    })
    return {
        "message": "Account deletion scheduled",
        "deletion_scheduled_for": scheduled_for.isoformat(),
        "cancellation_possible_until": (datetime.utcnow() + timedelta(days=7)).isoformat()
    }

@router.post("/cancel-deletion")
async def cancel_account_deletion(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    user_repo.update_user(user_id, {"is_active": True})
    log_audit_event(
        user_id=user_id,
        action="account_deletion_cancelled",
        resource_type="user",
        resource_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("Account deletion cancelled", extra={"user_id": user_id})
    return {"message": "Account deletion cancelled successfully"}

@router.get("/addresses", response_model=List[AddressResponse])
async def get_addresses(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository)
):
    user_id = request.state.user_id
    addresses = user_repo.get_user_addresses(user_id)
    address_responses = []
    for address in addresses:
        address_responses.append(AddressResponse(
            id=address.id,
            type=address.type,
            address_line1=address.address_line1,
            address_line2=address.address_line2,
            city=address.city,
            state=address.state,
            country=address.country,
            postal_code=address.postal_code,
            is_default=address.is_default,
            created_at=address.created_at,
            updated_at=address.updated_at
        ))
    logger.info("User addresses retrieved", extra={"user_id": user_id, "address_count": len(addresses)})
    return address_responses

@router.post("/addresses", response_model=AddressResponse)
async def create_address(
    request: Request,
    address_data: AddressCreate,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    address = user_repo.create_address(user_id, address_data.dict())
    log_audit_event(
        user_id=user_id,
        action="address_created",
        resource_type="address",
        resource_id=address.id,
        new_values=address_data.dict(),
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("Address created", extra={"user_id": user_id, "address_id": address.id})
    return AddressResponse(
        id=address.id,
        type=address.type,
        address_line1=address.address_line1,
        address_line2=address.address_line2,
        city=address.city,
        state=address.state,
        country=address.country,
        postal_code=address.postal_code,
        is_default=address.is_default,
        created_at=address.created_at,
        updated_at=address.updated_at
    )

@router.put("/addresses/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: int,
    address_update: AddressUpdate,
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    old_address = user_repo.get_address_by_id(address_id, user_id)
    if not old_address:
        raise HTTPException(status_code=404, detail="Address not found")
    old_values = {
        'type': old_address.type,
        'address_line1': old_address.address_line1,
        'address_line2': old_address.address_line2,
        'city': old_address.city,
        'state': old_address.state,
        'country': old_address.country,
        'postal_code': old_address.postal_code,
        'is_default': old_address.is_default
    }
    address = user_repo.update_address(address_id, user_id, address_update.dict(exclude_unset=True))
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    log_audit_event(
        user_id=user_id,
        action="address_updated",
        resource_type="address",
        resource_id=address_id,
        old_values=old_values,
        new_values=address_update.dict(exclude_unset=True),
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("Address updated", extra={"user_id": user_id, "address_id": address_id})
    return AddressResponse(
        id=address.id,
        type=address.type,
        address_line1=address.address_line1,
        address_line2=address.address_line2,
        city=address.city,
        state=address.state,
        country=address.country,
        postal_code=address.postal_code,
        is_default=address.is_default,
        created_at=address.created_at,
        updated_at=address.updated_at
    )

@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: int,
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    success = user_repo.delete_address(address_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Address not found")
    log_audit_event(
        user_id=user_id,
        action="address_deleted",
        resource_type="address",
        resource_id=address_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("Address deleted", extra={"user_id": user_id, "address_id": address_id})
    return {"message": "Address deleted successfully"}

@router.put("/addresses/{address_id}/default")
async def set_default_address(
    address_id: int,
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    success = user_repo.set_default_address(address_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Address not found")
    log_audit_event(
        user_id=user_id,
        action="address_set_default",
        resource_type="address",
        resource_id=address_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("Address set as default", extra={"user_id": user_id, "address_id": address_id})
    return {"message": "Address set as default successfully"}

@router.get("/sessions", response_model=List[SessionResponse])
async def get_sessions(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager)
):
    user_id = request.state.user_id
    tenant_id = request.state.tenant_id
    sessions = session_manager.get_active_user_sessions(user_id, tenant_id)
    session_responses = []
    for session in sessions:
        session_responses.append(SessionResponse(
            session_id=session.session_id,
            created_at=datetime.fromtimestamp(session.created_at).isoformat(),
            last_accessed=datetime.fromtimestamp(session.last_accessed).isoformat(),
            expires_at=datetime.fromtimestamp(session.expires_at).isoformat(),
            user_agent=session.user_agent,
            ip_address=session.ip_address
        ))
    logger.info("User sessions retrieved", extra={"user_id": user_id, "session_count": len(sessions)})
    return session_responses

@router.delete("/sessions/{session_id}")
async def terminate_session(
    session_id: str,
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    session = session_manager.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    session_manager.delete_session(session_id)
    log_audit_event(
        user_id=user_id,
        action="session_terminated",
        resource_type="session",
        resource_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("User session terminated", extra={"user_id": user_id, "session_id": session_id})
    return {"message": "Session terminated successfully"}

@router.post("/sessions/terminate-all")
async def terminate_all_sessions(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    tenant_id = request.state.tenant_id
    auth_header = request.headers.get("Authorization")
    current_token = auth_header[7:] if auth_header and auth_header.startswith("Bearer ") else None
    session_manager.delete_user_sessions(user_id, tenant_id, exclude_session=current_token)
    log_audit_event(
        user_id=user_id,
        action="all_sessions_terminated",
        resource_type="session",
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("All user sessions terminated", extra={"user_id": user_id})
    return {"message": "All other sessions terminated successfully"}

@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository)
):
    user_id = request.state.user_id
    preferences = user_repo.get_user_preferences(user_id)
    if not preferences:
        return UserPreferences()
    return UserPreferences(
        language=preferences.language,
        currency=preferences.currency,
        timezone=preferences.timezone,
        email_notifications=preferences.email_notifications,
        sms_notifications=preferences.sms_notifications,
        marketing_emails=preferences.marketing_emails,
        two_factor_enabled=preferences.two_factor_enabled
    )

@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(
    request: Request,
    preferences_data: UserPreferences,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    preferences = user_repo.update_user_preferences(user_id, preferences_data.dict(exclude_unset=True))
    log_audit_event(
        user_id=user_id,
        action="preferences_updated",
        resource_type="preferences",
        resource_id=preferences.id,
        new_values=preferences_data.dict(exclude_unset=True),
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("User preferences updated", extra={"user_id": user_id})
    return UserPreferences(
        language=preferences.language,
        currency=preferences.currency,
        timezone=preferences.timezone,
        email_notifications=preferences.email_notifications,
        sms_notifications=preferences.sms_notifications,
        marketing_emails=preferences.marketing_emails,
        two_factor_enabled=preferences.two_factor_enabled
    )

@router.post("/consent")
async def record_consent(
    request: Request,
    consent_data: ConsentRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip)
):
    user_id = request.state.user_id
    user_repo.record_user_consent(
        user_id=user_id,
        consent_type=consent_data.consent_type,
        granted=consent_data.granted,
        version=consent_data.version,
        ip_address=ip_address
    )
    logger.info("User consent recorded", extra={
        "user_id": user_id,
        "consent_type": consent_data.consent_type,
        "granted": consent_data.granted,
        "version": consent_data.version
    })
    return {"message": "Consent recorded successfully"}

@router.get("/consents")
async def get_consents(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository)
):
    user_id = request.state.user_id
    consents = user_repo.get_user_consents(user_id)
    return {"consents": consents}

@router.get("/login-history", response_model=List[LoginHistoryResponse])
async def get_login_history(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
    hours: int = 168,
    skip: int = 0,
    limit: int = 50
):
    user_id = request.state.user_id
    if hours > 720:
        hours = 720
    login_history = user_repo.get_login_history(
        user_id=user_id,
        hours=hours,
        skip=skip,
        limit=limit
    )
    history_responses = []
    for login in login_history:
        anonymized_ip = None
        if login.ip_address:
            ip_parts = str(login.ip_address).split('.')
            if len(ip_parts) == 4:
                anonymized_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.xxx"
        history_responses.append(LoginHistoryResponse(
            login_time=login.login_time,
            logout_time=login.logout_time,
            ip_address=anonymized_ip,
            device_info=login.device_info,
            status=login.status
        ))
    logger.info("User login history retrieved", extra={"user_id": user_id, "hours": hours})
    return history_responses

@router.get("/export-data")
async def export_user_data(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository)
):
    user_id = request.state.user_id
    user = user_repo.get_user_by_id(user_id)
    addresses = user_repo.get_user_addresses(user_id)
    preferences = user_repo.get_user_preferences(user_id)
    consents = user_repo.get_user_consents(user_id)
    login_history = user_repo.get_login_history(user_id, hours=720)
    export_data = {
        "profile": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "username": user.username,
            "phone": user.phone,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat()
        },
        "addresses": [
            {
                "type": addr.type,
                "address_line1": addr.address_line1,
                "address_line2": addr.address_line2,
                "city": addr.city,
                "state": addr.state,
                "country": addr.country,
                "postal_code": addr.postal_code,
                "is_default": addr.is_default,
                "created_at": addr.created_at.isoformat(),
                "updated_at": addr.updated_at.isoformat()
            } for addr in addresses
        ],
        "preferences": {
            "language": preferences.language if preferences else "en",
            "currency": preferences.currency if preferences else "USD",
            "timezone": preferences.timezone if preferences else "UTC",
            "email_notifications": preferences.email_notifications if preferences else True,
            "sms_notifications": preferences.sms_notifications if preferences else False,
            "marketing_emails": preferences.marketing_emails if preferences else False
        },
        "consents": [
            {
                "consent_type": consent.consent_type,
                "granted": consent.granted,
                "version": consent.version,
                "granted_at": consent.granted_at.isoformat()
            } for consent in consents
        ],
        "login_history": [
            {
                "login_time": login.login_time.isoformat(),
                "logout_time": login.logout_time.isoformat() if login.logout_time else None,
                "status": login.status
            } for login in login_history
        ]
    }
    logger.info("User data exported", extra={"user_id": user_id})
    return export_data

@router.get("/notification-preferences", response_model=UserNotificationPreferences)
async def get_notification_preferences(
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository)
):
    user_id = request.state.user_id
    preferences_dict = user_repo.get_user_notification_preferences(user_id)
    preferences = []
    for method, enabled in preferences_dict.items():
        preferences.append(NotificationPreference(
            notification_method=NotificationType(method),
            is_enabled=enabled
        ))
    return UserNotificationPreferences(preferences=preferences)

@router.put("/notification-preferences", response_model=UserNotificationPreferences)
async def update_notification_preferences(
    request: Request,
    preferences_data: UserNotificationPreferences,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    preferences_dict = {}
    for pref in preferences_data.preferences:
        preferences_dict[pref.notification_method.value] = pref.is_enabled
    user_repo.set_user_notification_preferences(user_id, preferences_dict)
    log_audit_event(
        user_id=user_id,
        action="notification_preferences_updated",
        resource_type="notification_preferences",
        new_values=preferences_dict,
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info("User notification preferences updated", extra={"user_id": user_id})
    updated_preferences_dict = user_repo.get_user_notification_preferences(user_id)
    updated_preferences = []
    for method, enabled in updated_preferences_dict.items():
        updated_preferences.append(NotificationPreference(
            notification_method=NotificationType(method),
            is_enabled=enabled
        ))
    return UserNotificationPreferences(preferences=updated_preferences)

@router.put("/notification-preferences/{notification_method}")
async def update_single_notification_preference(
    notification_method: NotificationType,
    is_enabled: bool,
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
    ip_address: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    user_id = request.state.user_id
    user_repo.update_user_notification_preference(user_id, notification_method.value, is_enabled)
    log_audit_event(
        user_id=user_id,
        action="notification_preference_updated",
        resource_type="notification_preference",
        new_values={notification_method.value: is_enabled},
        ip_address=ip_address,
        user_agent=user_agent
    )
    logger.info(
        "Single notification preference updated",
        extra={
            "user_id": user_id,
            "notification_method": notification_method.value,
            "is_enabled": is_enabled
        }
    )
    return {"message": f"Notification preference for {notification_method.value} updated successfully"}
