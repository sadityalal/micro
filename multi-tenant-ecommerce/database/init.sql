-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==================== CORE TABLES ====================

-- Core Tenant Table
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    domain VARCHAR(255) UNIQUE,
    subdomain VARCHAR(100) UNIQUE,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'inactive')),
    plan_type VARCHAR(50) DEFAULT 'starter',
    features JSONB DEFAULT '{}',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- User Roles Master Table
CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    level INTEGER NOT NULL UNIQUE,
    permissions JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users Table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    role_id INTEGER REFERENCES user_roles(id) DEFAULT 5,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    avatar_url VARCHAR(500), -- URL to image stored in upload service
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended', 'locked')),

    -- Security Features
    email_verified BOOLEAN DEFAULT false,
    phone_verified BOOLEAN DEFAULT false,
    is_locked BOOLEAN DEFAULT false,
    locked_until TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login TIMESTAMP,

    -- 2FA
    two_factor_enabled BOOLEAN DEFAULT false,
    two_factor_secret VARCHAR(100),

    -- Timestamps
    last_login TIMESTAMP,
    last_password_change TIMESTAMP,
    last_activity TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,

    UNIQUE(tenant_id, email)
);

-- User Addresses Table
CREATE TABLE user_addresses (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    address_type VARCHAR(20) DEFAULT 'shipping' CHECK (address_type IN ('shipping', 'billing', 'both')),
    is_default BOOLEAN DEFAULT false,

    -- Address Details
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    company VARCHAR(255),
    address_line1 VARCHAR(500) NOT NULL,
    address_line2 VARCHAR(500),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    country VARCHAR(2) NOT NULL,
    zipcode VARCHAR(20) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User Sessions
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    session_token VARCHAR(500) NOT NULL UNIQUE,
    refresh_token VARCHAR(500),
    device_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    location JSONB,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP NOT NULL,
    refresh_token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User Security Logs
CREATE TABLE user_security_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User Tax Info
CREATE TABLE user_tax_info (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    tax_type VARCHAR(10) NOT NULL CHECK (tax_type IN ('gst', 'vat')),
    tax_number VARCHAR(50) NOT NULL,
    business_name VARCHAR(255),
    business_type VARCHAR(50),
    country_code VARCHAR(2) NOT NULL,
    state_code VARCHAR(10),
    is_verified BOOLEAN DEFAULT false,
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, user_id),
    UNIQUE(tenant_id, tax_number)
);

-- ==================== AUDIT & SECURITY ====================

-- Audit Logs Table
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== PRODUCT CATALOG ====================

-- Categories Table
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES categories(id),
    image_url VARCHAR(500), -- URL to image
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    meta_title VARCHAR(255),
    meta_description TEXT,
    created_by INTEGER REFERENCES users(id),
    updated_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    UNIQUE(tenant_id, slug)
);

-- Brands Table
CREATE TABLE brands (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    logo_url VARCHAR(500), -- URL to logo
    is_active BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES users(id),
    updated_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    UNIQUE(tenant_id, slug)
);

-- Products Table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    brand_id INTEGER REFERENCES brands(id),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    short_description TEXT,
    sku VARCHAR(100) NOT NULL,

    -- Pricing
    price DECIMAL(10,2) NOT NULL,
    compare_price DECIMAL(10,2),
    cost_price DECIMAL(10,2),
    tax_rate DECIMAL(5,2) DEFAULT 0,

    -- Inventory
    stock_quantity INTEGER DEFAULT 0,
    track_quantity BOOLEAN DEFAULT true,
    allow_out_of_stock_purchase BOOLEAN DEFAULT false,
    low_stock_threshold INTEGER DEFAULT 5,

    -- Physical Properties
    weight DECIMAL(8,2),
    dimensions JSONB,

    -- Media URLs (stored in upload service)
    images JSONB DEFAULT '[]', -- Array of image URLs
    videos JSONB DEFAULT '[]', -- Array of video URLs

    -- Status & SEO
    is_featured BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    seo_title VARCHAR(255),
    seo_description TEXT,
    tags TEXT[] DEFAULT '{}',

    -- Sales Tracking
    total_stock_sold INTEGER DEFAULT 0,
    total_stock_available INTEGER DEFAULT 0,

    -- Audit
    created_by INTEGER REFERENCES users(id),
    updated_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,

    UNIQUE(tenant_id, slug),
    UNIQUE(tenant_id, sku)
);

-- Product Variants
CREATE TABLE product_variants (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    variant_options JSONB NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    compare_price DECIMAL(10,2),
    cost_price DECIMAL(10,2),
    stock_quantity INTEGER DEFAULT 0,
    track_quantity BOOLEAN DEFAULT true,
    weight DECIMAL(8,2),
    images JSONB DEFAULT '[]', -- Array of image URLs
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, sku)
);

-- Product Reviews
CREATE TABLE product_reviews (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    comment TEXT,
    is_approved BOOLEAN DEFAULT false,
    is_verified_purchase BOOLEAN DEFAULT false,
    helpful_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Wishlists
CREATE TABLE wishlists (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    name VARCHAR(255) DEFAULT 'My Wishlist',
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, user_id, name)
);

