"""
Django management command to import retraction data from Retraction Watch database.
This ensures perfect compatibility with Django's PostgreSQL setup.

Usage: python manage.py import_retractions
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils.dateparse import parse_date
import pandas as pd
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import retraction data from Retraction Watch CSV into PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing retraction data before import'
        )
        parser.add_argument(
            '--data-file',
            type=str,
            default='data/retractionwatchdatabase/retraction_watch.csv',
            help='Path to Retraction Watch CSV file'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of records to import (for testing)'
        )

    def handle(self, *args, **options):
        self.stdout.write("🚨 Starting Retraction Watch data import...")
        
        data_file = Path(options['data_file'])
        
        if not data_file.exists():
            self.stdout.write(
                self.style.ERROR(f"❌ Retraction Watch CSV file not found: {data_file}")
            )
            return
        
        try:
            with transaction.atomic():
                cursor = connection.cursor()
                
                # Django models will auto-create tables on first migration
                
                # Clear existing data if requested
                if options['clear']:
                    self.stdout.write("🗑️ Clearing existing retraction data...")
                    from papers.models_retraction import RetractedPaper
                    deleted_count = RetractedPaper.objects.all().count()
                    RetractedPaper.objects.all().delete()
                    self.stdout.write(f"Deleted {deleted_count} existing records")
                
                # Import data
                imported_count = self.import_retraction_data(data_file, options.get('limit'))
                
                # Show summary
                from papers.models_retraction import RetractedPaper
                total_count = RetractedPaper.objects.count()
                
                from django.db.models import Count
                nature_distribution = RetractedPaper.objects.values('retraction_nature').annotate(
                    count=Count('retraction_nature')
                ).exclude(
                    retraction_nature__isnull=True
                ).exclude(
                    retraction_nature=''
                ).order_by('-count')[:10]
                
                self.stdout.write(
                    self.style.SUCCESS("🎉 Retraction import completed successfully!")
                )
                self.stdout.write(f"📊 Summary:")
                self.stdout.write(f"   • Total retractions: {total_count} records")
                self.stdout.write(f"   • Newly imported: {imported_count} records")
                
                if nature_distribution:
                    self.stdout.write(f"📈 Top retraction natures:")
                    for item in nature_distribution:
                        self.stdout.write(f"   • {item['retraction_nature']}: {item['count']}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Import failed: {e}")
            )
            raise
    
    def create_tables(self, cursor):
        """Create retracted_papers table with PostgreSQL-compatible schema."""
        self.stdout.write("🔧 Creating retracted_papers table...")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS retracted_papers (
            id SERIAL PRIMARY KEY,
            record_id INTEGER UNIQUE,
            
            -- Original paper information
            original_title TEXT,
            original_pubmed_id BIGINT,
            original_doi VARCHAR(500),
            original_paper_date DATE,
            original_paper_url VARCHAR(2000),
            
            -- Retraction information
            retraction_title TEXT,
            retraction_doi VARCHAR(500),
            retraction_pubmed_id BIGINT,
            retraction_date DATE,
            retraction_url VARCHAR(2000),
            
            -- Paper metadata
            journal VARCHAR(1000),
            publisher VARCHAR(500),
            authors TEXT,
            country VARCHAR(200),
            subject TEXT,
            article_type VARCHAR(200),
            
            -- Retraction details
            retraction_nature VARCHAR(500),
            reason TEXT,
            notes TEXT,
            paywalled VARCHAR(10),
            
            -- Metadata
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_retracted_papers_original_pubmed_id ON retracted_papers(original_pubmed_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_retracted_papers_retraction_date ON retracted_papers(retraction_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_retracted_papers_journal ON retracted_papers(journal)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_retracted_papers_retraction_nature ON retracted_papers(retraction_nature)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_retracted_papers_country ON retracted_papers(country)")
        
        self.stdout.write("✅ Retracted papers table ready")
    
    def clean_pmid(self, pmid_str):
        """Extract numeric PMID from string."""
        if pd.isna(pmid_str) or pmid_str == '' or pmid_str == 'NA':
            return None
        
        pmid_str = str(pmid_str).strip()
        # Extract numbers only
        numbers = re.findall(r'\d+', pmid_str)
        if numbers:
            try:
                return int(numbers[0])
            except ValueError:
                return None
        return None
    
    def clean_date(self, date_str):
        """Parse date from various formats."""
        if pd.isna(date_str) or date_str == '' or date_str == 'NA':
            return None
        
        date_str = str(date_str).strip()
        
        # Try parsing with pandas first
        try:
            parsed = pd.to_datetime(date_str, errors='coerce')
            if pd.notna(parsed):
                return parsed.date()
        except:
            pass
        
        # Try Django's date parser
        try:
            return parse_date(date_str)
        except:
            pass
        
        return None
    
    def clean_text(self, text):
        """Clean text fields."""
        if pd.isna(text) or text == '' or text == 'NA':
            return ''
        return str(text).strip()
    
    def clean_url(self, url):
        """Clean and validate URL."""
        if pd.isna(url) or url == '' or url == 'NA':
            return ''
        
        url = str(url).strip()
        if not url.startswith(('http://', 'https://')):
            return ''
        
        return url[:2000]  # Limit URL length
    
    def import_retraction_data(self, filepath, limit=None):
        """Import retraction data from CSV."""
        self.stdout.write(f"📊 Importing retraction data from {filepath}...")
        
        try:
            # Try different encodings
            df = None
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    df = pd.read_csv(filepath, encoding=encoding, low_memory=False)
                    self.stdout.write(f"Loaded {len(df)} rows using {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise UnicodeDecodeError("Failed to read with any encoding")
            
            # Apply limit if specified
            if limit:
                df = df.head(limit)
                self.stdout.write(f"Limited to {len(df)} rows for testing")
            
            imported_count = 0
            error_count = 0
            
            for idx, row in df.iterrows():
                try:
                    # Clean and prepare data
                    record_id = self.clean_pmid(row.get('Record Id'))
                    original_title = self.clean_text(row.get('Title'))
                    original_pubmed_id = self.clean_pmid(row.get('OriginalPaperPubMedID'))
                    original_doi = self.clean_text(row.get('OriginalPaperDOI'))
                    original_paper_date = self.clean_date(row.get('OriginalPaperDate'))
                    
                    retraction_title = self.clean_text(row.get('RetractionTitle', ''))
                    retraction_doi = self.clean_text(row.get('RetractionDOI'))
                    retraction_pubmed_id = self.clean_pmid(row.get('RetractionPubMedID'))
                    retraction_date = self.clean_date(row.get('RetractionDate'))
                    
                    journal = self.clean_text(row.get('Journal'))
                    publisher = self.clean_text(row.get('Publisher'))
                    authors = self.clean_text(row.get('Author'))
                    country = self.clean_text(row.get('Country'))
                    subject = self.clean_text(row.get('Subject'))
                    article_type = self.clean_text(row.get('ArticleType'))
                    
                    retraction_nature = self.clean_text(row.get('RetractionNature'))
                    reason = self.clean_text(row.get('Reason'))
                    notes = self.clean_text(row.get('Notes'))
                    paywalled = self.clean_text(row.get('Paywalled'))
                    
                    # Extract URLs from URLS field if present
                    original_paper_url = ''
                    retraction_url = ''
                    urls_field = self.clean_text(row.get('URLS'))
                    if urls_field:
                        # Split URLs and try to categorize
                        urls = [url.strip() for url in urls_field.split(';') if url.strip()]
                        for url in urls[:2]:  # Take first two URLs
                            if 'retraction' in url.lower():
                                retraction_url = self.clean_url(url)
                            else:
                                original_paper_url = self.clean_url(url)
                    
                    # Create RetractedPaper instance using Django ORM
                    from papers.models_retraction import RetractedPaper
                    
                    RetractedPaper.objects.create(
                        record_id=record_id,
                        original_title=original_title,
                        original_pubmed_id=original_pubmed_id,
                        original_doi=original_doi,
                        original_paper_date=original_paper_date,
                        retraction_title=retraction_title,
                        retraction_doi=retraction_doi,
                        retraction_pubmed_id=retraction_pubmed_id,
                        retraction_date=retraction_date,
                        journal=journal,
                        authors=authors,
                        country=country,
                        subject=subject,
                        article_type=article_type,
                        retraction_nature=retraction_nature,
                        reason=reason,
                        notes=notes,
                        original_paper_url=original_paper_url,
                        retraction_url=retraction_url
                    )
                    
                    imported_count += 1
                    
                    if imported_count % 1000 == 0:
                        self.stdout.write(f"Imported {imported_count} retractions...")
                    
                except Exception as e:
                    error_count += 1
                    if error_count <= 10:  # Only show first 10 errors
                        self.stdout.write(f"Warning: Error importing row {idx}: {e}")
                    continue
            
            self.stdout.write(f"✅ Retraction data import complete: {imported_count} rows imported")
            if error_count > 0:
                self.stdout.write(f"⚠️  {error_count} rows had errors and were skipped")
            
            return imported_count
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to import retraction data: {e}"))
            return 0
