"""
Clinical Trial models for linking research papers with ClinicalTrials.gov data.

This module contains Django models for storing oral health clinical trial information
and linking it to research papers.
"""

from django.db import models
from django.urls import reverse
import json
import re
import uuid


class ClinicalTrial(models.Model):
    """Represents an oral health clinical trial from ClinicalTrials.gov."""
    
    # Identifiers
    nct_id = models.CharField("NCT ID", max_length=20, unique=True, primary_key=True)
    org_study_id = models.CharField("Organization Study ID", max_length=500, blank=True)
    
    # Basic trial information
    brief_title = models.TextField("Brief Title", blank=True)
    official_title = models.TextField("Official Title", blank=True)
    acronym = models.CharField("Acronym", max_length=100, blank=True)
    
    # Study design
    study_type = models.CharField("Study Type", max_length=50, blank=True)  # INTERVENTIONAL, OBSERVATIONAL
    phases = models.JSONField("Phases", default=list, blank=True)  # List of phases
    allocation = models.CharField("Allocation", max_length=50, blank=True)  # RANDOMIZED, NON_RANDOMIZED
    intervention_model = models.CharField("Intervention Model", max_length=100, blank=True)  # PARALLEL, CROSSOVER, etc.
    primary_purpose = models.CharField("Primary Purpose", max_length=100, blank=True)  # TREATMENT, PREVENTION, etc.
    
    # Masking/Blinding
    masking = models.CharField("Masking", max_length=50, blank=True)  # NONE, SINGLE, DOUBLE, TRIPLE, QUADRUPLE
    who_masked = models.JSONField("Who Masked", default=list, blank=True)  # List of who is masked
    
    # Status and dates
    overall_status = models.CharField("Overall Status", max_length=50, blank=True)  # NOT_YET_RECRUITING, RECRUITING, etc.
    why_stopped = models.TextField("Why Stopped", blank=True)
    start_date = models.DateField("Start Date", null=True, blank=True)
    start_date_type = models.CharField("Start Date Type", max_length=20, blank=True)  # ACTUAL, ESTIMATED
    completion_date = models.DateField("Completion Date", null=True, blank=True)
    completion_date_type = models.CharField("Completion Date Type", max_length=20, blank=True)
    primary_completion_date = models.DateField("Primary Completion Date", null=True, blank=True)
    primary_completion_date_type = models.CharField("Primary Completion Date Type", max_length=20, blank=True)
    
    # Enrollment
    enrollment_count = models.IntegerField("Enrollment Count", null=True, blank=True)
    enrollment_type = models.CharField("Enrollment Type", max_length=20, blank=True)  # ACTUAL, ESTIMATED
    
    # Study population
    minimum_age = models.CharField("Minimum Age", max_length=20, blank=True)
    maximum_age = models.CharField("Maximum Age", max_length=20, blank=True)
    sex = models.CharField("Sex", max_length=10, blank=True)  # ALL, FEMALE, MALE
    healthy_volunteers = models.BooleanField("Accepts Healthy Volunteers", null=True, blank=True)
    
    # Conditions and interventions
    conditions = models.JSONField("Conditions", default=list, blank=True)  # List of condition names
    interventions = models.JSONField("Interventions", default=list, blank=True)  # List of intervention details
    
    # Outcomes
    primary_outcomes = models.JSONField("Primary Outcomes", default=list, blank=True)
    secondary_outcomes = models.JSONField("Secondary Outcomes", default=list, blank=True)
    other_outcomes = models.JSONField("Other Outcomes", default=list, blank=True)
    
    # Eligibility
    eligibility_criteria = models.TextField("Eligibility Criteria", blank=True)
    
    # Locations
    locations = models.JSONField("Locations", default=list, blank=True)  # List of study locations
    
    # Sponsor and investigators
    lead_sponsor = models.JSONField("Lead Sponsor", default=dict, blank=True)
    responsible_party = models.JSONField("Responsible Party", default=dict, blank=True)
    investigators = models.JSONField("Investigators", default=list, blank=True)
    
    # Oral health specific metadata
    found_by_keywords = models.JSONField("Found By Keywords", default=list, blank=True, 
                                        help_text="Keywords that found this trial: Oral Health, Dental Health, etc.")
    
    # Raw data storage
    raw_data = models.JSONField("Raw JSON Data", default=dict, blank=True, 
                               help_text="Complete JSON data from ClinicalTrials.gov API")
    
    # Metadata
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)
    
    class Meta:
        verbose_name = "Clinical Trial"
        verbose_name_plural = "Clinical Trials"
        ordering = ['-start_date', 'nct_id']
        indexes = [
            models.Index(fields=['study_type']),
            models.Index(fields=['overall_status']),
            models.Index(fields=['start_date']),
            models.Index(fields=['primary_purpose']),
        ]
    
    def __str__(self):
        return f"{self.nct_id}: {self.brief_title[:100]}"
    
    def get_absolute_url(self):
        return f"https://clinicaltrials.gov/study/{self.nct_id}"
    
    @property
    def clinicaltrials_gov_url(self):
        return f"https://clinicaltrials.gov/study/{self.nct_id}"
    
    @property
    def is_interventional(self):
        return self.study_type and self.study_type.upper() == 'INTERVENTIONAL'
    
    @property
    def is_observational(self):
        return self.study_type and self.study_type.upper() == 'OBSERVATIONAL'
    
    @property
    def is_completed(self):
        return self.overall_status and self.overall_status.upper() in ['COMPLETED', 'TERMINATED']
    
    @property
    def is_recruiting(self):
        return self.overall_status and 'RECRUITING' in self.overall_status.upper()
    
    @property
    def display_status(self):
        """Human-readable status"""
        if not self.overall_status:
            return "Unknown"
        
        status_map = {
            'NOT_YET_RECRUITING': 'Not Yet Recruiting',
            'RECRUITING': 'Recruiting',
            'ENROLLING_BY_INVITATION': 'Enrolling by Invitation',
            'ACTIVE_NOT_RECRUITING': 'Active, Not Recruiting',
            'COMPLETED': 'Completed',
            'SUSPENDED': 'Suspended',
            'TERMINATED': 'Terminated',
            'WITHDRAWN': 'Withdrawn',
            'UNKNOWN': 'Unknown Status'
        }
        
        return status_map.get(self.overall_status.upper(), self.overall_status.title().replace('_', ' '))
    
    def get_conditions_display(self):
        """Get formatted conditions string"""
        if not self.conditions:
            return "Not specified"
        return ", ".join(self.conditions[:3]) + ("..." if len(self.conditions) > 3 else "")
    
    def get_primary_outcomes_count(self):
        """Get count of primary outcomes"""
        return len(self.primary_outcomes) if self.primary_outcomes else 0