-- Wishlist Items
CREATE TABLE wishlist_items (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    wishlist_id INTEGER REFERENCES wishlists(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(wishlist_id, product_id)
);

-- ==================== INVENTORY MANAGEMENT ====================

-- Inventory Logs
CREATE TABLE inventory_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    variant_id INTEGER REFERENCES product_variants(id),
    change_type VARCHAR(50) NOT NULL,
    quantity_change INTEGER NOT NULL,
    new_quantity INTEGER NOT NULL,
    reason TEXT,
    reference_id INTEGER,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stock Alerts
CREATE TABLE stock_alerts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    variant_id INTEGER REFERENCES product_variants(id),
    alert_type VARCHAR(50) NOT NULL,
    current_quantity INTEGER NOT NULL,
    threshold_quantity INTEGER NOT NULL,
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== CART & ORDERS ====================

-- Carts Table
CREATE TABLE carts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    session_id VARCHAR(255),
    cart_data JSONB DEFAULT '{}',
    total_amount DECIMAL(10,2) DEFAULT 0,
    item_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, session_id)
);

-- Cart Items
CREATE TABLE cart_items (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    cart_id INTEGER REFERENCES carts(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    variant_id INTEGER REFERENCES product_variants(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cart_id, product_id, variant_id)
);

-- Orders Table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id),

    -- Order Identification
    order_number VARCHAR(100) NOT NULL,

    -- Order Status
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded')),
    payment_status VARCHAR(50) DEFAULT 'pending' CHECK (payment_status IN ('pending', 'paid', 'failed', 'refunded', 'partially_refunded')),
    fulfillment_status VARCHAR(50) DEFAULT 'unfulfilled' CHECK (fulfillment_status IN ('unfulfilled', 'fulfilled', 'partially_fulfilled')),

    -- Address References
    billing_address_id INTEGER REFERENCES user_addresses(id),
    shipping_address_id INTEGER REFERENCES user_addresses(id),

    -- Pricing
    subtotal DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    shipping_amount DECIMAL(10,2) DEFAULT 0,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',

    -- Customer Notes
    customer_note TEXT,

    -- Timestamps
    confirmed_at TIMESTAMP,
    paid_at TIMESTAMP,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    cancelled_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_id, order_number)
);

