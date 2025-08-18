#!/usr/bin/env python3
"""
Import oral health evidence gaps data from CSV files into PostgreSQL database.

This script imports:
1. evidencegaps_cochrane_oral_metadata.csv - Main SoF table data
2. evidencegaps_dental_non_sofs.csv - Papers without SoF tables  
3. evidencegaps_cochrane_oral_metadata.csv - Article metadata (if needed for joining)
"""

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from pathlib import Path
import numpy as np
from decouple import config

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection using Django settings."""
    try:
        # Try to get from environment first (for production)
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            from urllib.parse import urlparse
            url = urlparse(database_url)
            return psycopg2.connect(
                host=url.hostname,
                port=url.port,
                database=url.path[1:],
                user=url.username,
                password=url.password
            )
        
        # For local development, use decouple config
        return psycopg2.connect(
            host=config('DB_HOST', default='localhost'),
            port=config('DB_PORT', default='5432'),
            database=config('DB_NAME', default='oral_production'),
            user=config('DB_USER', default='oral_user'),
            password=config('DB_PASSWORD', default='Choxos10203040')
        )
    except Exception as e:
        # Fallback to SQLite if PostgreSQL not available
        logger.warning(f"PostgreSQL connection failed: {e}")
        logger.info("Falling back to SQLite database...")
        import sqlite3
        db_path = Path('db.sqlite3')
        return sqlite3.connect(db_path)

def clean_grade_rating(rating):
    """Clean and standardize GRADE ratings."""
    if pd.isna(rating) or rating == '' or rating == '-' or rating == 'NA':
        return 'No Evidence Yet'
    
    rating = str(rating).strip()
    
    # Handle various formats
    rating_lower = rating.lower()
    if 'very low' in rating_lower:
        return 'Very Low'
    elif 'low' in rating_lower and 'very low' not in rating_lower:
        return 'Low'
    elif 'moderate' in rating_lower:
        return 'Moderate'
    elif 'high' in rating_lower:
        return 'High'
    else:
        return 'No Evidence Yet'

def parse_boolean_field(value):
    """Parse boolean fields from CSV."""
    if pd.isna(value) or value == '' or value == '-':
        return False
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        value_lower = value.lower().strip()
        return value_lower in ['true', 'yes', '1', 'on']
    
    return bool(value)

def safe_float(value):
    """Safely convert value to float."""
    if pd.isna(value) or value == '' or value == '-' or value == 'NA':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def safe_int(value):
    """Safely convert value to integer."""
    if pd.isna(value) or value == '' or value == '-' or value == 'NA':
        return None
    try:
        return int(float(value))  # Convert to float first to handle strings like "123.0"
    except (ValueError, TypeError):
        return None

def create_table_if_not_exists(cursor, is_postgres=False):
    """Create evidence_gaps table if it doesn't exist."""
    logger.info("Creating evidence_gaps table if it doesn't exist...")
    
    if is_postgres:
        # Read PostgreSQL schema
        with open('create_evidence_gaps_table.sql', 'r') as f:
            sql_script = f.read()
        cursor.execute(sql_script)
        logger.info("✅ PostgreSQL evidence_gaps table ready")
    else:
        # SQLite schema
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evidence_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT NOT NULL,
            review_title TEXT,
            authors TEXT,
            year TEXT,
            doi TEXT,
            table_number INTEGER,
            table_title TEXT,
            population TEXT,
            intervention TEXT,
            comparison TEXT,
            outcome TEXT NOT NULL,
            pico TEXT,
            grade_rating TEXT NOT NULL,
            certainty TEXT,
            participants TEXT,
            studies TEXT,
            comments TEXT,
            assumed_risk TEXT,
            corresponding_risk TEXT,
            relative_effect TEXT,
            measure TEXT,
            effect REAL,
            ci_lower REAL,
            ci_upper REAL,
            significant BOOLEAN,
            number_of_participants INTEGER,
            number_of_studies INTEGER,
            risk_of_bias BOOLEAN DEFAULT 0,
            imprecision BOOLEAN DEFAULT 0,
            inconsistency BOOLEAN DEFAULT 0,
            indirectness BOOLEAN DEFAULT 0,
            publication_bias BOOLEAN DEFAULT 0,
            reasons_for_grade TEXT,
            rate_per_100000 REAL,
            data_source TEXT DEFAULT 'sof',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        logger.info("✅ SQLite evidence_gaps table ready")

