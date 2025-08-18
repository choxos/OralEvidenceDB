# PostgreSQL Deployment Guide for Evidence Gaps

## Overview

The Evidence Gaps feature in OralEvidenceDB is fully compatible with PostgreSQL and includes comprehensive data import capabilities for oral health research analysis.

## PostgreSQL Setup

### 1. Database Configuration

Ensure your PostgreSQL database is configured with the credentials specified in your settings:

```bash
# VPS PostgreSQL setup (as per your deployment guide)
Database: oral_production
User: oral_user  
Password: Choxos10203040
Host: localhost
Port: 5432
```

### 2. Evidence Gaps Data Import

#### Using Django Management Command (Recommended for VPS)

The recommended approach for PostgreSQL deployment is to use the Django management command:

```bash
# Import evidence gaps data using Django ORM (PostgreSQL compatible)
python manage.py import_evidence_gaps --clear

# Or specify custom data directory
python manage.py import_evidence_gaps --data-dir /path/to/data/evidencegaps --clear
```

#### Using Standalone Import Script

Alternatively, you can use the standalone import script:

```bash
# This will auto-detect PostgreSQL and use appropriate syntax
python import_evidence_gaps_data.py
```

### 3. Data Files Required

Place these CSV files in `data/evidencegaps/`:

- `evidencegaps_dental_sofs.csv` - Cochrane Summary of Findings tables
- `evidencegaps_dental_non_sofs.csv` - Additional studies without SoF tables  
- `evidencegaps_cochrane_oral_metadata.csv` - Review metadata

### 4. Database Schema

The evidence_gaps table includes:

**Core Fields:**
- `review_id`, `review_title`, `authors`, `year`, `doi`
- `population`, `intervention`, `comparison`, `outcome`
- `grade_rating` (High, Moderate, Low, Very Low, No Evidence Yet)

**GRADE Assessment:**
- `risk_of_bias`, `imprecision`, `inconsistency`, `indirectness`, `publication_bias`
- `reasons_for_grade` (detailed text explanations)

**Effect Measures:**
- `measure` (RR, OR, MD, etc.), `effect`, `ci_lower`, `ci_upper`
- `significant` (boolean), `number_of_participants`, `number_of_studies`

**Data Source Tracking:**
- `data_source` ('sof' or 'non_sof')
- `rate_per_100000` (for non-SoF data)

## PostgreSQL-Specific Features

### 1. SQL Syntax Compatibility

- Uses `%s` placeholders for PostgreSQL (vs `?` for SQLite)
- `SERIAL PRIMARY KEY` for auto-incrementing IDs
- `DECIMAL(10,4)` for precise numeric values
- `TIMESTAMP WITH TIME ZONE` for proper timezone handling
- Boolean fields with proper `TRUE`/`FALSE` defaults

### 2. Indexing Strategy

Optimized indexes for evidence gaps queries:

```sql
CREATE INDEX idx_evidence_gaps_review_id ON evidence_gaps(review_id);
CREATE INDEX idx_evidence_gaps_grade_rating ON evidence_gaps(grade_rating);
CREATE INDEX idx_evidence_gaps_population ON evidence_gaps(population);
CREATE INDEX idx_evidence_gaps_intervention ON evidence_gaps(intervention);
```

### 3. Performance Optimizations

- Composite indexes for common filter combinations
- Full-text search index for text search functionality
- Proper foreign key relationships where applicable

## Expected Data Volume

Your mature oral health dataset includes:

- **Total Records:** 3,688 evidence gaps
- **SoF Data:** 2,423 records (Cochrane reviews)
- **Non-SoF Data:** 1,265 records (additional studies)

**GRADE Distribution:**
- No Evidence Yet: 2,210 (59.9%)
- Very Low: 789 (21.4%)
- Low: 483 (13.1%)
- Moderate: 180 (4.9%)
- High: 26 (0.7%)

## Deployment Steps

### On Your VPS (91.99.161.136):

1. **Upload Data Files:**
```bash
# Copy CSV files to VPS
scp data/evidencegaps/*.csv xeradb@91.99.161.136:/var/www/oral/data/evidencegaps/
```

2. **Run Import:**
```bash
# SSH to VPS
ssh xeradb@91.99.161.136

# Navigate to project directory
cd /var/www/oral

# Import evidence gaps data
python manage.py import_evidence_gaps --clear
```

3. **Verify Import:**
```bash
# Check data was imported correctly
python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute('SELECT COUNT(*) FROM evidence_gaps')
print(f'Total records: {cursor.fetchone()[0]}')
cursor.execute('SELECT grade_rating, COUNT(*) FROM evidence_gaps GROUP BY grade_rating ORDER BY COUNT(*) DESC')
for grade, count in cursor.fetchall():
    print(f'{grade}: {count}')
"
```

4. **Access Evidence Gaps:**
```
https://oral.xeradb.com/papers/evidence-gaps/
```

## Troubleshooting

### Common PostgreSQL Issues:

1. **Connection Errors:**
   - Verify PostgreSQL service is running
   - Check database credentials in Django settings
   - Ensure database `oral_production` exists

2. **Permission Issues:**
   - User `oral_user` must have CREATE TABLE permissions
   - Grant necessary permissions: `GRANT ALL ON DATABASE oral_production TO oral_user;`

3. **Encoding Issues:**
   - CSV files are handled with multiple encoding detection (UTF-8, Latin-1, CP1252)
   - PostgreSQL should be configured with UTF-8 encoding

4. **Performance:**
   - Run `VACUUM ANALYZE evidence_gaps;` after import for optimal query performance
   - Monitor query execution with `EXPLAIN ANALYZE`

## Features Available

Once deployed, the Evidence Gaps page provides:

- **Advanced Filtering:** By GRADE rating, population, intervention
- **Search Functionality:** Full-text search across all fields
- **Data Visualization:** GRADE distribution charts
- **Review Consolidation:** Groups multiple versions of the same review
- **Export Capabilities:** Ready for systematic review workflows

This implementation provides comprehensive evidence gaps analysis for oral health research with full PostgreSQL optimization.
