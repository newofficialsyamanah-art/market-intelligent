-- Market Intelligence & Prospect Identification System
-- MySQL schema (also auto-created by SQLAlchemy, this file is for manual setup / reference)

CREATE DATABASE IF NOT EXISTS market_intelligence CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE market_intelligence;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin','business_analyst','marketing','management','procurement') NOT NULL DEFAULT 'business_analyst',
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    source_type ENUM('file','url','api','manual') NOT NULL,
    config_json TEXT,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS raw_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT,
    source_type ENUM('file','url','api','manual') NOT NULL,
    original_name VARCHAR(255),
    raw_excerpt TEXT,
    extracted_json LONGTEXT,
    ai_classification VARCHAR(100),
    column_mapping_json TEXT,
    status ENUM('new','extracted','classified','mapped','validated','processed','error') DEFAULT 'new',
    error_message TEXT,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES data_sources(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS prospects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    industry VARCHAR(150),
    region VARCHAR(150),
    company_size VARCHAR(50),
    website VARCHAR(255),
    contact_name VARCHAR(150),
    contact_email VARCHAR(150),
    contact_phone VARCHAR(50),
    description TEXT,
    segment VARCHAR(100),
    score INT DEFAULT 0,
    score_reason TEXT,
    status ENUM('new','qualified','contacted','converted','rejected') DEFAULT 'new',
    raw_data_id INT,
    organization_id INT NULL,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_data_id) REFERENCES raw_data(id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);


CREATE TABLE IF NOT EXISTS market_analyses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_type ENUM('trend','industry_distribution','region_distribution','company_size','product_recommendation') NOT NULL,
    title VARCHAR(255),
    result_json LONGTEXT,
    ai_summary TEXT,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    product VARCHAR(150) NULL DEFAULT 'Jersey / Custom Teamwear',
    target_segment VARCHAR(150) NULL,
    organization_type VARCHAR(100) NULL,
    province VARCHAR(100) NULL,
    city VARCHAR(100) NULL,
    start_date DATETIME NULL,
    end_date DATETIME NULL,
    channel VARCHAR(100) NULL,
    segment_filter_json TEXT,
    prospect_count INT DEFAULT 0,
    status ENUM('draft','ready','exported','active','completed','closed') DEFAULT 'draft',
    created_by INT,
    notes TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS campaign_targets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    campaign_id INT NOT NULL,
    organization_id INT NOT NULL,
    product_fit_snapshot VARCHAR(255) NULL,
    opportunity_score_snapshot INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'targeted',
    notes TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ct_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    CONSTRAINT fk_ct_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    UNIQUE KEY uq_campaign_target_org (campaign_id, organization_id),
    KEY idx_ct_campaign (campaign_id),
    KEY idx_ct_org (organization_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255),
    report_type VARCHAR(100),
    content_json LONGTEXT,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(150),
    detail TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cron_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150),
    task_type VARCHAR(100),
    schedule_cron VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    last_run DATETIME NULL,
    last_status VARCHAR(255),
    duration_seconds FLOAT NULL,
    records_processed INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    error_summary TEXT NULL,
    next_run DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_agent_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_task VARCHAR(100) NOT NULL,
    model_name VARCHAR(100) DEFAULT 'llama-3.3-70b-versatile',
    prompt_template LONGTEXT,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS discovery_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    source_kind ENUM('organization','event') NOT NULL,
    category VARCHAR(100),
    query_text VARCHAR(500),
    region VARCHAR(100),
    source_urls_json TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_run DATETIME NULL,
    last_status VARCHAR(255),
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS procurement_suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    product VARCHAR(100) NOT NULL,
    material VARCHAR(255),
    region VARCHAR(150),
    website VARCHAR(500),
    source_url VARCHAR(500) NOT NULL,
    contact_email VARCHAR(150),
    contact_phone VARCHAR(100),
    description TEXT,
    fit_score INT DEFAULT 0,
    recommendation_json LONGTEXT,
    verification_status VARCHAR(50) DEFAULT 'discovered',
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id),
    KEY idx_procurement_product (product),
    KEY idx_procurement_fit_score (fit_score)
);

CREATE TABLE IF NOT EXISTS organizations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NULL,
    domain VARCHAR(150) NULL,
    organization_type VARCHAR(100) NOT NULL DEFAULT 'Perusahaan',
    industry VARCHAR(150),
    address VARCHAR(500),
    city VARCHAR(100),
    province VARCHAR(100),
    phone VARCHAR(100),
    email VARCHAR(150),
    website VARCHAR(500),
    social_json TEXT,
    source_url VARCHAR(500) NULL,
    description TEXT,
    product_fit VARCHAR(255) NULL,
    opportunity_score INT DEFAULT 0,
    priority_tier VARCHAR(50) NULL,
    source_id INT NULL,
    source_type VARCHAR(50) DEFAULT 'bps',
    employee_size VARCHAR(50) NULL,
    sport VARCHAR(100) NULL,
    organization_subtype VARCHAR(100) NULL,
    ai_scoring_json TEXT NULL,
    relevance_score INT DEFAULT 0,
    verification_status VARCHAR(50) DEFAULT 'discovered',
    provenance_json TEXT NULL,
    data_freshness DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_org_normalized_name (normalized_name),
    KEY idx_org_domain (domain),
    KEY idx_org_opportunity_score (opportunity_score),
    KEY idx_org_priority_tier (priority_tier),
    FOREIGN KEY (source_id) REFERENCES data_sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    event_type VARCHAR(150),
    organizer VARCHAR(255),
    organizer_id INT NULL,
    status VARCHAR(50) DEFAULT 'upcoming',
    start_date DATETIME NULL,
    end_date DATETIME NULL,
    venue VARCHAR(255),
    city VARCHAR(100),
    province VARCHAR(100),
    address VARCHAR(500),
    website VARCHAR(500),
    social_json TEXT,
    source_url VARCHAR(500) NULL,
    description TEXT,
    relevance_notes TEXT NULL,
    relevance_score INT DEFAULT 0,
    verification_status VARCHAR(50) DEFAULT 'discovered',
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_events_status (status),
    FOREIGN KEY (organizer_id) REFERENCES organizations(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS event_participants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    organization_id INT NOT NULL,
    role ENUM('organizer', 'exhibitor', 'sponsor', 'partner', 'speaker') NOT NULL,
    booth_number VARCHAR(50) NULL,
    notes TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ep_event FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    CONSTRAINT fk_ep_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    UNIQUE KEY uq_event_org_role (event_id, organization_id, role),
    KEY idx_ep_event (event_id),
    KEY idx_ep_org (organization_id)
);

CREATE TABLE IF NOT EXISTS duplicate_candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    organization_id INT NOT NULL,
    candidate_name VARCHAR(255) NOT NULL,
    candidate_source VARCHAR(100) NULL,
    candidate_payload_json TEXT NULL,
    match_tier VARCHAR(50) NOT NULL,
    confidence_score FLOAT NOT NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    reviewed_by INT NULL,
    reviewed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_cand_org (organization_id),
    KEY idx_cand_status (status),
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
);
