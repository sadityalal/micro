-- =====================================================
-- COMPLETE init.sql - PostgreSQL 17 - FULLY WORKING
-- Multi-Tenant E-Commerce + SaaS Platform Database Schema
-- Date: November 2024
-- Author: @ItsSaurabhAdi
-- =====================================================

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- =====================================================
-- ENUMERATIONS (CREATE FIRST)
-- =====================================================
CREATE TYPE tenant_status AS ENUM ('active', 'suspended', 'inactive');
CREATE TYPE order_status AS ENUM ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded');
CREATE TYPE payment_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'refunded', 'cancelled');
CREATE TYPE refund_status AS ENUM ('pending', 'approved', 'processed', 'rejected');
CREATE TYPE notification_type AS ENUM ('email', 'sms', 'whatsapp', 'telegram', 'push');
CREATE TYPE notification_status AS ENUM ('pending', 'sent', 'failed', 'delivered');
CREATE TYPE page_status AS ENUM ('draft', 'published', 'archived');
CREATE TYPE discount_type AS ENUM ('percentage', 'fixed_amount');
CREATE TYPE tax_type AS ENUM ('gst', 'vat', 'sales_tax', 'custom');
CREATE TYPE gst_slab AS ENUM ('0', '5', '12', '18', '28');
CREATE TYPE vat_rate AS ENUM ('0', '5', '8', '10', '20', '23');
CREATE TYPE setting_type AS ENUM ('string', 'integer', 'boolean', 'json', 'decimal');
CREATE TYPE payment_method_type AS ENUM ('bank', 'upi', 'wallet', 'card', 'net_banking', 'cod');
CREATE TYPE payment_gateway AS ENUM ('razorpay', 'stripe', 'paypal', 'paytm', 'phonepe', 'google_pay', 'instamojo', 'ccavenue', 'custom');
CREATE TYPE bank_status AS ENUM ('active', 'inactive', 'maintenance');
CREATE TYPE upi_type AS ENUM ('public', 'private');
CREATE TYPE password_policy_type AS ENUM ('basic', 'medium', 'strong', 'custom');
CREATE TYPE username_policy_type AS ENUM ('email', 'any', 'custom');
CREATE TYPE rate_limit_strategy AS ENUM ('fixed_window', 'sliding_window', 'token_bucket');
CREATE TYPE session_storage_type AS ENUM ('redis', 'database', 'jwt');
CREATE TYPE session_timeout_type AS ENUM ('absolute', 'sliding');
CREATE TYPE service_status AS ENUM ('active', 'maintenance', 'disabled');
CREATE TYPE database_type AS ENUM ('postgresql', 'mysql', 'mongodb');
CREATE TYPE cache_type AS ENUM ('redis', 'memcached', 'local');
CREATE TYPE queue_type AS ENUM ('rabbitmq', 'redis', 'sqs', 'kafka');
CREATE TYPE card_network AS ENUM ('visa', 'mastercard', 'rupay', 'amex', 'diners', 'discover', 'jcb');
CREATE TYPE card_type AS ENUM ('credit', 'debit', 'prepaid');

-- =====================================================
-- CORE TABLES (PROPER ORDER FOR DEPENDENCIES)
-- =====================================================

-- 1. Countries first (no dependencies)
CREATE TABLE countries (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(3) NOT NULL UNIQUE,
    currency_code VARCHAR(3) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Regions (depends on countries)
CREATE TABLE regions (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_id, code)
);

-- 3. Tenants (depends on countries)
CREATE TABLE tenants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    country_code VARCHAR(3) NOT NULL REFERENCES countries(code) ON DELETE RESTRICT,
    default_currency VARCHAR(3) DEFAULT 'USD',
    tax_type tax_type NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status tenant_status DEFAULT 'active'
);

-- 4. Users (depends on tenants)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT REFERENCES tenants(id) ON DELETE SET NULL,
    username VARCHAR(100) UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    telegram_username VARCHAR(100),
    additional_phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. User Roles (independent)
CREATE TABLE user_roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_system_role BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Permissions (independent)
CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    module VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Role Permissions (depends on roles and permissions)
CREATE TABLE role_permissions (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES user_roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role_id, permission_id)
);

