#!/usr/bin/env python3
"""
Comprehensive batch import for all years for OralEvidenceDB (1940+)
Applies proven corrections and settings for reliable import.

This script will:
1. Identify all years with JSON files
2. Apply corrected import settings to each year
3. Track progress and provide detailed reporting
4. Skip years that are already well imported (>95% success)
"""

import os
import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oral_evidence_db.settings')
django.setup()
from papers.models import Paper

def get_year_status():
    """Get import status for all years."""
    base_dir = Path('data/pubmed_json_by_year')
    years_data = {}
    
    if not base_dir.exists():
        return years_data
    
    for year_dir in base_dir.iterdir():
        if year_dir.is_dir() and year_dir.name.isdigit():
            year = int(year_dir.name)
            if year >= 1940:  # Focus on 1940 and beyond for oral health
                json_files = len(list(year_dir.glob('*.json')))
                imported_count = Paper.objects.filter(publication_year=year).count()
                failed_count = json_files - imported_count
                success_rate = (imported_count / json_files * 100) if json_files > 0 else 0
                
                years_data[year] = {
                    'json_files': json_files,
                    'imported': imported_count,
                    'failed': failed_count,
                    'success_rate': success_rate,
                    'needs_fix': success_rate < 95.0  # Less than 95% success needs fixing
                }
    
    return years_data

def import_year_with_corrections(year, year_data):
    """Import a specific year with corrections."""
    year_path = Path(f'data/pubmed_json_by_year/{year}')
    
    if not year_path.exists():
        return False, f"Directory not found: {year_path}"
    
    print(f"📅 Importing {year} with corrections")
    print(f"📊 Total JSON files: {year_data['json_files']:,}")
    print(f"📊 Currently imported: {year_data['imported']:,}")
    print(f"📊 Remaining to import: {year_data['failed']:,}")
    print(f"📊 Current success rate: {year_data['success_rate']:.1f}%")
    print()
    
    # Use small batch size (proven to fix 93%+ of transaction issues)
    batch_size = 50
    
    cmd = [
        'python3', 'manage.py', 'import_medline_json',
        '--json-dir', str(year_path),
        '--batch-size', str(batch_size),
        '--verbosity', '1'  # Less verbose for batch processing
    ]
    
    try:
        start_time = time.time()
        print(f"🚀 Starting import for {year}...")
        
        # Run the import
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=7200  # 2 hour timeout per year
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            # Get final count
            final_imported = Paper.objects.filter(publication_year=year).count()
            newly_imported = final_imported - year_data['imported']
            final_success_rate = (final_imported / year_data['json_files'] * 100) if year_data['json_files'] > 0 else 0
            
            print(f"✅ {year} completed in {duration/60:.1f} minutes")
            print(f"📊 Papers imported: {newly_imported:,}")
            print(f"📊 Final success rate: {final_success_rate:.1f}%")
            print(f"📊 Total papers for {year}: {final_imported:,}")
            
            return True, {
                'newly_imported': newly_imported,
                'final_imported': final_imported,
                'final_success_rate': final_success_rate,
                'duration_minutes': duration / 60
            }
        else:
            error_output = result.stderr if result.stderr else result.stdout
            print(f"❌ {year} failed with return code {result.returncode}")
            print(f"Error output: {error_output[:500]}...")
            return False, f"Command failed: {error_output[:200]}"
    
    except subprocess.TimeoutExpired:
        print(f"❌ {year} timed out after 2 hours")
        return False, "Import timed out after 2 hours"
    except Exception as e:
        print(f"❌ {year} failed with exception: {str(e)}")
        return False, f"Exception: {str(e)}"

