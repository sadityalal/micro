from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, Numeric, JSON, Enum, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

# =====================================================
# ENUMS (From your database schema)
# =====================================================
class TenantStatus(enum.Enum):
    active = 'active'
    suspended = 'suspended'
    inactive = 'inactive'

class OrderStatus(enum.Enum):
    pending = 'pending'
    confirmed = 'confirmed'
    processing = 'processing'
    shipped = 'shipped'
    delivered = 'delivered'
    cancelled = 'cancelled'
    refunded = 'refunded'

class PaymentStatus(enum.Enum):
    pending = 'pending'
    processing = 'processing'
    completed = 'completed'
    failed = 'failed'
    refunded = 'refunded'
    cancelled = 'cancelled'

class RefundStatus(enum.Enum):
    pending = 'pending'
    approved = 'approved'
    processed = 'processed'
    rejected = 'rejected'

class NotificationType(enum.Enum):
    email = 'email'
    sms = 'sms'
    whatsapp = 'whatsapp'
    telegram = 'telegram'
    push = 'push'

class NotificationStatus(enum.Enum):
    pending = 'pending'
    sent = 'sent'
    failed = 'failed'
    delivered = 'delivered'

class PageStatus(enum.Enum):
    draft = 'draft'
    published = 'published'
    archived = 'archived'

class DiscountType(enum.Enum):
    percentage = 'percentage'
    fixed_amount = 'fixed_amount'

class TaxType(enum.Enum):
    gst = 'gst'
    vat = 'vat'
    sales_tax = 'sales_tax'
    custom = 'custom'

class GstSlab(enum.Enum):
    zero = '0'
    five = '5'
    twelve = '12'
    eighteen = '18'
    twenty_eight = '28'

class VatRate(enum.Enum):
    zero = '0'
    five = '5'
    eight = '8'
    ten = '10'
    twenty = '20'
    twenty_three = '23'

class SettingType(enum.Enum):
    string = 'string'
    integer = 'integer'
    boolean = 'boolean'
    json = 'json'
    decimal = 'decimal'

class PaymentMethodType(enum.Enum):
    bank = 'bank'
    upi = 'upi'
    wallet = 'wallet'
    card = 'card'
    net_banking = 'net_banking'
    cod = 'cod'

class PaymentGateway(enum.Enum):
    razorpay = 'razorpay'
    stripe = 'stripe'
    paypal = 'paypal'
    paytm = 'paytm'
    phonepe = 'phonepe'
    google_pay = 'google_pay'
    instamojo = 'instamojo'
    ccavenue = 'ccavenue'
    custom = 'custom'

class BankStatus(enum.Enum):
    active = 'active'
    inactive = 'inactive'
    maintenance = 'maintenance'

class UpiType(enum.Enum):
    public = 'public'
    private = 'private'

class PasswordPolicyType(enum.Enum):
    basic = 'basic'
    medium = 'medium'
    strong = 'strong'
    custom = 'custom'

class UsernamePolicyType(enum.Enum):
    email = 'email'
    any = 'any'
    custom = 'custom'

class RateLimitStrategy(enum.Enum):
    fixed_window = 'fixed_window'
    sliding_window = 'sliding_window'
    token_bucket = 'token_bucket'

class SessionStorageType(enum.Enum):
    redis = 'redis'
    database = 'database'
    jwt = 'jwt'

class SessionTimeoutType(enum.Enum):
    absolute = 'absolute'
    sliding = 'sliding'

class ServiceStatus(enum.Enum):
    active = 'active'
    maintenance = 'maintenance'
    disabled = 'disabled'

class DatabaseType(enum.Enum):
    postgresql = 'postgresql'
    mysql = 'mysql'
    mongodb = 'mongodb'

class CacheType(enum.Enum):
    redis = 'redis'
    memcached = 'memcached'
    local = 'local'

class QueueType(enum.Enum):
    rabbitmq = 'rabbitmq'
    redis = 'redis'
    sqs = 'sqs'
    kafka = 'kafka'

class CardNetwork(enum.Enum):
    visa = 'visa'
    mastercard = 'mastercard'
    rupay = 'rupay'
    amex = 'amex'
    diners = 'diners'
    discover = 'discover'
    jcb = 'jcb'

class CardType(enum.Enum):
    credit = 'credit'
    debit = 'debit'
    prepaid = 'prepaid'