-- 8. User Role Assignments (depends on users and roles)
CREATE TABLE user_role_assignments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES user_roles(id) ON DELETE CASCADE,
    assigned_by BIGINT NOT NULL REFERENCES users(id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, role_id)
);

-- 9. Tenant Users (depends on tenants and users)
CREATE TABLE tenant_users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role_id BIGINT NOT NULL REFERENCES user_roles(id),
    UNIQUE(tenant_id, user_id)
);

-- =====================================================
-- SETTINGS TABLES (ALL DEPEND ON TENANTS)
-- =====================================================

CREATE TABLE tenant_system_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    setting_type setting_type DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, setting_key)
);

CREATE TABLE tenant_payment_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    gateway VARCHAR(50) NOT NULL,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    setting_type setting_type DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, gateway, setting_key)
);

CREATE TABLE tenant_shipping_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    setting_type setting_type DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, setting_key)
);

CREATE TABLE tenant_notification_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    setting_type setting_type DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, setting_key)
);

CREATE TABLE tenant_appearance_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    setting_type setting_type DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, setting_key)
);

CREATE TABLE system_settings (
    id BIGSERIAL PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT,
    setting_type setting_type DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE site_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    setting_type setting_type DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, setting_key)
);

-- =====================================================
-- SECURITY & CONFIGURATION TABLES
-- =====================================================

CREATE TABLE security_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    jwt_secret_key VARCHAR(255) NOT NULL,
    jwt_algorithm VARCHAR(20) DEFAULT 'HS256',
    access_token_expiry_minutes INTEGER DEFAULT 30,
    refresh_token_expiry_days INTEGER DEFAULT 7,
    password_reset_expiry_minutes INTEGER DEFAULT 30,
    max_login_attempts INTEGER DEFAULT 5,
    account_lockout_minutes INTEGER DEFAULT 30,
    require_https BOOLEAN DEFAULT TRUE,
    cors_origins JSONB DEFAULT '["http://localhost:3000"]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

CREATE TABLE login_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    password_policy password_policy_type DEFAULT 'medium',
    min_password_length INTEGER DEFAULT 8,
    require_uppercase BOOLEAN DEFAULT TRUE,
    require_lowercase BOOLEAN DEFAULT TRUE,
    require_numbers BOOLEAN DEFAULT TRUE,
    require_special_chars BOOLEAN DEFAULT TRUE,
    max_password_age_days INTEGER DEFAULT 90,
    password_history_count INTEGER DEFAULT 5,
    max_login_attempts INTEGER DEFAULT 5,
    lockout_duration_minutes INTEGER DEFAULT 30,
    username_policy username_policy_type DEFAULT 'email',
    session_timeout_minutes INTEGER DEFAULT 30,
    mfa_required BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

CREATE TABLE session_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    storage_type session_storage_type DEFAULT 'redis',
    timeout_type session_timeout_type DEFAULT 'sliding',
    session_timeout_minutes INTEGER DEFAULT 30,
    absolute_timeout_minutes INTEGER DEFAULT 480,
    sliding_timeout_minutes INTEGER DEFAULT 30,
    max_concurrent_sessions INTEGER DEFAULT 5,
    regenerate_session BOOLEAN DEFAULT TRUE,
    secure_cookies BOOLEAN DEFAULT TRUE,
    http_only_cookies BOOLEAN DEFAULT TRUE,
    same_site_policy VARCHAR(20) DEFAULT 'lax',
    cookie_domain VARCHAR(255),
    cookie_path VARCHAR(100) DEFAULT '/',
    enable_session_cleanup BOOLEAN DEFAULT TRUE,
    cleanup_interval_minutes INTEGER DEFAULT 60,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

CREATE TABLE rate_limit_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    strategy rate_limit_strategy DEFAULT 'fixed_window',
    requests_per_minute INTEGER DEFAULT 60,
    requests_per_hour INTEGER DEFAULT 1000,
    requests_per_day INTEGER DEFAULT 10000,
    burst_capacity INTEGER DEFAULT 10,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

CREATE TABLE logging_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    log_level VARCHAR(10) DEFAULT 'INFO',
    enable_audit_log BOOLEAN DEFAULT TRUE,
    enable_access_log BOOLEAN DEFAULT TRUE,
    enable_security_log BOOLEAN DEFAULT TRUE,
    retention_days INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

