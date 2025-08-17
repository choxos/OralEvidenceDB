"""
API views for OralEvidenceDB.
"""

from rest_framework import generics, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
try:
    from django_filters.rest_framework import DjangoFilterBackend
except ImportError:
    DjangoFilterBackend = None

from papers.models import Paper, Author, Journal, MeshTerm, PICOExtraction, LLMProvider
from papers.llm_extractors import PICOExtractionService, LLMExtractorFactory
from .serializers import (
    PaperListSerializer, PaperDetailSerializer, AuthorSerializer,
    JournalSerializer, MeshTermSerializer, PICOExtractionSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API results."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def api_documentation(request):
    """Comprehensive API documentation with examples."""
    return render(request, 'api/documentation.html')


class PaperListAPIView(generics.ListAPIView):
    """
    API view for listing oral health papers with search and filtering.
    
    Supports:
    - Search across title, abstract, and authors
    - Filter by journal, publication year, language
    - Filter by PICO availability
    - Ordering by various fields
    """
    
    serializer_class = PaperListSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter] + ([DjangoFilterBackend] if DjangoFilterBackend else [])
    search_fields = ['title', 'abstract', 'authors__first_name', 'authors__last_name']
    ordering_fields = ['pmid', 'publication_date', 'publication_year', 'title']
    ordering = ['-publication_date']
    filterset_fields = ['journal', 'publication_year', 'language', 'is_processed']
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Paper.objects.select_related('journal').prefetch_related(
            'authors',  # Prefetch authors relationship
            'pico_extractions'  # Prefetch PICO data for filtering
        ).only(
            'pmid', 'title', 'publication_date', 'publication_year', 'language',
            'journal__name', 'is_processed', 'abstract'
        )
        
        # Filter by PICO availability
        has_pico = self.request.query_params.get('has_pico')
        if has_pico is not None:
            if has_pico.lower() == 'true':
                queryset = queryset.filter(pico_extractions__isnull=False)
            elif has_pico.lower() == 'false':
                queryset = queryset.filter(pico_extractions__isnull=True)
        
        # Filter by author name
        author = self.request.query_params.get('author')
        if author:
            queryset = queryset.filter(
                Q(authors__first_name__icontains=author) |
                Q(authors__last_name__icontains=author)
            )
        
        # Filter by MeSH terms
        mesh = self.request.query_params.get('mesh')
        if mesh:
            queryset = queryset.filter(mesh_terms__descriptor_name__icontains=mesh)
        
        return queryset.distinct()


class PaperDetailAPIView(generics.RetrieveAPIView):
    """
    API view for retrieving detailed paper information including PICO extraction.
    """
    
    serializer_class = PaperDetailSerializer
    lookup_field = 'pmid'
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Paper.objects.select_related('journal').prefetch_related(
            'authors', 'mesh_terms', 'pico_extractions__llm_provider'
        )


class AuthorListAPIView(generics.ListAPIView):
    """API view for listing authors with search and filtering."""
    
    queryset = Author.objects.all().order_by('last_name', 'first_name')
    serializer_class = AuthorSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter] + ([DjangoFilterBackend] if DjangoFilterBackend else [])
    search_fields = ['first_name', 'last_name', 'email']
    ordering_fields = ['last_name', 'first_name']
    permission_classes = [AllowAny]


class JournalListAPIView(generics.ListAPIView):
    """API view for listing journals with search and filtering."""
    
    queryset = Journal.objects.all().order_by('name')
    serializer_class = JournalSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter] + ([DjangoFilterBackend] if DjangoFilterBackend else [])
    search_fields = ['name', 'issn', 'publisher']
    ordering_fields = ['name', 'impact_factor']
    permission_classes = [AllowAny]


class PICOExtractionListAPIView(generics.ListAPIView):
    """
    API view for listing PICO extractions with comprehensive filtering.
    
    Supports filtering by:
    - PICO elements (population, intervention, comparison, outcome, setting, timeframe)
    - Study type
    - LLM provider
    - Publication year
    - Journal
    """
    
    queryset = PICOExtraction.objects.select_related('paper__journal', 'llm_provider').order_by('-extracted_at')
    serializer_class = PICOExtractionSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter] + ([DjangoFilterBackend] if DjangoFilterBackend else [])
    search_fields = ['population', 'intervention', 'comparison', 'outcome', 'setting', 'timeframe', 'paper__title']
    ordering_fields = ['extracted_at', 'paper__publication_date', 'extraction_confidence']
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by study type
        study_type = self.request.query_params.get('study_type')
        if study_type:
            queryset = queryset.filter(study_type=study_type)
        
        # Filter by LLM provider
        provider = self.request.query_params.get('provider')
        if provider:
            queryset = queryset.filter(llm_provider__name=provider)
        
        # Filter by publication year
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(paper__publication_year=year)
        
        # Filter by journal
        journal_id = self.request.query_params.get('journal')
        if journal_id:
            queryset = queryset.filter(paper__journal_id=journal_id)
        
        # Filter by specific PICO elements
        for field in ['population', 'intervention', 'comparison', 'outcome', 'setting', 'timeframe']:
            value = self.request.query_params.get(field)
            if value:
                filter_kwargs = {f'{field}__icontains': value}
                queryset = queryset.filter(**filter_kwargs)
        
        return queryset


