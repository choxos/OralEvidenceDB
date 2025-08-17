"""
Models for citation analysis and tracking in oral health research.

This module handles citation data, impact metrics, and tracks
citations to retracted papers in oral health literature.
"""

from django.db import models
from django.utils import timezone
import uuid


class OpenAlexWork(models.Model):
    """
    Represents a work (publication) from the OpenAlex database.
    Used for tracking citation data and bibliometric analysis.
    """
    
    openalex_id = models.CharField("OpenAlex ID", max_length=500, unique=True, db_index=True)
    title = models.TextField("Work Title")
    doi = models.CharField("DOI", max_length=500, blank=True, db_index=True)
    pmid = models.BigIntegerField("PubMed ID", null=True, blank=True, db_index=True)
    
    # Publication metadata
    publication_year = models.IntegerField("Publication Year", null=True, blank=True, db_index=True)
    publication_date = models.DateField("Publication Date", null=True, blank=True)
    journal_name = models.CharField("Journal Name", max_length=1000, blank=True)
    
    # Citation metrics
    cited_by_count = models.IntegerField("Total Citations", default=0, db_index=True)
    is_retracted = models.BooleanField("Is Retracted", default=False, db_index=True)
    
    # Work type and classification
    work_type = models.CharField("Work Type", max_length=200, blank=True)
    is_oral_health_related = models.BooleanField("Oral Health Related", default=False, db_index=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_citation_check = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-cited_by_count', '-publication_year']
        indexes = [
            models.Index(fields=['openalex_id']),
            models.Index(fields=['pmid']),
            models.Index(fields=['doi']),
            models.Index(fields=['cited_by_count']),
            models.Index(fields=['is_retracted']),
            models.Index(fields=['publication_year']),
            models.Index(fields=['is_oral_health_related']),
        ]
    
    def __str__(self):
        return f"{self.title[:100]}... ({self.publication_year})"
    
    @property
    def short_title(self):
        """Return a shortened version of the title."""
        if len(self.title) > 80:
            return self.title[:80] + "..."
        return self.title
    
    def get_doi_url(self):
        """Get the DOI URL."""
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return None
    
    def get_pubmed_url(self):
        """Get the PubMed URL."""
        if self.pmid:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"
        return None
    
    def get_openalex_url(self):
        """Get the OpenAlex URL."""
        return f"https://openalex.org/{self.openalex_id}"


class CitingWork(models.Model):
    """
    Represents a work that cites another work.
    Used for tracking who cites retracted papers.
    """
    
    openalex_id = models.CharField("OpenAlex ID", max_length=500, unique=True, db_index=True)
    title = models.TextField("Citing Work Title")
    doi = models.CharField("DOI", max_length=500, blank=True)
    pmid = models.BigIntegerField("PubMed ID", null=True, blank=True)
    
    # Publication metadata
    publication_year = models.IntegerField("Publication Year", null=True, blank=True, db_index=True)
    publication_date = models.DateField("Publication Date", null=True, blank=True)
    journal_name = models.CharField("Journal Name", max_length=1000, blank=True)
    
    # Authors
    authors = models.TextField("Authors", blank=True)
    
    # Citation context (if available)
    citation_context = models.TextField("Citation Context", blank=True)
    
    # Classification
    is_oral_health_related = models.BooleanField("Oral Health Related", default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-publication_year', 'title']
        indexes = [
            models.Index(fields=['openalex_id']),
            models.Index(fields=['pmid']),
            models.Index(fields=['publication_year']),
            models.Index(fields=['is_oral_health_related']),
        ]
    
    def __str__(self):
        return f"Citing: {self.title[:80]}... ({self.publication_year})"


class CitationData(models.Model):
    """
    Citation analysis data for retracted papers.
    Tracks citation patterns before and after retraction.
    """
    
    # Link to retracted paper
    retracted_paper = models.OneToOneField(
        'papers.RetractedPaper',
        on_delete=models.CASCADE,
        related_name='citation_data'
    )
    
    # Citation counts
    total_citations = models.IntegerField("Total Citations", default=0, db_index=True)
    pre_retraction_citations = models.IntegerField("Pre-Retraction Citations", default=0)
    post_retraction_citations = models.IntegerField("Post-Retraction Citations", default=0, db_index=True)
    
    # Citation timeline
    first_citation_date = models.DateField("First Citation", null=True, blank=True)
    last_citation_date = models.DateField("Last Citation", null=True, blank=True)
    last_pre_retraction_citation = models.DateField("Last Pre-Retraction Citation", null=True, blank=True)
    first_post_retraction_citation = models.DateField("First Post-Retraction Citation", null=True, blank=True)
    
    # Analysis metrics
    problematic_score = models.FloatField(
        "Problematic Score", 
        default=0.0,
        help_text="Score based on post-retraction citations and citation velocity",
        db_index=True
    )
    
    # Citation sources
    citing_works = models.ManyToManyField(
        CitingWork,
        through='Citation',
        related_name='cited_retracted_papers'
    )
    
    # Data quality and freshness
    last_updated = models.DateTimeField("Last Updated", auto_now=True)
    data_completeness_score = models.FloatField("Data Completeness", default=0.0)
    
    # Analysis flags
    has_recent_citations = models.BooleanField("Has Recent Citations", default=False)
    needs_manual_review = models.BooleanField("Needs Manual Review", default=False)
    
    class Meta:
        ordering = ['-problematic_score', '-post_retraction_citations']
        indexes = [
            models.Index(fields=['total_citations']),
            models.Index(fields=['post_retraction_citations']),
            models.Index(fields=['problematic_score']),
            models.Index(fields=['has_recent_citations']),
        ]
    
    def __str__(self):
        return f"Citations for {self.retracted_paper.short_title}"
    
    @property
    def citation_reduction_ratio(self):
        """
        Calculate the ratio of post-retraction to pre-retraction citations.
        Lower values indicate better reduction in citations after retraction.
        """
        if self.pre_retraction_citations == 0:
            return None
        return self.post_retraction_citations / self.pre_retraction_citations
    
    @property
    def retraction_awareness_score(self):
        """
        Calculate awareness score (0-100) based on citation reduction.
        Higher scores indicate better awareness of the retraction.
        """
        ratio = self.citation_reduction_ratio
        if ratio is None:
            return None
        
        # Convert ratio to awareness score (inverted)
        # ratio of 0 = 100% awareness, ratio of 1 = 0% awareness
        awareness = max(0, min(100, (1 - ratio) * 100))
        return round(awareness, 1)
    
    def update_problematic_score(self):
        """Calculate and update the problematic score."""
        # Base score from post-retraction citations (normalized)
        base_score = min(100, self.post_retraction_citations * 2)
        
        # Boost score if citations are recent
        if self.has_recent_citations:
            base_score *= 1.5
        
        # Consider the retraction age
        if hasattr(self.retracted_paper, 'retraction_date') and self.retracted_paper.retraction_date:
            retraction_age_years = (timezone.now().date() - self.retracted_paper.retraction_date).days / 365.25
            # More problematic if getting cited long after retraction
            if retraction_age_years > 2:
                base_score *= 1.3
        
        self.problematic_score = round(min(100, base_score), 2)
        return self.problematic_score
    
    def update_recent_citations_flag(self):
        """Update the has_recent_citations flag."""
        if self.last_citation_date:
            six_months_ago = timezone.now().date() - timezone.timedelta(days=180)
            self.has_recent_citations = self.last_citation_date >= six_months_ago
        else:
            self.has_recent_citations = False


class Citation(models.Model):
    """
    Intermediate model linking citing works to citation data.
    Represents individual citation relationships.
    """
    
    citation_data = models.ForeignKey(CitationData, on_delete=models.CASCADE)
    citing_work = models.ForeignKey(CitingWork, on_delete=models.CASCADE)
    
    # Citation details
    citation_date = models.DateField("Citation Date", null=True, blank=True, db_index=True)
    is_post_retraction = models.BooleanField("Post-Retraction Citation", default=False, db_index=True)
    citation_type = models.CharField("Citation Type", max_length=100, blank=True)
    
    # Citation context analysis
    mentions_retraction = models.BooleanField("Mentions Retraction", default=False)
    citation_sentiment = models.CharField(
        "Citation Sentiment",
        max_length=20,
        choices=[
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
            ('unknown', 'Unknown')
        ],
        default='unknown'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-citation_date']
        unique_together = ['citation_data', 'citing_work']
        indexes = [
            models.Index(fields=['citation_date']),
            models.Index(fields=['is_post_retraction']),
            models.Index(fields=['mentions_retraction']),
        ]
    
    def __str__(self):
        return f"Citation: {self.citing_work.title[:50]}..."


class CitationAnalysisRun(models.Model):
    """
    Tracks citation analysis runs for monitoring and debugging.
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
    
    # Analysis parameters
    analysis_type = models.CharField(
        max_length=50,
        choices=[
            ('full_update', 'Full Citation Update'),
            ('recent_only', 'Recent Citations Only'),
            ('retracted_only', 'Retracted Papers Only'),
        ],
        default='recent_only'
    )
    
    # Results
    papers_analyzed = models.IntegerField(default=0)
    citations_processed = models.IntegerField(default=0)
    new_citations_found = models.IntegerField(default=0)
    errors_encountered = models.IntegerField(default=0)
    
    # Error logging
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['started_at']),
            models.Index(fields=['status']),
            models.Index(fields=['analysis_type']),
        ]
    
    def __str__(self):
        return f"Citation Analysis {self.started_at.strftime('%Y-%m-%d %H:%M')} - {self.status}"
    
    @property
    def duration(self):
        """Calculate analysis duration if completed."""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def success_rate(self):
        """Calculate success rate based on papers analyzed vs errors."""
        if self.papers_analyzed == 0:
            return 0
        return round((1 - self.errors_encountered / self.papers_analyzed) * 100, 1)
