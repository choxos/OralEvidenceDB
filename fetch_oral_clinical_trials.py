#!/usr/bin/env python3
"""
ClinicalTrials.gov Oral Health Studies Fetcher

This script fetches all oral health-related clinical trials from ClinicalTrials.gov API
and organizes them by start year in separate JSON files.

Search Keywords: Oral Health; Dental Health; Dental Caries; Dentistry; Oral Cancer

Usage: python3 fetch_oral_clinical_trials.py
"""

import requests
import json
import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

class OralClinicalTrialsFetcher:
    def __init__(self, base_dir: str = "data/clinicaltrials.gov_oral"):
        self.base_dir = Path(base_dir)
        self.api_base_url = "https://clinicaltrials.gov/api/v2/studies"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OralEvidenceDB-Fetcher/1.0 (Oral Health Clinical Research Data Collection)'
        })
        
        # Oral health search keywords as specified by user
        self.search_keywords = [
            "Oral Health",
            "Dental Health", 
            "Dental Caries",
            "Dentistry",
            "Oral Cancer"
        ]
        
        # Create base directory
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up logging
        self.setup_logging()
        
        # Progress tracking
        self.progress_file = self.base_dir / "fetch_progress.json"
        self.stats = {
            'total_fetched': 0,
            'total_expected': 0,
            'studies_by_year': {},
            'studies_by_keyword': {},
            'failed_requests': 0,
            'start_time': None,
            'last_page_token': None,
            'keywords_processed': []
        }
        
        # Load existing progress
        self.load_progress()
    
    def setup_logging(self):
        """Set up logging configuration"""
        log_file = self.base_dir / "fetch_log.txt"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='a'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_progress(self):
        """Load existing progress if available"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    saved_stats = json.load(f)
                    self.stats.update(saved_stats)
                self.logger.info(f"Resumed from previous session. Fetched so far: {self.stats['total_fetched']}")
            except Exception as e:
                self.logger.warning(f"Could not load progress file: {e}")
    
    def save_progress(self):
        """Save current progress"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            self.logger.error(f"Could not save progress: {e}")
    
    def get_total_count_for_keywords(self) -> Dict[str, int]:
        """Get the total number of studies for each keyword"""
        keyword_counts = {}
        total_unique = 0
        
        for keyword in self.search_keywords:
            try:
                params = {
                    'query.cond': keyword,
                    'countTotal': 'true',
                    'pageSize': '1'
                }
                response = self.session.get(self.api_base_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                count = data.get('totalCount', 0)
                keyword_counts[keyword] = count
                self.logger.info(f"Keyword '{keyword}': {count:,} studies found")
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                self.logger.error(f"Error getting count for '{keyword}': {e}")
                keyword_counts[keyword] = 0
        
        # Calculate total (note: there will be overlaps between keywords)
        total_unique = sum(keyword_counts.values())
        self.logger.info(f"Total studies across all keywords: {total_unique:,} (includes duplicates)")
        
        return keyword_counts
    
    def extract_start_year(self, study: Dict) -> Optional[str]:
        """Extract the start year from a study"""
        try:
            # Try to get the start date from various possible locations
            start_date = None
            
            # Method 1: protocolSection.statusModule.startDateStruct
            if 'protocolSection' in study:
                status_module = study['protocolSection'].get('statusModule', {})
                start_date_struct = status_module.get('startDateStruct', {})
                if start_date_struct and 'date' in start_date_struct:
                    start_date = start_date_struct['date']
            
            # Method 2: Try other possible locations
            if not start_date:
                # Alternative locations in the JSON structure
                locations_to_check = [
                    ['protocolSection', 'statusModule', 'studyFirstSubmitDate'],
                    ['protocolSection', 'statusModule', 'studyFirstPostDateStruct', 'date'],
                    ['studyFirstSubmitDate'],
                    ['startDate']
                ]
                
                for location in locations_to_check:
                    current = study
                    for key in location:
                        if isinstance(current, dict) and key in current:
                            current = current[key]
                        else:
                            current = None
                            break
                    if current:
                        start_date = current
                        break
            
            if start_date:
                # Extract year from date string (format: YYYY-MM-DD or similar)
                if isinstance(start_date, str) and len(start_date) >= 4:
                    year = start_date[:4]
                    if year.isdigit() and 1970 <= int(year) <= 2030:
                        return year
            
            # If no valid start date found, return 'unknown'
            return 'unknown'
            
        except Exception as e:
            self.logger.debug(f"Error extracting start year: {e}")
            return 'unknown'
    
    def save_study(self, study: Dict, keyword: str) -> bool:
        """Save a study to the appropriate year directory"""
        try:
            nct_id = study.get('protocolSection', {}).get('identificationModule', {}).get('nctId')
            if not nct_id:
                self.logger.warning("Study missing NCT ID, skipping")
                return False
            
            # Extract start year
            year = self.extract_start_year(study)
            
            # Create year directory
            year_dir = self.base_dir / str(year)
            year_dir.mkdir(exist_ok=True)
            
            # Save study JSON file
            study_file = year_dir / f"{nct_id}.json"
            
            # Add metadata about which keyword found this study
            study_with_meta = {
                'nct_id': nct_id,
                'found_by_keyword': keyword,
                'fetch_date': datetime.now().isoformat(),
                'original_data': study
            }
            
            # Don't overwrite existing studies (they might be found by multiple keywords)
            if study_file.exists():
                # Load existing and merge keywords that found this study
                try:
                    with open(study_file, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                    
                    # Add this keyword to the list if not already there
                    existing_keywords = existing.get('found_by_keywords', [existing.get('found_by_keyword')])
                    if keyword not in existing_keywords:
                        existing_keywords.append(keyword)
                        existing['found_by_keywords'] = existing_keywords
                        
                        with open(study_file, 'w', encoding='utf-8') as f:
                            json.dump(existing, f, indent=2, ensure_ascii=False)
                        self.logger.debug(f"Updated {nct_id} with additional keyword: {keyword}")
                except Exception as e:
                    self.logger.error(f"Error updating existing study {nct_id}: {e}")
                
                return False  # Not a new study
            
            with open(study_file, 'w', encoding='utf-8') as f:
                json.dump(study_with_meta, f, indent=2, ensure_ascii=False)
            
            # Update stats
            if year not in self.stats['studies_by_year']:
                self.stats['studies_by_year'][year] = 0
            self.stats['studies_by_year'][year] += 1
            
            if keyword not in self.stats['studies_by_keyword']:
                self.stats['studies_by_keyword'][keyword] = 0
            self.stats['studies_by_keyword'][keyword] += 1
            
            self.logger.debug(f"Saved study {nct_id} ({year}) - keyword: {keyword}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving study: {e}")
            return False
    
    def fetch_studies_for_keyword(self, keyword: str) -> int:
        """Fetch all studies for a specific keyword"""
        self.logger.info(f"🔍 Fetching studies for keyword: '{keyword}'")
        
        studies_fetched = 0
        page_token = None
        page_num = 1
        
        while True:
            try:
                params = {
                    'query.cond': keyword,
                    'pageSize': '100',  # Maximum allowed
                    'format': 'json'
                }
                
                if page_token:
                    params['pageToken'] = page_token
                
                self.logger.info(f"   📄 Fetching page {page_num} for '{keyword}'...")
                
                response = self.session.get(self.api_base_url, params=params, timeout=60)
                response.raise_for_status()
                data = response.json()
                
                studies = data.get('studies', [])
                if not studies:
                    self.logger.info(f"   ✅ No more studies for '{keyword}' - completed")
                    break
                
                # Save each study
                page_saved = 0
                for study in studies:
                    if self.save_study(study, keyword):
                        page_saved += 1
                        studies_fetched += 1
                        self.stats['total_fetched'] += 1
                
                self.logger.info(f"   📊 Page {page_num}: {page_saved} new studies saved, {len(studies)} total processed")
                
                # Check for next page
                page_token = data.get('nextPageToken')
                if not page_token:
                    self.logger.info(f"   ✅ Completed all pages for '{keyword}' - total: {studies_fetched}")
                    break
                
                page_num += 1
                
                # Save progress periodically
                if page_num % 5 == 0:
                    self.save_progress()
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error fetching page {page_num} for '{keyword}': {e}")
                self.stats['failed_requests'] += 1
                time.sleep(5)  # Wait longer on error
                continue
        
        return studies_fetched
    
    def run(self):
        """Main execution method"""
        self.logger.info("🦷 Starting ClinicalTrials.gov Oral Health Studies Fetch")
        self.logger.info("=" * 60)
        
        self.stats['start_time'] = datetime.now().isoformat()
        
        # Get total counts first
        self.logger.info("📊 Getting study counts for each keyword...")
        keyword_counts = self.get_total_count_for_keywords()
        
        total_expected = sum(keyword_counts.values())
        self.stats['total_expected'] = total_expected
        
        self.logger.info(f"📈 Expected total studies: {total_expected:,} (with duplicates)")
        self.logger.info(f"🔎 Keywords: {', '.join(self.search_keywords)}")
        self.logger.info("")
        
        # Fetch studies for each keyword
        for keyword in self.search_keywords:
            if keyword in self.stats.get('keywords_processed', []):
                self.logger.info(f"⏭️  Skipping already processed keyword: '{keyword}'")
                continue
            
            try:
                keyword_fetched = self.fetch_studies_for_keyword(keyword)
                self.stats['keywords_processed'].append(keyword)
                self.logger.info(f"✅ Completed '{keyword}': {keyword_fetched} new studies")
                self.save_progress()
                
                # Short break between keywords
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"❌ Failed to process keyword '{keyword}': {e}")
                continue
        
        # Final summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 ORAL CLINICAL TRIALS FETCH COMPLETE")
        self.logger.info("=" * 60)
        self.logger.info(f"🔍 Keywords processed: {len(self.stats['keywords_processed'])}/{len(self.search_keywords)}")
        self.logger.info(f"💾 Total unique studies fetched: {self.stats['total_fetched']:,}")
        self.logger.info(f"❌ Failed requests: {self.stats['failed_requests']}")
        
        if self.stats['studies_by_keyword']:
            self.logger.info("\n📋 Studies by keyword:")
            for keyword, count in self.stats['studies_by_keyword'].items():
                self.logger.info(f"   {keyword}: {count:,} studies")
        
        if self.stats['studies_by_year']:
            years = sorted(self.stats['studies_by_year'].keys())
            self.logger.info(f"\n📅 Year range: {years[0]} - {years[-1]}")
            self.logger.info(f"📈 Years covered: {len(years)} different years")
        
        self.logger.info(f"\n📁 Studies saved in: {self.base_dir}")
        
        # Save final progress
        self.save_progress()
        
        return self.stats

def main():
    """Main function"""
    print("🦷 OralEvidenceDB - ClinicalTrials.gov Fetcher")
    print("=" * 50)
    print("Fetching oral health clinical trials...")
    print("Keywords: Oral Health, Dental Health, Dental Caries, Dentistry, Oral Cancer")
    print()
    
    try:
        fetcher = OralClinicalTrialsFetcher()
        stats = fetcher.run()
        
        print(f"\n🎉 Fetch completed!")
        print(f"📊 {stats['total_fetched']:,} unique studies saved")
        print(f"📁 Check data/clinicaltrials.gov_oral/ for results")
        
    except KeyboardInterrupt:
        print("\n⏹️  Fetch interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during fetch: {e}")
        logging.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