@api_view(['POST'])
@permission_classes([AllowAny])  # Change to [IsAuthenticated] for production
def extract_pico_api(request, pmid):
    """
    Extract PICO elements from an oral health paper's abstract using AI.
    
    Body parameters:
    - provider: LLM provider ('openai', 'anthropic', 'google')
    - force_reextract: boolean to overwrite existing extraction
    """
    try:
        paper = get_object_or_404(Paper, pmid=pmid)
        provider = request.data.get('provider', 'openai')
        force_reextract = request.data.get('force_reextract', False)
        
        # Check if extraction already exists
        if not force_reextract and paper.pico_extractions.exists():
            return Response({
                'error': 'PICO extraction already exists. Use force_reextract=true to overwrite.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not paper.abstract:
            return Response({
                'error': 'Paper has no abstract for PICO extraction.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Perform extraction
        service = PICOExtractionService()
        extractions = service.extract_pico_for_paper(paper)
        
        serializer = PICOExtractionSerializer(extractions, many=True)
        return Response({
            'success': True,
            'message': f'PICO extraction completed using {provider}. {len(extractions)} PICO combinations extracted.',
            'pico_count': len(extractions),
            'data': serializer.data
        })
        
    except Exception as e:
        return Response({
            'error': f'Error extracting PICO: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def statistics_api(request):
    """
    Get comprehensive database statistics for oral health research.
    
    Returns counts and metrics for papers, PICO extractions, and other entities.
    """
    try:
        # Basic counts
        total_papers = Paper.objects.count()
        papers_with_pico = Paper.objects.filter(pico_extractions__isnull=False).count()
        total_authors = Author.objects.count()
        total_journals = Journal.objects.count()
        total_mesh_terms = MeshTerm.objects.count()
        total_pico_extractions = PICOExtraction.objects.count()
        
        # PICO statistics by provider
        pico_by_provider = list(PICOExtraction.objects.values(
            'llm_provider__name'
        ).annotate(count=Count('id')).order_by('-count'))
        
        # PICO statistics by study type
        pico_by_study_type = list(PICOExtraction.objects.exclude(
            study_type__in=['', None]
        ).values('study_type').annotate(count=Count('id')).order_by('-count')[:10])
        
        # Papers by year (last 10 years)
        papers_by_year = list(Paper.objects.exclude(
            publication_year__isnull=True
        ).values('publication_year').annotate(
            count=Count('pmid')
        ).order_by('-publication_year')[:10])
        
        # Top journals with most papers
        top_journals = list(Journal.objects.annotate(
            paper_count=Count('papers')
        ).filter(paper_count__gt=0).order_by('-paper_count')[:10].values(
            'name', 'paper_count'
        ))
        
        # PICO completion rate
        pico_percentage = round((papers_with_pico / total_papers * 100) if total_papers > 0 else 0, 1)
        
        return Response({
            'overview': {
                'total_papers': total_papers,
                'papers_with_pico': papers_with_pico,
                'pico_percentage': pico_percentage,
                'total_authors': total_authors,
                'total_journals': total_journals,
                'total_mesh_terms': total_mesh_terms,
                'total_pico_extractions': total_pico_extractions,
            },
            'pico_by_provider': pico_by_provider,
            'pico_by_study_type': pico_by_study_type,
            'papers_by_year': papers_by_year,
            'top_journals': top_journals,
        })
        
    except Exception as e:
        return Response({
            'error': f'Error retrieving statistics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def available_providers_api(request):
    """
    Get list of available LLM providers for PICO extraction.
    
    Returns provider information including capabilities and costs.
    """
    try:
        providers = LLMProvider.objects.filter(is_active=True).values(
            'name', 'display_name', 'model_name', 'api_cost_per_1k_tokens'
        )
        
        return Response({
            'available_providers': list(providers),
            'supported_providers': ['openai', 'anthropic', 'google'],
            'default_provider': 'openai'
        })
        
    except Exception as e:
        return Response({
            'error': f'Error retrieving providers: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_papers_api(request):
    """
    Advanced paper search with multiple criteria for oral health research.
    
    Query parameters:
    - q: General search query
    - author: Author name
    - journal: Journal name or ID
    - year_from, year_to: Publication year range
    - mesh: MeSH term
    - has_pico: Filter by PICO availability
    - study_type: Filter by study type (if has PICO)
    """
    try:
        query = request.GET.get('q', '')
        author = request.GET.get('author', '')
        journal = request.GET.get('journal', '')
        year_from = request.GET.get('year_from')
        year_to = request.GET.get('year_to')
        mesh = request.GET.get('mesh', '')
        has_pico = request.GET.get('has_pico')
        study_type = request.GET.get('study_type', '')
        
        queryset = Paper.objects.select_related('journal').prefetch_related('authors', 'pico_extractions')
        
        # Apply filters
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(abstract__icontains=query) |
                Q(authors__first_name__icontains=query) |
                Q(authors__last_name__icontains=query)
            )
        
        if author:
            queryset = queryset.filter(
                Q(authors__first_name__icontains=author) |
                Q(authors__last_name__icontains=author)
            )
        
        if journal:
            if journal.isdigit():
                queryset = queryset.filter(journal_id=journal)
            else:
                queryset = queryset.filter(journal__name__icontains=journal)
        
        if year_from:
            queryset = queryset.filter(publication_year__gte=year_from)
        
        if year_to:
            queryset = queryset.filter(publication_year__lte=year_to)
        
        if mesh:
            queryset = queryset.filter(mesh_terms__descriptor_name__icontains=mesh)
        
        if has_pico is not None:
            if has_pico.lower() == 'true':
                queryset = queryset.filter(pico_extractions__isnull=False)
            elif has_pico.lower() == 'false':
                queryset = queryset.filter(pico_extractions__isnull=True)
        
        if study_type:
            queryset = queryset.filter(pico_extractions__study_type=study_type)
        
        queryset = queryset.distinct()
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = PaperListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = PaperListSerializer(queryset, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': f'Error searching papers: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