# =====================================================
# CORE TABLES
# =====================================================
class Country(Base):
    __tablename__ = "countries"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(3), nullable=False, unique=True)
    currency_code = Column(String(3), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Region(Base):
    __tablename__ = "regions"
    id = Column(BigInteger, primary_key=True)
    country_id = Column(BigInteger, ForeignKey("countries.id"), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(String(10), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True)
    contact_email = Column(String(255))
    contact_phone = Column(String(20))
    country_code = Column(String(3), ForeignKey("countries.code"))
    default_currency = Column(String(3), default='USD')
    tax_type = Column(Enum(TaxType), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    status = Column(Enum(TenantStatus), default='active')


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"))
    username = Column(String(100), unique=True, nullable=True)  # For username login
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20))
    additional_phone = Column(String(20))  # Alternative phone for login
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserRole(Base):
    __tablename__ = "user_roles"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    is_system_role = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    module = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class RolePermission(Base):
    __tablename__ = "role_permissions"
    id = Column(BigInteger, primary_key=True)
    role_id = Column(BigInteger, ForeignKey("user_roles.id"), nullable=False)
    permission_id = Column(BigInteger, ForeignKey("permissions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class UserRoleAssignment(Base):
    __tablename__ = "user_role_assignments"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    role_id = Column(BigInteger, ForeignKey("user_roles.id"), nullable=False)
    assigned_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, server_default=func.now())

class TenantUser(Base):
    __tablename__ = "tenant_users"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, server_default=func.now())
    role_id = Column(BigInteger, ForeignKey("user_roles.id"), nullable=False)

# =====================================================
# SETTINGS TABLES
# =====================================================
class TenantSystemSettings(Base):
    __tablename__ = "tenant_system_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(Text)
    setting_type = Column(Enum(SettingType), default='string')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class TenantPaymentSettings(Base):
    __tablename__ = "tenant_payment_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    gateway = Column(String(50), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(Text)
    setting_type = Column(Enum(SettingType), default='string')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class TenantShippingSettings(Base):
    __tablename__ = "tenant_shipping_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(Text)
    setting_type = Column(Enum(SettingType), default='string')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class TenantNotificationSettings(Base):
    __tablename__ = "tenant_notification_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(Text)
    setting_type = Column(Enum(SettingType), default='string')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class TenantAppearanceSettings(Base):
    __tablename__ = "tenant_appearance_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(Text)
    setting_type = Column(Enum(SettingType), default='string')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class SystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(BigInteger, primary_key=True)
    setting_key = Column(String(100), nullable=False, unique=True)
    setting_value = Column(Text)
    setting_type = Column(Enum(SettingType), default='string')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class SiteSettings(Base):
    __tablename__ = "site_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(Text)
    setting_type = Column(Enum(SettingType), default='string')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# =====================================================
# SECURITY & CONFIGURATION TABLES
# =====================================================
class SecuritySettings(Base):
    __tablename__ = "security_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    jwt_secret_key = Column(String(255), nullable=False)
    jwt_algorithm = Column(String(20), default='HS256')
    access_token_expiry_minutes = Column(Integer, default=30)
    refresh_token_expiry_days = Column(Integer, default=7)
    password_reset_expiry_minutes = Column(Integer, default=30)
    max_login_attempts = Column(Integer, default=5)
    account_lockout_minutes = Column(Integer, default=30)
    require_https = Column(Boolean, default=True)
    cors_origins = Column(JSON, default='["http://localhost:3000"]')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class LoginSettings(Base):
    __tablename__ = "login_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    password_policy = Column(Enum(PasswordPolicyType), default='medium')
    min_password_length = Column(Integer, default=8)
    require_uppercase = Column(Boolean, default=True)
    require_lowercase = Column(Boolean, default=True)
    require_numbers = Column(Boolean, default=True)
    require_special_chars = Column(Boolean, default=True)
    max_password_age_days = Column(Integer, default=90)
    password_history_count = Column(Integer, default=5)
    max_login_attempts = Column(Integer, default=5)
    lockout_duration_minutes = Column(Integer, default=30)
    username_policy = Column(Enum(UsernamePolicyType), default='email')
    session_timeout_minutes = Column(Integer, default=30)
    mfa_required = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class SessionSettings(Base):
    __tablename__ = "session_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    storage_type = Column(Enum(SessionStorageType), default='redis')
    timeout_type = Column(Enum(SessionTimeoutType), default='sliding')
    session_timeout_minutes = Column(Integer, default=30)
    absolute_timeout_minutes = Column(Integer, default=480)
    sliding_timeout_minutes = Column(Integer, default=30)
    max_concurrent_sessions = Column(Integer, default=5)
    regenerate_session = Column(Boolean, default=True)
    secure_cookies = Column(Boolean, default=True)
    http_only_cookies = Column(Boolean, default=True)
    same_site_policy = Column(String(20), default='lax')
    cookie_domain = Column(String(255))
    cookie_path = Column(String(100), default='/')
    enable_session_cleanup = Column(Boolean, default=True)
    cleanup_interval_minutes = Column(Integer, default=60)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class RateLimitSettings(Base):
    __tablename__ = "rate_limit_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    strategy = Column(Enum(RateLimitStrategy), default='fixed_window')
    requests_per_minute = Column(Integer, default=60)
    requests_per_hour = Column(Integer, default=1000)
    requests_per_day = Column(Integer, default=10000)
    burst_capacity = Column(Integer, default=10)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class LoggingSettings(Base):
    __tablename__ = "logging_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    log_level = Column(String(10), default='INFO')
    enable_audit_log = Column(Boolean, default=True)
    enable_access_log = Column(Boolean, default=True)
    enable_security_log = Column(Boolean, default=True)
    retention_days = Column(Integer, default=30)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class InfrastructureSettings(Base):
    __tablename__ = "infrastructure_settings"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    service_name = Column(String(100), nullable=False)
    service_type = Column(String(50), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer)
    username = Column(String(255))
    password = Column(String(255))
    database_name = Column(String(100))
    connection_string = Column(Text)
    max_connections = Column(Integer, default=20)
    timeout_seconds = Column(Integer, default=30)
    status = Column(Enum(ServiceStatus), default='active')
    health_check_url = Column(String(500))
    config_metadata = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ServiceUrls(Base):
    __tablename__ = "service_urls"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    service_name = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=False)
    health_endpoint = Column(String(200))
    api_version = Column(String(20))
    timeout_ms = Column(Integer, default=30000)
    retry_attempts = Column(Integer, default=3)
    circuit_breaker_enabled = Column(Boolean, default=True)
    status = Column(Enum(ServiceStatus), default='active')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# =====================================================
