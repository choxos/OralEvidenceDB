"""
Django management command to import evidence gaps data.
This ensures perfect compatibility with Django's PostgreSQL setup.

Usage: python manage.py import_evidence_gaps
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
import pandas as pd
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import evidence gaps data from CSV files into PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing evidence gaps data before import'
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            default='data/evidencegaps',
            help='Directory containing CSV files'
        )

    def handle(self, *args, **options):
        self.stdout.write("🦷 Starting evidence gaps data import via Django...")
        
        data_dir = Path(options['data_dir'])
        sof_file = data_dir / 'evidencegaps_dental_sofs.csv'
        non_sof_file = data_dir / 'evidencegaps_dental_non_sofs.csv'
        
        # Verify files exist
        if not sof_file.exists():
            self.stdout.write(
                self.style.ERROR(f"❌ SoF file not found: {sof_file}")
            )
            return
        
        if not non_sof_file.exists():
            self.stdout.write(
                self.style.ERROR(f"❌ Non-SoF file not found: {non_sof_file}")
            )
            return
        
        try:
            with transaction.atomic():
                cursor = connection.cursor()
                
                # Create table using raw SQL (for PostgreSQL compatibility)
                self.create_table(cursor)
                
                # Clear existing data if requested
                if options['clear']:
                    self.stdout.write("🗑️ Clearing existing evidence gaps data...")
                    cursor.execute("DELETE FROM evidence_gaps")
                    deleted_count = cursor.rowcount
                    self.stdout.write(f"Deleted {deleted_count} existing records")
                
                # Import data
                sof_count = self.import_sof_data(cursor, sof_file)
                non_sof_count = self.import_non_sof_data(cursor, non_sof_file)
                
                # Show summary
                cursor.execute("SELECT COUNT(*) FROM evidence_gaps")
                total_count = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT grade_rating, COUNT(*) 
                    FROM evidence_gaps 
                    GROUP BY grade_rating 
                    ORDER BY COUNT(*) DESC
                """)
                grade_distribution = cursor.fetchall()
                
                self.stdout.write(
                    self.style.SUCCESS("🎉 Import completed successfully!")
                )
                self.stdout.write(f"📊 Summary:")
                self.stdout.write(f"   • SoF data: {sof_count} records")
                self.stdout.write(f"   • Non-SoF data: {non_sof_count} records")
                self.stdout.write(f"   • Total: {total_count} records")
                self.stdout.write(f"📈 GRADE distribution:")
                for grade, count in grade_distribution:
                    self.stdout.write(f"   • {grade}: {count}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Import failed: {e}")
            )
            raise
    
    def create_table(self, cursor):
        """Create evidence_gaps table with PostgreSQL-compatible schema."""
        self.stdout.write("🔧 Creating evidence_gaps table...")
        
        cursor.execute("""
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
            measure VARCHAR(50),
            effect DECIMAL(10,4),
            ci_lower DECIMAL(10,4),
            ci_upper DECIMAL(10,4),
            significant BOOLEAN,
            number_of_participants INTEGER,
            number_of_studies INTEGER,
            
            -- GRADE downgrading reasons
            risk_of_bias BOOLEAN DEFAULT FALSE,
            imprecision BOOLEAN DEFAULT FALSE,
            inconsistency BOOLEAN DEFAULT FALSE,
            indirectness BOOLEAN DEFAULT FALSE,
            publication_bias BOOLEAN DEFAULT FALSE,
            
            reasons_for_grade TEXT,
            rate_per_100000 DECIMAL(10,2),
            data_source VARCHAR(50) DEFAULT 'sof',
            
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_gaps_review_id ON evidence_gaps(review_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_gaps_grade_rating ON evidence_gaps(grade_rating)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_gaps_population ON evidence_gaps(population)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_gaps_intervention ON evidence_gaps(intervention)")
        
        self.stdout.write("✅ Evidence gaps table ready")
    
    def clean_grade_rating(self, rating):
        """Clean and standardize GRADE ratings."""
        if pd.isna(rating) or rating == '' or rating == '-' or rating == 'NA':
            return 'No Evidence Yet'
        
        rating = str(rating).strip()
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
    
    def parse_boolean_field(self, value):
        """Parse boolean fields from CSV."""
        if pd.isna(value) or value == '' or value == '-':
            return False
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            value_lower = value.lower().strip()
            return value_lower in ['true', 'yes', '1', 'on']
        
        return bool(value)
    
    def safe_float(self, value):
        """Safely convert value to float."""
        if pd.isna(value) or value == '' or value == '-' or value == 'NA':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def safe_int(self, value):
        """Safely convert value to integer."""
        if pd.isna(value) or value == '' or value == '-' or value == 'NA':
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def import_sof_data(self, cursor, filepath):
        """Import SoF table data from CSV."""
        self.stdout.write(f"📊 Importing SoF data from {filepath}...")
        
        try:
            # Try different encodings
            df = None
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    df = pd.read_csv(filepath, encoding=encoding)
                    self.stdout.write(f"Loaded {len(df)} rows using {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise UnicodeDecodeError("Failed to read with any encoding")
            
            imported_count = 0
            
            for _, row in df.iterrows():
                try:
                    # Parse GRADE downgrading reasons
                    risk_of_bias = self.parse_boolean_field(row.get('Risk of bias', False))
                    imprecision = self.parse_boolean_field(row.get('Imprecision', False))
                    inconsistency = self.parse_boolean_field(row.get('Inconsistency', False))
                    indirectness = self.parse_boolean_field(row.get('Indirectness', False))
                    publication_bias = self.parse_boolean_field(row.get('Publication bias', False))
                    
                    cursor.execute("""
                        INSERT INTO evidence_gaps (
                            review_id, review_title, population, intervention, comparison, outcome,
                            pico, measure, effect, ci_lower, ci_upper, significant,
                            number_of_participants, number_of_studies, grade_rating,
                            reasons_for_grade, risk_of_bias, imprecision, inconsistency,
                            indirectness, publication_bias, data_source, comments,
                            authors, year, doi
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                        self.safe_float(row.get('Effect')),
                        self.safe_float(row.get('CI Lower')),
                        self.safe_float(row.get('CI Upper')),
                        self.parse_boolean_field(row.get('Significant')),
                        self.safe_int(row.get('Number of participants')),
                        self.safe_int(row.get('Number of studies')),
                        self.clean_grade_rating(row.get('Certainty of the evidence (GRADE)')),
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
                    self.stdout.write(f"Warning: Error importing SoF row: {e}")
                    continue
            
            self.stdout.write(f"✅ SoF data import complete: {imported_count} rows")
            return imported_count
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to import SoF data: {e}"))
            return 0
    
    def import_non_sof_data(self, cursor, filepath):
        """Import non-SoF data from CSV."""
        self.stdout.write(f"📊 Importing non-SoF data from {filepath}...")
        
        try:
            # Try different encodings
            df = None
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    df = pd.read_csv(filepath, encoding=encoding)
                    self.stdout.write(f"Loaded {len(df)} rows using {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise UnicodeDecodeError("Failed to read with any encoding")
            
            imported_count = 0
            
            for _, row in df.iterrows():
                try:
                    cursor.execute("""
                        INSERT INTO evidence_gaps (
                            review_id, population, intervention, comparison, outcome,
                            measure, effect, ci_lower, ci_upper, significant,
                            number_of_participants, number_of_studies, grade_rating,
                            rate_per_100000, data_source
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        str(row.get('ID', '')),
                        str(row.get('Population', '')),
                        str(row.get('Intervention', '')),
                        str(row.get('Comparison', '')),
                        str(row.get('Outcome', '')),
                        str(row.get('Measure', '')),
                        self.safe_float(row.get('Effect')),
                        self.safe_float(row.get('CI Lower')),
                        self.safe_float(row.get('CI Upper')),
                        self.parse_boolean_field(row.get('Significant')),
                        self.safe_int(row.get('Number of participants')),
                        self.safe_int(row.get('Number of studies')),
                        self.clean_grade_rating(row.get('Certainty of the evidence (GRADE)')),
                        self.safe_float(row.get('Rate per 100000')),
                        'non_sof'
                    ))
                    
                    imported_count += 1
                    
                except Exception as e:
                    self.stdout.write(f"Warning: Error importing non-SoF row: {e}")
                    continue
            
            self.stdout.write(f"✅ Non-SoF data import complete: {imported_count} rows")
            return imported_count
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to import non-SoF data: {e}"))
            return 0
