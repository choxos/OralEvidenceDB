"""
Django management command to import NLM journal abbreviations.
This ensures journal names are properly abbreviated according to NLM standards.

Usage: python manage.py import_nlm_journals
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import pandas as pd
import logging
from pathlib import Path
from papers.models import Journal

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import NLM journal abbreviations from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-file',
            type=str,
            default='data/nlm_journals/nlm_journals_consolidated.csv',
            help='Path to NLM journals CSV file'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing journals with NLM abbreviations'
        )

    def handle(self, *args, **options):
        self.stdout.write("📚 Starting NLM journal abbreviations import...")
        
        data_file = Path(options['data_file'])
        
        if not data_file.exists():
            self.stdout.write(
                self.style.ERROR(f"❌ NLM journals CSV file not found: {data_file}")
            )
            return
        
        try:
            with transaction.atomic():
                # Import NLM journal data
                imported_count = self.import_nlm_journals(data_file, options['update_existing'])
                
                self.stdout.write(
                    self.style.SUCCESS("🎉 NLM journal import completed successfully!")
                )
                self.stdout.write(f"📊 Summary:")
                self.stdout.write(f"   • Journals processed: {imported_count} records")
                
                # Show stats
                total_journals = Journal.objects.count()
                self.stdout.write(f"   • Total journals in database: {total_journals}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Import failed: {e}")
            )
            raise
    
    def import_nlm_journals(self, filepath, update_existing=False):
        """Import NLM journal abbreviations from CSV."""
        self.stdout.write(f"📊 Importing NLM journal data from {filepath}...")
        
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
            
            processed_count = 0
            created_count = 0
            updated_count = 0
            
            # Print column names to understand structure
            self.stdout.write(f"CSV columns: {list(df.columns)}")
            
            for idx, row in df.iterrows():
                try:
                    # Extract journal data from actual CSV structure
                    full_name = self.clean_text(row.get('title_full', ''))
                    abbreviation = self.clean_text(row.get('title_abbreviation', ''))
                    issn_print = self.clean_text(row.get('issn_print', ''))
                    issn_electronic = self.clean_text(row.get('issn_electronic', ''))
                    nlm_id = self.clean_text(row.get('nlm_id', ''))
                    
                    # If no abbreviation, use full name
                    if not abbreviation and full_name:
                        abbreviation = full_name
                    
                    # Skip if no useful data
                    if not full_name or not abbreviation:
                        continue
                    
                    # In our system: 
                    # - 'name' field stores the abbreviation (what we display)
                    # - 'abbreviation' field stores the full name (for reference)
                    display_name = abbreviation  # What we show on website
                    reference_name = full_name   # Full name for reference
                    
                    # Look for existing journal by full name or abbreviation
                    from django.db import models
                    existing_journal = Journal.objects.filter(
                        models.Q(name__iexact=display_name) | 
                        models.Q(abbreviation__iexact=reference_name)
                    ).first()
                    
                    if existing_journal:
                        if update_existing:
                            # Update existing journal with NLM data
                            existing_journal.name = display_name  # Store abbreviation in name
                            existing_journal.abbreviation = reference_name  # Store full name in abbreviation
                            if issn_print:
                                existing_journal.issn_print = issn_print
                            if issn_electronic:
                                existing_journal.issn_electronic = issn_electronic
                            existing_journal.save()
                            updated_count += 1
                            
                            if processed_count % 100 == 0:
                                self.stdout.write(f"Updated journal: {display_name}")
                    else:
                        # Create new journal with NLM data
                        Journal.objects.create(
                            name=display_name,  # Store abbreviation in name field
                            abbreviation=reference_name,  # Store full name in abbreviation field
                            issn_print=issn_print,
                            issn_electronic=issn_electronic
                        )
                        created_count += 1
                        
                        if processed_count % 100 == 0:
                            self.stdout.write(f"Created journal: {display_name}")
                    
                    processed_count += 1
                    
                    if processed_count % 500 == 0:
                        self.stdout.write(f"Processed {processed_count} journals...")
                    
                except Exception as e:
                    self.stdout.write(f"Warning: Error processing row {idx}: {e}")
                    continue
            
            self.stdout.write(f"✅ NLM journal data import complete:")
            self.stdout.write(f"   • Processed: {processed_count} journals")
            self.stdout.write(f"   • Created: {created_count} new journals")
            self.stdout.write(f"   • Updated: {updated_count} existing journals")
            
            return processed_count
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to import NLM journals: {e}"))
            return 0
    
    def clean_text(self, text):
        """Clean text fields."""
        if pd.isna(text) or text == '' or text == 'NA':
            return ''
        return str(text).strip()
