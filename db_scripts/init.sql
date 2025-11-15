cat > multi_tenant_schema.sql << EOF
-- ==============================================
-- Multi-Tenant SaaS Database Schema
-- Includes full connectivity, constraints, enumerations, defaults
-- ==============================================

-- TENANTS
CREATE TABLE tenants (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_tenant_name(name),
    UNIQUE KEY uq_tenant_domain(domain)
);

-- USERS
CREATE TABLE users (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_user_email(tenant_id,email),
    UNIQUE KEY uq_user_phone(tenant_id,phone),
    CONSTRAINT fk_users_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- PASSWORD HISTORY
CREATE TABLE user_password_history (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    KEY idx_user_id(user_id),
    CONSTRAINT fk_user_password_history_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ROLES
CREATE TABLE user_roles (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    description TEXT NULL,
    is_system_role BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_role_name(tenant_id,name),
    CONSTRAINT fk_user_roles_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- PERMISSIONS
CREATE TABLE permissions (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT NULL,
    module VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_permission_name(tenant_id,name),
    CONSTRAINT fk_permissions_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- ROLE PERMISSIONS
CREATE TABLE role_permissions (
    id INT NOT NULL AUTO_INCREMENT,
    role_id INT NOT NULL,
    permission_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_role_permission(role_id, permission_id),
    CONSTRAINT fk_role_permissions_role FOREIGN KEY(role_id) REFERENCES user_roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

-- USER ROLE ASSIGNMENTS
CREATE TABLE user_role_assignments (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    assigned_by INT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_user_role(user_id, role_id),
    CONSTRAINT fk_user_role_assignments_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_role_assignments_role FOREIGN KEY(role_id) REFERENCES user_roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_role_assignments_by FOREIGN KEY(assigned_by) REFERENCES users(id)
);

-- COUNTRIES
CREATE TABLE countries (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    iso_code CHAR(3) NOT NULL,
    PRIMARY KEY(id),
    UNIQUE KEY uq_country_iso(iso_code)
);

-- STATES
CREATE TABLE states (
    id INT NOT NULL AUTO_INCREMENT,
    country_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(10) NULL,
    PRIMARY KEY(id),
    UNIQUE KEY uq_state_name(country_id, name),
    CONSTRAINT fk_states_country FOREIGN KEY(country_id) REFERENCES countries(id) ON DELETE CASCADE
);

-- CITIES
CREATE TABLE cities (
    id INT NOT NULL AUTO_INCREMENT,
    state_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    PRIMARY KEY(id),
    UNIQUE KEY uq_city_name(state_id, name),
    CONSTRAINT fk_cities_state FOREIGN KEY(state_id) REFERENCES states(id) ON DELETE CASCADE
);

-- PRODUCTS
CREATE TABLE products (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    sku VARCHAR(50) NULL,
    price DECIMAL(12,2) NOT NULL,
    stock INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_product_sku(tenant_id, sku),
    CONSTRAINT fk_products_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- ORDERS
CREATE TABLE orders (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    user_id INT NOT NULL,
    status ENUM('pending','paid','shipped','completed','cancelled','refunded') DEFAULT 'pending',
    total_amount DECIMAL(12,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    CONSTRAINT fk_orders_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_orders_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- PAYMENT HISTORY
CREATE TABLE payments (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    order_id INT NOT NULL,
    payment_gateway ENUM('razorpay','stripe','paypal','payu','ccavenue','instamojo','cod','wallet','upi') NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency CHAR(3) DEFAULT 'INR',
    status ENUM('pending','success','failed','refunded') DEFAULT 'pending',
    transaction_id VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    CONSTRAINT fk_payments_order FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_payments_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- NOTIFICATION LOGS
CREATE TABLE notification_logs (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    type ENUM('email','sms','push','telegram','whatsapp') NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NULL,
    message TEXT NULL,
    status ENUM('sent','failed','pending') DEFAULT 'sent',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    KEY idx_notification_tenant(tenant_id),
    CONSTRAINT fk_notification_logs_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- USER NOTIFICATION PREFERENCES
CREATE TABLE user_notification_preferences (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    notification_method ENUM('email','telegram','whatsapp','sms','push') NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_user_method(user_id, notification_method),
    CONSTRAINT fk_user_notification_preferences_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- TENANT SETTINGS SEPARATE TABLES
CREATE TABLE tenant_settings_payment (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    key_name VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    value_type ENUM('string','number','boolean','json') DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_payment_setting(tenant_id, key_name),
    CONSTRAINT fk_tenant_settings_payment_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE tenant_settings_notification (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    key_name VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    value_type ENUM('string','number','boolean','json') DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_notification_setting(tenant_id, key_name),
    CONSTRAINT fk_tenant_settings_notification_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE tenant_settings_infra (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    key_name VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    value_type ENUM('string','number','boolean','json') DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_infra_setting(tenant_id, key_name),
    CONSTRAINT fk_tenant_settings_infra_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- TENANT SETTINGS GENERAL / SITE SETTINGS
CREATE TABLE tenant_settings_general (
    id INT NOT NULL AUTO_INCREMENT,
    tenant_id INT NOT NULL,
    key_name VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    value_type ENUM('string','number','boolean','json') DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY(id),
    UNIQUE KEY uq_general_setting(tenant_id, key_name),
    CONSTRAINT fk_tenant_settings_general_tenant FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

EOF
