"""
Models for the OralEvidenceDB application.

This module contains Django models for storing oral health research papers,
authors, PICO elements, and related metadata.
"""

from django.db import models
from django.urls import reverse
from django.utils.text import slugify

# Import retracted papers model
from .models_retraction import RetractedPaper
# Import citation tracking models  
from .models_citation import OpenAlexWork, CitationData, CitingWork, CitationAnalysisRun
# Import clinical trial models
from .models_clinical_trial import ClinicalTrial, PaperClinicalTrial, NCTExtractionRun
# Import shared data repository models
from .models_shared_data import (DataRepository, DatasetAuthor, SharedDataset, 
                                DatasetAuthorshipOrder, DatasetPaperLink, DataSearchRun)
import uuid


class Journal(models.Model):
    """Represents a scientific journal."""
    
    # NOTE: We store abbreviations in 'name' field (what we display on website)
    # and full journal names in 'abbreviation' field (for reference)
    name = models.CharField("Journal Abbreviation", max_length=2000, unique=True, 
                           help_text="Journal abbreviation (displayed on website)")
    abbreviation = models.CharField("Full Journal Name", max_length=1000, blank=True,
                                  help_text="Full journal name (for reference)")
    issn_print = models.CharField("Print ISSN", max_length=100, blank=True)
    issn_electronic = models.CharField("Electronic ISSN", max_length=100, blank=True)
    impact_factor = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['abbreviation']),
        ]
    
    def __str__(self):
        # Always return the abbreviation (stored in name field)
        return self.name
    
    @property
    def display_name(self):
        """Return the journal abbreviation for display."""
        return self.name
    
    @property
    def full_name(self):
        """Return the full journal name."""
        return self.abbreviation or self.name


class Author(models.Model):
    """Represents a research paper author."""
    
    first_name = models.CharField(max_length=1000)
    last_name = models.CharField(max_length=1000)
    middle_initials = models.CharField(max_length=500, blank=True)
    email = models.EmailField(blank=True)
    orcid = models.CharField("ORCID ID", max_length=200, blank=True)
    affiliations = models.TextField(blank=True, help_text="Institutional affiliations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['orcid']),
        ]
    
    def __str__(self):
        return f"{self.last_name}, {self.first_name}"
    
    @property
    def full_name(self):
        """Return full name with middle initials if available."""
        parts = [self.first_name]
        if self.middle_initials:
            parts.append(self.middle_initials)
        parts.append(self.last_name)
        return ' '.join(parts)


class MeshTerm(models.Model):
    """Represents Medical Subject Headings (MeSH) terms."""
    
    descriptor_ui = models.CharField("Descriptor UI", max_length=200, blank=True)
    descriptor_name = models.CharField("Descriptor Name", max_length=2000)
    is_major_topic = models.BooleanField(default=False)
    tree_numbers = models.TextField(blank=True, help_text="MeSH tree numbers")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['descriptor_name']
        indexes = [
            models.Index(fields=['descriptor_ui']),
            models.Index(fields=['descriptor_name']),
            models.Index(fields=['is_major_topic']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['descriptor_ui'],
                condition=models.Q(descriptor_ui__isnull=False) & ~models.Q(descriptor_ui=''),
                name='unique_descriptor_ui_when_present'
            )
        ]
    
    def __str__(self):
        return self.descriptor_name