def import_sof_data(cursor, filepath, is_postgres=False):
    """Import SoF table data from CSV."""
    logger.info(f"📊 Importing SoF data from {filepath}...")
    
    try:
        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                logger.info(f"Loaded {len(df)} rows from SoF data using {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
        else:
            raise UnicodeDecodeError("Failed to read with any encoding")
        
        imported_count = 0
        error_count = 0
        
        # Choose correct placeholder style
        placeholder = '%s' if is_postgres else '?'
        placeholders = ', '.join([placeholder] * 26)
        
        for _, row in df.iterrows():
            try:
                # Parse GRADE downgrading reasons
                risk_of_bias = parse_boolean_field(row.get('Risk of bias', False))
                imprecision = parse_boolean_field(row.get('Imprecision', False))
                inconsistency = parse_boolean_field(row.get('Inconsistency', False))
                indirectness = parse_boolean_field(row.get('Indirectness', False))
                publication_bias = parse_boolean_field(row.get('Publication bias', False))
                
                # Insert row
                cursor.execute(f"""
                    INSERT INTO evidence_gaps (
                        review_id, review_title, population, intervention, comparison, outcome,
                        pico, measure, effect, ci_lower, ci_upper, significant,
                        number_of_participants, number_of_studies, grade_rating,
                        reasons_for_grade, risk_of_bias, imprecision, inconsistency,
                        indirectness, publication_bias, data_source, comments,
                        authors, year, doi
                    ) VALUES (
                        {placeholders}
                    )
                """, (
                    str(row.get('ID', '')),
                    str(row.get('Review', '')),
                    str(row.get('Population', '')),
                    str(row.get('Intervention', '')),
                    str(row.get('Comparison', '')),
                    str(row.get('Outcome', '')),
                    str(row.get('PICO', '')),
                    str(row.get('Measure', '')),
                    safe_float(row.get('Effect')),
                    safe_float(row.get('CI Lower')),
                    safe_float(row.get('CI Upper')),
                    parse_boolean_field(row.get('Significant')),
                    safe_int(row.get('Number of participants')),
                    safe_int(row.get('Number of studies')),
                    clean_grade_rating(row.get('Certainty of the evidence (GRADE)')),
                    str(row.get('Reasons for GRADE if not High', '')),
                    risk_of_bias,
                    imprecision,
                    inconsistency,
                    indirectness,
                    publication_bias,
                    'sof',
                    str(row.get('comments', '')),
                    str(row.get('authors', '')),
                    str(row.get('year', '')),
                    str(row.get('doi', ''))
                ))
                
                imported_count += 1
                
            except Exception as e:
                logger.warning(f"Error importing SoF row: {e}")
                error_count += 1
                continue
        
        logger.info(f"✅ SoF data import complete: {imported_count} rows imported, {error_count} errors")
        return imported_count
        
    except Exception as e:
        logger.error(f"❌ Failed to import SoF data: {e}")
        return 0

def import_non_sof_data(cursor, filepath, is_postgres=False):
    """Import non-SoF data from CSV."""
    logger.info(f"📊 Importing non-SoF data from {filepath}...")
    
    try:
        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                logger.info(f"Loaded {len(df)} rows from non-SoF data using {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
        else:
            raise UnicodeDecodeError("Failed to read with any encoding")
        
        imported_count = 0
        error_count = 0
        
        # Choose correct placeholder style
        placeholder = '%s' if is_postgres else '?'
        placeholders = ', '.join([placeholder] * 15)
        
        for _, row in df.iterrows():
            try:
                cursor.execute(f"""
                    INSERT INTO evidence_gaps (
                        review_id, population, intervention, comparison, outcome,
                        measure, effect, ci_lower, ci_upper, significant,
                        number_of_participants, number_of_studies, grade_rating,
                        rate_per_100000, data_source
                    ) VALUES (
                        {placeholders}
                    )
                """, (
                    str(row.get('ID', '')),
                    str(row.get('Population', '')),
                    str(row.get('Intervention', '')),
                    str(row.get('Comparison', '')),
                    str(row.get('Outcome', '')),
                    str(row.get('Measure', '')),
                    safe_float(row.get('Effect')),
                    safe_float(row.get('CI Lower')),
                    safe_float(row.get('CI Upper')),
                    parse_boolean_field(row.get('Significant')),
                    safe_int(row.get('Number of participants')),
                    safe_int(row.get('Number of studies')),
                    clean_grade_rating(row.get('Certainty of the evidence (GRADE)')),
                    safe_float(row.get('Rate per 100000')),
                    'non_sof'
                ))
                
                imported_count += 1
                
            except Exception as e:
                logger.warning(f"Error importing non-SoF row: {e}")
                error_count += 1
                continue
        
        logger.info(f"✅ Non-SoF data import complete: {imported_count} rows imported, {error_count} errors")
        return imported_count
        
    except Exception as e:
        logger.error(f"❌ Failed to import non-SoF data: {e}")
        return 0

def clear_existing_data(cursor):
    """Clear existing evidence gaps data."""
    logger.info("🗑️ Clearing existing evidence gaps data...")
    cursor.execute("DELETE FROM evidence_gaps")
    deleted_count = cursor.rowcount if hasattr(cursor, 'rowcount') else 0
    logger.info(f"Deleted {deleted_count} existing records")

def main():
    """Main import function."""
    logger.info("🦷 Starting oral health evidence gaps data import...")
    
    # Data file paths
    data_dir = Path('data/evidencegaps')
    sof_file = data_dir / 'evidencegaps_dental_sofs.csv'
    non_sof_file = data_dir / 'evidencegaps_dental_non_sofs.csv'
    metadata_file = data_dir / 'evidencegaps_cochrane_oral_metadata.csv'
    
    # Verify files exist
    missing_files = []
    for file_path in [sof_file, non_sof_file, metadata_file]:
        if not file_path.exists():
            missing_files.append(str(file_path))
    
    if missing_files:
        logger.error(f"❌ Missing data files: {', '.join(missing_files)}")
        return False
    
    # Connect to database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Detect database type
        is_postgres = False
        try:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            is_postgres = 'PostgreSQL' in version
            logger.info(f"🐘 Database type: {'PostgreSQL' if is_postgres else 'SQLite'}")
        except:
            logger.info("🗂️ Database type: SQLite (fallback)")
        
        # Create table
        create_table_if_not_exists(cursor, is_postgres)
        
        # Clear existing data
        clear_existing_data(cursor)
        
        # Import data
        sof_count = import_sof_data(cursor, sof_file, is_postgres)
        non_sof_count = import_non_sof_data(cursor, non_sof_file, is_postgres)
        
        # Commit changes
        conn.commit()
        
        # Show summary
        cursor.execute("SELECT COUNT(*) FROM evidence_gaps")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT grade_rating, COUNT(*) FROM evidence_gaps GROUP BY grade_rating ORDER BY grade_rating")
        grade_distribution = cursor.fetchall()
        
        logger.info("🎉 Import completed successfully!")
        logger.info(f"📊 Summary:")
        logger.info(f"   • SoF data: {sof_count} records")
        logger.info(f"   • Non-SoF data: {non_sof_count} records")
        logger.info(f"   • Total: {total_count} records")
        logger.info(f"📈 GRADE distribution:")
        for grade, count in grade_distribution:
            logger.info(f"   • {grade}: {count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
