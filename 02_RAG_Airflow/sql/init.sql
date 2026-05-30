-- RAG Pipeline - PostgreSQL Initialization
-- This creates metadata tracking tables (Qdrant handles vectors)
-- Run this to track pipeline runs, evaluations, and document history

-- Enable UUID extension for unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Documents metadata table
-- Tracks all documents that have been processed
-- ============================================
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(50) NOT NULL,  -- 's3', 'filesystem', 'url', 'postgres'
    source_uri TEXT NOT NULL,           -- Full URI of document
    filename VARCHAR(500),
    content_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash of content
    file_size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(content_hash)
);

CREATE INDEX idx_documents_source_type ON documents(source_type);
CREATE INDEX idx_documents_content_hash ON documents(content_hash);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);

-- ============================================
-- Chunks metadata table
-- Tracks all text chunks created from documents
-- ============================================
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,       -- Position in original document
    total_chunks INTEGER NOT NULL,      -- Total chunks for this document
    chunk_text TEXT NOT NULL,
    token_count INTEGER,
    embedding_model VARCHAR(100),
    qdrant_point_id VARCHAR(100),       -- Reference to Qdrant point ID
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_created_at ON chunks(created_at DESC);

-- ============================================
-- Evaluation results table
-- Tracks retrieval quality metrics over time
-- ============================================
CREATE TABLE IF NOT EXISTS eval_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(100),                -- Airflow run ID or MLflow run ID
    collection_name VARCHAR(100) NOT NULL,
    total_queries INTEGER NOT NULL,
    recall_at_1 NUMERIC(5,4),
    recall_at_5 NUMERIC(5,4),
    recall_at_10 NUMERIC(5,4),
    mrr NUMERIC(5,4),                   -- Mean Reciprocal Rank
    avg_query_latency_ms NUMERIC(10,2),
    passed_threshold BOOLEAN,
    threshold_value NUMERIC(5,4),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_eval_results_created_at ON eval_results(created_at DESC);
CREATE INDEX idx_eval_results_collection ON eval_results(collection_name);

-- ============================================
-- Ingestion log table
-- Tracks each pipeline run
-- ============================================
CREATE TABLE IF NOT EXISTS ingestion_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id VARCHAR(100) NOT NULL,
    dag_id VARCHAR(100),
    execution_date TIMESTAMP,
    documents_extracted INTEGER DEFAULT 0,
    documents_deduplicated INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    chunks_embedded INTEGER DEFAULT 0,
    vectors_upserted INTEGER DEFAULT 0,
    status VARCHAR(20),                 -- 'running', 'success', 'failed', 'rolled_back'
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_ingestion_log_run_id ON ingestion_log(run_id);
CREATE INDEX idx_ingestion_log_status ON ingestion_log(status);
CREATE INDEX idx_ingestion_log_started_at ON ingestion_log(started_at DESC);

-- ============================================
-- Helper function: Get latest eval score
-- ============================================
CREATE OR REPLACE FUNCTION get_latest_recall()
RETURNS NUMERIC AS $$
    SELECT recall_at_5 
    FROM eval_results 
    ORDER BY created_at DESC 
    LIMIT 1;
$$ LANGUAGE SQL;

-- ============================================
-- Helper function: Get pipeline health status
-- ============================================
CREATE OR REPLACE FUNCTION get_pipeline_health()
RETURNS TABLE (
    last_run_time TIMESTAMP,
    last_status VARCHAR,
    last_recall NUMERIC,
    total_documents BIGINT,
    total_chunks BIGINT
) AS $$
    SELECT 
        il.completed_at as last_run_time,
        il.status as last_status,
        er.recall_at_5 as last_recall,
        COUNT(DISTINCT d.id) as total_documents,
        COUNT(DISTINCT c.id) as total_chunks
    FROM ingestion_log il
    LEFT JOIN eval_results er ON il.run_id = er.run_id
    CROSS JOIN documents d
    CROSS JOIN chunks c
    WHERE il.completed_at IS NOT NULL
    ORDER BY il.completed_at DESC
    LIMIT 1;
$$ LANGUAGE SQL;

-- ============================================
-- Sample data for testing (optional)
-- ============================================
-- Uncomment to insert test data
-- INSERT INTO documents (source_type, source_uri, filename, content_hash, file_size_bytes)
-- VALUES 
--     ('filesystem', '/data/test.pdf', 'test.pdf', 'abc123', 1024),
--     ('s3', 's3://bucket/doc.pdf', 'doc.pdf', 'def456', 2048);

COMMENT ON TABLE documents IS 'Tracks all processed documents with metadata';
COMMENT ON TABLE chunks IS 'Tracks text chunks created from documents';
COMMENT ON TABLE eval_results IS 'Stores retrieval evaluation metrics over time';
COMMENT ON TABLE ingestion_log IS 'Logs each pipeline execution run';