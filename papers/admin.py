"""
Admin configuration for oral health papers.
"""

from django.contrib import admin
from .models import (
    Paper, Author, Journal, MeshTerm, PICOExtraction, 
    LLMProvider, AuthorPaper, DataImportLog, UserProfile
)


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation', 'impact_factor', 'created_at']
    search_fields = ['name', 'abbreviation', 'issn_print', 'issn_electronic']
    list_filter = ['created_at']
    ordering = ['name']


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'email', 'orcid', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'orcid']
    list_filter = ['created_at']
    ordering = ['last_name', 'first_name']


@admin.register(MeshTerm)
class MeshTermAdmin(admin.ModelAdmin):
    list_display = ['descriptor_name', 'descriptor_ui', 'is_major_topic', 'created_at']
    search_fields = ['descriptor_name', 'descriptor_ui']
    list_filter = ['is_major_topic', 'created_at']
    ordering = ['descriptor_name']


class AuthorPaperInline(admin.TabularInline):
    model = AuthorPaper
    extra = 0
    fields = ['author', 'author_order', 'is_corresponding', 'is_first_author', 'is_last_author']


class PICOExtractionInline(admin.StackedInline):
    model = PICOExtraction
    extra = 0
    fields = [
        'population', 'intervention', 'comparison', 'outcome', 'results',
        'setting', 'study_type', 'timeframe', 'llm_provider', 'extraction_confidence',
        'is_manually_verified'
    ]


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ['pmid', 'title_short', 'journal', 'publication_year', 'is_processed', 'created_at']
    list_filter = ['journal', 'publication_year', 'is_processed', 'language', 'created_at']
    search_fields = ['pmid', 'title', 'doi', 'authors__last_name']
    ordering = ['-publication_date', '-pmid']
    readonly_fields = ['pmid', 'created_at', 'updated_at']
    filter_horizontal = ['mesh_terms']
    inlines = [AuthorPaperInline, PICOExtractionInline]
    
    fieldsets = [
        ('Basic Information', {
            'fields': ('pmid', 'title', 'abstract', 'language')
        }),
        ('Publication Details', {
            'fields': ('journal', 'volume', 'issue', 'pages', 'doi', 'pmc')
        }),
        ('Dates', {
            'fields': ('publication_date', 'publication_year', 'epub_date', 'received_date', 'accepted_date')
        }),
        ('Classification', {
            'fields': ('publication_types', 'publication_status', 'study_type_classifications')
        }),
        ('Processing', {
            'fields': ('is_processed', 'processing_error')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_indexed'),
            'classes': ('collapse',)
        }),
    ]
    
    def title_short(self, obj):
        return obj.title[:100] + "..." if len(obj.title) > 100 else obj.title
    title_short.short_description = 'Title'


@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'model_name', 'is_active', 'api_cost_per_1k_tokens', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'display_name', 'model_name']
    ordering = ['display_name']


@admin.register(PICOExtraction)
class PICOExtractionAdmin(admin.ModelAdmin):
    list_display = ['paper', 'study_type', 'llm_provider', 'extraction_confidence', 'is_manually_verified', 'extracted_at']
    list_filter = ['study_type', 'llm_provider', 'is_manually_verified', 'extracted_at']
    search_fields = ['paper__pmid', 'paper__title', 'population', 'intervention', 'outcome']
    ordering = ['-extracted_at']
    readonly_fields = ['extracted_at', 'updated_at']
    
    fieldsets = [
        ('Paper Link', {
            'fields': ('paper',)
        }),
        ('PICO Elements', {
            'fields': ('population', 'intervention', 'comparison', 'outcome', 'results')
        }),
        ('Additional Elements', {
            'fields': ('setting', 'study_type', 'timeframe', 'study_design', 'sample_size', 'study_duration')
        }),
        ('Extraction Metadata', {
            'fields': ('llm_provider', 'extraction_confidence', 'extraction_prompt', 'raw_llm_response')
        }),
        ('Quality Control', {
            'fields': ('is_manually_verified', 'verification_notes')
        }),
        ('Timestamps', {
            'fields': ('extracted_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]


@admin.register(DataImportLog)
class DataImportLogAdmin(admin.ModelAdmin):
    list_display = ['started_at', 'status', 'total_papers_found', 'papers_imported', 'papers_updated', 'papers_failed']
    list_filter = ['status', 'started_at']
    search_fields = ['query', 'error_message']
    ordering = ['-started_at']
    readonly_fields = ['id', 'started_at', 'completed_at', 'duration']
    
    fieldsets = [
        ('Import Details', {
            'fields': ('id', 'query', 'status')
        }),
        ('Results', {
            'fields': ('total_papers_found', 'papers_imported', 'papers_updated', 'papers_failed')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'duration')
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    ]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'institution', 'preferred_theme', 'created_at']
    list_filter = ['preferred_theme', 'created_at']
    search_fields = ['user__username', 'user__email', 'institution', 'orcid']
    filter_horizontal = ['bookmarked_papers']
    ordering = ['-created_at']
    
    fieldsets = [
        ('User Information', {
            'fields': ('user', 'institution', 'research_interests', 'orcid')
        }),
        ('Preferences', {
            'fields': ('preferred_theme',)
        }),
        ('Bookmarks', {
            'fields': ('bookmarked_papers',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]


# Register retraction models if available
try:
    from .models_retraction import RetractedPaper, RetractionImportLog
    
    @admin.register(RetractedPaper)
    class RetractedPaperAdmin(admin.ModelAdmin):
        list_display = ['short_title', 'journal', 'retraction_date', 'retraction_nature', 'original_pubmed_id']
        list_filter = ['retraction_nature', 'retraction_date', 'journal', 'country']
        search_fields = ['original_title', 'journal', 'authors', 'reason']
        ordering = ['-retraction_date']
        readonly_fields = ['created_at', 'updated_at']
        
        fieldsets = [
            ('Original Paper', {
                'fields': ('original_title', 'original_pubmed_id', 'original_doi', 'original_paper_date')
            }),
            ('Retraction Details', {
                'fields': ('retraction_title', 'retraction_doi', 'retraction_pubmed_id', 'retraction_date')
            }),
            ('Publication Info', {
                'fields': ('journal', 'authors', 'country', 'subject')
            }),
            ('Retraction Analysis', {
                'fields': ('retraction_nature', 'reason', 'notes')
            }),
            ('URLs', {
                'fields': ('original_paper_url', 'retraction_url'),
                'classes': ('collapse',)
            }),
            ('Metadata', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        ]

except ImportError:
    pass


# Register citation models if available
try:
    from .models_citation import OpenAlexWork, CitationData, CitingWork
    
    @admin.register(OpenAlexWork)
    class OpenAlexWorkAdmin(admin.ModelAdmin):
        list_display = ['short_title', 'publication_year', 'cited_by_count', 'is_retracted', 'is_oral_health_related']
        list_filter = ['is_retracted', 'is_oral_health_related', 'publication_year', 'work_type']
        search_fields = ['title', 'doi', 'pmid', 'openalex_id']
        ordering = ['-cited_by_count']

    @admin.register(CitationData)
    class CitationDataAdmin(admin.ModelAdmin):
        list_display = ['retracted_paper', 'total_citations', 'post_retraction_citations', 'problematic_score']
        list_filter = ['has_recent_citations', 'needs_manual_review']
        ordering = ['-problematic_score']

except ImportError:
    pass
