"""
PMID Extractor for Clinical Trials

This service extracts and matches PMIDs from clinical trial references,
enabling bidirectional linking between papers and trials.
"""

import re
import logging
from typing import Set, List, Dict, Optional
from django.db.models import Q

from ..models import Paper
from ..models_clinical_trial import ClinicalTrial, PaperClinicalTrial

logger = logging.getLogger(__name__)


class PMIDExtractor:
    """Extracts PMID numbers from clinical trial references."""
    
    PMID_PATTERNS = [
        # Standard PMID format
        r'\bPMID:\s*(\d+)\b',
        r'\bPubMed ID:\s*(\d+)\b',
        
        # PubMed URL patterns
        r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)',
        r'ncbi\.nlm\.nih\.gov/pubmed/(\d+)',
        r'pubmed\.gov/(\d+)',
        
        # DOI with PMID
        r'doi\.org/[^\s]*pmid[/:](\d+)',
        
        # Reference patterns
        r'PMID\s+(\d+)',
        r'PubMed\s+(\d+)',
        r'\[PubMed:\s*(\d+)\]',
        
        # Numeric patterns that might be PMIDs (8+ digits)
        r'\b(\d{8,})\b',  # This will have more false positives
    ]
    
    @classmethod
    def extract_pmids(cls, text: str, strict: bool = True) -> Set[str]:
        """
        Extract PMID numbers from text.
        
        Args:
            text: Text to search for PMIDs
            strict: If True, only use high-confidence patterns
            
        Returns:
            Set of unique PMID numbers found
        """
        if not text:
            return set()
        
        pmids = set()
        patterns = cls.PMID_PATTERNS[:-1] if strict else cls.PMID_PATTERNS
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                pmid = str(match).strip()
                # Validate PMID (should be 1-8 digits typically)
                if pmid.isdigit() and 1 <= len(pmid) <= 9:
                    pmids.add(pmid)
        
        return pmids
    
    @classmethod
    def extract_from_trial_references(cls, trial_data: Dict) -> Set[str]:
        """
        Extract PMIDs from clinical trial reference sections.
        
        Args:
            trial_data: Raw trial JSON data
            
        Returns:
            Set of PMID numbers found in references
        """
        pmids = set()
        
        try:
            # Check various reference sections in the trial data
            references_sections = [
                ['protocolSection', 'referencesModule', 'references'],
                ['protocolSection', 'referencesModule', 'seeAlsoLinks'],
                ['derivedSection', 'miscInfoModule', 'versionHolder'],
            ]
            
            for section_path in references_sections:
                current = trial_data
                for key in section_path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        current = None
                        break
                
                if current:
                    # Extract from references list
                    if isinstance(current, list):
                        for ref in current:
                            if isinstance(ref, dict):
                                # Check citation field
                                citation = ref.get('citation', '')
                                pmids.update(cls.extract_pmids(citation))
                                
                                # Check URL field
                                url = ref.get('url', '')
                                pmids.update(cls.extract_pmids(url))
                    
                    # Extract from string fields
                    elif isinstance(current, str):
                        pmids.update(cls.extract_pmids(current))
            
            # Also check description fields for references
            description_paths = [
                ['protocolSection', 'descriptionModule', 'briefSummary'],
                ['protocolSection', 'descriptionModule', 'detailedDescription'],
            ]
            
            for desc_path in description_paths:
                current = trial_data
                for key in desc_path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        current = None
                        break
                
                if isinstance(current, str):
                    pmids.update(cls.extract_pmids(current, strict=True))
        
        except Exception as e:
            logger.debug(f"Error extracting PMIDs from trial references: {e}")
        
        return pmids


