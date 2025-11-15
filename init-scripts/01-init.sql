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

-- Multi-Tenant Management
CREATE TABLE tenants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    country_code VARCHAR(3) NOT NULL, -- ISO country code
    default_currency VARCHAR(3) DEFAULT 'USD',
    tax_type tax_type NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status tenant_status DEFAULT 'active'
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
    country_id BIGINT NOT NULL,
    region_id BIGINT,
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

-- Internationalization & Regions
CREATE TABLE countries (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(3) NOT NULL UNIQUE, -- ISO code
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
    country_code VARCHAR(3) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    status bank_status DEFAULT 'active',
    processing_fee DECIMAL(5,2) DEFAULT 0,
    min_amount DECIMAL(10,2) DEFAULT 0,
    max_amount DECIMAL(10,2) DEFAULT 100000,
    supported_gateways payment_gateway[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, bank_code, country_code),
    -- Foreign Key to countries table
    FOREIGN KEY (country_code) REFERENCES countries(code) ON DELETE RESTRICT
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
    country_code VARCHAR(3) NOT NULL,
    min_amount DECIMAL(10,2) DEFAULT 0,
    max_amount DECIMAL(10,2) DEFAULT 50000,
    processing_fee DECIMAL(5,2) DEFAULT 0,
    supported_currencies VARCHAR(3)[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, wallet_code, country_code),
    -- Foreign Key to countries table
    FOREIGN KEY (country_code) REFERENCES countries(code) ON DELETE RESTRICT
);

-- Card Networks Support with proper FKs
CREATE TABLE card_support (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    card_network card_network NOT NULL,
    card_type card_type NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    country_code VARCHAR(3) NOT NULL,
    processing_fee_percentage DECIMAL(5,2) DEFAULT 0,
    processing_fee_fixed DECIMAL(10,2) DEFAULT 0,
    min_amount DECIMAL(10,2) DEFAULT 0,
    max_amount DECIMAL(10,2) DEFAULT 100000,
    supported_gateways payment_gateway[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, card_network, card_type, country_code),
    -- Foreign Key to countries table
    FOREIGN KEY (country_code) REFERENCES countries(code) ON DELETE RESTRICT
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

-- Indexes for better performance
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

-- Add foreign key from users to tenants
ALTER TABLE users ADD CONSTRAINT fk_users_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL;


-- Create admin user with superuser privileges
CREATE USER admin WITH PASSWORD 'admin123' SUPERUSER CREATEDB CREATEROLE INHERIT LOGIN;

-- Grant all privileges on the database to admin
GRANT ALL PRIVILEGES ON DATABASE pavitra_db TO admin;

-- Allow admin to connect from anywhere
ALTER USER admin WITH SUPERUSER;

-- Create extensions that might be useful for e-commerce
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set up additional configuration
ALTER SYSTEM SET listen_addresses = '*';
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Create a default tenant first
INSERT INTO tenants (id, name, domain, contact_email, country_code, tax_type, status)
VALUES (1, 'Default Tenant', 'default.local', 'admin@default.local', 'IN', 'gst', 'active')
ON CONFLICT (id) DO NOTHING;

-- Ensure we have some countries first
INSERT INTO countries (name, code, currency_code, is_active) VALUES
('India', 'IN', 'INR', true),
('United States', 'US', 'USD', true),
('United Kingdom', 'UK', 'GBP', true)
ON CONFLICT (code) DO NOTHING;

-- Sample data for banking (using the tenant we just created)
INSERT INTO supported_banks (tenant_id, bank_name, bank_code, country_code, is_active) VALUES
(1, 'State Bank of India', 'SBIN0000001', 'IN', true),
(1, 'HDFC Bank', 'HDFC0000001', 'IN', true),
(1, 'ICICI Bank', 'ICIC0000001', 'IN', true)
ON CONFLICT DO NOTHING;

INSERT INTO upi_support (tenant_id, upi_id, upi_name, is_active) VALUES
(1, 'merchant@ybl', 'Google Pay', true),
(1, 'merchant@paytm', 'PayTM UPI', true)
ON CONFLICT DO NOTHING;

INSERT INTO wallet_support (tenant_id, wallet_name, wallet_code, country_code, is_active) VALUES
(1, 'PayTM Wallet', 'PAYTM_WALLET', 'IN', true),
(1, 'PhonePe Wallet', 'PHONEPE_WALLET', 'IN', true)
ON CONFLICT DO NOTHING;

INSERT INTO card_support (tenant_id, card_network, card_type, country_code, is_active) VALUES
(1, 'visa', 'credit', 'IN', true),
(1, 'mastercard', 'debit', 'IN', true),
(1, 'rupay', 'debit', 'IN', true)
ON CONFLICT DO NOTHING;

INSERT INTO payment_gateway_config (tenant_id, gateway, is_active, is_live) VALUES
(1, 'razorpay', true, false),
(1, 'stripe', true, false)
ON CONFLICT DO NOTHING;

-- Reload configuration
SELECT pg_reload_conf();