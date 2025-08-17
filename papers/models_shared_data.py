"""
Models for tracking shared research data in oral health studies.

This module handles data repository information, shared datasets,
and links between papers and their associated research data.
"""

from django.db import models
from django.utils import timezone
import uuid


class DataRepository(models.Model):
    """
    Represents data repositories where oral health research data is shared.
    """
    
    name = models.CharField("Repository Name", max_length=500, unique=True, db_index=True)
    display_name = models.CharField("Display Name", max_length=500)
    description = models.TextField("Description", blank=True)
    
    # Repository details
    base_url = models.URLField("Base URL", max_length=1000)
    repository_type = models.CharField(
        "Repository Type",
        max_length=100,
        choices=[
            ('institutional', 'Institutional Repository'),
            ('discipline_specific', 'Discipline-Specific Repository'),
            ('general_purpose', 'General Purpose Repository'),
            ('government', 'Government Repository'),
            ('publisher', 'Publisher Repository'),
            ('project_specific', 'Project-Specific Repository'),
        ],
        blank=True
    )
    
    # Focus areas
    primary_focus = models.CharField("Primary Focus", max_length=200, blank=True)
    supports_oral_health = models.BooleanField("Supports Oral Health Research", default=True)
    
    # Technical details
    api_endpoint = models.URLField("API Endpoint", max_length=1000, blank=True)
    supports_api = models.BooleanField("Supports API Access", default=False)
    metadata_standard = models.CharField("Metadata Standard", max_length=200, blank=True)
    
    # Quality indicators
    is_active = models.BooleanField("Is Active", default=True, db_index=True)
    requires_registration = models.BooleanField("Requires Registration", default=False)
    has_doi_assignment = models.BooleanField("Assigns DOIs", default=False)
    peer_reviewed = models.BooleanField("Peer Reviewed", default=False)
    
    # Statistics
    total_datasets = models.IntegerField("Total Datasets", default=0)
    oral_health_datasets = models.IntegerField("Oral Health Datasets", default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_checked = models.DateTimeField("Last Checked", null=True, blank=True)
    
    class Meta:
        ordering = ['display_name']
        verbose_name_plural = "Data Repositories"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['repository_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['supports_oral_health']),
        ]
    
    def __str__(self):
        return self.display_name
    
    @property
    def oral_health_percentage(self):
        """Calculate percentage of datasets related to oral health."""
        if self.total_datasets == 0:
            return 0
        return round((self.oral_health_datasets / self.total_datasets) * 100, 1)


class DatasetAuthor(models.Model):
    """
    Authors of shared datasets (may differ from paper authors).
    """
    
    first_name = models.CharField("First Name", max_length=500)
    last_name = models.CharField("Last Name", max_length=500)
    middle_name = models.CharField("Middle Name", max_length=500, blank=True)
    email = models.EmailField("Email", blank=True)
    orcid = models.CharField("ORCID ID", max_length=200, blank=True, db_index=True)
    
    # Affiliations
    affiliation = models.TextField("Affiliation", blank=True)
    department = models.CharField("Department", max_length=500, blank=True)
    institution = models.CharField("Institution", max_length=500, blank=True)
    country = models.CharField("Country", max_length=200, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        unique_together = ['first_name', 'last_name', 'orcid']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['orcid']),
            models.Index(fields=['institution']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        """Return full name with middle name if available."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return ' '.join(parts)


class SharedDataset(models.Model):
    """
    Represents a shared dataset in an oral health research repository.
    """
    
    # Dataset identifiers
    dataset_id = models.CharField("Dataset ID", max_length=500, db_index=True)
    repository = models.ForeignKey(DataRepository, on_delete=models.CASCADE, related_name='datasets')
    
    # Basic information
    title = models.TextField("Dataset Title")
    description = models.TextField("Description", blank=True)
    abstract = models.TextField("Abstract", blank=True)
    
    # Publication details
    doi = models.CharField("DOI", max_length=500, blank=True, db_index=True)
    url = models.URLField("Dataset URL", max_length=1000)
    version = models.CharField("Version", max_length=100, blank=True)
    
    # Oral health classification
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
            ('epidemiology', 'Oral Health Epidemiology'),
            ('public_health', 'Oral Public Health'),
            ('clinical_trials', 'Clinical Trial Data'),
            ('genomics', 'Oral Health Genomics'),
            ('microbiome', 'Oral Microbiome'),
            ('imaging', 'Oral/Dental Imaging'),
            ('other', 'Other')
        ],
        blank=True,
        db_index=True
    )
    
    # Dataset characteristics
    data_type = models.CharField(
        "Data Type",
        max_length=100,
        choices=[
            ('clinical', 'Clinical Data'),
            ('epidemiological', 'Epidemiological Data'),
            ('laboratory', 'Laboratory Data'),
            ('imaging', 'Imaging Data'),
            ('genomic', 'Genomic Data'),
            ('survey', 'Survey Data'),
            ('administrative', 'Administrative Data'),
            ('mixed', 'Mixed Data Types'),
            ('other', 'Other')
        ],
        blank=True
    )
    
    # Technical details
    file_format = models.CharField("File Format", max_length=200, blank=True)
    file_count = models.IntegerField("Number of Files", null=True, blank=True)
    storage_size = models.CharField("Storage Size", max_length=100, blank=True)
    
    # Access and licensing
    access_status = models.CharField(
        "Access Status",
        max_length=50,
        choices=[
            ('open', 'Open Access'),
            ('restricted', 'Restricted Access'),
            ('embargo', 'Embargo Period'),
            ('closed', 'Closed Access'),
            ('unknown', 'Unknown')
        ],
        default='unknown',
        db_index=True
    )
    
    license = models.CharField("License", max_length=200, blank=True)
    usage_terms = models.TextField("Usage Terms", blank=True)
    
    # Temporal information
    publication_date = models.DateField("Publication Date", null=True, blank=True)
    last_modified = models.DateTimeField("Last Modified", null=True, blank=True)
    embargo_end_date = models.DateField("Embargo End Date", null=True, blank=True)
    
    # Quality indicators
    has_metadata = models.BooleanField("Has Metadata", default=False)
    metadata_quality_score = models.FloatField("Metadata Quality Score", null=True, blank=True)
    peer_reviewed = models.BooleanField("Peer Reviewed", default=False)
    
    # Usage statistics
    download_count = models.IntegerField("Download Count", default=0)
    view_count = models.IntegerField("View Count", default=0)
    citation_count = models.IntegerField("Citation Count", default=0)
    
    # Resource type
    resource_type = models.CharField(
        "Resource Type",
        max_length=100,
        choices=[
            ('dataset', 'Dataset'),
            ('code', 'Code/Software'),
            ('documentation', 'Documentation'),
            ('protocol', 'Study Protocol'),
            ('questionnaire', 'Questionnaire'),
            ('other', 'Other')
        ],
        default='dataset'
    )
    
    # Authors (many-to-many relationship)
    authors = models.ManyToManyField(
        DatasetAuthor,
        through='DatasetAuthorshipOrder',
        related_name='datasets'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-publication_date', '-created_at']
        unique_together = ['dataset_id', 'repository']
        indexes = [
            models.Index(fields=['dataset_id']),
            models.Index(fields=['doi']),
            models.Index(fields=['oral_health_category']),
            models.Index(fields=['data_type']),
            models.Index(fields=['access_status']),
            models.Index(fields=['publication_date']),
        ]
    
    def __str__(self):
        return f"{self.title[:80]}..."
    
    @property
    def short_title(self):
        """Return a shortened version of the title."""
        if len(self.title) > 100:
            return self.title[:100] + "..."
        return self.title
    
    @property
    def is_oral_health_related(self):
        """Check if this dataset is related to oral health."""
        return self.oral_health_category != '' and self.oral_health_category != 'other'
    
    @property
    def is_openly_accessible(self):
        """Check if the dataset is openly accessible."""
        return self.access_status == 'open'
    
    def get_repository_url(self):
        """Get the full URL to this dataset in its repository."""
        if self.url:
            return self.url
        elif self.repository.base_url and self.dataset_id:
            return f"{self.repository.base_url}/{self.dataset_id}"
        return None


class DatasetAuthorshipOrder(models.Model):
    """
    Intermediate model for dataset authorship with order.
    """
    
    dataset = models.ForeignKey(SharedDataset, on_delete=models.CASCADE)
    author = models.ForeignKey(DatasetAuthor, on_delete=models.CASCADE)
    author_order = models.PositiveIntegerField("Author Order")
    
    # Author roles
    is_corresponding = models.BooleanField("Corresponding Author", default=False)
    is_primary = models.BooleanField("Primary Author", default=False)
    role = models.CharField("Role", max_length=200, blank=True)
    
    class Meta:
        ordering = ['dataset', 'author_order']
        unique_together = ['dataset', 'author']
        indexes = [
            models.Index(fields=['dataset', 'author_order']),
        ]
    
    def __str__(self):
        return f"{self.author} - {self.dataset.short_title} (Order: {self.author_order})"


class DatasetPaperLink(models.Model):
    """
    Links between published papers and shared datasets.
    """
    
    paper = models.ForeignKey(
        'papers.Paper',
        on_delete=models.CASCADE,
        related_name='dataset_links'
    )
    dataset = models.ForeignKey(
        SharedDataset,
        on_delete=models.CASCADE,
        related_name='paper_links'
    )
    
    # Link details
    link_type = models.CharField(
        "Link Type",
        max_length=50,
        choices=[
            ('primary_data', 'Primary Data Source'),
            ('supplementary_data', 'Supplementary Data'),
            ('reanalysis_data', 'Data for Reanalysis'),
            ('validation_data', 'Validation Dataset'),
            ('code_software', 'Code/Software'),
            ('protocol', 'Study Protocol'),
            ('other', 'Other')
        ],
        default='supplementary_data',
        db_index=True
    )
    
    # Confidence and verification
    confidence_score = models.FloatField(
        "Confidence Score",
        null=True,
        blank=True,
        help_text="Confidence in the paper-dataset link (0.0-1.0)"
    )
    
    extraction_method = models.CharField(
        "Extraction Method",
        max_length=50,
        choices=[
            ('automatic_doi', 'Automatic DOI Detection'),
            ('automatic_url', 'Automatic URL Detection'),
            ('manual_review', 'Manual Review'),
            ('author_declaration', 'Author Declaration'),
            ('repository_search', 'Repository Search'),
            ('other', 'Other')
        ],
        default='automatic_doi'
    )
    
    # Verification
    is_verified = models.BooleanField("Manually Verified", default=False)
    verified_by = models.CharField("Verified By", max_length=200, blank=True)
    verification_notes = models.TextField("Verification Notes", blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['paper', 'dataset']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['link_type']),
            models.Index(fields=['confidence_score']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        return f"{self.paper.pmid} <-> {self.dataset.short_title}"
    
    @property
    def is_high_confidence_link(self):
        """Check if this is a high-confidence paper-dataset link."""
        return self.confidence_score and self.confidence_score >= 0.8


class DataSearchRun(models.Model):
    """
    Tracks data repository search and extraction runs.
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
    
    # Search parameters
    repositories_searched = models.JSONField("Repositories Searched", default=list)
    search_terms = models.TextField("Search Terms", blank=True)
    date_range_start = models.DateField("Date Range Start", null=True, blank=True)
    date_range_end = models.DateField("Date Range End", null=True, blank=True)
    
    # Results
    datasets_found = models.IntegerField(default=0)
    datasets_processed = models.IntegerField(default=0)
    new_datasets_added = models.IntegerField(default=0)
    existing_datasets_updated = models.IntegerField(default=0)
    paper_links_created = models.IntegerField(default=0)
    
    # Error tracking
    errors_encountered = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['started_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Data Search {self.started_at.strftime('%Y-%m-%d %H:%M')} - {self.status}"
    
    @property
    def duration(self):
        """Calculate search duration if completed."""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def success_rate(self):
        """Calculate success rate."""
        if self.datasets_processed == 0:
            return 0
        return round((1 - self.errors_encountered / self.datasets_processed) * 100, 1)
