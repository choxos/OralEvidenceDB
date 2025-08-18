"""
Clinical Trial Service for OralEvidenceDB

This module provides services for:
1. Extracting NCT numbers from paper abstracts and titles
2. Fetching clinical trial data from ClinicalTrials.gov API
3. Linking papers with clinical trials
"""

import re
import requests
import logging
from datetime import datetime, timezone
from typing import List, Set, Optional, Tuple, Dict
from django.db import transaction
from django.utils import timezone as django_timezone

from ..models import Paper
from ..models_clinical_trial import ClinicalTrial, PaperClinicalTrial, NCTExtractionRun

logger = logging.getLogger(__name__)


class NCTExtractor:
    """Extracts NCT numbers from paper text content."""
    
    # Regex patterns for NCT number detection
    NCT_PATTERNS = [
        # Standard NCT format: NCT followed by 8 digits
        r'\bNCT\d{8}\b',
        
        # NCT with spaces, hyphens, or other separators
        r'\bNCT[\s\-_]*\d{8}\b',
        
        # ClinicalTrials.gov identifier variations
        r'ClinicalTrials\.gov[:\s]*[Ii]dentifier[\s:]*NCT\d{8}',
        r'ClinicalTrials\.gov[:\s]*NCT\d{8}',
        r'clinicaltrials\.gov[/\s]*NCT\d{8}',
        
        # Trial registration patterns
        r'[Tt]rial\s+[Rr]egistration[:\s]*NCT\d{8}',
        r'[Rr]egistered[:\s]*NCT\d{8}',
        r'[Rr]egistration[:\s]*NCT\d{8}',
        
        # URL patterns
        r'https?://(?:www\.)?clinicaltrials\.gov/[^/]*NCT\d{8}',
        
        # Parenthetical references
        r'\(NCT\d{8}\)',
        
        # Case insensitive variations
        r'\bnct\d{8}\b',  # lowercase
        r'\bNct\d{8}\b',  # mixed case
    ]
    
    @classmethod
    def extract_nct_numbers(cls, text: str) -> Set[str]:
        """
        Extract NCT numbers from text.
        
        Args:
            text: Text to search for NCT numbers
            
        Returns:
            Set of unique NCT numbers found (normalized to uppercase)
        """
        if not text:
            return set()
        
        nct_numbers = set()
        
        for pattern in cls.NCT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract just the NCT number part
                nct_match = re.search(r'NCT\d{8}', match, re.IGNORECASE)
                if nct_match:
                    nct_numbers.add(nct_match.group().upper())
        
        return nct_numbers
    
    @classmethod
    def extract_with_context(cls, text: str, context_length: int = 100) -> List[Tuple[str, str]]:
        """
        Extract NCT numbers with surrounding context.
        
        Args:
            text: Text to search
            context_length: Characters of context to include around each NCT number
            
        Returns:
            List of tuples (nct_number, context)
        """
        if not text:
            return []
        
        results = []
        
        for pattern in cls.NCT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Extract NCT number
                nct_match = re.search(r'NCT\d{8}', match.group(), re.IGNORECASE)
                if nct_match:
                    nct_number = nct_match.group().upper()
                    
                    # Get context around the match
                    start = max(0, match.start() - context_length)
                    end = min(len(text), match.end() + context_length)
                    context = text[start:end].strip()
                    
                    results.append((nct_number, context))
        
        return results