class Paper(models.Model):
    """Represents a research paper from PubMed focused on oral health."""
    
    # PubMed identifiers
    pmid = models.BigIntegerField("PubMed ID", unique=True, primary_key=True)
    pmc = models.CharField("PMC ID", max_length=200, blank=True)
    doi = models.CharField("DOI", max_length=2000, blank=True)
    
    # Basic paper information
    title = models.TextField()
    abstract = models.TextField(blank=True)
    language = models.CharField(max_length=100, default='eng')
    
    # Journal and publication info
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='papers')
    volume = models.CharField(max_length=200, blank=True)
    issue = models.CharField(max_length=200, blank=True)
    pages = models.CharField(max_length=500, blank=True)
    
    # Dates
    publication_date = models.DateField(null=True, blank=True)
    publication_year = models.IntegerField(null=True, blank=True)
    epub_date = models.DateField("Electronic Publication Date", null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    accepted_date = models.DateField(null=True, blank=True)
    
    # Publication types and status
    publication_types = models.TextField(blank=True, help_text="Comma-separated publication types")
    publication_status = models.CharField(max_length=500, blank=True)
    
    # Authors and MeSH terms (many-to-many relationships)
    authors = models.ManyToManyField(Author, through='AuthorPaper', related_name='papers')
    mesh_terms = models.ManyToManyField(MeshTerm, related_name='papers', blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_indexed = models.DateTimeField(null=True, blank=True)
    
    # Processing status
    is_processed = models.BooleanField(default=False, help_text="Whether PICO extraction has been performed")
    processing_error = models.TextField(blank=True)
    
    # Study type classification
    study_type_classifications = models.JSONField(
        default=list, 
        blank=True,
        help_text="Study type classifications with confidence scores"
    )
    
    class Meta:
        ordering = ['-publication_date', '-pmid']
        indexes = [
            models.Index(fields=['pmid']),
            models.Index(fields=['doi']),
            models.Index(fields=['publication_date']),
            models.Index(fields=['publication_year']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['journal']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['doi'],
                condition=models.Q(doi__isnull=False) & ~models.Q(doi=''),
                name='unique_doi_when_present'
            )
        ]
    
    def __str__(self):
        return f"PMID:{self.pmid} - {self.title[:100]}..."
    
    def get_absolute_url(self):
        return reverse('papers:detail', kwargs={'pmid': self.pmid})
    
    @property
    def slug(self):
        """Generate a URL-friendly slug from the title."""
        return slugify(self.title[:50])
    
    @property
    def pubmed_url(self):
        """Return the PubMed URL for this paper."""
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"
    
    @property
    def doi_url(self):
        """Return the DOI URL if DOI is available."""
        return f"https://doi.org/{self.doi}" if self.doi else None
    
    def get_retraction_info(self):
        """Get retraction information for this paper if it exists."""
        if self.pmid:
            try:
                return RetractedPaper.objects.get(original_pubmed_id=self.pmid)
            except RetractedPaper.DoesNotExist:
                pass
        return None

    @property
    def is_retracted(self):
        """Check if this paper has been retracted."""
        return self.get_retraction_info() is not None
    
    def get_study_type_classifications(self, force_refresh=False):
        """Get study type classifications, computing them if not cached."""
        if not self.study_type_classifications or force_refresh:
            from .study_type_classifier import StudyTypeClassifier
            classifier = StudyTypeClassifier()
            classifications = classifier.classify_paper(self)
            
            # Convert to JSON-serializable format
            all_classifications = [
                {
                    'classification': result.classification.value,
                    'confidence': result.confidence,
                    'description': result.description,
                    'matched_criteria': result.matched_criteria
                }
                for result in classifications
            ]
            
            # Apply priority logic: show only most compatible classification 
            # plus any clinical trial specifications
            self.study_type_classifications = self._filter_priority_classifications(all_classifications)
            # Don't auto-save here to avoid side effects
        
        return self.study_type_classifications
    
    def _filter_priority_classifications(self, classifications):
        """Filter classifications to show only the most compatible plus clinical trial specs."""
        if not classifications:
            return []
        
        # Define clinical trial specifications that should always be shown
        clinical_trial_specs = {
            'placebo_controlled_rct',
            'open_label_rct', 
            'single_blind_rct',
            'double_blind_rct',
            'triple_blind_rct'
        }
        
        # Define main study types (non-specifications)
        main_study_types = {
            'cohort_study', 'case_control_study', 'cross_sectional_study',
            'randomized_controlled_trial', 'controlled_clinical_trial', 'clinical_trial',
            'single_arm_trial', 'pilot_study', 'case_report', 'case_series',
            'systematic_review', 'meta_analysis', 'network_meta_analysis',
            'matching_adjusted_indirect_comparison', 'simulated_treatment_comparison',
            'multilevel_network_meta_regression', 'animal_studies', 'economic_evaluations',
            'guidelines', 'patient_perspectives', 'qualitative_studies', 'surveys_questionnaires'
        }
        
        # Separate main classifications from specifications
        main_classifications = [c for c in classifications if c['classification'] in main_study_types]
        specification_classifications = [c for c in classifications if c['classification'] in clinical_trial_specs]
        
        # Get the highest confidence main classification
        if main_classifications:
            # Sort by confidence (highest first) and take the most compatible one
            main_classifications.sort(key=lambda x: x['confidence'], reverse=True)
            primary_classification = main_classifications[0]
            
            # Include the primary classification plus any clinical trial specifications
            result = [primary_classification]
            
            # Add clinical trial specifications if they exist and the primary is a clinical trial
            clinical_trial_types = {
                'randomized_controlled_trial', 'controlled_clinical_trial', 'clinical_trial'
            }
            
            if primary_classification['classification'] in clinical_trial_types and specification_classifications:
                # Sort specifications by confidence and include all of them
                specification_classifications.sort(key=lambda x: x['confidence'], reverse=True)
                result.extend(specification_classifications)
            
            return result
        
        # Fallback: if no main classifications, return all (shouldn't happen normally)
        return classifications
    
    @property
    def primary_study_type_classification(self):
        """Get the highest confidence study type classification."""
        classifications = self.get_study_type_classifications()
        if classifications:
            return classifications[0]  # Highest confidence first
        return None
    
    @property
    def study_types(self):
        """Get list of study type names for display."""
        from .templatetags.paper_filters import format_study_type_classification
        classifications = self.get_study_type_classifications()
        return [
            format_study_type_classification(result['classification'])
            for result in classifications
        ]
    
    # Backward compatibility methods
    def get_cda_classifications(self, force_refresh=False):
        """Backward compatibility method - calls get_study_type_classifications."""
        return self.get_study_type_classifications(force_refresh)
    
    @property
    def cda_classifications(self):
        """Backward compatibility property - returns study_type_classifications."""
        return self.study_type_classifications
    
    @property
    def primary_cda_classification(self):
        """Backward compatibility property - calls primary_study_type_classification."""
        return self.primary_study_type_classification
    
    @property
    def cda_study_types(self):
        """Backward compatibility property - calls study_types."""
        return self.study_types


class AuthorPaper(models.Model):
    """Intermediate model for author-paper relationship with order."""
    
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE)
    author_order = models.PositiveIntegerField()
    is_corresponding = models.BooleanField(default=False)
    is_first_author = models.BooleanField(default=False)
    is_last_author = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['paper', 'author_order']
        unique_together = ['author', 'paper']
        indexes = [
            models.Index(fields=['paper', 'author_order']),
            models.Index(fields=['is_corresponding']),
            models.Index(fields=['is_first_author']),
        ]
    
    def __str__(self):
        return f"{self.author} - {self.paper.pmid} (Order: {self.author_order})"


class LLMProvider(models.Model):
    """Represents different LLM providers for PICO extraction."""
    
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI (ChatGPT)'),
        ('anthropic', 'Anthropic (Claude)'),
        ('google', 'Google (Gemini)'),
        ('ollama', 'Ollama (Local)'),
    ]
    
    name = models.CharField(max_length=500, unique=True)
    display_name = models.CharField(max_length=1000)
    model_name = models.CharField(max_length=1000, help_text="Specific model used (e.g., gpt-4, claude-3)")
    is_active = models.BooleanField(default=True)
    api_cost_per_1k_tokens = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['display_name']
    
    def __str__(self):
        return f"{self.display_name} ({self.model_name})"


