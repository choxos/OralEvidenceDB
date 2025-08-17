#!/usr/bin/env python3
"""
Parse MEDLINE format text files (from PubMed entrez) and convert to JSON format.
Organizes JSON files by publication year in subdirectories.

This script parses the MEDLINE text format and creates individual JSON files
for each paper, organized by year, ready for database import.

Usage:
    python scripts/parse_medline_to_json_by_year.py
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

class MedlineParserByYear:
    """Parser for MEDLINE format text files with year-based organization."""
    
    def __init__(self):
        self.current_record = {}
        self.current_field = None
        self.stats = {
            'total_records': 0,
            'successful_parses': 0,
            'failed_parses': 0,
            'missing_pmids': 0,
            'missing_years': 0,
            'years_found': set()
        }
    
    def parse_date(self, date_string: str) -> Optional[str]:
        """Parse various date formats from MEDLINE."""
        if not date_string:
            return None
        
        # Clean up date string
        date_string = date_string.strip()
        
        # Common patterns
        patterns = [
            r'(\d{4})\s+(\w{3})\s+(\d{1,2})',  # 2025 Jan 15
            r'(\d{4})\s+(\w{3})',              # 2025 Jan
            r'(\d{4})',                        # 2025
            r'(\d{8})',                        # 20250115
        ]
        
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        for pattern in patterns:
            match = re.search(pattern, date_string)
            if match:
                if len(match.groups()) == 3:  # Year Month Day
                    year, month_name, day = match.groups()
                    month = month_map.get(month_name, '01')
                    return f"{year}-{month}-{day.zfill(2)}"
                elif len(match.groups()) == 2:  # Year Month
                    year, month_name = match.groups()
                    month = month_map.get(month_name, '01')
                    return f"{year}-{month}-01"
                elif len(match.groups()) == 1:  # Year only or YYYYMMDD
                    date_val = match.groups()[0]
                    if len(date_val) == 8:  # YYYYMMDD
                        return f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
                    else:  # Year only
                        return f"{date_val}-01-01"
        
        return None
    
    def extract_year(self, date_string: str, dp_field: str = "") -> Optional[int]:
        """Extract publication year from date string or DP field."""
        # Try publication date first
        if date_string:
            year_match = re.search(r'(\d{4})', date_string)
            if year_match:
                year = int(year_match.group(1))
                if 1800 <= year <= 2030:  # Reasonable year range
                    return year
        
        # Try DP field as fallback
        if dp_field:
            year_match = re.search(r'(\d{4})', dp_field)
            if year_match:
                year = int(year_match.group(1))
                if 1800 <= year <= 2030:
                    return year
        
        return None
    
    def parse_authors(self, authors_list: List[str], full_authors_list: List[str] = None) -> List[Dict]:
        """Parse author information from AU and FAU fields."""
        authors = []
        full_authors_dict = {}
        
        # Create mapping from short to full names
        if full_authors_list:
            for i, full_name in enumerate(full_authors_list):
                if i < len(authors_list):
                    full_authors_dict[authors_list[i]] = full_name
        
        for i, author in enumerate(authors_list):
            author_info = {
                'order': i + 1,
                'short_name': author,
                'full_name': full_authors_dict.get(author, author),
                'is_first_author': i == 0,
                'is_last_author': i == len(authors_list) - 1
            }
            
            # Parse name parts from full name
            full_name = author_info['full_name']
            if ', ' in full_name:
                parts = full_name.split(', ')
                author_info['last_name'] = parts[0]
                if len(parts) > 1:
                    first_parts = parts[1].split()
                    author_info['first_name'] = first_parts[0] if first_parts else ''
                    author_info['middle_initials'] = ' '.join(first_parts[1:]) if len(first_parts) > 1 else ''
            else:
                # Handle other formats
                name_parts = full_name.split()
                if len(name_parts) >= 2:
                    author_info['first_name'] = name_parts[0]
                    author_info['last_name'] = name_parts[-1]
                    author_info['middle_initials'] = ' '.join(name_parts[1:-1]) if len(name_parts) > 2 else ''
                else:
                    author_info['last_name'] = full_name
                    author_info['first_name'] = ''
                    author_info['middle_initials'] = ''
            
            authors.append(author_info)
        
        return authors
    
    def parse_keywords(self, keywords_list: List[str]) -> List[str]:
        """Parse and clean keywords."""
        cleaned_keywords = []
        for keyword in keywords_list:
            # Remove MeSH qualifiers (text after /)
            if '/' in keyword:
                keyword = keyword.split('/')[0]
            
            # Clean and normalize
            keyword = keyword.strip().strip('*')
            if keyword and len(keyword) > 2:
                cleaned_keywords.append(keyword)
        
        return cleaned_keywords
    
    def parse_record(self, record_text: str) -> Optional[Dict]:
        """Parse a single MEDLINE record."""
        lines = record_text.strip().split('\n')
        record = {}
        current_field = None
        
        # Initialize lists for multi-value fields
        multi_value_fields = {
            'AU': [], 'FAU': [], 'AD': [], 'MH': [], 'OT': [], 'AB': [], 'TI': []
        }
        
        for line in lines:
            if not line.strip():
                continue
                
            # Check if this is a field line (starts with field tag)
            if line[:4] and line[4:6] == '- ':
                current_field = line[:4].strip()
                content = line[6:].strip()
                
                if current_field in multi_value_fields:
                    if content:
                        multi_value_fields[current_field].append(content)
                else:
                    record[current_field] = content
            elif current_field and line.startswith('      '):
                # Continuation line
                content = line[6:].strip()
                if current_field in multi_value_fields:
                    if multi_value_fields[current_field]:
                        multi_value_fields[current_field][-1] += ' ' + content
                    else:
                        multi_value_fields[current_field].append(content)
                else:
                    if current_field in record:
                        record[current_field] += ' ' + content
                    else:
                        record[current_field] = content
        
        # Merge multi-value fields into record
        for field, values in multi_value_fields.items():
            if values:
                record[field] = values
        
        return record
    
    def convert_to_json(self, medline_record: Dict) -> Optional[Dict]:
        """Convert MEDLINE record to JSON format suitable for database import."""
        try:
            # Required PMID
            pmid = medline_record.get('PMID')
            if not pmid:
                self.stats['missing_pmids'] += 1
                return None
            
            # Convert lists to single strings for certain fields
            title = medline_record.get('TI', [])
            if isinstance(title, list):
                title = ' '.join(title)
            
            abstract_parts = medline_record.get('AB', [])
            if isinstance(abstract_parts, list):
                abstract = ' '.join(abstract_parts)
            else:
                abstract = abstract_parts or ''
            
            # Parse publication date and extract year
            pub_date = medline_record.get('DP', '')
            formatted_date = self.parse_date(pub_date)
            pub_year = self.extract_year(pub_date, medline_record.get('DA', ''))
            
            if not pub_year:
                self.stats['missing_years'] += 1
                print(f"Warning: No valid year found for PMID {pmid}, DP: '{pub_date}', DA: '{medline_record.get('DA', '')}'")
                return None
            
            self.stats['years_found'].add(pub_year)
            
            # Parse authors
            authors_short = medline_record.get('AU', [])
            authors_full = medline_record.get('FAU', [])
            authors = self.parse_authors(authors_short, authors_full)
            
            # Parse MeSH terms and keywords
            mesh_terms = medline_record.get('MH', [])
            keywords = medline_record.get('OT', [])
            all_keywords = self.parse_keywords(mesh_terms + keywords)
            
            # Build JSON record
            json_record = {
                'pmid': pmid,
                'title': title or '',
                'abstract': abstract,
                'publication_date': formatted_date,
                'publication_year': pub_year,
                'journal': {
                    'name': medline_record.get('JT', ''),
                    'iso_abbreviation': medline_record.get('TA', ''),
                    'volume': medline_record.get('VI', ''),
                    'issue': medline_record.get('IP', ''),
                    'pages': medline_record.get('PG', ''),
                    'issn': medline_record.get('IS', '')
                },
                'authors': authors,
                'affiliations': medline_record.get('AD', []),
                'mesh_terms': mesh_terms,
                'keywords': all_keywords,
                'doi': medline_record.get('AID', ''),
                'pmc_id': medline_record.get('PMC', ''),
                'language': medline_record.get('LA', []),
                'publication_type': medline_record.get('PT', []),
                'country': medline_record.get('PL', ''),
                'nlm_id': medline_record.get('NlmUniqueID', ''),
                'date_created': medline_record.get('CRDT', ''),
                'date_completed': medline_record.get('DCOM', ''),
                'date_revised': medline_record.get('LR', ''),
                'status': medline_record.get('STAT', ''),
                'owner': medline_record.get('OWN', ''),
                'indexing_method': medline_record.get('DA', ''),
                'original_medline': medline_record
            }
            
            return json_record
            
        except Exception as e:
            print(f"Error converting record {medline_record.get('PMID', 'unknown')}: {str(e)}")
            return None
    
    def parse_file(self, input_file: Path, output_dir: Path) -> Dict[str, Any]:
        """Parse a MEDLINE file and create JSON files organized by year."""
        print(f"📄 Parsing: {input_file}")
        
        if not input_file.exists():
            return {'error': 'File not found'}
        
        try:
            with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return {'error': f'Failed to read file: {str(e)}'}
        
        # Split into records (each record ends with blank line)
        records = re.split(r'\n\s*\n', content)
        
        file_stats = {
            'records_processed': 0,
            'records_saved': 0,
            'records_failed': 0,
            'years_created': set()
        }
        
        for i, record_text in enumerate(records):
            if not record_text.strip():
                continue
                
            # Parse the MEDLINE record
            medline_record = self.parse_record(record_text)
            if not medline_record:
                file_stats['records_failed'] += 1
                continue
            
            # Convert to JSON format
            json_record = self.convert_to_json(medline_record)
            if not json_record:
                file_stats['records_failed'] += 1
                continue
            
            file_stats['records_processed'] += 1
            
            # Create year directory if needed
            year = json_record['publication_year']
            year_dir = output_dir / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)
            file_stats['years_created'].add(year)
            
            # Save JSON file named by PMID
            json_file = year_dir / f"{json_record['pmid']}.json"
            try:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(json_record, f, ensure_ascii=False, indent=2)
                file_stats['records_saved'] += 1
                
                if file_stats['records_saved'] % 1000 == 0:
                    print(f"  💾 Saved {file_stats['records_saved']} records...")
                    
            except Exception as e:
                print(f"Error saving {json_record['pmid']}: {str(e)}")
                file_stats['records_failed'] += 1
        
        return file_stats


def main():
    """Main function to process all MEDLINE files."""
    # Setup paths
    input_dir = Path('data/pubmed_entrez_search')
    output_dir = Path('data/pubmed_json_by_year')
    
    print("🦷 OralEvidenceDB MEDLINE Parser")
    print("=" * 50)
    print(f"📂 Input directory: {input_dir}")
    print(f"📁 Output directory: {output_dir}")
    
    if not input_dir.exists():
        print(f"❌ Error: Input directory not found: {input_dir}")
        print("Run download_pubmed_articles.sh first to download MEDLINE files")
        return
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all MEDLINE files
    medline_files = list(input_dir.glob('oralevidencedb_pubmed_*.txt'))
    if not medline_files:
        print(f"❌ No MEDLINE files found in {input_dir}")
        print("Expected files: oralevidencedb_pubmed_YYYY.txt")
        return
    
    print(f"📚 Found {len(medline_files)} MEDLINE files")
    
    # Initialize parser
    parser = MedlineParserByYear()
    
    # Process each file
    total_stats = {
        'files_processed': 0,
        'files_successful': 0,
        'total_records_saved': 0,
        'total_records_failed': 0,
        'all_years_created': set()
    }
    
    for medline_file in sorted(medline_files):
        file_stats = parser.parse_file(medline_file, output_dir)
        
        if 'error' in file_stats:
            print(f"❌ Failed to process {medline_file.name}: {file_stats['error']}")
        else:
            total_stats['files_processed'] += 1
            total_stats['files_successful'] += 1
            total_stats['total_records_saved'] += file_stats['records_saved']
            total_stats['total_records_failed'] += file_stats['records_failed']
            total_stats['all_years_created'].update(file_stats['years_created'])
            
            print(f"✅ {medline_file.name}: {file_stats['records_saved']} saved, {file_stats['records_failed']} failed")
    
    # Final summary
    print("\n" + "=" * 50)
    print("📊 PARSING SUMMARY")
    print("=" * 50)
    print(f"Files processed: {total_stats['files_successful']}/{len(medline_files)}")
    print(f"Total records saved: {total_stats['total_records_saved']:,}")
    print(f"Total records failed: {total_stats['total_records_failed']:,}")
    print(f"Success rate: {(total_stats['total_records_saved']/(total_stats['total_records_saved']+total_stats['total_records_failed'])*100):.1f}%")
    
    print(f"\n📅 Years created: {sorted(total_stats['all_years_created'])}")
    print(f"Year range: {min(total_stats['all_years_created'])} - {max(total_stats['all_years_created'])}")
    
    print(f"\n📁 JSON files saved in: {output_dir}")
    print("\n🔄 Next step: Run import script to load into database")
    print("   python import_all_years_corrected.py")


if __name__ == '__main__':
    main()