-- Order Items
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    order_id INTEGER REFERENCES orders(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    variant_id INTEGER REFERENCES product_variants(id),
    product_name VARCHAR(255) NOT NULL,
    product_sku VARCHAR(100) NOT NULL,
    variant_options JSONB,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order History
CREATE TABLE order_history (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    order_id INTEGER REFERENCES orders(id) NOT NULL,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    variant_id INTEGER REFERENCES product_variants(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order Status History
CREATE TABLE order_status_history (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    order_id INTEGER REFERENCES orders(id) NOT NULL,
    status VARCHAR(50) NOT NULL,
    note TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== PAYMENTS ====================

-- Payments Table
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    order_id INTEGER REFERENCES orders(id) NOT NULL,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    payment_method VARCHAR(100) NOT NULL,
    payment_gateway VARCHAR(100),
    transaction_id VARCHAR(255),
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled', 'refunded')),
    gateway_response JSONB,
    failure_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payment History
CREATE TABLE payment_history (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    order_id INTEGER REFERENCES orders(id) NOT NULL,
    payment_id INTEGER REFERENCES payments(id) NOT NULL,
    product_id INTEGER REFERENCES products(id) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payment Gateway Logs
CREATE TABLE payment_gateway_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    payment_id INTEGER REFERENCES payments(id),
    request_data JSONB,
    response_data JSONB,
    status_code INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== SHIPPING ====================

-- Shipping Zones
CREATE TABLE shipping_zones (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    name VARCHAR(255) NOT NULL,
    countries TEXT[] NOT NULL,
    states TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shipping Methods
CREATE TABLE shipping_methods (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    zone_id INTEGER REFERENCES shipping_zones(id) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    free_shipping_threshold DECIMAL(10,2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== DISCOUNTS & COUPONS ====================

-- Discounts/Coupons
CREATE TABLE discounts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    discount_type VARCHAR(20) NOT NULL CHECK (discount_type IN ('percentage', 'fixed_amount', 'free_shipping')),
    discount_value DECIMAL(10,2) NOT NULL,
    minimum_order_amount DECIMAL(10,2),
    maximum_discount_amount DECIMAL(10,2),
    usage_limit INTEGER,
    used_count INTEGER DEFAULT 0,
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, code)
);

-- Discount Rules
CREATE TABLE discount_rules (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    discount_id INTEGER REFERENCES discounts(id) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    rule_value JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== NOTIFICATIONS ====================

-- Notifications Table
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    is_read BOOLEAN DEFAULT false,
    sent_via JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email Templates
CREATE TABLE email_templates (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    name VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    variables JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

-- ==================== FILES ====================

-- File Uploads (Metadata only - actual files in upload service)
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_url VARCHAR(500) NOT NULL, -- URL to actual file in upload service
    file_size INTEGER NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    upload_type VARCHAR(50) NOT NULL,
    is_public BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== SETTINGS TABLES ====================

-- Session Settings
CREATE TABLE session_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    session_timeout INTEGER DEFAULT 3600,
    max_sessions_per_user INTEGER DEFAULT 5,
    allow_concurrent_sessions BOOLEAN DEFAULT true,
    cookie_secure BOOLEAN DEFAULT true,
    cookie_http_only BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

-- Rate Limit Settings
CREATE TABLE rate_limit_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    requests_per_minute INTEGER DEFAULT 60,
    requests_per_hour INTEGER DEFAULT 1000,
    burst_limit INTEGER DEFAULT 10,
    enable_ip_rate_limit BOOLEAN DEFAULT true,
    enable_user_rate_limit BOOLEAN DEFAULT true,
    blocked_ips TEXT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

-- Frontend Settings
CREATE TABLE frontend_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    site_name VARCHAR(255) DEFAULT 'My Store',
    site_tagline VARCHAR(500),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    store_address TEXT,
    facebook_url VARCHAR(500),
    instagram_url VARCHAR(500),
    twitter_url VARCHAR(500),
    youtube_url VARCHAR(500),
    linkedin_url VARCHAR(500),
    tax_number VARCHAR(50),
    registration_number VARCHAR(50),
    default_currency VARCHAR(3) DEFAULT 'USD',
    available_currencies TEXT[] DEFAULT '{"USD", "EUR", "GBP", "INR"}',
    default_language VARCHAR(10) DEFAULT 'en',
    available_languages TEXT[] DEFAULT '{"en", "es", "fr", "hi"}',
    timezone VARCHAR(50) DEFAULT 'UTC',
    primary_color VARCHAR(7) DEFAULT '#2563eb',
    secondary_color VARCHAR(7) DEFAULT '#64748b',
    logo_url VARCHAR(500),
    favicon_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

-- Global Banks Master Table
CREATE TABLE banks (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(2) NOT NULL,
    bank_code VARCHAR(20) NOT NULL,
    bank_name VARCHAR(255) NOT NULL,
    bank_full_name VARCHAR(500),
    bank_type VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    logo_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, bank_code)
);

-- Bank Settings
CREATE TABLE bank_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    bank_id INTEGER REFERENCES banks(id) NOT NULL,
    is_enabled BOOLEAN DEFAULT true,
    merchant_code VARCHAR(100),
    encryption_key VARCHAR(500),
    test_mode_credentials JSONB,
    live_mode_credentials JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, bank_id)
);

-- Payment Provider Settings
CREATE TABLE payment_provider_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    provider_type VARCHAR(50) NOT NULL,
    provider_name VARCHAR(100) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT false,
    is_test_mode BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 1,
    supported_countries TEXT[] DEFAULT '{}',
    credentials JSONB NOT NULL DEFAULT '{}',
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, provider_type, provider_name, payment_method)
);

-- UPI Settings
CREATE TABLE upi_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    upi_id VARCHAR(255) NOT NULL,
    merchant_name VARCHAR(255),
    is_active BOOLEAN DEFAULT false,
    gateway_provider VARCHAR(100),
    merchant_vpa VARCHAR(255),
    qr_code_url VARCHAR(500),
    qr_code_image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, upi_id)
);

-- Notification Provider Settings
CREATE TABLE notification_provider_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    provider_type VARCHAR(50) NOT NULL,
    provider_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT false,
    is_default BOOLEAN DEFAULT false,
    priority INTEGER DEFAULT 1,
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, provider_type, provider_name)
);

-- Tax Settings
CREATE TABLE tax_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    tax_calculation_enabled BOOLEAN DEFAULT true,
    prices_include_tax BOOLEAN DEFAULT false,
    display_prices_with_tax BOOLEAN DEFAULT true,
    tax_system VARCHAR(20) DEFAULT 'vat',
    default_tax_rate DECIMAL(5,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

-- State Tax Rates
CREATE TABLE state_tax_rates (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    state_code VARCHAR(10) NOT NULL,
    state_name VARCHAR(100) NOT NULL,
    tax_rate DECIMAL(5,2) NOT NULL,
    tax_type VARCHAR(20) DEFAULT 'standard',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, country_code, state_code)
);

-- Country Tax Rates
CREATE TABLE country_tax_rates (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    country_name VARCHAR(100) NOT NULL,
    tax_rate DECIMAL(5,2) NOT NULL,
    tax_type VARCHAR(20) DEFAULT 'vat',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, country_code)
);

-- Shipping Settings
CREATE TABLE shipping_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    shipping_calculation_enabled BOOLEAN DEFAULT true,
    free_shipping_enabled BOOLEAN DEFAULT false,
    free_shipping_min_amount DECIMAL(10,2) DEFAULT 0,
    origin_country VARCHAR(2) DEFAULT 'US',
    origin_state VARCHAR(100),
    origin_city VARCHAR(100),
    origin_zipcode VARCHAR(20),
    origin_address TEXT,
    default_package_weight DECIMAL(8,2) DEFAULT 0.5,
    default_package_length DECIMAL(8,2) DEFAULT 10,
    default_package_width DECIMAL(8,2) DEFAULT 10,
    default_package_height DECIMAL(8,2) DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

