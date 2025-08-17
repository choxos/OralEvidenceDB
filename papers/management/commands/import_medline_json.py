"""
Django management command to import MEDLINE JSON files into the database.

Usage:
    python manage.py import_medline_json --json-dir data/pubmed_json_by_year/2024 --update-journals
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.utils import timezone
from django.utils.dateparse import parse_date

from papers.models import Paper, Author, Journal, MeshTerm, AuthorPaper, DataImportLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import MEDLINE JSON files into the OralEvidenceDB database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--json-dir',
            type=str,
            required=True,
            help='Directory containing JSON files to import'
        )
        
        parser.add_argument(
            '--update-journals',
            action='store_true',
            help='Update journal information from NLM data'
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)'
        )
        
        parser.add_argument(
            '--max-files',
            type=int,
            help='Maximum number of JSON files to process (for testing)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without saving to database'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = {
            'total_files': 0,
            'papers_created': 0,
            'papers_updated': 0,
            'papers_skipped': 0,
            'authors_created': 0,
            'journals_created': 0,
            'mesh_terms_created': 0,
            'errors': 0
        }
        self.journal_cache = {}
        self.author_cache = {}
        self.mesh_cache = {}
    
    def parse_date_safely(self, date_string: str) -> Optional[date]:
        """Safely parse date string."""
        if not date_string:
            return None
        
        try:
            return parse_date(date_string)
        except (ValueError, TypeError):
            # Try to extract just the year
            if isinstance(date_string, str) and len(date_string) >= 4:
                year_match = date_string[:4]
                if year_match.isdigit():
                    try:
                        return date(int(year_match), 1, 1)
                    except ValueError:
                        pass
            return None
    
    def get_or_create_journal(self, journal_data: Dict) -> Optional[Journal]:
        """Get or create a journal from journal data."""
        if not journal_data or not journal_data.get('name'):
            return None
        
        journal_name = journal_data['name'].strip()
        if not journal_name:
            return None
        
        # Check cache first
        if journal_name in self.journal_cache:
            return self.journal_cache[journal_name]
        
        # Try to find existing journal
        journal = Journal.objects.filter(name__iexact=journal_name).first()
        
        if not journal:
            try:
                journal = Journal.objects.create(
                    name=journal_name,
                    iso_abbreviation=journal_data.get('iso_abbreviation', ''),
                    issn=journal_data.get('issn', ''),
                    nlm_id=journal_data.get('nlm_id', ''),
                    country=journal_data.get('country', '')
                )
                self.stats['journals_created'] += 1
                if self.verbosity >= 2:
                    self.stdout.write(f"Created journal: {journal_name}")
            except Exception as e:
                if self.verbosity >= 1:
                    self.stdout.write(f"Error creating journal '{journal_name}': {str(e)}")
                return None
        
        # Cache the journal
        self.journal_cache[journal_name] = journal
        return journal
    
    def get_or_create_author(self, author_data: Dict) -> Optional[Author]:
        """Get or create an author from author data."""
        first_name = author_data.get('first_name', '').strip()
        last_name = author_data.get('last_name', '').strip()
        
        if not last_name:
            return None
        
        # Create cache key
        cache_key = f"{first_name}|{last_name}"
        
        # Check cache first
        if cache_key in self.author_cache:
            return self.author_cache[cache_key]
        
        # Try to find existing author
        author_query = Author.objects.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name
        )
        
        # Add middle initials to query if available
        middle_initials = author_data.get('middle_initials', '').strip()
        if middle_initials:
            author_query = author_query.filter(middle_initials__iexact=middle_initials)
        
        author = author_query.first()
        
        if not author:
            try:
                author = Author.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    middle_initials=middle_initials,
                    full_name=author_data.get('full_name', f"{first_name} {last_name}").strip()
                )
                self.stats['authors_created'] += 1
                if self.verbosity >= 2:
                    self.stdout.write(f"Created author: {author.full_name}")
            except Exception as e:
                if self.verbosity >= 1:
                    self.stdout.write(f"Error creating author '{first_name} {last_name}': {str(e)}")
                return None
        
        # Cache the author
        self.author_cache[cache_key] = author
        return author
    
    def get_or_create_mesh_term(self, mesh_term: str) -> Optional[MeshTerm]:
        """Get or create a MeSH term."""
        mesh_term = mesh_term.strip()
        if not mesh_term:
            return None
        
        # Check cache first
        if mesh_term in self.mesh_cache:
            return self.mesh_cache[mesh_term]
        
        # Try to find existing MeSH term
        mesh_obj = MeshTerm.objects.filter(name__iexact=mesh_term).first()
        
        if not mesh_obj:
            try:
                mesh_obj = MeshTerm.objects.create(name=mesh_term)
                self.stats['mesh_terms_created'] += 1
                if self.verbosity >= 2:
                    self.stdout.write(f"Created MeSH term: {mesh_term}")
            except Exception as e:
                if self.verbosity >= 1:
                    self.stdout.write(f"Error creating MeSH term '{mesh_term}': {str(e)}")
                return None
        
        # Cache the MeSH term
        self.mesh_cache[mesh_term] = mesh_obj
        return mesh_obj
    
    def import_paper(self, json_data: Dict) -> bool:
        """Import a single paper from JSON data."""
        try:
            pmid = json_data.get('pmid')
            if not pmid:
                if self.verbosity >= 1:
                    self.stdout.write("Skipping record without PMID")
                return False
            
            # Check if paper already exists
            existing_paper = Paper.objects.filter(pmid=pmid).first()
            if existing_paper and not self.update_existing:
                self.stats['papers_skipped'] += 1
                return True
            
            # Parse publication date
            pub_date = self.parse_date_safely(json_data.get('publication_date'))
            
            # Get or create journal
            journal_data = json_data.get('journal', {})
            journal = self.get_or_create_journal(journal_data)
            
            # Prepare paper data
            paper_data = {
                'pmid': pmid,
                'title': json_data.get('title', '')[:1000],  # Truncate if too long
                'abstract': json_data.get('abstract', ''),
                'publication_date': pub_date,
                'publication_year': json_data.get('publication_year'),
                'volume': journal_data.get('volume', '')[:50],
                'issue': journal_data.get('issue', '')[:50],
                'pages': journal_data.get('pages', '')[:100],
                'doi': json_data.get('doi', '')[:200],
                'pmc_id': json_data.get('pmc_id', '')[:50],
                'language': ', '.join(json_data.get('language', [])) if json_data.get('language') else '',
                'publication_type': ', '.join(json_data.get('publication_type', [])) if json_data.get('publication_type') else '',
                'country': json_data.get('country', '')[:100],
                'journal': journal,
            }
            
            # Create or update paper
            if existing_paper:
                for key, value in paper_data.items():
                    setattr(existing_paper, key, value)
                existing_paper.save()
                paper = existing_paper
                self.stats['papers_updated'] += 1
                if self.verbosity >= 2:
                    self.stdout.write(f"Updated paper: {pmid}")
            else:
                paper = Paper.objects.create(**paper_data)
                self.stats['papers_created'] += 1
                if self.verbosity >= 2:
                    self.stdout.write(f"Created paper: {pmid}")
            
            # Handle authors
            authors_data = json_data.get('authors', [])
            if authors_data and not existing_paper:  # Only create authors for new papers
                for author_data in authors_data:
                    author = self.get_or_create_author(author_data)
                    if author:
                        try:
                            AuthorPaper.objects.create(
                                author=author,
                                paper=paper,
                                order=author_data.get('order', 1),
                                is_first_author=author_data.get('is_first_author', False),
                                is_last_author=author_data.get('is_last_author', False),
                                affiliation=author_data.get('affiliation', '')[:500]
                            )
                        except Exception as e:
                            if self.verbosity >= 1:
                                self.stdout.write(f"Error linking author to paper {pmid}: {str(e)}")
            
            # Handle MeSH terms
            mesh_terms = json_data.get('mesh_terms', [])
            if mesh_terms and not existing_paper:  # Only create MeSH terms for new papers
                for mesh_term in mesh_terms:
                    mesh_obj = self.get_or_create_mesh_term(mesh_term)
                    if mesh_obj:
                        try:
                            paper.mesh_terms.add(mesh_obj)
                        except Exception as e:
                            if self.verbosity >= 1:
                                self.stdout.write(f"Error linking MeSH term to paper {pmid}: {str(e)}")
            
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            if self.verbosity >= 1:
                self.stdout.write(f"Error importing paper {pmid}: {str(e)}")
            return False
    
    def handle(self, *args, **options):
        """Main command handler."""
        self.verbosity = options['verbosity']
        self.update_existing = not options.get('papers_only', False)
        
        json_dir = Path(options['json_dir'])
        if not json_dir.exists():
            raise CommandError(f"JSON directory not found: {json_dir}")
        
        # Find JSON files
        json_files = list(json_dir.glob('*.json'))
        if not json_files:
            raise CommandError(f"No JSON files found in {json_dir}")
        
        if options['max_files']:
            json_files = json_files[:options['max_files']]
        
        self.stdout.write(f"🦷 Starting import of {len(json_files)} JSON files from {json_dir}")
        
        batch_size = options['batch_size']
        processed = 0
        
        # Create import log entry
        import_log = DataImportLog.objects.create(
            source_type='medline_json',
            source_path=str(json_dir),
            status='in_progress',
            total_records=len(json_files)
        )
        
        try:
            for json_file in json_files:
                if options['dry_run']:
                    self.stdout.write(f"DRY RUN: Would process {json_file}")
                    continue
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    with transaction.atomic():
                        success = self.import_paper(json_data)
                        if success:
                            processed += 1
                    
                    if processed % batch_size == 0:
                        self.stdout.write(f"📊 Processed {processed}/{len(json_files)} files...")
                        
                except Exception as e:
                    self.stats['errors'] += 1
                    if self.verbosity >= 1:
                        self.stdout.write(f"Error processing {json_file}: {str(e)}")
            
            # Update import log
            import_log.status = 'completed' if self.stats['errors'] == 0 else 'completed_with_errors'
            import_log.successful_records = self.stats['papers_created'] + self.stats['papers_updated']
            import_log.failed_records = self.stats['errors']
            import_log.completed_at = timezone.now()
            import_log.save()
            
        except Exception as e:
            # Update import log on failure
            import_log.status = 'failed'
            import_log.error_message = str(e)
            import_log.completed_at = timezone.now()
            import_log.save()
            raise
        
        # Print summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("📊 IMPORT SUMMARY")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Total files processed: {processed}")
        self.stdout.write(f"Papers created: {self.stats['papers_created']}")
        self.stdout.write(f"Papers updated: {self.stats['papers_updated']}")
        self.stdout.write(f"Papers skipped: {self.stats['papers_skipped']}")
        self.stdout.write(f"Authors created: {self.stats['authors_created']}")
        self.stdout.write(f"Journals created: {self.stats['journals_created']}")
        self.stdout.write(f"MeSH terms created: {self.stats['mesh_terms_created']}")
        self.stdout.write(f"Errors: {self.stats['errors']}")
        
        if self.stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(f"\n⚠️  {self.stats['errors']} errors occurred during import"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ Import completed successfully!"))
