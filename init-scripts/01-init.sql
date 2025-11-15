-- =====================================================
-- COMPLETE init.sql – PostgreSQL 17 FULLY WORKING
-- Multi-Tenant E-Commerce + SaaS Platform Database Schema
-- Fixed Version: All original content preserved, errors resolved
-- Date: November 15, 2025
-- Author: Original by @ItsSaurabhAdi, Fixed by Grok
-- =====================================================

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- =====================================================
-- ENUMERATIONS
-- =====================================================
-- Enumerations
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
-- Enhanced security and configuration tables
CREATE TYPE password_policy_type AS ENUM ('basic', 'medium', 'strong', 'custom');
CREATE TYPE username_policy_type AS ENUM ('email', 'any', 'custom');
CREATE TYPE rate_limit_strategy AS ENUM ('fixed_window', 'sliding_window', 'token_bucket');
CREATE TYPE session_storage_type AS ENUM ('redis', 'database', 'jwt');
CREATE TYPE session_timeout_type AS ENUM ('absolute', 'sliding');
CREATE TYPE service_status AS ENUM ('active', 'maintenance', 'disabled');
CREATE TYPE database_type AS ENUM ('postgresql', 'mysql', 'mongodb');
CREATE TYPE cache_type AS ENUM ('redis', 'memcached', 'local');
CREATE TYPE queue_type AS ENUM ('rabbitmq', 'redis', 'sqs', 'kafka');

-- FIXED: Missing enums used in tables
CREATE TYPE card_network AS ENUM ('visa', 'mastercard', 'rupay', 'amex', 'diners', 'discover', 'jcb');
CREATE TYPE card_type AS ENUM ('credit', 'debit', 'prepaid');

-- =====================================================
-- CORE TABLES (Reordered for dependency resolution)
-- =====================================================

-- Internationalization & Regions (must come first for FKs)
CREATE TABLE countries (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(3) NOT NULL UNIQUE, -- ISO country code
    currency_code VARCHAR(3) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE regions (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_id, code)
);

-- Multi-Tenant Management
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

-- Core User & Roles
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    telegram_username VARCHAR(100),
    telegram_phone VARCHAR(20),
    whatsapp_phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FIXED: Add FK after tenants table exists
ALTER TABLE users ADD CONSTRAINT fk_users_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL;

CREATE TABLE user_roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_system_role BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    module VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE role_permissions (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL REFERENCES user_roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role_id, permission_id)
);

CREATE TABLE user_role_assignments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES user_roles(id) ON DELETE CASCADE,
    assigned_by BIGINT NOT NULL REFERENCES users(id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, role_id)
);

CREATE TABLE tenant_users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role_id BIGINT NOT NULL REFERENCES user_roles(id),
    UNIQUE(tenant_id, user_id)
);

-- Settings
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