class PICOExtraction(models.Model):
    """Represents PICO elements extracted from an oral health research paper's abstract."""
    
    # Comprehensive study type choices for oral health research
    STUDY_TYPE_CHOICES = [
        ('randomized_controlled_trial', 'Randomized Controlled Trial (RCT)'),
        ('systematic_review', 'Systematic Review'),
        ('meta_analysis', 'Meta-Analysis'),
        ('cohort_study', 'Cohort Study'),
        ('case_control_study', 'Case-Control Study'),
        ('cross_sectional_study', 'Cross-Sectional Study'),
        ('case_series', 'Case Series'),
        ('case_report', 'Case Report'),
        ('clinical_trial', 'Clinical Trial'),
        ('pilot_study', 'Pilot Study'),
        ('observational_study', 'Observational Study'),
        ('retrospective_study', 'Retrospective Study'),
        ('prospective_study', 'Prospective Study'),
        ('longitudinal_study', 'Longitudinal Study'),
        ('experimental_study', 'Experimental Study'),
        ('quasi_experimental', 'Quasi-Experimental Study'),
        ('descriptive_study', 'Descriptive Study'),
        ('analytical_study', 'Analytical Study'),
        ('ecological_study', 'Ecological Study'),
        ('narrative_review', 'Narrative Review'),
        ('scoping_review', 'Scoping Review'),
        ('umbrella_review', 'Umbrella Review'),
        ('laboratory_study', 'Laboratory Study'),
        ('animal_study', 'Animal Study'),
        ('in_vitro_study', 'In Vitro Study'),
        ('survey', 'Survey'),
        ('interview_study', 'Interview Study'),
        ('qualitative_study', 'Qualitative Study'),
        ('mixed_methods', 'Mixed Methods Study'),
        ('diagnostic_study', 'Diagnostic Study'),
        ('prognostic_study', 'Prognostic Study'),
        ('health_technology_assessment', 'Health Technology Assessment'),
        ('cost_effectiveness_study', 'Cost-Effectiveness Study'),
        ('guidelines', 'Clinical Practice Guidelines'),
        ('consensus_statement', 'Consensus Statement'),
        ('expert_opinion', 'Expert Opinion'),
        ('other', 'Other'),
        ('not_specified', 'Not Specified'),
    ]
    
    # Link to paper - allowing multiple PICO extractions per paper
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='pico_extractions')
    
    # Extended PICO elements (PICOSTS) adapted for oral health research
    population = models.TextField(blank=True, help_text="Patient population or participants (e.g., adults with periodontal disease, children with caries)")
    intervention = models.TextField(blank=True, help_text="Intervention or exposure (e.g., fluoride treatment, periodontal therapy, oral hygiene instructions)")
    comparison = models.TextField(blank=True, help_text="Comparison or control group (e.g., placebo, standard care, no treatment)")
    outcome = models.TextField(blank=True, help_text="Outcome measures (e.g., caries reduction, periodontal healing, oral health-related quality of life)")
    results = models.TextField(blank=True, help_text="Numerical results, statistical findings, or quantitative answers")
    setting = models.TextField(blank=True, help_text="Setting where the study was conducted (e.g., dental clinic, hospital, community health center)")
    study_type = models.CharField(
        max_length=50, 
        choices=STUDY_TYPE_CHOICES, 
        blank=True,
        help_text="Type of study design"
    )
    timeframe = models.TextField(blank=True, help_text="Study timeframe, duration, or follow-up period")
    
    # Additional structured elements (kept for backward compatibility)
    study_design = models.CharField(max_length=2000, blank=True)
    sample_size = models.CharField(max_length=1000, blank=True)
    study_duration = models.CharField(max_length=1000, blank=True)
    
    # Extraction metadata
    llm_provider = models.ForeignKey(LLMProvider, on_delete=models.SET_NULL, null=True)
    extraction_confidence = models.FloatField(null=True, blank=True, help_text="Confidence score 0-1")
    extraction_prompt = models.TextField(blank=True)
    raw_llm_response = models.TextField(blank=True)
    
    # Quality indicators
    is_manually_verified = models.BooleanField(default=False)
    verification_notes = models.TextField(blank=True)
    
    # Timestamps
    extracted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-extracted_at']
        indexes = [
            models.Index(fields=['paper']),
            models.Index(fields=['llm_provider']),
            models.Index(fields=['is_manually_verified']),
            models.Index(fields=['extracted_at']),
        ]
    
    def __str__(self):
        return f"PICO for PMID:{self.paper.pmid}"
    
    def get_study_type_display_short(self):
        """Get a shorter display name for study type."""
        type_mapping = {
            'randomized_controlled_trial': 'RCT',
            'systematic_review': 'Systematic Review',
            'meta_analysis': 'Meta-Analysis',
            'cohort_study': 'Cohort',
            'case_control_study': 'Case-Control',
            'cross_sectional_study': 'Cross-Sectional',
            'case_series': 'Case Series',
            'case_report': 'Case Report',
            'clinical_trial': 'Clinical Trial',
            'observational_study': 'Observational',
        }
        return type_mapping.get(self.study_type, self.get_study_type_display())
    
    @property
    def has_complete_pico(self):
        """Check if all main PICO elements are present."""
        return bool(self.population and self.intervention and self.comparison and self.outcome)


