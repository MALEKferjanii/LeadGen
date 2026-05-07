-- LeadGen Francophone 360+ — Database Schema
-- PostgreSQL 15

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Schéma Metabase isolé pour éviter les conflits avec les données applicatives
CREATE SCHEMA IF NOT EXISTS metabase;
CREATE SCHEMA IF NOT EXISTS n8n;

CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    linkedin_url VARCHAR(500) UNIQUE,
    website VARCHAR(500),
    country CHAR(2),
    city VARCHAR(100),
    sector VARCHAR(80),
    company_size_min INT,
    company_size_max INT,
    description TEXT,
    technologies TEXT[] DEFAULT '{}',
    source VARCHAR(50) NOT NULL,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    full_name VARCHAR(255),
    job_title VARCHAR(255),
    email VARCHAR(255),
    linkedin_url VARCHAR(500) UNIQUE,
    is_decision_maker BOOLEAN DEFAULT FALSE,
    source VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    opportunity_type VARCHAR(50),
    technologies TEXT[] DEFAULT '{}',
    budget_min INT,
    budget_max INT,
    source_url VARCHAR(1000),
    source_platform VARCHAR(80),
    country CHAR(2),
    status VARCHAR(30) DEFAULT 'new',
    priority_score SMALLINT DEFAULT 0,
    sector_label VARCHAR(80),
    tech_label VARCHAR(80),
    priority_label VARCHAR(20),
    nlp_confidence FLOAT,
    posted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID REFERENCES opportunities(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    generated_linkedin_msg TEXT,
    generated_email TEXT,
    status VARCHAR(30) DEFAULT 'draft',
    sent_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes pour les requêtes Metabase
CREATE INDEX idx_opp_country ON opportunities(country);
CREATE INDEX idx_opp_sector ON opportunities(sector_label);
CREATE INDEX idx_opp_score ON opportunities(priority_score DESC);
CREATE INDEX idx_opp_status ON opportunities(status);
CREATE INDEX idx_opp_created ON opportunities(created_at DESC);
CREATE INDEX idx_comp_country ON companies(country);
CREATE INDEX idx_comp_sector ON companies(sector);

-- Trigger auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_companies_updated
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_opp_updated
    BEFORE UPDATE ON opportunities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