class ClinicalTrialFetcher:
    """Fetches clinical trial data from ClinicalTrials.gov API."""
    
    def __init__(self):
        self.api_base_url = "https://clinicaltrials.gov/api/v2/studies"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OralEvidenceDB/1.0 (Oral Health Clinical Research)'
        })
    
    def fetch_trial_data(self, nct_id: str) -> Optional[Dict]:
        """
        Fetch trial data for a specific NCT ID.
        
        Args:
            nct_id: NCT identifier (e.g., 'NCT00000001')
            
        Returns:
            Dictionary with trial data or None if not found
        """
        if not nct_id or not nct_id.startswith('NCT'):
            logger.warning(f"Invalid NCT ID format: {nct_id}")
            return None
        
        try:
            url = f"{self.api_base_url}/{nct_id}"
            params = {
                'format': 'json',
                'fields': 'all'  # Get all available fields
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # The API returns studies in a list, get the first one
            studies = data.get('studies', [])
            if studies:
                return studies[0]
            else:
                logger.info(f"No study data found for {nct_id}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching trial data for {nct_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {nct_id}: {e}")
            return None


class ClinicalTrialService:
    """Main service for clinical trial operations."""
    
    def __init__(self):
        self.extractor = NCTExtractor()
        self.fetcher = ClinicalTrialFetcher()
    
    def extract_nct_from_paper(self, paper: Paper) -> List[Tuple[str, str]]:
        """
        Extract NCT numbers from a paper's title and abstract.
        
        Args:
            paper: Paper object to extract NCT numbers from
            
        Returns:
            List of tuples (nct_number, context)
        """
        nct_with_context = []
        
        # Search in title
        if paper.title:
            title_ncts = self.extractor.extract_with_context(paper.title, 50)
            nct_with_context.extend(title_ncts)
        
        # Search in abstract
        if paper.abstract:
            abstract_ncts = self.extractor.extract_with_context(paper.abstract, 100)
            nct_with_context.extend(abstract_ncts)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ncts = []
        for nct, context in nct_with_context:
            if nct not in seen:
                unique_ncts.append((nct, context))
                seen.add(nct)
        
        return unique_ncts
    
    def parse_trial_data(self, trial_json: Dict) -> Dict:
        """
        Parse trial JSON data into structured format for database storage.
        
        Args:
            trial_json: Raw JSON data from ClinicalTrials.gov API
            
        Returns:
            Dictionary with parsed trial data
        """
        try:
            protocol = trial_json.get('protocolSection', {})
            
            # Identification
            identification = protocol.get('identificationModule', {})
            nct_id = identification.get('nctId', '')
            
            # Basic info
            brief_title = identification.get('briefTitle', '')
            official_title = identification.get('officialTitle', '')
            acronym = identification.get('acronym', '')
            org_study_id = identification.get('orgStudyId', '')
            
            # Design
            design = protocol.get('designModule', {})
            study_type = design.get('studyType', '')
            phases = design.get('phases', [])
            
            # Status
            status = protocol.get('statusModule', {})
            overall_status = status.get('overallStatus', '')
            why_stopped = status.get('whyStopped', '')
            
            # Dates
            start_date = None
            start_date_type = ''
            if status.get('startDateStruct'):
                start_date = status['startDateStruct'].get('date')
                start_date_type = status['startDateStruct'].get('type', '')
            
            completion_date = None
            completion_date_type = ''
            if status.get('completionDateStruct'):
                completion_date = status['completionDateStruct'].get('date')
                completion_date_type = status['completionDateStruct'].get('type', '')
            
            # Conditions and interventions
            conditions_module = protocol.get('conditionsModule', {})
            conditions = conditions_module.get('conditions', [])
            
            interventions_module = protocol.get('armsInterventionsModule', {})
            interventions = interventions_module.get('interventions', [])
            
            # Eligibility
            eligibility_module = protocol.get('eligibilityModule', {})
            eligibility_criteria = eligibility_module.get('eligibilityCriteria', '')
            minimum_age = eligibility_module.get('minimumAge', '')
            maximum_age = eligibility_module.get('maximumAge', '')
            sex = eligibility_module.get('sex', '')
            healthy_volunteers = eligibility_module.get('healthyVolunteers')
            
            # Outcomes
            outcomes_module = protocol.get('outcomesModule', {})
            primary_outcomes = outcomes_module.get('primaryOutcomes', [])
            secondary_outcomes = outcomes_module.get('secondaryOutcomes', [])
            
            # Enrollment
            enrollment_count = None
            enrollment_type = ''
            if design.get('enrollmentInfo'):
                enrollment_count = design['enrollmentInfo'].get('count')
                enrollment_type = design['enrollmentInfo'].get('type', '')
            
            # Sponsor
            sponsor_module = protocol.get('sponsorCollaboratorsModule', {})
            lead_sponsor = sponsor_module.get('leadSponsor', {})
            
            # Locations
            contacts_locations = protocol.get('contactsLocationsModule', {})
            locations = contacts_locations.get('locations', [])
            
            return {
                'nct_id': nct_id,
                'org_study_id': org_study_id,
                'brief_title': brief_title,
                'official_title': official_title,
                'acronym': acronym,
                'study_type': study_type,
                'phases': phases,
                'overall_status': overall_status,
                'why_stopped': why_stopped,
                'start_date': self.parse_date(start_date),
                'start_date_type': start_date_type,
                'completion_date': self.parse_date(completion_date),
                'completion_date_type': completion_date_type,
                'enrollment_count': enrollment_count,
                'enrollment_type': enrollment_type,
                'minimum_age': minimum_age,
                'maximum_age': maximum_age,
                'sex': sex,
                'healthy_volunteers': healthy_volunteers,
                'conditions': conditions,
                'interventions': interventions,
                'primary_outcomes': primary_outcomes,
                'secondary_outcomes': secondary_outcomes,
                'eligibility_criteria': eligibility_criteria,
                'locations': locations,
                'lead_sponsor': lead_sponsor,
                'raw_data': trial_json
            }
            
        except Exception as e:
            logger.error(f"Error parsing trial data: {e}")
            return {'raw_data': trial_json}
    
    def parse_date(self, date_string: str) -> Optional[str]:
        """Parse date string into YYYY-MM-DD format."""
        if not date_string:
            return None
        
        try:
            # Try to parse common date formats
            for fmt in ['%Y-%m-%d', '%Y-%m', '%Y']:
                try:
                    date_obj = datetime.strptime(date_string, fmt)
                    return date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # If no format matches, return as-is if it looks like a date
            if len(date_string) >= 4 and date_string[:4].isdigit():
                return date_string
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing date '{date_string}': {e}")
            return None
    
    def get_or_create_clinical_trial(self, nct_id: str) -> Optional[ClinicalTrial]:
        """
        Get existing clinical trial or fetch from API and create new one.
        
        Args:
            nct_id: NCT identifier
            
        Returns:
            ClinicalTrial object or None if not found/error
        """
        # Check if trial already exists
        try:
            return ClinicalTrial.objects.get(nct_id=nct_id)
        except ClinicalTrial.DoesNotExist:
            pass
        
        # Fetch from API
        trial_data = self.fetcher.fetch_trial_data(nct_id)
        if not trial_data:
            logger.info(f"Could not fetch trial data for {nct_id}")
            return None
        
        # Parse and save
        try:
            parsed_data = self.parse_trial_data(trial_data)
            clinical_trial = ClinicalTrial.objects.create(**parsed_data)
            logger.info(f"Created clinical trial: {nct_id}")
            return clinical_trial
            
        except Exception as e:
            logger.error(f"Error creating clinical trial {nct_id}: {e}")
            return None
    
    def link_paper_to_trials(self, paper: Paper, extraction_method: str = 'title_abstract') -> int:
        """
        Link a paper to all clinical trials mentioned in its text.
        
        Args:
            paper: Paper object to process
            extraction_method: Method used to find NCT numbers
            
        Returns:
            Number of new links created
        """
        nct_with_context = self.extract_nct_from_paper(paper)
        if not nct_with_context:
            return 0
        
        links_created = 0
        
        for nct_id, context in nct_with_context:
            try:
                # Get or create clinical trial
                clinical_trial = self.get_or_create_clinical_trial(nct_id)
                if not clinical_trial:
                    logger.warning(f"Could not get clinical trial for {nct_id}")
                    continue
                
                # Create link if it doesn't exist
                link, created = PaperClinicalTrial.objects.get_or_create(
                    paper=paper,
                    clinical_trial=clinical_trial,
                    defaults={
                        'extraction_method': extraction_method,
                        'context_snippet': context[:500],  # Truncate context
                        'confidence': 'medium'  # Default confidence
                    }
                )
                
                if created:
                    links_created += 1
                    logger.info(f"Linked paper {paper.pmid} to trial {nct_id}")
                
            except Exception as e:
                logger.error(f"Error linking paper {paper.pmid} to trial {nct_id}: {e}")
                continue
        
        return links_created
    
    def run_extraction_for_papers(self, papers_queryset=None, year_filter=None) -> NCTExtractionRun:
        """
        Run NCT extraction for multiple papers.
        
        Args:
            papers_queryset: QuerySet of papers to process (defaults to all)
            year_filter: Filter papers by publication year
            
        Returns:
            NCTExtractionRun object with results
        """
        # Create extraction run record
        extraction_run = NCTExtractionRun.objects.create(
            status='in_progress',
            year_filter=year_filter
        )
        
        try:
            # Get papers to process
            if papers_queryset is None:
                papers_queryset = Paper.objects.all()
            
            if year_filter:
                papers_queryset = papers_queryset.filter(publication_year=year_filter)
            
            # Process papers
            total_papers = papers_queryset.count()
            papers_with_nct = 0
            total_nct_found = 0
            new_links_created = 0
            
            start_time = django_timezone.now()
            
            for paper in papers_queryset:
                try:
                    nct_numbers = self.extractor.extract_nct_numbers(
                        f"{paper.title or ''} {paper.abstract or ''}"
                    )
                    
                    if nct_numbers:
                        papers_with_nct += 1
                        total_nct_found += len(nct_numbers)
                        
                        links = self.link_paper_to_trials(paper)
                        new_links_created += links
                
                except Exception as e:
                    logger.error(f"Error processing paper {paper.pmid}: {e}")
                    continue
            
            # Update extraction run
            end_time = django_timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            extraction_run.status = 'completed'
            extraction_run.total_papers = total_papers
            extraction_run.papers_with_nct = papers_with_nct
            extraction_run.total_nct_found = total_nct_found
            extraction_run.new_links_created = new_links_created
            extraction_run.completed_at = end_time
            extraction_run.duration_seconds = int(duration)
            extraction_run.save()
            
            logger.info(f"NCT extraction completed: {new_links_created} new links created")
            
        except Exception as e:
            extraction_run.status = 'failed'
            extraction_run.error_message = str(e)
            extraction_run.save()
            logger.error(f"NCT extraction failed: {e}")
        
        return extraction_run