class DataImportLog(models.Model):
    """Logs data import operations from PubMed for oral health research."""
    
    IMPORT_STATUS_CHOICES = [
        ('started', 'Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.TextField(help_text="PubMed search query used", default="(Stomatognathic Diseases[MeSH Major Topic]) OR (Dentistry[MeSH Major Topic]) OR (Oral Health[MeSH Major Topic])")
    total_papers_found = models.IntegerField(null=True, blank=True)
    papers_imported = models.IntegerField(default=0)
    papers_updated = models.IntegerField(default=0)
    papers_failed = models.IntegerField(default=0)
    
    status = models.CharField(max_length=200, choices=IMPORT_STATUS_CHOICES, default='started')
    error_message = models.TextField(blank=True)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"Import {self.id} - {self.status}"
    
    @property
    def duration(self):
        """Calculate import duration if completed."""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None


class UserProfile(models.Model):
    """Extended user profile for oral health researchers."""
    
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    institution = models.CharField(max_length=2000, blank=True)
    research_interests = models.TextField(blank=True, help_text="Research interests in oral health")
    orcid = models.CharField("ORCID ID", max_length=200, blank=True)
    
    # Theme preferences
    preferred_theme = models.CharField(
        max_length=100,
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='light'
    )
    
    # Saved searches and bookmarks
    saved_searches = models.JSONField(default=list, blank=True)
    bookmarked_papers = models.ManyToManyField(Paper, blank=True, related_name='bookmarked_by')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['orcid']),
        ]
    
    def __str__(self):
        return f"Profile: {self.user.username}"