class PaperClinicalTrial(models.Model):
    """Links research papers with clinical trials."""
    
    EXTRACTION_METHODS = [
        ('title_abstract', 'Title/Abstract NCT Search'),
        ('trial_references', 'Trial References/Results'),
        ('manual', 'Manual Curation'),
        ('author_disclosure', 'Author Disclosure'),
        ('supplementary', 'Supplementary Materials'),
    ]
    
    CONFIDENCE_LEVELS = [
        ('high', 'High Confidence'),
        ('medium', 'Medium Confidence'), 
        ('low', 'Low Confidence'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey('Paper', on_delete=models.CASCADE, related_name='clinical_trial_links')
    clinical_trial = models.ForeignKey(ClinicalTrial, on_delete=models.CASCADE, related_name='paper_links')
    
    # Link metadata
    extraction_method = models.CharField("Extraction Method", max_length=20, 
                                       choices=EXTRACTION_METHODS, default='title_abstract')
    confidence = models.CharField("Confidence Level", max_length=10, 
                                choices=CONFIDENCE_LEVELS, default='medium')
    
    # Context information
    context_snippet = models.TextField("Context Snippet", blank=True,
                                     help_text="Text snippet where NCT number was found")
    notes = models.TextField("Notes", blank=True)
    
    # Verification
    verified = models.BooleanField("Verified", default=False)
    verified_by = models.CharField("Verified By", max_length=100, blank=True)
    verified_at = models.DateTimeField("Verified At", null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)
    
    class Meta:
        verbose_name = "Paper-Clinical Trial Link"
        verbose_name_plural = "Paper-Clinical Trial Links"
        unique_together = ['paper', 'clinical_trial']
        indexes = [
            models.Index(fields=['extraction_method']),
            models.Index(fields=['confidence']),
            models.Index(fields=['verified']),
        ]
    
    def __str__(self):
        return f"{self.paper.title[:50]}... → {self.clinical_trial.nct_id}"
    
    def get_extraction_method_display_with_icon(self):
        """Get extraction method display with icon"""
        icons = {
            'title_abstract': '🔍',
            'trial_references': '📋',
            'manual': '👤',
            'author_disclosure': '📝',
            'supplementary': '📎',
        }
        method_display = self.get_extraction_method_display()
        icon = icons.get(self.extraction_method, '📄')
        return f"{icon} {method_display}"


class NCTExtractionRun(models.Model):
    """Tracks NCT number extraction runs for papers."""
    
    EXTRACTION_STATUSES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Run metadata
    run_date = models.DateTimeField("Run Date", auto_now_add=True)
    run_by = models.CharField("Run By", max_length=100, default="system")
    status = models.CharField("Status", max_length=20, choices=EXTRACTION_STATUSES, default='pending')
    
    # Scope
    total_papers = models.IntegerField("Total Papers Processed", default=0)
    papers_with_nct = models.IntegerField("Papers with NCT Numbers", default=0)
    total_nct_found = models.IntegerField("Total NCT Numbers Found", default=0)
    new_links_created = models.IntegerField("New Links Created", default=0)
    
    # Filters used
    year_filter = models.IntegerField("Year Filter", null=True, blank=True)
    journal_filter = models.CharField("Journal Filter", max_length=200, blank=True)
    
    # Results
    error_message = models.TextField("Error Message", blank=True)
    completed_at = models.DateTimeField("Completed At", null=True, blank=True)
    duration_seconds = models.IntegerField("Duration (seconds)", null=True, blank=True)
    
    class Meta:
        verbose_name = "NCT Extraction Run"
        verbose_name_plural = "NCT Extraction Runs"
        ordering = ['-run_date']
    
    def __str__(self):
        return f"NCT Extraction Run {self.run_date.strftime('%Y-%m-%d %H:%M')} - {self.status}"
    
    @property
    def success_rate(self):
        """Calculate extraction success rate"""
        if self.total_papers == 0:
            return 0
        return (self.papers_with_nct / self.total_papers) * 100