# SESSIONS & LOGS
# =====================================================
class Session(Base):
    __tablename__ = "sessions"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"))
    session_token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class LoginHistory(Base):
    __tablename__ = "login_history"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)  # Allow NULL
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"))
    attempted_email = Column(String(255), nullable=False)  # Add this line
    login_time = Column(DateTime, server_default=func.now())
    logout_time = Column(DateTime)
    ip_address = Column(String(45))
    device_info = Column(JSON)
    status = Column(String(20), default='success')

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"))
    action = Column(String(100), nullable=False)
    meta = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

class PasswordHistory(Base):
    __tablename__ = "password_history"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    password_hash = Column(String(255), nullable=False)
    changed_at = Column(DateTime, server_default=func.now())

# =====================================================
# NOTIFICATION TABLES
# =====================================================
class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    type = Column(Enum(NotificationType), nullable=False)
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255))
    message = Column(Text, nullable=False)
    status = Column(Enum(NotificationStatus), default='pending')
    created_at = Column(DateTime, server_default=func.now())

class UserNotificationPreference(Base):
    __tablename__ = "user_notification_preferences"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    notification_method = Column(Enum(NotificationType), nullable=False)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# =====================================================
# HISTORY & AUDIT TABLES
# =====================================================
class PaymentHistory(Base):
    __tablename__ = "payment_history"
    id = Column(BigInteger, primary_key=True)
    payment_id = Column(BigInteger, ForeignKey("payments.id"), nullable=False)
    old_status = Column(Enum(PaymentStatus))
    new_status = Column(Enum(PaymentStatus), nullable=False)
    changed_by = Column(BigInteger, ForeignKey("users.id"))
    changed_at = Column(DateTime, server_default=func.now())
    meta = Column(JSON)

class OrderHistory(Base):
    __tablename__ = "order_history"
    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=False)
    old_status = Column(Enum(OrderStatus))
    new_status = Column(Enum(OrderStatus), nullable=False)
    changed_by = Column(BigInteger, ForeignKey("users.id"))
    changed_at = Column(DateTime, server_default=func.now())
    meta = Column(JSON)

class RefundHistory(Base):
    __tablename__ = "refund_history"
    id = Column(BigInteger, primary_key=True)
    refund_id = Column(BigInteger, ForeignKey("refunds.id"), nullable=False)
    old_status = Column(Enum(RefundStatus))
    new_status = Column(Enum(RefundStatus), nullable=False)
    changed_by = Column(BigInteger, ForeignKey("users.id"))
    changed_at = Column(DateTime, server_default=func.now())
    meta = Column(JSON)

class SettingsHistory(Base):
    __tablename__ = "settings_history"
    id = Column(BigInteger, primary_key=True)
    setting_table = Column(String(50), nullable=False)
    setting_id = Column(BigInteger, nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_by = Column(BigInteger, ForeignKey("users.id"))
    changed_at = Column(DateTime, server_default=func.now())

class UserRoleHistory(Base):
    __tablename__ = "user_role_history"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    role_id = Column(BigInteger, ForeignKey("user_roles.id"), nullable=False)
    action = Column(String(20), nullable=False)
    changed_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, server_default=func.now())

class NotificationHistory(Base):
    __tablename__ = "notification_history"
    id = Column(BigInteger, primary_key=True)
    notification_log_id = Column(BigInteger, ForeignKey("notification_logs.id"), nullable=False)
    status = Column(Enum(NotificationStatus), nullable=False)
    sent_at = Column(DateTime, server_default=func.now())
    error_message = Column(Text)

class ActivityHistory(Base):
    __tablename__ = "activity_history"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"))
    action = Column(String(100), nullable=False)
    meta = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

# =====================================================
# API & FILES
# =====================================================
class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    key_name = Column(String(100), nullable=False)
    key_value = Column(String(255), nullable=False, unique=True)
    permissions = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class File(Base):
    __tablename__ = "files"
    id = Column(BigInteger, primary_key=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    uploaded_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    file_type = Column(String(50), nullable=False)
    url = Column(Text, nullable=False)
    file_name = Column(String(255))
    file_size = Column(BigInteger)
    mime_type = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())