class TrialPaperMatcher:
    """Matches clinical trials with papers using various strategies."""
    
    def __init__(self):
        self.pmid_extractor = PMIDExtractor()
    
    def match_by_pmid_references(self, clinical_trial: ClinicalTrial) -> List[Paper]:
        """
        Find papers that match PMIDs mentioned in trial references.
        
        Args:
            clinical_trial: ClinicalTrial object
            
        Returns:
            List of matching Paper objects
        """
        if not clinical_trial.raw_data:
            return []
        
        # Extract PMIDs from trial references
        pmids = self.pmid_extractor.extract_from_trial_references(clinical_trial.raw_data)
        
        if not pmids:
            return []
        
        # Find papers with matching PMIDs
        matching_papers = Paper.objects.filter(pmid__in=pmids)
        
        logger.info(f"Found {matching_papers.count()} papers matching PMIDs from trial {clinical_trial.nct_id}")
        
        return list(matching_papers)
    
    def match_by_title_similarity(self, clinical_trial: ClinicalTrial, threshold: float = 0.8) -> List[Paper]:
        """
        Find papers with similar titles to the clinical trial.
        
        Args:
            clinical_trial: ClinicalTrial object
            threshold: Similarity threshold (not implemented yet - placeholder)
            
        Returns:
            List of potentially matching Paper objects
        """
        # This is a placeholder for title similarity matching
        # Would require implementing text similarity algorithms
        # For now, return empty list
        return []
    
    def match_by_conditions_and_dates(self, clinical_trial: ClinicalTrial) -> List[Paper]:
        """
        Find papers that might be related based on conditions and date ranges.
        
        Args:
            clinical_trial: ClinicalTrial object
            
        Returns:
            List of potentially related Paper objects
        """
        if not clinical_trial.conditions:
            return []
        
        # Build search terms from conditions
        search_terms = []
        for condition in clinical_trial.conditions:
            # Extract key terms from condition names
            terms = re.findall(r'\b\w{3,}\b', condition.lower())
            search_terms.extend(terms)
        
        if not search_terms:
            return []
        
        # Search for papers with these terms in title or abstract
        query = Q()
        for term in search_terms[:5]:  # Limit to avoid overly complex queries
            query |= Q(title__icontains=term) | Q(abstract__icontains=term)
        
        # Also filter by date range if available
        if clinical_trial.start_date:
            # Look for papers published around the trial start date
            start_year = clinical_trial.start_date.year
            query &= Q(publication_year__gte=start_year - 1, 
                      publication_year__lte=start_year + 3)
        
        matching_papers = Paper.objects.filter(query)[:50]  # Limit results
        
        logger.info(f"Found {matching_papers.count()} papers with condition-based matching for trial {clinical_trial.nct_id}")
        
        return list(matching_papers)
    
    def create_links_from_references(self, clinical_trial: ClinicalTrial) -> int:
        """
        Create paper-trial links based on PMID references in the trial.
        
        Args:
            clinical_trial: ClinicalTrial object
            
        Returns:
            Number of new links created
        """
        matching_papers = self.match_by_pmid_references(clinical_trial)
        links_created = 0
        
        for paper in matching_papers:
            try:
                link, created = PaperClinicalTrial.objects.get_or_create(
                    paper=paper,
                    clinical_trial=clinical_trial,
                    defaults={
                        'extraction_method': 'trial_references',
                        'confidence': 'high',
                        'context_snippet': f'Paper PMID {paper.pmid} referenced in trial {clinical_trial.nct_id}',
                        'notes': 'Automatically linked via PMID reference in trial data'
                    }
                )
                
                if created:
                    links_created += 1
                    logger.info(f"Linked paper {paper.pmid} to trial {clinical_trial.nct_id} via reference")
            
            except Exception as e:
                logger.error(f"Error creating link between paper {paper.pmid} and trial {clinical_trial.nct_id}: {e}")
                continue
        
        return links_created
    
    def run_reference_matching(self, trials_queryset=None) -> Dict[str, int]:
        """
        Run reference-based matching for multiple trials.
        
        Args:
            trials_queryset: QuerySet of trials to process (defaults to all)
            
        Returns:
            Dictionary with matching statistics
        """
        if trials_queryset is None:
            trials_queryset = ClinicalTrial.objects.all()
        
        stats = {
            'trials_processed': 0,
            'trials_with_references': 0,
            'total_links_created': 0,
            'errors': 0
        }
        
        for trial in trials_queryset:
            try:
                stats['trials_processed'] += 1
                
                # Check if trial has raw data with potential references
                if not trial.raw_data:
                    continue
                
                # Extract PMIDs to see if there are any references
                pmids = self.pmid_extractor.extract_from_trial_references(trial.raw_data)
                if pmids:
                    stats['trials_with_references'] += 1
                    links_created = self.create_links_from_references(trial)
                    stats['total_links_created'] += links_created
                
            except Exception as e:
                logger.error(f"Error processing trial {trial.nct_id} for reference matching: {e}")
                stats['errors'] += 1
                continue
        
        logger.info(f"Reference matching completed: {stats['total_links_created']} new links from {stats['trials_with_references']} trials")
        
        return stats