-- Currency Settings
CREATE TABLE currency_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    default_currency VARCHAR(3) DEFAULT 'USD',
    available_currencies TEXT[] DEFAULT '{"USD", "EUR", "GBP", "INR"}',
    auto_currency_detection BOOLEAN DEFAULT true,
    default_language VARCHAR(10) DEFAULT 'en',
    available_languages TEXT[] DEFAULT '{"en", "es", "fr", "hi"}',
    timezone VARCHAR(50) DEFAULT 'UTC',
    date_format VARCHAR(20) DEFAULT 'YYYY-MM-DD',
    time_format VARCHAR(20) DEFAULT '24h',
    weight_unit VARCHAR(10) DEFAULT 'kg',
    dimension_unit VARCHAR(10) DEFAULT 'cm',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

-- Security Settings
CREATE TABLE security_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    password_min_length INTEGER DEFAULT 8,
    password_require_uppercase BOOLEAN DEFAULT true,
    password_require_lowercase BOOLEAN DEFAULT true,
    password_require_numbers BOOLEAN DEFAULT true,
    password_require_symbols BOOLEAN DEFAULT true,
    password_expiry_days INTEGER DEFAULT 90,
    max_login_attempts INTEGER DEFAULT 5,
    lockout_duration_minutes INTEGER DEFAULT 30,
    require_2fa BOOLEAN DEFAULT false,
    session_timeout_minutes INTEGER DEFAULT 60,
    enable_api_rate_limit BOOLEAN DEFAULT true,
    api_rate_limit_per_minute INTEGER DEFAULT 60,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id)
);

-- Site Settings Table (if not exists)
CREATE TABLE IF NOT EXISTS site_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT NOT NULL,
    data_type VARCHAR(20) DEFAULT 'string',
    is_public BOOLEAN DEFAULT false,
    UNIQUE(tenant_id, setting_key)
);

-- ==================== ANALYTICS VIEWS ====================

-- Product Sales Summary View
CREATE OR REPLACE VIEW product_sales_summary AS
SELECT
    p.tenant_id,
    p.id as product_id,
    p.name as product_name,
    p.sku,
    c.name as category_name,
    p.total_stock_sold as total_units_sold,
    COALESCE(SUM(oi.quantity), 0) as recent_units_sold,
    COALESCE(SUM(oi.total_price), 0) as recent_revenue,
    p.created_at
FROM products p
LEFT JOIN categories c ON p.category_id = c.id AND p.tenant_id = c.tenant_id
LEFT JOIN order_items oi ON p.id = oi.product_id AND p.tenant_id = oi.tenant_id
LEFT JOIN orders o ON oi.order_id = o.id AND oi.tenant_id = o.tenant_id
WHERE p.tenant_id = 1
GROUP BY p.id, p.name, p.sku, c.name, p.total_stock_sold, p.created_at;

-- Category Sales Summary View
CREATE OR REPLACE VIEW category_sales_summary AS
SELECT
    c.tenant_id,
    c.id as category_id,
    c.name as category_name,
    c.parent_id,
    COUNT(DISTINCT p.id) as total_products,
    COALESCE(SUM(p.total_stock_sold), 0) as total_units_sold,
    COALESCE(SUM(oi.quantity), 0) as recent_units_sold,
    COALESCE(SUM(oi.total_price), 0) as recent_revenue
FROM categories c
LEFT JOIN products p ON c.id = p.category_id AND c.tenant_id = p.tenant_id
LEFT JOIN order_items oi ON p.id = oi.product_id AND p.tenant_id = oi.tenant_id
LEFT JOIN orders o ON oi.order_id = o.id AND oi.tenant_id = o.tenant_id
WHERE c.tenant_id = 1
GROUP BY c.id, c.name, c.parent_id;

-- Best Sellers View
CREATE OR REPLACE VIEW best_sellers AS
SELECT
    tenant_id,
    product_id,
    product_name,
    category_name,
    total_units_sold,
    recent_revenue,
    RANK() OVER (ORDER BY total_units_sold DESC) as sales_rank
FROM product_sales_summary;

-- Trending Products View
CREATE OR REPLACE VIEW trending_products AS
SELECT
    p.tenant_id,
    p.id as product_id,
    p.name as product_name,
    c.name as category_name,
    COUNT(oi.id) as recent_orders,
    SUM(oi.quantity) as recent_units_sold,
    RANK() OVER (ORDER BY COUNT(oi.id) DESC) as trend_rank
FROM products p
LEFT JOIN categories c ON p.category_id = c.id AND p.tenant_id = c.tenant_id
LEFT JOIN order_items oi ON p.id = oi.product_id AND p.tenant_id = oi.tenant_id
LEFT JOIN orders o ON oi.order_id = o.id AND oi.tenant_id = o.tenant_id
WHERE o.created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY p.id, p.name, c.name, p.tenant_id;

-- ==================== INSERT DEFAULT DATA ====================

-- Insert Default User Roles (if not exists)
INSERT INTO user_roles (name, description, level, permissions) VALUES
('super_admin', 'Full system access across all tenants', 1000, '{"*": "*"}'),
('admin', 'Full access within tenant', 100, '{"products": ["create", "read", "update", "delete"], "orders": ["create", "read", "update", "delete"], "users": ["create", "read", "update", "delete"], "settings": ["read", "update"]}'),
('manager', 'Manage products and orders', 50, '{"products": ["create", "read", "update"], "orders": ["create", "read", "update"], "users": ["read"], "settings": ["read"]}'),
('staff', 'Limited management access', 10, '{"products": ["read", "update"], "orders": ["read", "update"], "users": ["read"]}'),
('customer', 'Regular customer', 1, '{"products": ["read"], "orders": ["create", "read"], "profile": ["read", "update"]}')
ON CONFLICT (name) DO NOTHING;