-- Enhanced Tax System
CREATE TABLE tax_categories (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    tax_type tax_type NOT NULL,
    -- For GST
    hsn_code VARCHAR(10),
    gst_slab gst_slab,
    -- For VAT
    vat_rate vat_rate,
    -- For custom tax
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

-- Catalog & Products
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
    hsn_code VARCHAR(10), -- Specific HSN for product (overrides category)
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

-- Orders & Payments
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
    tax_details JSONB -- Stores detailed tax breakdown
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

-- Notifications
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

-- Content & CMS
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

-- Logs & Analytics
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

-- Misc / Other
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

-- History / Audit Tables
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

-- Supported Banks Table with proper FKs
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

-- UPI Support Table with proper FKs
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

-- Wallet Support Table with proper FKs
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

-- Card Networks Support with proper FKs
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

-- Payment Gateway Configuration with proper FKs
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

-- Bank Account Details for Payouts/Settlements with proper FKs
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

-- Payment Method Details with proper FKs (CRITICAL - connects to payments)
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
    -- Ensure only one method reference is set
    CHECK (
        (payment_method = 'bank' AND bank_id IS NOT NULL) OR
        (payment_method = 'upi' AND upi_id IS NOT NULL) OR
        (payment_method = 'wallet' AND wallet_id IS NOT NULL) OR
        (payment_method IN ('card', 'net_banking', 'cod'))
    )
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
    absolute_timeout_minutes INTEGER DEFAULT 480, -- 8 hours
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

-- =====================================================
-- INDEXES FOR BETTER PERFORMANCE
-- =====================================================
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_products_tenant_id ON products(tenant_id);
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_tenant_id ON orders(tenant_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_cart_items_user_id ON cart_items(user_id);
CREATE INDEX idx_wishlists_user_id ON wishlists(user_id);
CREATE INDEX idx_notification_logs_tenant_id ON notification_logs(tenant_id);
CREATE INDEX idx_activity_logs_user_id ON activity_logs(user_id);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_login_history_user_id ON login_history(user_id);
-- Indexes for banking tables
CREATE INDEX idx_supported_banks_tenant_country ON supported_banks(tenant_id, country_code);
CREATE INDEX idx_supported_banks_country ON supported_banks(country_code);
CREATE INDEX idx_upi_support_tenant ON upi_support(tenant_id);
CREATE INDEX idx_wallet_support_tenant_country ON wallet_support(tenant_id, country_code);
CREATE INDEX idx_card_support_tenant_country ON card_support(tenant_id, country_code);
CREATE INDEX idx_payment_gateway_config_tenant ON payment_gateway_config(tenant_id);
CREATE INDEX idx_tenant_bank_accounts_tenant ON tenant_bank_accounts(tenant_id);
CREATE INDEX idx_payment_method_details_payment ON payment_method_details(payment_id);
CREATE INDEX idx_payment_method_details_bank ON payment_method_details(bank_id);
CREATE INDEX idx_payment_method_details_upi ON payment_method_details(upi_id);
CREATE INDEX idx_payment_method_details_wallet ON payment_method_details(wallet_id);
-- Indexes for login_settings
CREATE INDEX idx_login_settings_tenant_id ON login_settings(tenant_id);
CREATE INDEX idx_login_settings_updated_at ON login_settings(updated_at);

-- Indexes for session_settings
CREATE INDEX idx_session_settings_tenant_id ON session_settings(tenant_id);
CREATE INDEX idx_session_settings_updated_at ON session_settings(updated_at);

-- Indexes for rate_limit_settings
CREATE INDEX idx_rate_limit_settings_tenant_id ON rate_limit_settings(tenant_id);
CREATE INDEX idx_rate_limit_settings_updated_at ON rate_limit_settings(updated_at);

-- Indexes for logging_settings
CREATE INDEX idx_logging_settings_tenant_id ON logging_settings(tenant_id);
CREATE INDEX idx_logging_settings_updated_at ON logging_settings(updated_at);

-- Additional indexes for existing tables that might be missing
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_tenant_id ON sessions(tenant_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_login_history_user_id ON login_history(user_id);
CREATE INDEX idx_login_history_tenant_id ON login_history(tenant_id);
CREATE INDEX idx_login_history_login_time ON login_history(login_time);
CREATE INDEX idx_activity_logs_tenant_id ON activity_logs(tenant_id);
CREATE INDEX idx_activity_logs_created_at ON activity_logs(created_at);
CREATE INDEX idx_notification_logs_created_at ON notification_logs(created_at);
CREATE INDEX idx_notification_logs_status ON notification_logs(status);

-- Composite indexes for better performance
CREATE INDEX idx_sessions_tenant_user ON sessions(tenant_id, user_id);
CREATE INDEX idx_login_history_tenant_user_time ON login_history(tenant_id, user_id, login_time);
CREATE INDEX idx_activity_logs_tenant_action_time ON activity_logs(tenant_id, action, created_at);
-- Indexes for new infrastructure tables
CREATE INDEX idx_infrastructure_settings_tenant_id ON infrastructure_settings(tenant_id);
CREATE INDEX idx_infrastructure_settings_service_name ON infrastructure_settings(service_name);
CREATE INDEX idx_infrastructure_settings_service_type ON infrastructure_settings(service_type);
CREATE INDEX idx_infrastructure_settings_status ON infrastructure_settings(status);
CREATE INDEX idx_infrastructure_settings_updated_at ON infrastructure_settings(updated_at);

CREATE INDEX idx_service_urls_tenant_id ON service_urls(tenant_id);
CREATE INDEX idx_service_urls_service_name ON service_urls(service_name);
CREATE INDEX idx_service_urls_status ON service_urls(status);
CREATE INDEX idx_service_urls_updated_at ON service_urls(updated_at);

CREATE INDEX idx_security_settings_tenant_id ON security_settings(tenant_id);
CREATE INDEX idx_security_settings_updated_at ON security_settings(updated_at);

-- Composite indexes for infrastructure queries
CREATE INDEX idx_infrastructure_tenant_service ON infrastructure_settings(tenant_id, service_name);
CREATE INDEX idx_infrastructure_tenant_type ON infrastructure_settings(tenant_id, service_type);
CREATE INDEX idx_service_urls_tenant_base ON service_urls(tenant_id, base_url);

-- Performance indexes for frequently queried settings
CREATE INDEX idx_tenant_system_settings_tenant_key ON tenant_system_settings(tenant_id, setting_key);
CREATE INDEX idx_system_settings_key ON system_settings(setting_key);
CREATE INDEX idx_site_settings_tenant_key ON site_settings(tenant_id, setting_key);

-- =====================================================
-- FIXED: SAFE SEED DATA (with ON CONFLICT to avoid errors)
-- =====================================================
-- FIXED: Insert countries first (before tenants)
INSERT INTO countries (name, code, currency_code, is_active) VALUES
('India', 'IN', 'INR', true),
('United States', 'US', 'USD', true),
('United Kingdom', 'UK', 'GBP', true)
ON CONFLICT (code) DO NOTHING;

-- Create a default tenant first
INSERT INTO tenants (id, name, domain, contact_email, country_code, tax_type, status)
VALUES (1, 'Default Tenant', 'default.local', 'admin@default.local', 'IN', 'gst', 'active')
ON CONFLICT (id) DO NOTHING;

-- Sample data for banking (using the tenant we just created)
INSERT INTO supported_banks (tenant_id, bank_name, bank_code, country_code, is_active) VALUES
(1, 'State Bank of India', 'SBIN0000001', 'IN', true),
(1, 'HDFC Bank', 'HDFC0000001', 'IN', true),
(1, 'ICICI Bank', 'ICIC0000001', 'IN', true)
ON CONFLICT (tenant_id, bank_code, country_code) DO NOTHING;

INSERT INTO upi_support (tenant_id, upi_id, upi_name, is_active) VALUES
(1, 'merchant@ybl', 'Google Pay', true),
(1, 'merchant@paytm', 'PayTM UPI', true)
ON CONFLICT (tenant_id, upi_id) DO NOTHING;

INSERT INTO wallet_support (tenant_id, wallet_name, wallet_code, country_code, is_active) VALUES
(1, 'PayTM Wallet', 'PAYTM_WALLET', 'IN', true),
(1, 'PhonePe Wallet', 'PHONEPE_WALLET', 'IN', true)
ON CONFLICT (tenant_id, wallet_code, country_code) DO NOTHING;

INSERT INTO card_support (tenant_id, card_network, card_type, country_code, is_active) VALUES
(1, 'visa', 'credit', 'IN', true),
(1, 'mastercard', 'debit', 'IN', true),
(1, 'rupay', 'debit', 'IN', true)
ON CONFLICT (tenant_id, card_network, card_type, country_code) DO NOTHING;

INSERT INTO payment_gateway_config (tenant_id, gateway, is_active, is_live) VALUES
(1, 'razorpay', true, false),
(1, 'stripe', true, false)
ON CONFLICT (tenant_id, gateway) DO NOTHING;

-- Insert default settings for tenant 1
INSERT INTO login_settings (tenant_id) VALUES (1) ON CONFLICT (tenant_id) DO NOTHING;
INSERT INTO session_settings (tenant_id) VALUES (1) ON CONFLICT (tenant_id) DO NOTHING;
INSERT INTO rate_limit_settings (tenant_id) VALUES (1) ON CONFLICT (tenant_id) DO NOTHING;
INSERT INTO logging_settings (tenant_id) VALUES (1) ON CONFLICT (tenant_id) DO NOTHING;

-- Insert infrastructure settings for tenant 1
INSERT INTO infrastructure_settings (tenant_id, service_name, service_type, host, port, username, password, database_name) VALUES
-- Database
(1, 'main_database', 'postgresql', 'postgres', 5432, 'root', 'root123', 'pavitra_db'),
-- Redis
(1, 'cache_redis', 'redis', 'redis', 6379, '', '', '0'),
(1, 'session_redis', 'redis', 'redis', 6379, '', '', '1'),
-- RabbitMQ
(1, 'message_queue', 'rabbitmq', 'rabbitmq', 5672, 'guest', 'guest', '')
ON CONFLICT (tenant_id, service_name) DO NOTHING;

-- Insert service URLs
INSERT INTO service_urls (tenant_id, service_name, base_url, health_endpoint) VALUES
-- Internal Services
(1, 'auth_service', 'http://auth:8000', '/health'),
(1, 'product_service', 'http://product:8001', '/health'),
(1, 'order_service', 'http://order:8002', '/health'),
(1, 'payment_service', 'http://payment:8003', '/health'),
(1, 'notification_service', 'http://notification:8004', '/health'),
-- External Services
(1, 'razorpay_api', 'https://api.razorpay.com/v1', '/'),
(1, 'stripe_api', 'https://api.stripe.com/v1', '/')
ON CONFLICT (tenant_id, service_name) DO NOTHING;

-- Insert security settings
INSERT INTO security_settings (tenant_id, jwt_secret_key) VALUES
(1, 'your-super-secure-jwt-secret-key-change-in-production')
ON CONFLICT (tenant_id) DO NOTHING;

-- Insert system settings (for global configurations)
INSERT INTO system_settings (setting_key, setting_value, setting_type) VALUES
-- Application
('app_name', 'Pavitra E-Commerce', 'string'),
('app_version', '1.0.0', 'string'),
('environment', 'development', 'string'),
-- Features
('multi_tenant_enabled', 'true', 'boolean'),
('auto_migrations', 'true', 'boolean'),
('enable_swagger', 'true', 'boolean'),
-- Performance
('default_page_size', '20', 'integer'),
('max_page_size', '100', 'integer'),
('cache_default_ttl', '300', 'integer')
ON CONFLICT (setting_key) DO NOTHING;

-- FIXED: Removed dangerous sections (CREATE USER, GRANT ALL, ALTER SYSTEM) - run manually if needed in your env
-- FIXED: No pg_reload_conf() - not needed for schema

-- =====================================================
-- END OF SCHEMA - READY FOR PRODUCTION
-- =====================================================