def main():
    """Main import function."""
    print("🦷 OralEvidenceDB Batch Import - All Years Corrected")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path('manage.py').exists():
        print("❌ Error: manage.py not found. Run this script from the project root.")
        sys.exit(1)
    
    # Check data directory
    data_dir = Path('data/pubmed_json_by_year')
    if not data_dir.exists():
        print("❌ Error: JSON data directory not found")
        print(f"Expected: {data_dir}")
        print("Run the parsing script first: python scripts/parse_medline_to_json_by_year.py")
        sys.exit(1)
    
    print("📊 Analyzing current import status...")
    years_data = get_year_status()
    
    if not years_data:
        print("❌ No year data found. Make sure JSON files are organized by year.")
        sys.exit(1)
    
    # Sort years and categorize
    years_needing_import = []
    years_well_imported = []
    
    for year, data in sorted(years_data.items()):
        if data['needs_fix']:
            years_needing_import.append((year, data))
        else:
            years_well_imported.append((year, data))
    
    print(f"\n📈 Import Status Summary:")
    print(f"Years needing import/fixing: {len(years_needing_import)}")
    print(f"Years already well imported (>95%): {len(years_well_imported)}")
    
    if years_well_imported:
        print(f"\n✅ Well imported years: {[year for year, _ in years_well_imported]}")
    
    if not years_needing_import:
        print("\n🎉 All years are already well imported! No work needed.")
        return
    
    print(f"\n🔧 Years requiring import/fixes:")
    total_files_to_process = 0
    total_papers_to_import = 0
    
    for year, data in years_needing_import:
        print(f"  {year}: {data['failed']:,} remaining ({data['success_rate']:.1f}% complete)")
        total_files_to_process += data['json_files']
        total_papers_to_import += data['failed']
    
    print(f"\n📊 Total work:")
    print(f"  Files to process: {total_files_to_process:,}")
    print(f"  Papers to import: {total_papers_to_import:,}")
    
    # Confirm before starting
    response = input("\n🤔 Proceed with batch import? (y/N): ")
    if response.lower() != 'y':
        print("Import cancelled.")
        return
    
    # Start batch import
    print("\n🚀 Starting batch import with corrections...")
    start_time = time.time()
    
    results = {
        'successful_years': [],
        'failed_years': [],
        'total_imported': 0,
        'total_duration': 0
    }
    
    for year, year_data in years_needing_import:
        print(f"\n{'='*20} YEAR {year} {'='*20}")
        
        success, result_data = import_year_with_corrections(year, year_data)
        
        if success:
            results['successful_years'].append(year)
            results['total_imported'] += result_data['newly_imported']
            results['total_duration'] += result_data['duration_minutes']
            
            # Log success
            with open('import_success_log.txt', 'a') as f:
                f.write(f"{datetime.now().isoformat()}: {year} - {result_data['newly_imported']} papers in {result_data['duration_minutes']:.1f}min\\n")
        else:
            results['failed_years'].append((year, result_data))
            
            # Log failure
            with open('import_error_log.txt', 'a') as f:
                f.write(f"{datetime.now().isoformat()}: {year} FAILED - {result_data}\\n")
        
        # Small break between years
        time.sleep(2)
    
    # Final summary
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print("📊 FINAL BATCH IMPORT SUMMARY")
    print(f"{'='*60}")
    print(f"Successful years: {len(results['successful_years'])}")
    print(f"Failed years: {len(results['failed_years'])}")
    print(f"Total papers imported: {results['total_imported']:,}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"Average time per year: {results['total_duration']/len(years_needing_import):.1f} minutes")
    
    if results['successful_years']:
        print(f"✅ Successful years: {results['successful_years']}")
    
    if results['failed_years']:
        print(f"❌ Failed years:")
        for year, error in results['failed_years']:
            print(f"  {year}: {error}")
    
    # Final database stats
    print(f"\n📈 Final Database Statistics:")
    for year in range(1940, 2026):
        count = Paper.objects.filter(publication_year=year).count()
        if count > 0:
            print(f"  {year}: {count:,} papers")
    
    total_papers = Paper.objects.count()
    print(f"\n🦷 Total papers in OralEvidenceDB: {total_papers:,}")
    
    if results['failed_years']:
        print(f"\n⚠️  Some years failed to import. Check import_error_log.txt for details.")
        print("You can re-run this script to retry failed years.")
    else:
        print(f"\n🎉 All imports completed successfully!")
        print("🔍 Check Django admin panel for detailed paper statistics.")

if __name__ == '__main__':
    main()
