-- PPV Fulfillment Monitor Database Schema
-- PostgreSQL initialization script

-- Create main database (if not exists)
CREATE DATABASE ppv_fulfillment_dev;
CREATE DATABASE ppv_fulfillment_test;

-- Connect to development database
\c ppv_fulfillment_dev;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data uploads table
CREATE TABLE data_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    upload_path TEXT NOT NULL,
    uploaded_by UUID REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'pending', -- pending, processed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL
);

-- Data analysis results table
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_id UUID REFERENCES data_uploads(id),
    analysis_type VARCHAR(100) NOT NULL, -- trend_analysis, correlation, etc.
    results JSONB NOT NULL, -- Store analysis results as JSON
    chart_config JSONB NULL, -- Plotly chart configuration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dashboards table
CREATE TABLE dashboards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL, -- Dashboard layout and widget config
    created_by UUID REFERENCES users(id),
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_data_uploads_status ON data_uploads(status);
CREATE INDEX idx_data_uploads_created_at ON data_uploads(created_at);
CREATE INDEX idx_analysis_results_upload_id ON analysis_results(upload_id);
CREATE INDEX idx_analysis_results_type ON analysis_results(analysis_type);
CREATE INDEX idx_dashboards_created_by ON dashboards(created_by);

-- Insert default admin user
INSERT INTO users (id, email, name) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'admin@example.com', 'Admin User');