-- Insert Default Tenant (if not exists)
INSERT INTO tenants (name, slug, subdomain, status, plan_type) VALUES
('Default Store', 'default', 'default', 'active', 'enterprise')
ON CONFLICT (slug) DO NOTHING;

-- Insert Default Super Admin User (password: admin123) (if not exists)
INSERT INTO users (tenant_id, role_id, email, password_hash, first_name, last_name, email_verified) VALUES
(1, 1, 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0L8k7CuOb1CV', 'Admin', 'User', true)
ON CONFLICT (tenant_id, email) DO NOTHING;

-- Insert User Addresses (if not exists)
INSERT INTO user_addresses (
    tenant_id, user_id, address_type, is_default, first_name, last_name, phone, email,
    address_line1, city, state, country, zipcode
) VALUES
(
    1, 1, 'both', true, 'John', 'Doe', '+1234567890', 'john@example.com',
    '123 Main Street', 'Mumbai', 'Maharashtra', 'IN', '400001'
),
(
    1, 1, 'shipping', false, 'John', 'Doe', '+1234567890', 'john@example.com',
    '456 Office Complex', 'Mumbai', 'Maharashtra', 'IN', '400002'
)
ON CONFLICT DO NOTHING;

-- Insert Categories (if not exists)
INSERT INTO categories (tenant_id, name, slug, description, image_url, is_active, sort_order, parent_id) VALUES
-- Main Categories
(1, 'Electronics', 'electronics', 'Latest electronic gadgets and devices', '/assets/categories/electronics.webp', true, 1, NULL),
(1, 'Fashion', 'fashion', 'Trendy clothing and accessories', '/assets/categories/fashion.webp', true, 2, NULL),
(1, 'Home & Living', 'home-living', 'Home decor and living essentials', '/assets/categories/home-living.webp', true, 3, NULL),
(1, 'Beauty', 'beauty', 'Skincare and beauty products', '/assets/categories/beauty.webp', true, 4, NULL),

-- Sub-categories for Electronics
(1, 'Headphones', 'headphones', 'Wireless and wired headphones', '/assets/categories/headphones.webp', true, 1, 1),
(1, 'Smartwatches', 'smartwatches', 'Smart watches and fitness trackers', '/assets/categories/smartwatches.webp', true, 2, 1),
(1, 'Wireless Earbuds', 'wireless-earbuds', 'True wireless earbuds', '/assets/categories/earbuds.webp', true, 3, 1),
(1, 'Bluetooth Speakers', 'bluetooth-speakers', 'Portable bluetooth speakers', '/assets/categories/speakers.webp', true, 4, 1),

-- Sub-categories for Fashion
(1, 'Men''s Clothing', 'mens-clothing', 'Clothing for men', '/assets/categories/mens-clothing.webp', true, 1, 2),
(1, 'Women''s Clothing', 'womens-clothing', 'Clothing for women', '/assets/categories/womens-clothing.webp', true, 2, 2),
(1, 'Kids'' Clothing', 'kids-clothing', 'Clothing for kids', '/assets/categories/kids-clothing.webp', true, 3, 2),
(1, 'Accessories', 'accessories', 'Fashion accessories', '/assets/categories/accessories.webp', true, 4, 2),

-- Sub-categories for Home & Living
(1, 'Home Decor', 'home-decor', 'Home decoration items', '/assets/categories/home-decor.webp', true, 1, 3),
(1, 'Kitchen', 'kitchen', 'Kitchen appliances and tools', '/assets/categories/kitchen.webp', true, 2, 3),
(1, 'Furniture', 'furniture', 'Home furniture', '/assets/categories/furniture.webp', true, 3, 3),

-- Sub-categories for Beauty
(1, 'Skincare', 'skincare', 'Face and body skincare', '/assets/categories/skincare.webp', true, 1, 4),
(1, 'Makeup', 'makeup', 'Cosmetics and makeup', '/assets/categories/makeup.webp', true, 2, 4),
(1, 'Haircare', 'haircare', 'Hair care products', '/assets/categories/haircare.webp', true, 3, 4)
ON CONFLICT (tenant_id, slug) DO NOTHING;

-- Insert Brands (if not exists)
INSERT INTO brands (tenant_id, name, slug, description, logo_url, is_active) VALUES
(1, 'AudioMaster', 'audiomaster', 'Premium audio products', '/assets/brands/audiomaster.webp', true),
(1, 'TechWear', 'techwear', 'Smart wearable technology', '/assets/brands/techwear.webp', true),
(1, 'SoundBeats', 'soundbeats', 'High-quality audio devices', '/assets/brands/soundbeats.webp', true),
(1, 'FashionElite', 'fashionelite', 'Premium fashion brand', '/assets/brands/fashionelite.webp', true),
(1, 'HomeStyle', 'homestyle', 'Home and living products', '/assets/brands/homestyle.webp', true),
(1, 'BeautyGlow', 'beautyglow', 'Skincare and beauty products', '/assets/brands/beautyglow.webp', true)
ON CONFLICT (tenant_id, slug) DO NOTHING;

-- Insert Products (if not exists)
INSERT INTO products (
    tenant_id, category_id, brand_id, name, slug, description, short_description,
    sku, price, compare_price, cost_price, stock_quantity, track_quantity,
    weight, images, is_featured, is_active, tags, total_stock_sold, total_stock_available,
    created_at
) VALUES
-- Electronics - Headphones
(
    1, 5, 1, 'Premium Wireless Headphones', 'premium-wireless-headphones',
    'Experience crystal-clear audio with noise cancellation, 30-hour battery life, and premium comfort.',
    'Noise cancelling wireless headphones with 30h battery',
    'AUDIO-001', 299.99, 399.99, 180.00, 45, true, 0.45,
    '["/assets/products/headphones-1.webp", "/assets/products/headphones-2.webp"]',
    true, true, '{"wireless", "noise-cancelling", "premium"}', 156, 45,
    '2024-09-15 10:00:00'
),
-- Electronics - Smartwatches
(
    1, 6, 2, 'Smart Fitness Tracker', 'smart-fitness-tracker',
    'Advanced fitness tracker with heart rate monitoring, GPS, sleep tracking, and 7-day battery life.',
    'Fitness tracker with heart rate and GPS',
    'WEAR-001', 89.99, 129.99, 45.00, 67, true, 0.05,
    '["/assets/products/fitness-tracker-1.webp", "/assets/products/fitness-tracker-2.webp"]',
    true, true, '{"fitness", "health", "smartwatch"}', 234, 67,
    '2024-11-01 09:15:00'
),
-- Electronics - Wireless Earbuds
(
    1, 7, 3, 'True Wireless Earbuds Pro', 'true-wireless-earbuds-pro',
    'True wireless earbuds with active noise cancellation, wireless charging, and 8h battery life.',
    'Noise cancelling wireless earbuds with charging case',
    'EARB-001', 179.99, 229.99, 95.00, 89, true, 0.06,
    '["/assets/products/earbuds-1.webp", "/assets/products/earbuds-2.webp"]',
    true, true, '{"wireless", "noise-cancelling", "earbuds"}', 167, 89,
    '2024-11-20 11:20:00'
),
-- Fashion - Men's Clothing
(
    1, 9, 4, 'Premium Leather Jacket', 'premium-leather-jacket',
    'Genuine leather jacket with premium finish, multiple pockets, and comfortable fit.',
    'Genuine leather jacket for men',
    'FASH-001', 199.99, 299.99, 120.00, 28, true, 1.2,
    '["/assets/products/leather-jacket-1.webp", "/assets/products/leather-jacket-2.webp"]',
    true, true, '{"leather", "jacket", "premium"}', 67, 28,
    '2024-09-20 12:00:00'
),
-- Beauty - Skincare
(
    1, 15, 6, 'Vitamin C Serum', 'vitamin-c-serum',
    'Anti-aging vitamin C serum with hyaluronic acid, brightens skin and reduces wrinkles.',
    'Anti-aging vitamin C serum for glowing skin',
    'BEAU-001', 29.99, 39.99, 12.00, 78, true, 0.1,
    '["/assets/products/serum-1.webp", "/assets/products/serum-2.webp"]',
    true, true, '{"skincare", "serum", "anti-aging"}', 156, 78,
    '2024-10-08 11:15:00'
)
ON CONFLICT (tenant_id, slug) DO NOTHING;

-- Insert Orders (if not exists)
INSERT INTO orders (
    tenant_id, user_id, order_number, status, payment_status,
    billing_address_id, shipping_address_id,
    subtotal, tax_amount, shipping_amount, total_amount, currency,
    created_at
) VALUES
(
    1, 1, 'ORD-1001', 'delivered', 'paid',
    1, 1,
    299.99, 27.00, 0, 326.99, 'USD',
    '2024-11-25 10:00:00'
),
(
    1, 1, 'ORD-1002', 'delivered', 'paid',
    1, 2,
    429.97, 38.70, 5.99, 474.66, 'USD',
    '2024-11-20 14:30:00'
),
(
    1, 1, 'ORD-1003', 'shipped', 'paid',
    1, 1,
    179.99, 16.20, 0, 196.19, 'USD',
    '2024-11-22 09:15:00'
)
ON CONFLICT (tenant_id, order_number) DO NOTHING;

-- Insert Order Items (if not exists)
INSERT INTO order_items (tenant_id, order_id, product_id, product_name, product_sku, quantity, unit_price, total_price) VALUES
-- Order 1
(1, 1, 1, 'Premium Wireless Headphones', 'AUDIO-001', 1, 299.99, 299.99),
-- Order 2
(1, 2, 2, 'Smart Fitness Tracker', 'WEAR-001', 2, 89.99, 179.98),
(1, 2, 3, 'True Wireless Earbuds Pro', 'EARB-001', 1, 179.99, 179.99),
(1, 2, 5, 'Vitamin C Serum', 'BEAU-001', 1, 29.99, 29.99),
-- Order 3
(1, 3, 3, 'True Wireless Earbuds Pro', 'EARB-001', 1, 179.99, 179.99)
ON CONFLICT DO NOTHING;

-- Insert Payments (if not exists)
INSERT INTO payments (tenant_id, order_id, user_id, payment_method, payment_gateway, amount, currency, status, created_at) VALUES
(1, 1, 1, 'credit_card', 'stripe', 326.99, 'USD', 'completed', '2024-11-25 10:05:00'),
(1, 2, 1, 'paypal', 'paypal', 474.66, 'USD', 'completed', '2024-11-20 14:35:00'),
(1, 3, 1, 'credit_card', 'stripe', 196.19, 'USD', 'completed', '2024-11-22 09:20:00')
ON CONFLICT DO NOTHING;

-- Insert Global Banks (if not exists)
INSERT INTO banks (country_code, bank_code, bank_name, bank_full_name, bank_type) VALUES
-- Indian Banks
('IN', 'SBI', 'State Bank of India', 'State Bank of India', 'public'),
('IN', 'HDFC', 'HDFC Bank', 'HDFC Bank Limited', 'private'),
('IN', 'ICICI', 'ICICI Bank', 'ICICI Bank Limited', 'private'),
-- US Banks
('US', 'BOA', 'Bank of America', 'Bank of America', 'commercial'),
('US', 'CHASE', 'Chase Bank', 'JPMorgan Chase Bank', 'commercial'),
-- UK Banks
('GB', 'HSBC', 'HSBC', 'HSBC Bank plc', 'commercial'),
('GB', 'BARCLAYS', 'Barclays', 'Barclays Bank', 'commercial')
ON CONFLICT (country_code, bank_code) DO NOTHING;

-- Insert Tax Rates (if not exists)
INSERT INTO country_tax_rates (tenant_id, country_code, country_name, tax_rate, tax_type) VALUES
(1, 'US', 'United States', 0, 'sales_tax'),
(1, 'GB', 'United Kingdom', 20, 'vat'),
(1, 'IN', 'India', 18, 'gst')
ON CONFLICT (tenant_id, country_code) DO NOTHING;

INSERT INTO state_tax_rates (tenant_id, country_code, state_code, state_name, tax_rate, tax_type) VALUES
-- Indian States GST
(1, 'IN', 'MH', 'Maharashtra', 18, 'standard'),
(1, 'IN', 'DL', 'Delhi', 18, 'standard'),
(1, 'IN', 'KA', 'Karnataka', 18, 'standard'),
-- US State Sales Tax
(1, 'US', 'CA', 'California', 7.25, 'sales_tax'),
(1, 'US', 'NY', 'New York', 8.875, 'sales_tax')
ON CONFLICT (tenant_id, country_code, state_code) DO NOTHING;

-- Insert Default Settings (if not exists)
INSERT INTO frontend_settings (tenant_id, site_name, contact_email, default_currency) VALUES
(1, 'My Awesome Store', 'hello@example.com', 'USD')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO tax_settings (tenant_id, tax_calculation_enabled, tax_system) VALUES
(1, true, 'vat')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO security_settings (tenant_id) VALUES (1)
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO session_settings (tenant_id) VALUES (1)
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO rate_limit_settings (tenant_id) VALUES (1)
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO shipping_settings (tenant_id) VALUES (1)
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO currency_settings (tenant_id) VALUES (1)
ON CONFLICT (tenant_id) DO NOTHING;

-- ==================== CREATE INDEXES ====================

-- Core Indexes
CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);

