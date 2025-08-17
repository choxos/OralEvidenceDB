"""
Models for clinical trials related to oral health research.

This module handles clinical trial data from ClinicalTrials.gov
and links trials to published papers in oral health literature.
"""

from django.db import models
from django.utils import timezone
import uuid


class ClinicalTrial(models.Model):
    """
    Clinical trial data from ClinicalTrials.gov focused on oral health studies.
    """
    
    # ClinicalTrials.gov identifiers
    nct_id = models.CharField("NCT Number", max_length=50, unique=True, db_index=True)
    org_study_id = models.CharField("Organization Study ID", max_length=500, blank=True)
    
    # Basic trial information
    brief_title = models.TextField("Brief Title")
    official_title = models.TextField("Official Title", blank=True)
    brief_summary = models.TextField("Brief Summary", blank=True)
    detailed_description = models.TextField("Detailed Description", blank=True)
    
    # Study design
    study_type = models.CharField(
        "Study Type",
        max_length=100,
        choices=[
            ('interventional', 'Interventional'),
            ('observational', 'Observational'),
            ('expanded_access', 'Expanded Access'),
            ('other', 'Other')
        ],
        blank=True
    )
    
    study_phase = models.CharField(
        "Study Phase",
        max_length=50,
        choices=[
            ('early_phase_1', 'Early Phase 1'),
            ('phase_1', 'Phase 1'),
            ('phase_1_phase_2', 'Phase 1/Phase 2'),
            ('phase_2', 'Phase 2'),
            ('phase_2_phase_3', 'Phase 2/Phase 3'),
            ('phase_3', 'Phase 3'),
            ('phase_4', 'Phase 4'),
            ('not_applicable', 'Not Applicable')
        ],
        blank=True
    )
    
    # Intervention and condition
    primary_purpose = models.CharField("Primary Purpose", max_length=200, blank=True)
    intervention_type = models.CharField("Intervention Type", max_length=200, blank=True)
    intervention_name = models.TextField("Intervention Name", blank=True)
    condition = models.TextField("Condition/Disease", blank=True)
    
    # Oral health specific fields
    oral_health_category = models.CharField(
        "Oral Health Category",
        max_length=100,
        choices=[
            ('dental_caries', 'Dental Caries'),
            ('periodontal_disease', 'Periodontal Disease'),
            ('oral_cancer', 'Oral Cancer'),
            ('orthodontics', 'Orthodontics'),
            ('endodontics', 'Endodontics'),
            ('prosthodontics', 'Prosthodontics'),
            ('oral_surgery', 'Oral Surgery'),
            ('oral_medicine', 'Oral Medicine'),
            ('oral_pathology', 'Oral Pathology'),
            ('preventive_dentistry', 'Preventive Dentistry'),
            ('pediatric_dentistry', 'Pediatric Dentistry'),
            ('geriatric_dentistry', 'Geriatric Dentistry'),
            ('special_needs_dentistry', 'Special Needs Dentistry'),
            ('oral_hygiene', 'Oral Hygiene'),
            ('other', 'Other')
        ],
        blank=True,
        db_index=True
    )
    
    # Study status and timeline
    overall_status = models.CharField(
        "Overall Status",
        max_length=50,
        choices=[
            ('not_yet_recruiting', 'Not yet recruiting'),
            ('recruiting', 'Recruiting'),
            ('enrolling_by_invitation', 'Enrolling by invitation'),
            ('active_not_recruiting', 'Active, not recruiting'),
            ('suspended', 'Suspended'),
            ('terminated', 'Terminated'),
            ('completed', 'Completed'),
            ('withdrawn', 'Withdrawn'),
            ('unknown', 'Unknown status')
        ],
        blank=True,
        db_index=True
    )
    
    start_date = models.DateField("Study Start Date", null=True, blank=True)
    completion_date = models.DateField("Study Completion Date", null=True, blank=True)
    primary_completion_date = models.DateField("Primary Completion Date", null=True, blank=True)
    
    # Enrollment
    enrollment = models.IntegerField("Target Enrollment", null=True, blank=True)
    enrollment_type = models.CharField("Enrollment Type", max_length=50, blank=True)
    
    # Eligibility
    minimum_age = models.CharField("Minimum Age", max_length=50, blank=True)
    maximum_age = models.CharField("Maximum Age", max_length=50, blank=True)
    gender = models.CharField("Gender", max_length=50, blank=True)
    eligibility_criteria = models.TextField("Eligibility Criteria", blank=True)
    
    # Location and contacts
    locations = models.TextField("Study Locations", blank=True)
    sponsor = models.CharField("Lead Sponsor", max_length=500, blank=True)
    collaborators = models.TextField("Collaborators", blank=True)
    
    # Primary and secondary outcomes
    primary_outcomes = models.TextField("Primary Outcomes", blank=True)
    secondary_outcomes = models.TextField("Secondary Outcomes", blank=True)
    
    # URLs and references
    clinical_trials_url = models.URLField("ClinicalTrials.gov URL", max_length=500, blank=True)
    
    # Data management
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_verified = models.DateField("Last Verified", null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date', 'nct_id']
        indexes = [
            models.Index(fields=['nct_id']),
            models.Index(fields=['overall_status']),
            models.Index(fields=['oral_health_category']),
            models.Index(fields=['start_date']),
            models.Index(fields=['study_type']),
            models.Index(fields=['study_phase']),
        ]
    
    def __str__(self):
        return f"{self.nct_id}: {self.brief_title[:80]}..."
    
    @property
    def short_title(self):
        """Return a shortened version of the brief title."""
        if len(self.brief_title) > 100:
            return self.brief_title[:100] + "..."
        return self.brief_title
    
    @property
    def is_oral_health_trial(self):
        """Check if this is an oral health related trial based on keywords."""
        oral_health_keywords = [
            'dental', 'tooth', 'teeth', 'oral', 'gum', 'gingival',
            'periodontal', 'caries', 'cavity', 'orthodontic', 'endodontic',
            'prosthodontic', 'maxillofacial', 'stomatology', 'fluoride'
        ]
        
        text_to_search = ' '.join([
            self.brief_title.lower(),
            self.condition.lower(),
            self.intervention_name.lower(),
        ])
        
        return any(keyword in text_to_search for keyword in oral_health_keywords)
    
    @property
    def study_duration_days(self):
        """Calculate study duration in days."""
        if self.start_date and self.completion_date:
            return (self.completion_date - self.start_date).days
        return None
    
    @property
    def is_recruiting(self):
        """Check if the trial is currently recruiting participants."""
        return self.overall_status in ['recruiting', 'not_yet_recruiting', 'enrolling_by_invitation']
    
    @property
    def is_completed(self):
        """Check if the trial is completed."""
        return self.overall_status == 'completed'
    
    def get_clinicaltrials_url(self):
        """Generate ClinicalTrials.gov URL."""
        if self.nct_id:
            return f"https://clinicaltrials.gov/ct2/show/{self.nct_id}"
        return None


class PaperClinicalTrial(models.Model):
    """
    Link between published papers and clinical trials.
    Tracks which papers report results from which trials.
    """
    
    paper = models.ForeignKey(
        'papers.Paper',
        on_delete=models.CASCADE,
        related_name='clinical_trials'
    )
    clinical_trial = models.ForeignKey(
        ClinicalTrial,
        on_delete=models.CASCADE,
        related_name='papers'
    )
    
    # Relationship details
    relationship_type = models.CharField(
        "Relationship Type",
        max_length=50,
        choices=[
            ('results_paper', 'Results Paper'),
            ('protocol_paper', 'Protocol Paper'),
            ('secondary_analysis', 'Secondary Analysis'),
            ('sub_study', 'Sub-study'),
            ('meta_analysis', 'Includes in Meta-analysis'),
            ('review', 'Reviews/Mentions Trial'),
            ('other', 'Other')
        ],
        default='results_paper',
        db_index=True
    )
    
    # Extraction details
    extraction_method = models.CharField(
        "Extraction Method",
        max_length=50,
        choices=[
            ('automatic_nct', 'Automatic NCT ID Detection'),
            ('manual_review', 'Manual Review'),
            ('author_declaration', 'Author Declaration'),
            ('registry_search', 'Registry Search'),
            ('other', 'Other')
        ],
        default='automatic_nct'
    )
    
    confidence_score = models.FloatField(
        "Confidence Score",
        null=True,
        blank=True,
        help_text="Confidence in the paper-trial link (0.0-1.0)"
    )
    
    # Results reporting
    reports_primary_outcome = models.BooleanField("Reports Primary Outcome", default=False)
    reports_secondary_outcomes = models.BooleanField("Reports Secondary Outcomes", default=False)
    follow_up_duration = models.CharField("Follow-up Duration", max_length=200, blank=True)
    
    # Quality indicators
    is_preregistered = models.BooleanField("Was Pre-registered", default=False)
    registration_timing = models.CharField(
        "Registration Timing",
        max_length=50,
        choices=[
            ('prospective', 'Prospective'),
            ('retrospective', 'Retrospective'),
            ('unknown', 'Unknown')
        ],
        blank=True
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_by = models.CharField("Verified By", max_length=200, blank=True)
    notes = models.TextField("Additional Notes", blank=True)
    
    class Meta:
        unique_together = ['paper', 'clinical_trial']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['relationship_type']),
            models.Index(fields=['extraction_method']),
            models.Index(fields=['is_preregistered']),
            models.Index(fields=['reports_primary_outcome']),
        ]
    
    def __str__(self):
        return f"{self.paper.pmid} <-> {self.clinical_trial.nct_id}"
    
    @property
    def is_high_confidence_link(self):
        """Check if this is a high-confidence paper-trial link."""
        return self.confidence_score and self.confidence_score >= 0.8


