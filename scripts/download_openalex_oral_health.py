#!/usr/bin/env python3
"""
Download oral health papers from OpenAlex API.

This script downloads papers from OpenAlex using a comprehensive oral health search query.
Papers are downloaded from inception to 2025 with no date restrictions.

Search terms include: dental, dentistry, oral health, oral medicine, stomatology, 
odontology, maxillofacial, periodontal, endodontic, orthodontic, prosthodontic, 
oral surgery, dental caries, periodontitis, gingivitis, oral cancer, dental implants, 
root canal, dental restoration, dentures, braces, oral hygiene, dental materials, 
oral microbiology, dental radiography, and many more oral health related terms.
"""

import os
import json
import requests
import time
from pathlib import Path
from typing import Dict, List, Optional
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/openalex_oral_health_download.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OralHealthOpenAlexDownloader:
    """Download oral health papers from OpenAlex API."""
    
    def __init__(self, base_dir: str = "data/openalex_oral_health"):
        self.base_url = "https://api.openalex.org/works"
        self.base_dir = Path(base_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OralEvidenceDB/1.0 (mailto:oral.research@xeradb.com)',
            'Accept': 'application/json'
        })
        
        # Comprehensive oral health search terms as provided by user
        self.search_terms = [
            "dental", "dentistry", "oral health", "oral medicine", "stomatology", 
            "odontology", "maxillofacial", "orofacial", "periodontal", "endodontic", 
            "orthodontic", "prosthodontic", "oral surgery", "periodontics", 
            "endodontics", "orthodontics", "prosthodontics", "pediatric dentistry", 
            "oral pathology", "oral biology", "teeth", "tooth", "gingiva", "gums", 
            "oral cavity", "dental caries", "tooth decay", "periodontitis", 
            "gingivitis", "oral cancer", "dental implant", "root canal", 
            "dental restoration", "dentures", "braces", "oral hygiene", 
            "dental materials", "oral microbiology", "dental radiography"
        ]
        
        # Create directory structure
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir = self.base_dir / "json_papers"
        self.json_dir.mkdir(exist_ok=True)
        
        # Create year-based subdirectories
        self.by_year_dir = self.base_dir / "by_year"
        self.by_year_dir.mkdir(exist_ok=True)
        
        logger.info(f"🦷 OralEvidenceDB OpenAlex Downloader Initialized")
        logger.info(f"📁 Base directory: {self.base_dir}")
        logger.info(f"📄 JSON papers: {self.json_dir}")
        logger.info(f"📅 By year: {self.by_year_dir}")
    
    def make_request(self, url: str, params: Dict) -> Optional[Dict]:
        """Make API request with error handling and rate limiting."""
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Rate limiting - OpenAlex allows 100,000 requests per day
            # Be respectful with 0.1 second delay
            time.sleep(0.1)
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            logger.error(f"URL: {url}")
            logger.error(f"Params: {params}")
            return None
    
    def reconstruct_abstract(self, inverted_index: Dict) -> str:
        """Reconstruct abstract text from OpenAlex inverted index."""
        if not inverted_index:
            return ""
        
        try:
            # Find the maximum position to create array
            max_pos = max(max(positions) for positions in inverted_index.values())
            words = [''] * (max_pos + 1)
            
            # Place words in their positions
            for word, positions in inverted_index.items():
                for pos in positions:
                    if pos < len(words):
                        words[pos] = word
            
            # Join words to form abstract
            abstract = ' '.join(words).strip()
            return abstract
            
        except Exception as e:
            logger.debug(f"Failed to reconstruct abstract: {e}")
            return ""
    
    def save_paper(self, paper: Dict) -> bool:
        """Save a paper as JSON file with reconstructed abstract."""
        try:
            # Extract OpenAlex ID from the paper
            openalex_id = paper.get('id', '').split('/')[-1]
            if not openalex_id:
                logger.debug("No OpenAlex ID found")
                return False
            
            # Reconstruct abstract from inverted index
            inverted_index = paper.get('abstract_inverted_index')
            if inverted_index:
                abstract = self.reconstruct_abstract(inverted_index)
                if abstract:
                    paper['reconstructed_abstract'] = abstract
            
            # Save to main JSON directory
            filename = self.json_dir / f"{openalex_id}.json"
            if filename.exists():
                logger.debug(f"Paper {openalex_id} already exists, skipping")
                return False
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(paper, f, indent=2, ensure_ascii=False)
            
            # Also save by year if publication_year is available
            pub_year = paper.get('publication_year')
            if pub_year and isinstance(pub_year, int):
                year_dir = self.by_year_dir / str(pub_year)
                year_dir.mkdir(exist_ok=True)
                year_filename = year_dir / f"{openalex_id}.json"
                
                with open(year_filename, 'w', encoding='utf-8') as f:
                    json.dump(paper, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved paper: {openalex_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save paper: {e}")
            return False
    
    def build_search_query(self) -> str:
        """Build OpenAlex search query from oral health terms."""
        # Create OR query for title and abstract
        title_queries = [f'title.search:"{term}"' for term in self.search_terms]
        abstract_queries = [f'abstract.search:"{term}"' for term in self.search_terms]
        
        # Combine title and abstract searches
        all_queries = title_queries + abstract_queries
        search_query = "|".join(all_queries)
        
        return search_query
    
    def download_papers(self, max_papers: Optional[int] = None) -> Dict:
        """Download oral health papers from OpenAlex with no date restrictions."""
        logger.info("🔍 Starting oral health papers download from OpenAlex")
        logger.info(f"📅 Date range: From inception to 2025")
        logger.info(f"🔎 Search terms: {len(self.search_terms)} oral health related terms")
        
        stats = {
            'total_found': 0,
            'papers_saved': 0,
            'papers_skipped': 0,
            'papers_with_abstracts': 0,
            'errors': 0,
            'years_coverage': set(),
            'start_time': datetime.now()
        }
        
        # Build comprehensive search query
        search_query = self.build_search_query()
        logger.info(f"🔍 Using search query with {len(self.search_terms)} terms")
        
        cursor = "*"  # Start cursor pagination
        page_num = 1
        
        while cursor is not None:
            params = {
                'filter': search_query,
                'cursor': cursor,
                'per-page': 200,  # Maximum allowed per page
                'select': 'id,doi,title,publication_year,publication_date,type,authorships,concepts,abstract_inverted_index,cited_by_count,primary_location,mesh,topics,keywords,language,open_access'
            }
            
            logger.info(f"📄 Processing batch {page_num}...")
            
            try:
                data = self.make_request(self.base_url, params)
                if not data:
                    logger.error(f"Failed to get data for batch {page_num}")
                    stats['errors'] += 1
                    break
                
                results = data.get('results', [])
                if not results:
                    logger.info("✅ No more results found")
                    break
                
                # Update total count from first page
                if page_num == 1:
                    meta = data.get('meta', {})
                    stats['total_found'] = meta.get('count', 0)
                    logger.info(f"📊 Total papers found: {stats['total_found']:,}")
                
                # Process papers in this batch
                for paper in results:
                    if max_papers and stats['papers_saved'] >= max_papers:
                        logger.info(f"🎯 Reached maximum papers limit: {max_papers}")
                        cursor = None
                        break
                    
                    if self.save_paper(paper):
                        stats['papers_saved'] += 1
                        
                        # Track years coverage
                        pub_year = paper.get('publication_year')
                        if pub_year:
                            stats['years_coverage'].add(pub_year)
                        
                        # Track abstracts
                        if paper.get('abstract_inverted_index'):
                            stats['papers_with_abstracts'] += 1
                    else:
                        stats['papers_skipped'] += 1
                
                # Get next cursor
                cursor = data.get('meta', {}).get('next_cursor')
                page_num += 1
                
                # Progress update every 10 batches
                if page_num % 10 == 0:
                    logger.info(f"📈 Progress: {stats['papers_saved']:,} saved, "
                              f"{stats['papers_skipped']:,} skipped, "
                              f"batch {page_num}")
                
                if cursor is None:
                    logger.info("✅ All batches processed")
                    break
                    
            except Exception as e:
                logger.error(f"Error processing batch {page_num}: {e}")
                stats['errors'] += 1
                break
        
        # Final statistics
        stats['end_time'] = datetime.now()
        stats['duration'] = stats['end_time'] - stats['start_time']
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 ORAL HEALTH OPENALEX DOWNLOAD COMPLETE")
        logger.info("=" * 60)
        logger.info(f"🔍 Total papers found: {stats['total_found']:,}")
        logger.info(f"💾 Papers saved: {stats['papers_saved']:,}")
        logger.info(f"⏭️  Papers skipped (already exist): {stats['papers_skipped']:,}")
        logger.info(f"📝 Papers with abstracts: {stats['papers_with_abstracts']:,}")
        logger.info(f"❌ Errors: {stats['errors']}")
        logger.info(f"⏱️  Duration: {stats['duration']}")
        
        if stats['years_coverage']:
            min_year = min(stats['years_coverage'])
            max_year = max(stats['years_coverage'])
            logger.info(f"📅 Year range: {min_year} - {max_year}")
            logger.info(f"📈 Years covered: {len(stats['years_coverage'])} different years")
        
        logger.info(f"📁 Files saved in: {self.base_dir}")
        
        return stats

def main():
    """Main function to run the oral health OpenAlex downloader."""
    print("🦷 OralEvidenceDB - OpenAlex Download")
    print("=" * 50)
    print("Downloading oral health research papers from OpenAlex")
    print("No date restrictions - from inception to 2025")
    print()
    
    try:
        # Initialize downloader
        downloader = OralHealthOpenAlexDownloader()
        
        # Download papers (no limit - download everything)
        stats = downloader.download_papers()
        
        print(f"\n🎉 Download completed!")
        print(f"📊 {stats['papers_saved']:,} papers saved")
        print(f"📁 Check data/openalex_oral_health/ for results")
        
        # Save download statistics
        stats_file = downloader.base_dir / "download_stats.json"
        with open(stats_file, 'w') as f:
            # Convert datetime objects to strings for JSON serialization
            json_stats = {k: str(v) if isinstance(v, datetime) else 
                         list(v) if isinstance(v, set) else v 
                         for k, v in stats.items()}
            json.dump(json_stats, f, indent=2)
        
        print(f"📈 Statistics saved to: {stats_file}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Download interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during download: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