-- Product Indexes
CREATE INDEX IF NOT EXISTS idx_products_tenant_id ON products(tenant_id);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_brand_id ON products(brand_id);
CREATE INDEX IF NOT EXISTS idx_products_slug ON products(slug);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);

-- Order Indexes
CREATE INDEX IF NOT EXISTS idx_orders_tenant_id ON orders(tenant_id);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);

-- Payment Indexes
CREATE INDEX IF NOT EXISTS idx_payments_tenant_id ON payments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);

-- Address Indexes
CREATE INDEX IF NOT EXISTS idx_user_addresses_user_id ON user_addresses(user_id);
CREATE INDEX IF NOT EXISTS idx_user_addresses_tenant_id ON user_addresses(tenant_id);

-- Inventory Indexes
CREATE INDEX IF NOT EXISTS idx_inventory_logs_product_id ON inventory_logs(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_logs_tenant_id ON inventory_logs(tenant_id);

-- Settings Indexes
CREATE INDEX IF NOT EXISTS idx_settings_tenant_id ON frontend_settings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tax_rates_country ON country_tax_rates(country_code);
CREATE INDEX IF NOT EXISTS idx_state_tax_rates_state ON state_tax_rates(state_code);

-- Audit Indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

SELECT '🚀 Database initialized successfully with proper structure!' as status;

-- ==================== INSERT SETTINGS DATA ====================

-- Insert Session Settings (if not exists)
INSERT INTO session_settings (tenant_id, session_timeout, max_sessions_per_user, allow_concurrent_sessions) VALUES
(1, 3600, 5, true)
ON CONFLICT (tenant_id) DO UPDATE SET
    session_timeout = EXCLUDED.session_timeout,
    max_sessions_per_user = EXCLUDED.max_sessions_per_user,
    allow_concurrent_sessions = EXCLUDED.allow_concurrent_sessions;

-- Insert Rate Limit Settings (if not exists)
INSERT INTO rate_limit_settings (tenant_id, requests_per_minute, requests_per_hour, burst_limit) VALUES
(1, 60, 1000, 10)
ON CONFLICT (tenant_id) DO UPDATE SET
    requests_per_minute = EXCLUDED.requests_per_minute,
    requests_per_hour = EXCLUDED.requests_per_hour,
    burst_limit = EXCLUDED.burst_limit;

-- Insert Security Settings (if not exists)
INSERT INTO security_settings (tenant_id, password_min_length, password_require_uppercase, password_require_lowercase, password_require_numbers, password_require_symbols, max_login_attempts, lockout_duration_minutes) VALUES
(1, 8, true, true, true, true, 5, 30)
ON CONFLICT (tenant_id) DO UPDATE SET
    password_min_length = EXCLUDED.password_min_length,
    password_require_uppercase = EXCLUDED.password_require_uppercase,
    password_require_lowercase = EXCLUDED.password_require_lowercase,
    password_require_numbers = EXCLUDED.password_require_numbers,
    password_require_symbols = EXCLUDED.password_require_symbols,
    max_login_attempts = EXCLUDED.max_login_attempts,
    lockout_duration_minutes = EXCLUDED.lockout_duration_minutes;

-- Insert Site Settings (Service URLs) (if not exists)
INSERT INTO site_settings (tenant_id, setting_key, setting_value) VALUES
(1, 'auth_service_url', 'http://auth-service:8000'),
(1, 'user_service_url', 'http://user-service:8000'),
(1, 'cart_service_url', 'http://cart-service:8000'),
(1, 'tenant_service_url', 'http://tenant-service:8000'),
(1, 'product_service_url', 'http://product-service:8000'),
(1, 'payment_service_url', 'http://payment-service:8000'),
(1, 'notification_service_url', 'http://notification-service:8000'),
(1, 'site_name', 'Pavitra Store'),
(1, 'contact_email', 'hello@pavitra.com'),
(1, 'contact_phone', '+91-9876543210'),
(1, 'default_currency', 'INR')
ON CONFLICT (tenant_id, setting_key) DO UPDATE SET
    setting_value = EXCLUDED.setting_value;

-- Insert Frontend Settings (if not exists)
INSERT INTO frontend_settings (tenant_id, site_name, contact_email, contact_phone, default_currency, primary_color, secondary_color) VALUES
(1, 'Pavitra Store', 'hello@pavitra.com', '+91-9876543210', 'INR', '#2563eb', '#64748b')
ON CONFLICT (tenant_id) DO UPDATE SET
    site_name = EXCLUDED.site_name,
    contact_email = EXCLUDED.contact_email,
    contact_phone = EXCLUDED.contact_phone,
    default_currency = EXCLUDED.default_currency,
    primary_color = EXCLUDED.primary_color,
    secondary_color = EXCLUDED.secondary_color;

-- Insert Tax Settings (if not exists)
INSERT INTO tax_settings (tenant_id, tax_calculation_enabled, prices_include_tax, display_prices_with_tax, tax_system, default_tax_rate) VALUES
(1, true, false, true, 'gst', 18.0)
ON CONFLICT (tenant_id) DO UPDATE SET
    tax_calculation_enabled = EXCLUDED.tax_calculation_enabled,
    prices_include_tax = EXCLUDED.prices_include_tax,
    display_prices_with_tax = EXCLUDED.display_prices_with_tax,
    tax_system = EXCLUDED.tax_system,
    default_tax_rate = EXCLUDED.default_tax_rate;

-- Insert Shipping Settings (if not exists)
INSERT INTO shipping_settings (tenant_id, shipping_calculation_enabled, free_shipping_enabled, free_shipping_min_amount, origin_country, origin_state, origin_city) VALUES
(1, true, true, 500.00, 'IN', 'Maharashtra', 'Mumbai')
ON CONFLICT (tenant_id) DO UPDATE SET
    shipping_calculation_enabled = EXCLUDED.shipping_calculation_enabled,
    free_shipping_enabled = EXCLUDED.free_shipping_enabled,
    free_shipping_min_amount = EXCLUDED.free_shipping_min_amount,
    origin_country = EXCLUDED.origin_country,
    origin_state = EXCLUDED.origin_state,
    origin_city = EXCLUDED.origin_city;

-- Insert Currency Settings (if not exists)
INSERT INTO currency_settings (tenant_id, default_currency, available_currencies, default_language, available_languages, timezone) VALUES
(1, 'INR', '{"INR", "USD", "EUR"}', 'en', '{"en", "hi"}', 'Asia/Kolkata')
ON CONFLICT (tenant_id) DO UPDATE SET
    default_currency = EXCLUDED.default_currency,
    available_currencies = EXCLUDED.available_currencies,
    default_language = EXCLUDED.default_language,
    available_languages = EXCLUDED.available_languages,
    timezone = EXCLUDED.timezone;

SELECT '✅ Settings data inserted successfully!' as status;
SELECT '✅ Settings data inserted successfully!' as status;