class NCTExtractionRun(models.Model):
    """
    Tracks NCT ID extraction runs from papers.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Run metadata
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('started', 'Started'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='started'
    )
    
    # Processing parameters
    source_type = models.CharField(
        "Source Type",
        max_length=50,
        choices=[
            ('pubmed_abstracts', 'PubMed Abstracts'),
            ('full_text_pmc', 'Full Text PMC'),
            ('manual_input', 'Manual Input'),
        ],
        default='pubmed_abstracts'
    )
    
    # Results
    papers_processed = models.IntegerField(default=0)
    nct_ids_extracted = models.IntegerField(default=0)
    new_trials_added = models.IntegerField(default=0)
    existing_trials_updated = models.IntegerField(default=0)
    paper_trial_links_created = models.IntegerField(default=0)
    
    # Error tracking
    papers_failed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['started_at']),
            models.Index(fields=['status']),
            models.Index(fields=['source_type']),
        ]
    
    def __str__(self):
        return f"NCT Extraction {self.started_at.strftime('%Y-%m-%d %H:%M')} - {self.status}"
    
    @property
    def duration(self):
        """Calculate extraction duration if completed."""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def success_rate(self):
        """Calculate success rate."""
        if self.papers_processed == 0:
            return 0
        return round((1 - self.papers_failed / self.papers_processed) * 100, 1)
