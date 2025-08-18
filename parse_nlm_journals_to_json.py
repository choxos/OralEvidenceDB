#!/usr/bin/env python3
"""
Parse downloaded NLM journal MEDLINE files to JSON format
Organizes by: [broad_subject_term]/[title_full]/[year]/

Based on: scripts/parse_medline_to_json_by_year.py
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
import argparse

def parse_medline_record(record_text):
    """
    Parse a single MEDLINE record into a structured dictionary.
    Based on existing parsing logic from parse_medline_to_json_by_year.py
    """
    if not record_text.strip():
        return None
        
    lines = record_text.strip().split('\n')
    record = {}
    current_field = None
    current_value = []
    
    for line in lines:
        line = line.rstrip()
        
        if not line:
            continue
            
        if line.startswith('    ') or line.startswith('\t'):
            # Continuation line
            if current_field:
                current_value.append(line.strip())
        else:
            # Save previous field
            if current_field and current_value:
                if current_field in record:
                    if isinstance(record[current_field], list):
                        record[current_field].append(' '.join(current_value))
                    else:
                        record[current_field] = [record[current_field], ' '.join(current_value)]
                else:
                    record[current_field] = ' '.join(current_value)
            
            # Parse new field
            if '- ' in line:
                parts = line.split('- ', 1)
                if len(parts) == 2:
                    current_field = parts[0].strip()
                    current_value = [parts[1].strip()] if parts[1].strip() else []
                else:
                    current_field = None
                    current_value = []
            else:
                current_field = None
                current_value = []
    
    # Save last field
    if current_field and current_value:
        if current_field in record:
            if isinstance(record[current_field], list):
                record[current_field].append(' '.join(current_value))
            else:
                record[current_field] = [record[current_field], ' '.join(current_value)]
        else:
            record[current_field] = ' '.join(current_value)
    
    return record if record else None

def extract_publication_year(record):
    """Extract publication year from MEDLINE record"""
    # Try different date fields
    date_fields = ['DP', 'DEP', 'EDAT', 'DA']
    
    for field in date_fields:
        if field in record:
            date_str = record[field]
            if isinstance(date_str, list):
                date_str = date_str[0]
            
            # Extract year using regex
            year_match = re.search(r'(\d{4})', str(date_str))
            if year_match:
                year = int(year_match.group(1))
                if 1800 <= year <= 2030:  # Reasonable year range
                    return year
    
    return None

def process_medline_file(medline_file_path, output_dir):
    """Process a single MEDLINE file and save records as JSON"""
    print(f"  📄 Processing: {medline_file_path.name}")
    
    try:
        with open(medline_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(medline_file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            print(f"    ❌ Error reading file: {e}")
            return 0
    
    if not content.strip():
        print(f"    ⚠️  Empty file, skipping")
        return 0
    
    # Split records by blank lines or record separators
    records = re.split(r'\n\s*\n', content)
    parsed_count = 0
    year_counts = {}
    
    for i, record_text in enumerate(records):
        if not record_text.strip():
            continue
            
        record = parse_medline_record(record_text)
        if not record:
            continue
        
        # Extract publication year
        pub_year = extract_publication_year(record)
        if not pub_year:
            # If no year found, try to extract from filename
            year_match = re.search(r'_(\d{4})\.txt$', medline_file_path.name)
            if year_match:
                pub_year = int(year_match.group(1))
            else:
                pub_year = 'unknown'
        
        # Create year directory
        year_dir = output_dir / str(pub_year)
        year_dir.mkdir(exist_ok=True)
        
        # Count papers by year
        year_counts[pub_year] = year_counts.get(pub_year, 0) + 1
        
        # Save record as JSON
        pmid = record.get('PMID', f'record_{i+1}')
        if isinstance(pmid, list):
            pmid = pmid[0]
        
        json_filename = f"{pmid}.json"
        json_path = year_dir / json_filename
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
            parsed_count += 1
        except Exception as e:
            print(f"    ⚠️  Error saving {pmid}: {e}")
    
    if parsed_count > 0:
        print(f"    ✅ Parsed {parsed_count} records")
        for year, count in sorted(year_counts.items()):
            print(f"      📅 {year}: {count} papers")
    else:
        print(f"    ⚠️  No valid records found")
    
    return parsed_count

def process_journal(journal_dir):
    """Process all MEDLINE files for a single journal"""
    journal_name = journal_dir.name
    medline_dir = journal_dir / 'medline'
    
    if not medline_dir.exists():
        print(f"  ⚠️  No medline directory found in {journal_dir}")
        return 0
    
    print(f"📖 Processing Journal: {journal_name}")
    
    # Create JSON output directory
    json_dir = journal_dir / 'json'
    json_dir.mkdir(exist_ok=True)
    
    # Process all MEDLINE files
    medline_files = list(medline_dir.glob('*.txt'))
    if not medline_files:
        print(f"  ⚠️  No MEDLINE files found")
        return 0
    
    total_records = 0
    for medline_file in sorted(medline_files):
        records_count = process_medline_file(medline_file, json_dir)
        total_records += records_count
    
    # Create summary
    summary = {
        'journal_name': journal_name,
        'processed_date': datetime.now().isoformat(),
        'total_records': total_records,
        'medline_files_processed': len(medline_files),
        'json_directory': str(json_dir)
    }
    
    summary_path = journal_dir / 'parsing_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    print(f"  📊 Journal Summary: {total_records} total records")
    print(f"  💾 Saved to: {json_dir}")
    return total_records

def main():
    parser = argparse.ArgumentParser(
        description='Parse NLM journal MEDLINE files to JSON format'
    )
    parser.add_argument(
        '--data-dir', 
        type=str, 
        default='nlm_journals_data',
        help='Base directory containing NLM journals data'
    )
    parser.add_argument(
        '--subject', 
        type=str,
        help='Process only journals from specific subject (e.g., "Dentistry")'
    )
    parser.add_argument(
        '--journal', 
        type=str,
        help='Process only specific journal (directory name)'
    )
    parser.add_argument(
        '--resume', 
        action='store_true',
        help='Skip journals that already have JSON directories'
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        sys.exit(1)
    
    print("📚 NLM Journals MEDLINE to JSON Parser")
    print("=====================================")
    print(f"📁 Data directory: {data_dir}")
    print(f"📊 Subject filter: {args.subject or 'All subjects'}")
    print(f"📖 Journal filter: {args.journal or 'All journals'}")
    print(f"🔄 Resume mode: {'Yes' if args.resume else 'No'}")
    print()
    
    total_journals = 0
    processed_journals = 0
    total_records = 0
    
    # Process each subject directory
    for subject_dir in data_dir.iterdir():
        if not subject_dir.is_dir():
            continue
            
        if args.subject and subject_dir.name != args.subject:
            continue
            
        print(f"📂 Subject: {subject_dir.name}")
        
        # Process each journal directory
        for journal_dir in subject_dir.iterdir():
            if not journal_dir.is_dir():
                continue
                
            if args.journal and journal_dir.name != args.journal:
                continue
            
            total_journals += 1
            
            # Skip if already processed (resume mode)
            if args.resume and (journal_dir / 'json').exists():
                print(f"  ⏭️  Skipping {journal_dir.name} (already processed)")
                continue
            
            try:
                records_count = process_journal(journal_dir)
                if records_count > 0:
                    processed_journals += 1
                    total_records += records_count
            except Exception as e:
                print(f"  ❌ Error processing {journal_dir.name}: {e}")
        
        print()
    
    print("🎉 NLM Journals Parsing Complete!")
    print("📊 Final Summary:")
    print(f"   📚 Total journals found: {total_journals}")
    print(f"   ✅ Journals successfully processed: {processed_journals}")
    print(f"   📄 Total records parsed: {total_records:,}")
    print(f"   📁 Data location: {data_dir}/")
    print()
    print("💡 JSON files are organized by:")
    print("   📂 [subject]/[journal]/json/[year]/[pmid].json")

if __name__ == '__main__':
    main()