CREATE TABLE infrastructure_settings (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_name VARCHAR(100) NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER,
    username VARCHAR(255),
    password VARCHAR(255),
    database_name VARCHAR(100),
    connection_string TEXT,
    max_connections INTEGER DEFAULT 20,
    timeout_seconds INTEGER DEFAULT 30,
    status service_status DEFAULT 'active',
    health_check_url VARCHAR(500),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, service_name)
);

CREATE TABLE service_urls (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_name VARCHAR(100) NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    health_endpoint VARCHAR(200),
    api_version VARCHAR(20),
    timeout_ms INTEGER DEFAULT 30000,
    retry_attempts INTEGER DEFAULT 3,
    circuit_breaker_enabled BOOLEAN DEFAULT TRUE,
    status service_status DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, service_name)
);

-- =====================================================
-- E-COMMERCE TABLES
-- =====================================================

CREATE TABLE tax_categories (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    tax_type tax_type NOT NULL,
    hsn_code VARCHAR(10),
    gst_slab gst_slab,
    vat_rate vat_rate,
    custom_rate DECIMAL(5,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

CREATE TABLE regional_tax_rates (
    id BIGSERIAL PRIMARY KEY,
    tax_category_id BIGINT NOT NULL REFERENCES tax_categories(id) ON DELETE CASCADE,
    country_id BIGINT NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    region_id BIGINT REFERENCES regions(id) ON DELETE CASCADE,
    tax_rate DECIMAL(5,2) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tax_category_id, country_id, region_id, effective_from)
);

CREATE TABLE categories (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    parent_id BIGINT REFERENCES categories(id),
    description TEXT,
    tax_category_id BIGINT REFERENCES tax_categories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE brands (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sku VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    stock_qty INTEGER DEFAULT 0,
    category_id BIGINT REFERENCES categories(id),
    brand_id BIGINT REFERENCES brands(id),
    tax_category_id BIGINT REFERENCES tax_categories(id),
    hsn_code VARCHAR(10),
    weight DECIMAL(8,2),
    dimensions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, sku)
);

CREATE TABLE product_images (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    alt_text VARCHAR(255),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE inventory_logs (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    change_qty INTEGER NOT NULL,
    reason VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id BIGINT REFERENCES users(id)
);

CREATE TABLE reviews (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, user_id)
);

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id),
    order_number VARCHAR(50) NOT NULL UNIQUE,
    status order_status DEFAULT 'pending',
    subtotal_amount DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    shipping_amount DECIMAL(10,2) DEFAULT 0,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    shipping_address JSONB NOT NULL,
    billing_address JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    total_price DECIMAL(10,2) NOT NULL,
    tax_details JSONB
);

CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    gateway VARCHAR(50) NOT NULL,
    status payment_status DEFAULT 'pending',
    transaction_id VARCHAR(255),
    gateway_response JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE refunds (
    id BIGSERIAL PRIMARY KEY,
    payment_id BIGINT NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    reason TEXT NOT NULL,
    status refund_status DEFAULT 'pending',
    processed_by BIGINT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE coupons (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL UNIQUE,
    discount_type discount_type NOT NULL,
    discount_value DECIMAL(10,2) NOT NULL,
    max_uses INTEGER,
    used_count INTEGER DEFAULT 0,
    min_order_amount DECIMAL(10,2) DEFAULT 0,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cart_items (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id)
);

CREATE TABLE wishlists (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id)
);

-- =====================================================
-- NOTIFICATION & CONTENT TABLES
-- =====================================================

CREATE TABLE notification_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type notification_type NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    subject VARCHAR(255),
    message TEXT NOT NULL,
    status notification_status DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_notification_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_method notification_type NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, notification_method)
);

CREATE TABLE pages (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    status page_status DEFAULT 'draft',
    seo_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, slug)
);

CREATE TABLE banners (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    image_url TEXT NOT NULL,
    link VARCHAR(500),
    sort_order INTEGER DEFAULT 0,
    status page_status DEFAULT 'published',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE blogs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    author_id BIGINT NOT NULL REFERENCES users(id),
    status page_status DEFAULT 'draft',
    published_at TIMESTAMP,
    seo_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, slug)
);

-- =====================================================
-- LOGS & ANALYTICS TABLES
-- =====================================================

