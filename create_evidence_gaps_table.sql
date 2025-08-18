-- SQL script to create the evidence_gaps table for oral health research
CREATE TABLE IF NOT EXISTS evidence_gaps (
    id SERIAL PRIMARY KEY,
    review_id VARCHAR(255) NOT NULL,
    review_title TEXT,
    authors TEXT,
    year VARCHAR(10),
    doi TEXT,
    table_number INTEGER,
    table_title TEXT,
    population TEXT,
    intervention TEXT,
    comparison TEXT,
    outcome TEXT NOT NULL,
    pico TEXT,
    grade_rating VARCHAR(50) NOT NULL,
    certainty VARCHAR(50),
    participants VARCHAR(100),
    studies VARCHAR(100),
    comments TEXT,
    assumed_risk TEXT,
    corresponding_risk TEXT,
    relative_effect VARCHAR(255),
    
    -- Additional columns for oral health data
    measure VARCHAR(50), -- RR, OR, MD, etc.
    effect DECIMAL(10,4),
    ci_lower DECIMAL(10,4),
    ci_upper DECIMAL(10,4),
    significant BOOLEAN,
    number_of_participants INTEGER,
    number_of_studies INTEGER,
    
    -- GRADE downgrading reasons (boolean fields)
    risk_of_bias BOOLEAN DEFAULT FALSE,
    imprecision BOOLEAN DEFAULT FALSE,
    inconsistency BOOLEAN DEFAULT FALSE,
    indirectness BOOLEAN DEFAULT FALSE,
    publication_bias BOOLEAN DEFAULT FALSE,
    
    -- Specific GRADE downgrading reasons text
    reasons_for_grade TEXT,
    
    -- Rate per 100,000 (for non-SoF data)
    rate_per_100000 DECIMAL(10,2),
    
    -- Data source tracking
    data_source VARCHAR(50) DEFAULT 'sof', -- 'sof' or 'non_sof'
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_review_id ON evidence_gaps(review_id);
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_grade_rating ON evidence_gaps(grade_rating);
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_population ON evidence_gaps(population);
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_intervention ON evidence_gaps(intervention);
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_data_source ON evidence_gaps(data_source);
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_significant ON evidence_gaps(significant);

-- Create a composite index for filtering
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_composite ON evidence_gaps(grade_rating, data_source, significant);

-- Create an index for text search
CREATE INDEX IF NOT EXISTS idx_evidence_gaps_text_search ON evidence_gaps 
USING gin(to_tsvector('english', review_title || ' ' || population || ' ' || intervention || ' ' || comparison || ' ' || outcome));
