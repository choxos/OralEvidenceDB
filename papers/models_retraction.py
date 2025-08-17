"""
Models for tracking retracted oral health research papers.

This module handles retraction data from Retraction Watch database
and tracks papers that have been retracted due to various reasons.
"""

from django.db import models
from django.urls import reverse
from django.utils import timezone


class RetractedPaper(models.Model):
    """
    Model for retracted papers from Retraction Watch database.
    Tracks oral health research papers that have been retracted.
    """
    
    # Retraction Watch Database fields
    record_id = models.IntegerField("Retraction Watch Record ID", unique=True, null=True, blank=True)
    
    # Original paper information
    original_title = models.TextField("Original Paper Title", blank=True)
    original_pubmed_id = models.BigIntegerField("Original PubMed ID", null=True, blank=True, db_index=True)
    original_doi = models.CharField("Original DOI", max_length=500, blank=True)
    original_paper_date = models.DateField("Original Publication Date", null=True, blank=True)
    
    # Retraction information
    retraction_title = models.TextField("Retraction Notice Title", blank=True)
    retraction_doi = models.CharField("Retraction DOI", max_length=500, blank=True)
    retraction_pubmed_id = models.BigIntegerField("Retraction PubMed ID", null=True, blank=True)
    retraction_date = models.DateField("Retraction Date", null=True, blank=True, db_index=True)
    
    # Paper metadata
    journal = models.CharField("Journal Name", max_length=1000, blank=True, db_index=True)
    authors = models.TextField("Authors", blank=True)
    country = models.CharField("Country", max_length=200, blank=True)
    subject = models.CharField("Subject Area", max_length=500, blank=True)
    
    # Retraction details
    retraction_nature = models.CharField("Nature of Retraction", max_length=500, blank=True, db_index=True)
    reason = models.TextField("Retraction Reasons", blank=True)
    notes = models.TextField("Additional Notes", blank=True)
    
    # URLs and links
    article_type = models.CharField("Article Type", max_length=200, blank=True)
    original_paper_url = models.URLField("Original Paper URL", max_length=2000, blank=True)
    retraction_url = models.URLField("Retraction Notice URL", max_length=2000, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-retraction_date', '-original_paper_date']
        indexes = [
            models.Index(fields=['original_pubmed_id']),
            models.Index(fields=['retraction_date']),
            models.Index(fields=['journal']),
            models.Index(fields=['retraction_nature']),
            models.Index(fields=['country']),
            models.Index(fields=['subject']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['original_pubmed_id'],
                condition=models.Q(original_pubmed_id__isnull=False),
                name='unique_retracted_paper_pmid'
            )
        ]
    
    def __str__(self):
        title = self.original_title[:100] + "..." if len(self.original_title) > 100 else self.original_title
        return f"Retracted: {title}"
    
    def get_absolute_url(self):
        """Get URL to view the retraction details."""
        if self.original_pubmed_id:
            return reverse('papers:detail', kwargs={'pmid': self.original_pubmed_id})
        return '#'
    
    @property
    def short_title(self):
        """Return a shortened version of the original title."""
        if len(self.original_title) > 80:
            return self.original_title[:80] + "..."
        return self.original_title
    
    @property
    def retraction_delay_days(self):
        """Calculate the number of days between publication and retraction."""
        if self.original_paper_date and self.retraction_date:
            return (self.retraction_date - self.original_paper_date).days
        return None
    
    @property
    def retraction_delay_years(self):
        """Calculate the number of years between publication and retraction."""
        delay_days = self.retraction_delay_days
        if delay_days is not None:
            return round(delay_days / 365.25, 1)
        return None
    
    @property
    def reason_list(self):
        """Parse the reason field into a list of individual reasons."""
        if not self.reason:
            return []
        
        # Split by common delimiters and clean up
        reasons = []
        for delimiter in [';', ',', '|']:
            if delimiter in self.reason:
                reasons = [r.strip() for r in self.reason.split(delimiter) if r.strip()]
                break
        
        # If no delimiters found, return the whole reason as a single item
        if not reasons and self.reason.strip():
            reasons = [self.reason.strip()]
        
        return reasons
    
    @property
    def primary_reason(self):
        """Get the primary (first) reason for retraction."""
        reasons = self.reason_list
        return reasons[0] if reasons else "Reason not specified"
    
    @property
    def is_recent_retraction(self):
        """Check if this is a recent retraction (within last year)."""
        if not self.retraction_date:
            return False
        
        one_year_ago = timezone.now().date() - timezone.timedelta(days=365)
        return self.retraction_date >= one_year_ago
    
    @property
    def is_oral_health_related(self):
        """
        Check if this retracted paper is related to oral health research.
        This is a heuristic based on keywords in title, journal, and subject.
        """
        oral_health_keywords = [
            'dental', 'dentistry', 'tooth', 'teeth', 'oral', 'gum', 'gingival',
            'periodontal', 'periodontitis', 'gingivitis', 'caries', 'cavity',
            'orthodontic', 'endodontic', 'prosthodontic', 'oral surgery',
            'oral pathology', 'oral medicine', 'maxillofacial', 'stomatology',
            'plaque', 'tartar', 'fluoride', 'oral hygiene', 'mouth'
        ]
        
        # Combine title, journal, and subject for keyword search
        text_to_search = ' '.join([
            self.original_title.lower(),
            self.journal.lower(),
            self.subject.lower()
        ])
        
        return any(keyword in text_to_search for keyword in oral_health_keywords)
    
    def get_pubmed_url(self):
        """Get PubMed URL for the original paper."""
        if self.original_pubmed_id:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.original_pubmed_id}/"
        return None
    
    def get_retraction_pubmed_url(self):
        """Get PubMed URL for the retraction notice."""
        if self.retraction_pubmed_id:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.retraction_pubmed_id}/"
        return None
    
    def get_doi_url(self):
        """Get DOI URL for the original paper."""
        if self.original_doi:
            return f"https://doi.org/{self.original_doi}"
        return None
    
    def get_retraction_doi_url(self):
        """Get DOI URL for the retraction notice."""
        if self.retraction_doi:
            return f"https://doi.org/{self.retraction_doi}"
        return None


class RetractionImportLog(models.Model):
    """Log retraction data import operations."""
    
    IMPORT_STATUS_CHOICES = [
        ('started', 'Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=IMPORT_STATUS_CHOICES, default='started')
    
    total_records_processed = models.IntegerField(default=0)
    records_imported = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_skipped = models.IntegerField(default=0)
    
    source_file = models.CharField(max_length=500, blank=True, help_text="Path to source CSV file")
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Retraction Import {self.started_at.strftime('%Y-%m-%d %H:%M')} - {self.status}"
    
    @property
    def duration(self):
        """Calculate import duration if completed."""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None