CREATE TABLE activity_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    tenant_id BIGINT REFERENCES tenants(id),
    action VARCHAR(100) NOT NULL,
    meta JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE analytics_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    module VARCHAR(50) NOT NULL,
    metric VARCHAR(100) NOT NULL,
    value DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id BIGINT REFERENCES tenants(id),
    session_token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key_name VARCHAR(100) NOT NULL,
    key_value VARCHAR(255) NOT NULL UNIQUE,
    permissions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE files (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by BIGINT NOT NULL REFERENCES users(id),
    file_type VARCHAR(50) NOT NULL,
    url TEXT NOT NULL,
    file_name VARCHAR(255),
    file_size BIGINT,
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- PAYMENT & BANKING TABLES
-- =====================================================

CREATE TABLE supported_banks (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    bank_name VARCHAR(100) NOT NULL,
    bank_code VARCHAR(20) NOT NULL,
    bank_logo_url TEXT,
    country_code VARCHAR(3) NOT NULL REFERENCES countries(code) ON DELETE RESTRICT,
    is_active BOOLEAN DEFAULT TRUE,
    status bank_status DEFAULT 'active',
    processing_fee DECIMAL(5,2) DEFAULT 0,
    min_amount DECIMAL(10,2) DEFAULT 0,
    max_amount DECIMAL(10,2) DEFAULT 100000,
    supported_gateways payment_gateway[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, bank_code, country_code)
);

CREATE TABLE upi_support (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    upi_id VARCHAR(100) NOT NULL,
    upi_name VARCHAR(100) NOT NULL,
    upi_type upi_type DEFAULT 'public',
    qr_code_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    supported_apps VARCHAR(100)[],
    max_amount_per_transaction DECIMAL(10,2) DEFAULT 100000,
    max_transactions_per_day INTEGER DEFAULT 10,
    processing_fee DECIMAL(5,2) DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, upi_id)
);

CREATE TABLE wallet_support (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    wallet_name VARCHAR(100) NOT NULL,
    wallet_code VARCHAR(50) NOT NULL,
    wallet_logo_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    country_code VARCHAR(3) NOT NULL REFERENCES countries(code) ON DELETE RESTRICT,
    min_amount DECIMAL(10,2) DEFAULT 0,
    max_amount DECIMAL(10,2) DEFAULT 50000,
    processing_fee DECIMAL(5,2) DEFAULT 0,
    supported_currencies VARCHAR(3)[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, wallet_code, country_code)
);

CREATE TABLE card_support (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    card_network card_network NOT NULL,
    card_type card_type NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    country_code VARCHAR(3) NOT NULL REFERENCES countries(code) ON DELETE RESTRICT,
    processing_fee_percentage DECIMAL(5,2) DEFAULT 0,
    processing_fee_fixed DECIMAL(10,2) DEFAULT 0,
    min_amount DECIMAL(10,2) DEFAULT 0,
    max_amount DECIMAL(10,2) DEFAULT 100000,
    supported_gateways payment_gateway[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, card_network, card_type, country_code)
);

CREATE TABLE payment_gateway_config (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    gateway payment_gateway NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    is_live BOOLEAN DEFAULT FALSE,
    api_key VARCHAR(255),
    api_secret VARCHAR(255),
    webhook_secret VARCHAR(255),
    merchant_id VARCHAR(100),
    gateway_credentials JSONB,
    supported_currencies VARCHAR(3)[] DEFAULT '{USD}',
    supported_countries VARCHAR(3)[],
    config_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, gateway)
);

