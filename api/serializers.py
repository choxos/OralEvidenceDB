"""
API serializers for the OralEvidenceDB.
"""

from rest_framework import serializers
from papers.models import (
    Paper, Author, Journal, MeshTerm, PICOExtraction, 
    LLMProvider, AuthorPaper, DataImportLog
)


class JournalSerializer(serializers.ModelSerializer):
    """Serializer for Journal model."""
    
    paper_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Journal
        fields = [
            'id', 'name', 'abbreviation', 'issn_print', 'issn_electronic',
            'impact_factor', 'paper_count', 'created_at', 'updated_at'
        ]


class AuthorSerializer(serializers.ModelSerializer):
    """Serializer for Author model."""
    
    full_name = serializers.CharField(read_only=True)
    paper_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Author
        fields = [
            'id', 'first_name', 'last_name', 'middle_initials', 'full_name',
            'email', 'orcid', 'affiliations', 'paper_count', 'created_at', 'updated_at'
        ]


class AuthorPaperSerializer(serializers.ModelSerializer):
    """Serializer for AuthorPaper relationship."""
    
    author = AuthorSerializer(read_only=True)
    
    class Meta:
        model = AuthorPaper
        fields = [
            'author', 'author_order', 'is_corresponding', 
            'is_first_author', 'is_last_author'
        ]


class MeshTermSerializer(serializers.ModelSerializer):
    """Serializer for MeshTerm model."""
    
    paper_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = MeshTerm
        fields = [
            'id', 'descriptor_ui', 'descriptor_name', 'is_major_topic',
            'tree_numbers', 'paper_count', 'created_at'
        ]


class LLMProviderSerializer(serializers.ModelSerializer):
    """Serializer for LLMProvider model."""
    
    extraction_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = LLMProvider
        fields = [
            'id', 'name', 'display_name', 'model_name', 'is_active',
            'api_cost_per_1k_tokens', 'extraction_count', 'created_at'
        ]


class PICOExtractionSerializer(serializers.ModelSerializer):
    """Serializer for extended PICOExtraction model."""
    
    llm_provider = LLMProviderSerializer(read_only=True)
    has_complete_pico = serializers.BooleanField(read_only=True)
    study_type_display = serializers.CharField(source='get_study_type_display', read_only=True)
    
    class Meta:
        model = PICOExtraction
        fields = [
            'id', 'population', 'intervention', 'comparison', 'outcome', 'results',
            'setting', 'study_type', 'study_type_display', 'timeframe',
            'study_design', 'sample_size', 'study_duration',
            'llm_provider', 'extraction_confidence', 'has_complete_pico',
            'is_manually_verified', 'verification_notes',
            'extracted_at', 'updated_at'
        ]


class PaperListSerializer(serializers.ModelSerializer):
    """Simplified serializer for paper list views."""
    
    journal = serializers.CharField(source='journal.name', read_only=True)
    author_count = serializers.IntegerField(read_only=True)
    mesh_count = serializers.IntegerField(read_only=True)
    has_pico = serializers.SerializerMethodField()
    pubmed_url = serializers.CharField(read_only=True)
    doi_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = Paper
        fields = [
            'pmid', 'title', 'journal', 'publication_date', 'publication_year',
            'volume', 'issue', 'pages', 'language', 'author_count', 'mesh_count',
            'has_pico', 'is_processed', 'pubmed_url', 'doi_url', 'created_at'
        ]
    
    def get_has_pico(self, obj):
        """Check if paper has PICO extraction."""
        return obj.pico_extractions.exists()


class PaperDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual paper views."""
    
    journal = JournalSerializer(read_only=True)
    authors = AuthorPaperSerializer(source='authorpaper_set', many=True, read_only=True)
    mesh_terms = MeshTermSerializer(many=True, read_only=True)
    pico_extractions = PICOExtractionSerializer(many=True, read_only=True)
    pubmed_url = serializers.CharField(read_only=True)
    doi_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = Paper
        fields = [
            'pmid', 'pmc', 'doi', 'title', 'abstract', 'language',
            'journal', 'volume', 'issue', 'pages',
            'publication_date', 'publication_year', 'epub_date',
            'received_date', 'accepted_date',
            'publication_types', 'publication_status',
            'authors', 'mesh_terms', 'pico_extractions',
            'is_processed', 'processing_error',
            'pubmed_url', 'doi_url',
            'created_at', 'updated_at', 'last_indexed'
        ]


class DataImportLogSerializer(serializers.ModelSerializer):
    """Serializer for DataImportLog model."""
    
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = DataImportLog
        fields = [
            'id', 'query', 'total_papers_found', 'papers_imported',
            'papers_updated', 'papers_failed', 'status', 'error_message',
            'started_at', 'completed_at', 'duration'
        ]
    
    def get_duration(self, obj):
        """Get import duration in seconds."""
        duration = obj.duration
        return duration.total_seconds() if duration else None


class PICOExtractionRequestSerializer(serializers.Serializer):
    """Serializer for PICO extraction requests."""
    
    provider = serializers.ChoiceField(
        choices=['openai', 'anthropic', 'google'],
        required=False,
        help_text="LLM provider to use for extraction"
    )
    force_reextract = serializers.BooleanField(
        default=False,
        help_text="Force re-extraction even if PICO already exists"
    )


class SearchSerializer(serializers.Serializer):
    """Serializer for search requests."""
    
    q = serializers.CharField(
        required=False,
        help_text="Search query for title, abstract, authors, etc."
    )
    journal = serializers.IntegerField(
        required=False,
        help_text="Filter by journal ID"
    )
    year = serializers.IntegerField(
        required=False,
        help_text="Filter by publication year"
    )
    has_pico = serializers.BooleanField(
        required=False,
        help_text="Filter by PICO extraction status"
    )
    ordering = serializers.ChoiceField(
        choices=[
            '-publication_date', 'publication_date',
            '-pmid', 'pmid', 'title', '-title'
        ],
        default='-publication_date',
        required=False,
        help_text="Ordering field"
    )


class StatisticsSerializer(serializers.Serializer):
    """Serializer for database statistics."""
    
    total_papers = serializers.IntegerField()
    papers_with_pico = serializers.IntegerField()
    pico_percentage = serializers.FloatField()
    total_journals = serializers.IntegerField()
    total_authors = serializers.IntegerField()
    total_mesh_terms = serializers.IntegerField()
    recent_imports = serializers.IntegerField()
    
    # Provider statistics
    llm_providers = LLMProviderSerializer(many=True)
    
    # Temporal statistics
    papers_by_year = serializers.DictField()
    top_journals = serializers.ListField()
    top_mesh_terms = serializers.ListField()