CREATE TABLE tenant_bank_accounts (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_holder_name VARCHAR(255) NOT NULL,
    account_number VARCHAR(50) NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    bank_code VARCHAR(20) NOT NULL,
    branch_name VARCHAR(100),
    branch_address TEXT,
    account_type VARCHAR(20) CHECK (account_type IN ('savings', 'current', 'corporate')),
    currency VARCHAR(3) DEFAULT 'USD',
    is_primary BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_document_url TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payment_method_details (
    id BIGSERIAL PRIMARY KEY,
    payment_id BIGINT NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    payment_method payment_method_type NOT NULL,
    gateway payment_gateway NOT NULL,
    method_details JSONB NOT NULL,
    bank_id BIGINT REFERENCES supported_banks(id) ON DELETE SET NULL,
    upi_id BIGINT REFERENCES upi_support(id) ON DELETE SET NULL,
    wallet_id BIGINT REFERENCES wallet_support(id) ON DELETE SET NULL,
    card_network card_network,
    card_last_four VARCHAR(4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (payment_method = 'bank' AND bank_id IS NOT NULL) OR
        (payment_method = 'upi' AND upi_id IS NOT NULL) OR
        (payment_method = 'wallet' AND wallet_id IS NOT NULL) OR
        (payment_method IN ('card', 'net_banking', 'cod'))
    )
);

-- =====================================================
-- HISTORY & AUDIT TABLES
-- =====================================================

CREATE TABLE password_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payment_history (
    id BIGSERIAL PRIMARY KEY,
    payment_id BIGINT NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    old_status payment_status,
    new_status payment_status NOT NULL,
    changed_by BIGINT REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta JSONB
);

CREATE TABLE order_history (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    old_status order_status,
    new_status order_status NOT NULL,
    changed_by BIGINT REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta JSONB
);

CREATE TABLE refund_history (
    id BIGSERIAL PRIMARY KEY,
    refund_id BIGINT NOT NULL REFERENCES refunds(id) ON DELETE CASCADE,
    old_status refund_status,
    new_status refund_status NOT NULL,
    changed_by BIGINT REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta JSONB
);

CREATE TABLE settings_history (
    id BIGSERIAL PRIMARY KEY,
    setting_table VARCHAR(50) NOT NULL,
    setting_id BIGINT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by BIGINT REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_role_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES user_roles(id),
    action VARCHAR(20) NOT NULL CHECK (action IN ('assigned', 'removed')),
    changed_by BIGINT NOT NULL REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE login_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id BIGINT REFERENCES tenants(id),
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logout_time TIMESTAMP,
    ip_address INET,
    attempted_email VARCHAR(255),
    device_info JSONB,
    status VARCHAR(20) DEFAULT 'success'
);

CREATE TABLE notification_history (
    id BIGSERIAL PRIMARY KEY,
    notification_log_id BIGINT NOT NULL REFERENCES notification_logs(id) ON DELETE CASCADE,
    status notification_status NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

CREATE TABLE inventory_history (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    old_qty INTEGER NOT NULL,
    new_qty INTEGER NOT NULL,
    changed_by BIGINT REFERENCES users(id),
    reason VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE activity_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    tenant_id BIGINT REFERENCES tenants(id),
    action VARCHAR(100) NOT NULL,
    meta JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEXES (AFTER ALL TABLES ARE CREATED)
-- =====================================================

-- Users indexes
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);

-- Products indexes
CREATE INDEX idx_products_tenant_id ON products(tenant_id);
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_sku ON products(sku);

-- Orders indexes
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_tenant_id ON orders(tenant_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at);

-- Payments indexes
CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_created_at ON payments(created_at);

-- Security & Settings indexes
CREATE INDEX idx_security_settings_tenant_id ON security_settings(tenant_id);
CREATE INDEX idx_login_settings_tenant_id ON login_settings(tenant_id);
CREATE INDEX idx_session_settings_tenant_id ON session_settings(tenant_id);
CREATE INDEX idx_rate_limit_settings_tenant_id ON rate_limit_settings(tenant_id);
CREATE INDEX idx_logging_settings_tenant_id ON logging_settings(tenant_id);
CREATE INDEX idx_infrastructure_settings_tenant_id ON infrastructure_settings(tenant_id);
CREATE INDEX idx_service_urls_tenant_id ON service_urls(tenant_id);

-- Composite indexes for performance
CREATE INDEX idx_sessions_tenant_user ON sessions(tenant_id, user_id);
CREATE INDEX idx_login_history_tenant_user_time ON login_history(tenant_id, user_id, login_time);
CREATE INDEX idx_activity_logs_tenant_action_time ON activity_logs(tenant_id, action, created_at);

-- =====================================================
-- SEED DATA (INSERT AFTER ALL TABLES AND INDEXES)
-- =====================================================

-- Insert countries
INSERT INTO countries (name, code, currency_code, is_active) VALUES
('India', 'IN', 'INR', true),
('United States', 'US', 'USD', true),
('United Kingdom', 'UK', 'GBP', true)
ON CONFLICT (code) DO NOTHING;

-- Insert default tenant
INSERT INTO tenants (id, name, domain, contact_email, country_code, tax_type, status)
VALUES (1, 'Default Tenant', 'default.local', 'admin@default.local', 'IN', 'gst', 'active')
ON CONFLICT (id) DO NOTHING;

-- Insert security settings
INSERT INTO security_settings (tenant_id, jwt_secret_key, jwt_algorithm, access_token_expiry_minutes, refresh_token_expiry_days, password_reset_expiry_minutes, require_https, max_login_attempts, account_lockout_minutes, cors_origins) VALUES
(1, 'your-super-secure-jwt-secret-key-change-in-production-64-chars-minimum', 'HS256', 30, 7, 30, true, 5, 30, '["http://localhost:3000", "https://app.pavitra.shop", "https://admin.pavitra.shop"]')
ON CONFLICT (tenant_id) DO UPDATE SET
    jwt_secret_key = EXCLUDED.jwt_secret_key,
    updated_at = CURRENT_TIMESTAMP;

-- Insert session settings
INSERT INTO session_settings (tenant_id, storage_type, timeout_type, session_timeout_minutes, absolute_timeout_minutes, sliding_timeout_minutes, max_concurrent_sessions, regenerate_session, secure_cookies, http_only_cookies, same_site_policy, cookie_domain, cookie_path, enable_session_cleanup, cleanup_interval_minutes) VALUES
(1, 'redis', 'sliding', 30, 480, 30, 5, true, true, true, 'lax', NULL, '/', true, 60)
ON CONFLICT (tenant_id) DO UPDATE SET
    updated_at = CURRENT_TIMESTAMP;

-- Insert rate limit settings
INSERT INTO rate_limit_settings (tenant_id, strategy, requests_per_minute, requests_per_hour, requests_per_day, burst_capacity, enabled) VALUES
(1, 'fixed_window', 60, 1000, 10000, 10, true)
ON CONFLICT (tenant_id) DO UPDATE SET
    updated_at = CURRENT_TIMESTAMP;

-- Insert login settings
INSERT INTO login_settings (tenant_id, password_policy, min_password_length, require_uppercase, require_lowercase, require_numbers, require_special_chars, max_password_age_days, password_history_count, max_login_attempts, lockout_duration_minutes, username_policy, session_timeout_minutes, mfa_required) VALUES
(1, 'medium', 8, true, true, true, true, 90, 5, 5, 30, 'email', 30, false)
ON CONFLICT (tenant_id) DO UPDATE SET
    updated_at = CURRENT_TIMESTAMP;

-- Insert logging settings
INSERT INTO logging_settings (tenant_id, log_level, enable_audit_log, enable_access_log, enable_security_log, retention_days) VALUES
(1, 'INFO', true, true, true, 30)
ON CONFLICT (tenant_id) DO UPDATE SET
    updated_at = CURRENT_TIMESTAMP;

-- Insert infrastructure settings
INSERT INTO infrastructure_settings (tenant_id, service_name, service_type, host, port, username, password, database_name, status) VALUES
(1, 'main_database', 'postgresql', 'postgres', 5432, 'root', 'root123', 'pavitra_db', 'active'),
(1, 'cache_redis', 'redis', 'redis', 6379, '', '', '0', 'active'),
(1, 'session_redis', 'redis', 'redis', 6379, '', '', '1', 'active'),
(1, 'rate_limit_redis', 'redis', 'redis', 6379, '', '', '2', 'active'),
(1, 'message_queue', 'rabbitmq', 'rabbitmq', 5672, 'guest', 'guest', '', 'active')
ON CONFLICT (tenant_id, service_name) DO UPDATE SET
    updated_at = CURRENT_TIMESTAMP;

-- Insert service URLs
INSERT INTO service_urls (tenant_id, service_name, base_url, health_endpoint, timeout_ms, retry_attempts, circuit_breaker_enabled, status) VALUES
(1, 'auth_service', 'http://auth:8000', '/health', 30000, 3, true, 'active'),
(1, 'product_service', 'http://product:8001', '/health', 30000, 3, true, 'active'),
(1, 'order_service', 'http://order:8002', '/health', 30000, 3, true, 'active'),
(1, 'payment_service', 'http://payment:8003', '/health', 30000, 3, true, 'active'),
(1, 'notification_service', 'http://notification:8004', '/health', 30000, 3, true, 'active')
ON CONFLICT (tenant_id, service_name) DO UPDATE SET
    updated_at = CURRENT_TIMESTAMP;

-- Insert default roles
INSERT INTO user_roles (id, name, description, is_system_role) VALUES
(1, 'super_admin', 'Full system access', true),
(2, 'admin', 'Administrator with management rights', true),
(3, 'manager', 'Business manager', true),
(4, 'customer', 'Regular customer', true)
ON CONFLICT (id) DO NOTHING;

-- Insert permissions
INSERT INTO permissions (id, name, description, module) VALUES
(1, 'users:create', 'Create users', 'users'),
(2, 'users:read', 'View users', 'users'),
(3, 'users:update', 'Update users', 'users'),
(4, 'users:delete', 'Delete users', 'users'),
(5, 'products:create', 'Create products', 'products'),
(6, 'products:read', 'View products', 'products'),
(7, 'products:update', 'Update products', 'products'),
(8, 'products:delete', 'Delete products', 'products'),
(9, 'orders:create', 'Create orders', 'orders'),
(10, 'orders:read', 'View orders', 'orders'),
(11, 'orders:read_all', 'View all orders', 'orders'),
(12, 'orders:update_status', 'Update order status', 'orders'),
(13, 'analytics:view', 'View analytics', 'analytics'),
(14, 'profile:read', 'View own profile', 'profile'),
(15, 'profile:update', 'Update own profile', 'profile'),
(16, 'cart:manage', 'Manage shopping cart', 'cart')
ON CONFLICT (id) DO NOTHING;

-- Assign permissions to roles
INSERT INTO role_permissions (role_id, permission_id) VALUES
-- Super Admin gets all permissions
(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),
(1, 9), (1, 10), (1, 11), (1, 12), (1, 13), (1, 14), (1, 15), (1, 16),
-- Admin gets most permissions except some user management
(2, 2), (2, 3), (2, 5), (2, 6), (2, 7), (2, 8), (2, 11), (2, 12), (2, 13),
-- Manager gets business operations permissions
(3, 6), (3, 7), (3, 11), (3, 12), (3, 13),
-- Customer gets basic permissions
(4, 6), (4, 9), (4, 10), (4, 14), (4, 15), (4, 16)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Create default super admin user (password: admin123)
INSERT INTO users (id, tenant_id, username, first_name, last_name, email, password_hash) VALUES
(1, 1, 'admin', 'System', 'Administrator', 'admin@pavitra.shop', '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$RdescudvJCsgt3ub+bxdWRhLLqn1n2JMhyVJ+L0mx4Y')
ON CONFLICT (id) DO NOTHING;

-- Assign super admin role to default user
INSERT INTO user_role_assignments (user_id, role_id, assigned_by) VALUES
(1, 1, 1)
ON CONFLICT (user_id, role_id) DO NOTHING;

-- Add user to tenant
INSERT INTO tenant_users (tenant_id, user_id, role_id) VALUES
(1, 1, 1)
ON CONFLICT (tenant_id, user_id) DO NOTHING;

-- Insert system settings
INSERT INTO system_settings (setting_key, setting_value, setting_type) VALUES
('app_name', 'Pavitra E-Commerce', 'string'),
('app_version', '1.0.0', 'string'),
('environment', 'development', 'string'),
('multi_tenant_enabled', 'true', 'boolean'),
('auto_migrations', 'true', 'boolean'),
('enable_swagger', 'true', 'boolean'),
('default_page_size', '20', 'integer'),
('max_page_size', '100', 'integer'),
('cache_default_ttl', '300', 'integer')
ON CONFLICT (setting_key) DO NOTHING;

-- =====================================================
-- DATABASE USER CREATION (ADD AT THE TOP AFTER EXTENSIONS)
-- =====================================================

-- Create admin user with full privileges
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'admin') THEN
        CREATE USER admin WITH PASSWORD 'admin123';
        ALTER USER admin WITH SUPERUSER CREATEDB CREATEROLE LOGIN;
    END IF;
END $$;

-- Grant all privileges on the database
GRANT ALL PRIVILEGES ON DATABASE pavitra_db TO admin;

-- Grant all privileges on all tables in public schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO admin;

-- Ensure future objects are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO admin;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO admin;

-- =====================================================
-- END OF SCRIPT
-- =====================================================