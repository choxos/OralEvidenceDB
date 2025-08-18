"""
Views for the oral health research papers app.
"""

import logging
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Case, When, Value, IntegerField, Prefetch
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from django.urls import reverse
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from .models import (
    Paper, Author, Journal, MeshTerm, PICOExtraction, 
    LLMProvider, AuthorPaper, DataImportLog
)

logger = logging.getLogger(__name__)


def dashboard(request):
    """Dashboard view with oral health research statistics."""
    try:
        # Get basic stats
        stats = {
            'total_papers': Paper.objects.count(),
            'papers_with_pico': Paper.objects.filter(pico_extractions__isnull=False).distinct().count(),
            'total_journals': Journal.objects.count(),
        }
        
        # Add papers with shared datasets count
        try:
            papers_with_data = Paper.objects.filter(
                Q(abstract__icontains='github.com') |
                Q(abstract__icontains='data available') |
                Q(abstract__icontains='supplementary') |
                Q(doi__icontains='figshare') |
                Q(doi__icontains='zenodo') |
                Q(doi__icontains='osf.io')
            ).distinct().count()
            stats['papers_with_shared_data'] = papers_with_data
        except:
            stats['papers_with_shared_data'] = 0
        
        # Get recent papers
        recent_papers = Paper.objects.select_related('journal').order_by('-created_at')[:5]
        
        # Get top journals
        top_journals = Journal.objects.annotate(
            paper_count=Count('papers')
        ).filter(paper_count__gt=0).order_by('-paper_count')[:10]
        
        # Get papers by year for chart
        papers_by_year = Paper.objects.filter(
            publication_year__isnull=False,
            publication_year__gte=2010
        ).values('publication_year').annotate(
            count=Count('pmid')
        ).order_by('publication_year')
        
        context = {
            'stats': stats,
            'recent_papers': recent_papers,
            'top_journals': top_journals,
            'papers_by_year': papers_by_year,
        }
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        context = {
            'stats': {
                'total_papers': 0,
                'papers_with_pico': 0,
                'total_journals': 0,
                'papers_with_shared_data': 0,
            },
            'recent_papers': [],
            'top_journals': [],
            'papers_by_year': [],
            'error': str(e)
        }
    
    return render(request, 'papers/dashboard.html', context)


class PaperListView(ListView):
    """
    List view for oral health papers with advanced search and filtering capabilities.
    """
    
    model = Paper
    template_name = 'papers/paper_list.html'
    context_object_name = 'papers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Paper.objects.select_related('journal').prefetch_related('authors')
        
        # Search functionality
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = self._apply_search_filter(queryset, search_query)
        
        # Advanced filtering
        queryset = self._apply_advanced_filters(queryset)
        
        # Ordering
        order_by = self.request.GET.get('order_by', '-publication_date')
        if order_by in ['-publication_date', 'publication_date', 'title', '-pmid']:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('-publication_date')
        
        return queryset.distinct()
    
    def _apply_search_filter(self, queryset, search_query):
        """Apply text search across multiple fields."""
        return queryset.filter(
            Q(title__icontains=search_query) |
            Q(abstract__icontains=search_query) |
            Q(authors__first_name__icontains=search_query) |
            Q(authors__last_name__icontains=search_query) |
            Q(mesh_terms__descriptor_name__icontains=search_query) |
            Q(journal__name__icontains=search_query)
        ).distinct()
    
    def _apply_advanced_filters(self, queryset):
        """Apply various filters based on GET parameters."""
        
        # Journal filter
        journal_id = self.request.GET.get('journal')
        if journal_id:
            try:
                queryset = queryset.filter(journal__id=int(journal_id))
            except ValueError:
                pass
        
        # Year filter
        year = self.request.GET.get('year')
        if year:
            try:
                queryset = queryset.filter(publication_year=int(year))
            except ValueError:
                pass
        
        # Filter by shared data availability
        has_data = self.request.GET.get('has_data')
        if has_data == 'true':
            try:
                # Look for shared data indicators (adapted for oral health)
                queryset = queryset.filter(
                    Q(abstract__icontains='github.com') |
                    Q(abstract__icontains='data available') |
                    Q(abstract__icontains='supplementary material') |
                    Q(abstract__icontains='supplemental material') |
                    Q(abstract__icontains='supporting information') |
                    Q(doi__icontains='figshare') |
                    Q(doi__icontains='zenodo') |
                    Q(doi__icontains='osf.io') |
                    Q(doi__icontains='dryad')
                ).distinct()
            except Exception:
                pass
        
        # Filter by PICO status
        has_pico = self.request.GET.get('has_pico')
        if has_pico == 'true':
            queryset = queryset.filter(pico_extractions__isnull=False).distinct()
        elif has_pico == 'false':
            queryset = queryset.filter(pico_extractions__isnull=True)
        
        # Filter by Associated Data availability 
        has_data = self.request.GET.get('has_data')
        if has_data == 'true':
            # Papers with associated data (GitHub repos, shared datasets, etc.)
            queryset = queryset.filter(
                Q(abstract__icontains='github.com') |
                Q(abstract__icontains='data available') |
                Q(abstract__icontains='supplementary') |
                Q(doi__icontains='figshare') |
                Q(doi__icontains='zenodo') |
                Q(doi__icontains='osf.io')
            ).distinct()
        elif has_data == 'false':
            # Papers without associated data indicators
            queryset = queryset.exclude(
                Q(abstract__icontains='github.com') |
                Q(abstract__icontains='data available') |
                Q(abstract__icontains='supplementary') |
                Q(doi__icontains='figshare') |
                Q(doi__icontains='zenodo') |
                Q(doi__icontains='osf.io')
            )
        
        # Filter by shared data availability
        has_data = self.request.GET.get('has_data')
        if has_data == 'true':
            try:
                # Look for GitHub repositories or shared data indicators
                queryset = queryset.filter(
                    Q(abstract__icontains='github.com') |
                    Q(abstract__icontains='data available') |
                    Q(abstract__icontains='supplementary material') |
                    Q(abstract__icontains='supplemental material') |
                    Q(abstract__icontains='supporting information') |
                    Q(doi__icontains='figshare') |
                    Q(doi__icontains='zenodo') |
                    Q(doi__icontains='osf.io') |
                    Q(doi__icontains='dryad')
                ).distinct()
            except Exception:
                pass
        elif has_data == 'false':
            try:
                # Exclude papers with shared data indicators
                queryset = queryset.exclude(
                    Q(abstract__icontains='github.com') |
                    Q(abstract__icontains='data available') |
                    Q(abstract__icontains='supplementary material') |
                    Q(abstract__icontains='supplemental material') |
                    Q(abstract__icontains='supporting information') |
                    Q(doi__icontains='figshare') |
                    Q(doi__icontains='zenodo') |
                    Q(doi__icontains='osf.io') |
                    Q(doi__icontains='dryad')
                )
            except Exception:
                pass
        
        return queryset
    
    def _filter_by_author(self, queryset, author_search):
        """Filter papers by author name with flexible matching."""
        
        # Handle different author search formats
        author_parts = author_search.strip().split()
        
        if len(author_parts) == 1:
            # Single term - could be first name, last name, or partial name
            term = author_parts[0]
            author_query = (
                Q(first_name__icontains=term) |
                Q(last_name__icontains=term) |
                Q(initials__icontains=term)
            )
        elif len(author_parts) == 2:
            # Two terms - likely first and last name
            first, last = author_parts
            author_query = (
                Q(first_name__icontains=first, last_name__icontains=last) |
                Q(first_name__icontains=last, last_name__icontains=first) |  # Reverse order
                Q(last_name__icontains=f"{last}, {first}") |  # "Last, First" format
                Q(initials__icontains=first, last_name__icontains=last)
            )
        else:
            # Multiple terms - combine all
            combined = " ".join(author_parts)
            author_query = (
                Q(first_name__icontains=combined) |
                Q(last_name__icontains=combined) |
                Q(initials__icontains=combined)
            )
        
        return queryset.filter(author_query).distinct()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['journals'] = Journal.objects.annotate(
            paper_count=Count('papers')
        ).filter(paper_count__gt=0).order_by('name')
        
        context['years'] = Paper.objects.values_list(
            'publication_year', flat=True
        ).distinct().order_by('-publication_year')
        
        # Add all current filter values for the search template
        context['current_search'] = self.request.GET.get('q', '')
        context['current_journal'] = self.request.GET.get('journal', '')
        context['current_year'] = self.request.GET.get('year', '')
        context['current_has_pico'] = self.request.GET.get('has_pico', '')
        context['current_has_data'] = self.request.GET.get('has_data', '')
        context['current_order'] = self.request.GET.get('order_by', '-publication_date')
        
        # Add advanced filter values
        context['filter_values'] = {
            'title': self.request.GET.get('title', ''),
            'pmid': self.request.GET.get('pmid', ''),
            'pmcid': self.request.GET.get('pmcid', ''),
            'doi': self.request.GET.get('doi', ''),
            'author': self.request.GET.get('author', ''),
            'mesh': self.request.GET.get('mesh', ''),
            'publication_type': self.request.GET.get('publication_type', ''),
            'journal_name': self.request.GET.get('journal_name', ''),
            'year_from': self.request.GET.get('year_from', ''),
            'year_to': self.request.GET.get('year_to', ''),
            'language': self.request.GET.get('language', ''),
            'study_type': self.request.GET.get('study_type', ''),
        }
        
        # Calculate search statistics (avoid double query execution)
        total_papers = Paper.objects.count()
        context['total_papers'] = total_papers
        context['filtered_count'] = context['paginator'].count if context['paginator'] else 0
        
        return context


class PaperDetailView(DetailView):
    """Detail view for individual oral health papers."""
    
    model = Paper
    template_name = 'papers/paper_detail.html'
    context_object_name = 'paper'
    slug_field = 'pmid'
    slug_url_kwarg = 'pmid'
    
    def get_queryset(self):
        from django.db.models import Prefetch
        return Paper.objects.select_related('journal').prefetch_related(
            'authorpaper_set__author',
            'mesh_terms',
            Prefetch('pico_extractions', 
                     queryset=PICOExtraction.objects.select_related('llm_provider').order_by('-extracted_at'))
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get ordered authors
        context['author_papers'] = self.object.authorpaper_set.select_related('author').order_by('author_order')
        
        # Get clinical trial links with trial details (with safety check)
        try:
            context['clinical_trial_links'] = self.object.clinical_trials.select_related('clinical_trial').order_by(
                '-created_at', 'clinical_trial__start_date'
            )
        except AttributeError:
            # clinical_trials relationship doesn't exist yet (migrations not run)
            context['clinical_trial_links'] = []
        
        # Check if user has bookmarked this paper
        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                context['is_bookmarked'] = profile.bookmarked_papers.filter(pmid=self.object.pmid).exists()
            except:
                context['is_bookmarked'] = False
        
        # Get associated data for the Associated Data card (focus on shared datasets and GitHub repos)
        associated_data = {
            'shared_datasets': {
                'count': 0,
                'items': []
            }
        }
        
        # Shared Datasets and GitHub Repositories
        try:
            # Extract GitHub URLs and DOIs from abstract and full text
            import re
            
            text_to_search = f"{self.object.abstract or ''} {self.object.title or ''}"
            
            # GitHub repository pattern
            github_pattern = r'github\.com/[\w.-]+/[\w.-]+'
            github_matches = re.findall(github_pattern, text_to_search, re.IGNORECASE)
            
            # Data repository patterns (Figshare, Zenodo, OSF, etc.)
            data_patterns = [
                (r'figshare\.com/\S+', 'Figshare'),
                (r'zenodo\.org/\S+', 'Zenodo'),
                (r'osf\.io/\S+', 'OSF'),
                (r'dryad\.org/\S+', 'Dryad')
            ]
            
            datasets = []
            
            # Add GitHub repositories
            for github_url in github_matches[:3]:  # Limit to first 3
                datasets.append({
                    'title': f"GitHub Repository: {github_url.split('/')[-1]}",
                    'url': f"https://{github_url}",
                    'description': "Code repository",
                    'type': 'github'
                })
            
            # Add data repositories
            for pattern, repo_type in data_patterns:
                matches = re.findall(pattern, text_to_search, re.IGNORECASE)
                for match in matches[:2]:  # Limit each type
                    datasets.append({
                        'title': f"{repo_type} Dataset",
                        'url': match if match.startswith('http') else f"https://{match}",
                        'description': f"Dataset hosted on {repo_type}",
                        'type': repo_type.lower()
                    })
            
            associated_data['shared_datasets'] = {
                'count': len(datasets),
                'items': datasets
            }
        except Exception as e:
            logger.error(f"Error extracting associated data: {e}")

        
        context['associated_data'] = associated_data
        
        return context


class PICOSearchView(ListView):
    """Advanced PICO-based search interface."""
    
    model = Paper
    template_name = 'papers/pico_search.html'
    context_object_name = 'papers'
    paginate_by = 10
    
    def get_queryset(self):
        """Filter papers based on PICO criteria."""
        
        # Start with papers that have PICO extractions
        queryset = Paper.objects.filter(
            pico_extractions__isnull=False
        ).select_related('journal').prefetch_related(
            'pico_extractions__llm_provider', 'authors'
        ).distinct()
        
        # Build PICO filters
        pico_filters = Q()
        
        # Population filter
        population = self.request.GET.get('population')
        if population:
            pico_filters &= Q(pico_extractions__population__icontains=population)
            
        intervention = self.request.GET.get('intervention')
        if intervention:
            pico_filters &= Q(pico_extractions__intervention__icontains=intervention)
            
        comparison = self.request.GET.get('comparison')
        if comparison:
            pico_filters &= Q(pico_extractions__comparison__icontains=comparison)
            
        outcome = self.request.GET.get('outcome')
        if outcome:
            pico_filters &= Q(pico_extractions__outcome__icontains=outcome)
            
        setting = self.request.GET.get('setting')
        if setting:
            pico_filters &= Q(pico_extractions__setting__icontains=setting)
            
        timeframe = self.request.GET.get('timeframe')
        if timeframe:
            pico_filters &= Q(pico_extractions__timeframe__icontains=timeframe)
        
        # Study type filter
        study_type = self.request.GET.get('study_type')
        if study_type:
            pico_filters &= Q(pico_extractions__study_type=study_type)
        
        # LLM provider filter
        llm_provider = self.request.GET.get('llm_provider')
        if llm_provider:
            pico_filters &= Q(pico_extractions__llm_provider__name=llm_provider)
        
        # Publication year filter
        year = self.request.GET.get('year')
        if year:
            pico_filters &= Q(publication_year=year)
        
        # Apply filters
        if pico_filters:
            queryset = queryset.filter(pico_filters)
        
        # Order by relevance (papers with more recent PICO extractions first)
        return queryset.order_by('-pico_extractions__extracted_at', '-publication_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get available filter options from existing PICO extractions
        from django.core.cache import cache
        
        # Cache expensive queries for filter options
        context['filter_options'] = cache.get_or_set(
            'pico_filter_options',
            self._get_filter_options,
            timeout=300  # 5 minutes
        )
        
        # Add current search parameters
        context['current_filters'] = {
            'population': self.request.GET.get('population', ''),
            'intervention': self.request.GET.get('intervention', ''),
            'comparison': self.request.GET.get('comparison', ''),
            'outcome': self.request.GET.get('outcome', ''),
            'setting': self.request.GET.get('setting', ''),
            'timeframe': self.request.GET.get('timeframe', ''),
            'study_type': self.request.GET.get('study_type', ''),
            'llm_provider': self.request.GET.get('llm_provider', ''),
            'year': self.request.GET.get('year', ''),
        }
        
        # Add summary statistics
        context['stats'] = cache.get_or_set(
            'pico_basic_stats',
            lambda: {
                'total_papers_with_pico': Paper.objects.filter(pico_extractions__isnull=False).distinct().count(),
                'total_picos': PICOExtraction.objects.count(),
            },
            timeout=300  # 5 minutes
        )

        return context
    
    def _get_filter_options(self):
        """Get available values for PICO filter dropdowns."""
        
        # Get common PICO terms from existing extractions
        pico_data = PICOExtraction.objects.values_list(
            'population', 'intervention', 'comparison', 'outcome',
            'setting', 'timeframe', 'study_type'
        ).distinct()
        
        # Extract and clean unique terms
        populations = set()
        interventions = set()
        comparisons = set()
        outcomes = set()
        settings = set()
        timeframes = set()
        study_types = set()
        
        for p, i, c, o, s, t, st in pico_data:
            if p: populations.update(term.strip() for term in p.split(',')[:3])  # Limit splits
            if i: interventions.update(term.strip() for term in i.split(',')[:3])
            if c: comparisons.update(term.strip() for term in c.split(',')[:3])
            if o: outcomes.update(term.strip() for term in o.split(',')[:3])
            if s: settings.update(term.strip() for term in s.split(',')[:3])
            if t: timeframes.update(term.strip() for term in t.split(',')[:3])
            if st: study_types.add(st.strip())
        
        return {
            'populations': sorted([p for p in populations if len(p) > 2])[:50],
            'interventions': sorted([i for i in interventions if len(i) > 2])[:50],
            'comparisons': sorted([c for c in comparisons if len(c) > 2])[:50],
            'outcomes': sorted([o for o in outcomes if len(o) > 2])[:50],
            'settings': sorted([s for s in settings if len(s) > 2])[:20],
            'timeframes': sorted([t for t in timeframes if len(t) > 2])[:20],
            'study_types': sorted(study_types)[:20],
            'llm_providers': list(LLMProvider.objects.values_list('name', flat=True)),
            'years': list(Paper.objects.filter(
                pico_extractions__isnull=False
            ).values_list('publication_year', flat=True).distinct().order_by('-publication_year'))
        }


@require_POST
@csrf_exempt
def extract_pico_ajax(request, pmid):
    """AJAX endpoint for PICO extraction."""
    try:
        paper = get_object_or_404(Paper, pmid=pmid)
        
        if not paper.abstract:
            return JsonResponse({
                'status': 'error',
                'message': 'No abstract available for PICO extraction'
            })
        
        # Import here to avoid circular imports
        from .llm_extractors import extract_pico_from_abstract
        
        # Extract PICO using LLM
        pico_data = extract_pico_from_abstract(paper)
        
        if pico_data:
            return JsonResponse({
                'status': 'success',
                'message': 'PICO extracted successfully',
                'pico_data': pico_data
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to extract PICO elements'
            })
            
    except Exception as e:
        logger.error(f"PICO extraction error for paper {pmid}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error during PICO extraction: {str(e)}'
        })


@login_required
@require_POST
def bookmark_paper(request, pmid):
    """Toggle bookmark status for a paper."""
    try:
        paper = get_object_or_404(Paper, pmid=pmid)
        
        # Get or create user profile
        profile, created = request.user.profile, False
        try:
            profile = request.user.profile
        except:
            from .models import UserProfile
            profile = UserProfile.objects.create(user=request.user)
        
        # Toggle bookmark
        if profile.bookmarked_papers.filter(pmid=pmid).exists():
            profile.bookmarked_papers.remove(paper)
            bookmarked = False
            message = "Bookmark removed"
        else:
            profile.bookmarked_papers.add(paper)
            bookmarked = True
            message = "Paper bookmarked"
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'bookmarked': bookmarked,
                'message': message
            })
        else:
            messages.success(request, message)
            return redirect('papers:detail', pmid=pmid)
            
    except Exception as e:
        logger.error(f"Bookmark error: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Error updating bookmark'
            })
        else:
            messages.error(request, "Error updating bookmark")
            return redirect('papers:detail', pmid=pmid)


def search_suggestions(request):
    """AJAX endpoint for search suggestions."""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 3:
        return JsonResponse({'suggestions': []})
    
    try:
        # Get paper title suggestions
        paper_titles = Paper.objects.filter(
            title__icontains=query
        ).values_list('title', flat=True)[:5]
        
        # Get author suggestions
        author_names = Author.objects.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query)
        ).values_list('last_name', 'first_name')[:5]
        
        # Get MeSH term suggestions
        mesh_terms = MeshTerm.objects.filter(
            descriptor_name__icontains=query
        ).values_list('descriptor_name', flat=True)[:5]
        
        suggestions = []
        
        # Add paper title suggestions
        for title in paper_titles:
            suggestions.append({
                'type': 'title',
                'text': title[:100],
                'category': 'Papers'
            })
        
        # Add author suggestions
        for last_name, first_name in author_names:
            full_name = f"{first_name} {last_name}".strip()
            if full_name:
                suggestions.append({
                    'type': 'author',
                    'text': full_name,
                    'category': 'Authors'
                })
        
        # Add MeSH term suggestions
        for term in mesh_terms:
            suggestions.append({
                'type': 'mesh',
                'text': term,
                'category': 'MeSH Terms'
            })
        
        return JsonResponse({'suggestions': suggestions[:15]})
        
    except Exception as e:
        logger.error(f"Search suggestions error: {str(e)}")
        return JsonResponse({'suggestions': []})


def toggle_theme(request):
    """Toggle between light and dark themes."""
    if request.method == 'POST':
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                current_theme = profile.preferred_theme
            except:
                # Create profile if it doesn't exist
                from .models import UserProfile
                profile = UserProfile.objects.create(user=request.user, preferred_theme='light')
                current_theme = 'light'
            
            new_theme = 'dark' if current_theme == 'light' else 'light'
            profile.preferred_theme = new_theme
            profile.save()
        else:
            # For anonymous users, use session storage
            current_theme = request.session.get('theme', 'light')
            new_theme = 'dark' if current_theme == 'light' else 'light'
            request.session['theme'] = new_theme
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'new_theme': new_theme
            })
    
    return redirect(request.META.get('HTTP_REFERER', '/'))


def about(request):
    """About page for the OralEvidenceDB project."""
    return render(request, 'papers/about.html')


class RetractionsListView(ListView):
    """List view for retracted papers with filtering and search."""
    
    template_name = 'papers/retractions_list.html'
    context_object_name = 'retracted_papers'
    paginate_by = 20
    
    def get_queryset(self):
        try:
            from .models_retraction import RetractedPaper
            
            # Base queryset
            queryset = RetractedPaper.objects.all().order_by('-retraction_date')
            
            # Search functionality
            search_query = self.request.GET.get('q', '').strip()
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(authors__icontains=search_query) |
                    Q(journal__icontains=search_query) |
                    Q(reason__icontains=search_query)
                )
            
            # Journal filter
            journal = self.request.GET.get('journal', '').strip()
            if journal:
                queryset = queryset.filter(journal__icontains=journal)
            
            # Year filter
            year = self.request.GET.get('year', '').strip()
            if year:
                try:
                    queryset = queryset.filter(retraction_date__year=int(year))
                except ValueError:
                    pass
            
            # Reason filter
            reason = self.request.GET.get('reason', '').strip()
            if reason:
                queryset = queryset.filter(reason__icontains=reason)
            
            return queryset
        except ImportError:
            # RetractedPaper model not available
            return RetractedPaper.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            from .models_retraction import RetractedPaper
            from .models_citation import CitationData
            from django.db.models import Sum, Count, Avg, Q
            
            # Basic statistics
            context['total_retractions'] = RetractedPaper.objects.count()
            context['recent_retractions'] = RetractedPaper.objects.filter(
                retraction_date__gte=timezone.now() - timedelta(days=365)
            ).count()
            
            # Top journals by retraction count
            context['top_journals'] = RetractedPaper.objects.values('journal').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Top reasons for retraction
            context['top_reasons'] = RetractedPaper.objects.exclude(
                reason__isnull=True
            ).exclude(
                reason__exact=''
            ).values('reason').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Get papers with highest citation counts
            context['most_cited_retracted'] = RetractedPaper.objects.exclude(
                total_citations__isnull=True
            ).order_by('-total_citations')[:10]

            
            # Get papers with post-retraction citations
            context['post_retraction_citations'] = CitationData.objects.select_related(
                'retracted_paper'
            ).filter(
                post_retraction_citations__gt=0
            ).order_by('-post_retraction_citations')[:10]
            
            # Citation summary statistics
            citation_stats = CitationData.objects.aggregate(
                total_papers_with_citations=Count('id'),
                total_citations=Sum('total_citations'),
                total_post_retraction_citations=Sum('post_retraction_citations'),
                papers_with_post_retraction=Count('id', filter=Q(post_retraction_citations__gt=0))
            )
            context['citation_stats'] = citation_stats
        except Exception:
            # Citation models not available or other error
            context['most_problematic_papers'] = []
            context['post_retraction_citations'] = []
            context['citation_stats'] = {}
        
        context['has_filters'] = bool(self.request.GET)
        
        return context


def evidence_gaps(request):
    """Evidence Gaps page showing Cochrane SoF analysis with consolidated reviews."""
    from django.core.paginator import Paginator
    from django.db import connection
    import re
    from collections import defaultdict, OrderedDict
    
    def extract_base_review_id(review_id):
        """Extract base review ID (e.g., CD000253 from CD000253.PUB3)"""
        match = re.match(r'(CD\d+)', review_id)
        return match.group(1) if match else review_id
    
    def get_version_number(review_id):
        """Extract version number for sorting (PUB3 -> 3, no PUB -> 0)"""
        match = re.search(r'\.PUB(\d+)$', review_id)
        return int(match.group(1)) if match else 0
    
    try:
        cursor = connection.cursor()
        
        # Build base query - use original comments as downgrade reasons
        base_query = """
        SELECT *, 
               CASE 
                   WHEN grade_rating = 'High' THEN 'None'
                   WHEN grade_rating = 'No Evidence Yet' THEN 'N/A'
                   WHEN comments IS NOT NULL AND comments != '' THEN comments
                   ELSE 'Not specified'
               END as downgrade_reason_summary
        FROM evidence_gaps
        WHERE 1=1
        """
        params = []
        
        # Apply filters
        search = request.GET.get('q', '').strip()
        if search:
            base_query += " AND (review_title ILIKE %s OR population ILIKE %s OR intervention ILIKE %s OR comparison ILIKE %s OR outcome ILIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param] * 5)
        
        grade = request.GET.get('grade', '').strip()
        if grade:
            base_query += " AND grade_rating = %s"
            params.append(grade)
        
        population = request.GET.get('population', '').strip()
        if population:
            base_query += " AND population = %s"
            params.append(population)
        
        intervention = request.GET.get('intervention', '').strip()
        if intervention:
            base_query += " AND intervention = %s"
            params.append(intervention)
        
        # Order by review title for better grouping
        base_query += " ORDER BY review_title, review_id DESC, grade_rating, population, intervention"
        
        # Execute main query with dictfetchall
        cursor.execute(base_query, params)
        columns = [col[0] for col in cursor.description]
        evidence_gaps = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Group evidence gaps by base review ID
        grouped_reviews = defaultdict(lambda: {
            'base_id': '',
            'latest_title': '',
            'latest_year': '',
            'latest_authors': '',
            'latest_doi': '',
            'versions': defaultdict(list)
        })
        
        for gap in evidence_gaps:
            base_id = extract_base_review_id(gap['review_id'])
            version_num = get_version_number(gap['review_id'])
            
            # Update latest title info if this is a newer version
            if (not grouped_reviews[base_id]['latest_title'] or 
                version_num > get_version_number(grouped_reviews[base_id]['base_id'])):
                grouped_reviews[base_id]['base_id'] = gap['review_id']
                grouped_reviews[base_id]['latest_title'] = gap.get('review_title', '') or base_id
                grouped_reviews[base_id]['latest_year'] = gap.get('year', '')
                grouped_reviews[base_id]['latest_authors'] = gap.get('authors', '')
                grouped_reviews[base_id]['latest_doi'] = gap.get('doi', '')
            
            # Group PICOs by version
            grouped_reviews[base_id]['versions'][gap['review_id']].append(gap)
        
        # Convert to ordered list and sort versions within each review
        consolidated_reviews = []
        for base_id, review_data in grouped_reviews.items():
            # Sort versions by version number (descending, so latest first)
            sorted_versions = OrderedDict()
            for version_id in sorted(review_data['versions'].keys(), 
                                   key=get_version_number, reverse=True):
                sorted_versions[version_id] = review_data['versions'][version_id]
            
            review_data['versions'] = sorted_versions
            review_data['total_picos'] = sum(len(picos) for picos in sorted_versions.values())
            consolidated_reviews.append(review_data)
        
        # Sort consolidated reviews by latest title
        consolidated_reviews.sort(key=lambda x: x['latest_title'])
        
        # Pagination
        paginator = Paginator(consolidated_reviews, 20)  # Show more per page with collapsible tables
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get summary statistics
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT review_id) as total_reviews,
                COUNT(*) as total_outcomes
            FROM evidence_gaps
        """)
        stats_row = cursor.fetchone()
        total_reviews = stats_row[0]
        total_outcomes = stats_row[1]
        
        # Count distinct base reviews
        base_reviews = len(set(extract_base_review_id(gap['review_id']) for gap in evidence_gaps))
        
        # Get grade distribution with specific order
        cursor.execute("""
            SELECT grade_rating, COUNT(*) as count 
            FROM evidence_gaps 
            GROUP BY grade_rating
        """)
        grade_columns = [col[0] for col in cursor.description]
        grade_stats = [dict(zip(grade_columns, row)) for row in cursor.fetchall()]
        
        # Get downgrading reasons statistics for LATEST VERSIONS ONLY
        # First, get the latest version ID for each review series
        latest_versions = []
        for base_id, review_data in grouped_reviews.items():
            # Get the latest version (highest version number)
            latest_version_id = max(review_data['versions'].keys(), key=get_version_number)
            latest_versions.append(latest_version_id)
        
        if latest_versions:
            # Create placeholders for the IN clause
            placeholders = ','.join(['%s'] * len(latest_versions))
            cursor.execute(f"""
                SELECT 
                    SUM(CASE WHEN risk_of_bias = true THEN 1 ELSE 0 END) as risk_of_bias_count,
                    SUM(CASE WHEN imprecision = true THEN 1 ELSE 0 END) as imprecision_count,
                    SUM(CASE WHEN inconsistency = true THEN 1 ELSE 0 END) as inconsistency_count,
                    SUM(CASE WHEN indirectness = true THEN 1 ELSE 0 END) as indirectness_count,
                    SUM(CASE WHEN publication_bias = true THEN 1 ELSE 0 END) as publication_bias_count,
                    COUNT(*) as total_picos
                FROM evidence_gaps 
                WHERE review_id IN ({placeholders}) 
                  AND grade_rating != 'High' AND grade_rating != 'No Evidence Yet'
            """, latest_versions)
            downgrade_stats_row = cursor.fetchone()
        else:
            downgrade_stats_row = (0, 0, 0, 0, 0, 0)
        
        # Calculate downgrading reasons with percentages
        downgrade_reasons = {}
        if downgrade_stats_row and downgrade_stats_row[5] > 0:  # total_picos > 0
            total_downgraded = downgrade_stats_row[5]
            downgrade_reasons = {
                'risk_of_bias': {
                    'count': downgrade_stats_row[0],
                    'percentage': round((downgrade_stats_row[0] / total_downgraded) * 100, 1)
                },
                'imprecision': {
                    'count': downgrade_stats_row[1], 
                    'percentage': round((downgrade_stats_row[1] / total_downgraded) * 100, 1)
                },
                'inconsistency': {
                    'count': downgrade_stats_row[2],
                    'percentage': round((downgrade_stats_row[2] / total_downgraded) * 100, 1)
                },
                'indirectness': {
                    'count': downgrade_stats_row[3],
                    'percentage': round((downgrade_stats_row[3] / total_downgraded) * 100, 1)
                },
                'publication_bias': {
                    'count': downgrade_stats_row[4],
                    'percentage': round((downgrade_stats_row[4] / total_downgraded) * 100, 1)
                }
            }
        
        # Order grades properly: High, Moderate, Low, Very Low, No Evidence Yet
        grade_order = ['High', 'Moderate', 'Low', 'Very Low', 'No Evidence Yet']
        grade_counts = OrderedDict()
        
        # Add grades in the specified order
        for grade in grade_order:
            for stat in grade_stats:
                if stat['grade_rating'] == grade:
                    grade_counts[grade] = stat['count']
                    break
            else:
                grade_counts[grade] = 0  # Add with 0 count if not found
        
        # Get unique populations and interventions for filters
        cursor.execute("SELECT DISTINCT population FROM evidence_gaps WHERE population IS NOT NULL AND population != '' ORDER BY population")
        populations = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT intervention FROM evidence_gaps WHERE intervention IS NOT NULL AND intervention != '' ORDER BY intervention")  
        interventions = [row[0] for row in cursor.fetchall()]
        
        # Transform data for template
        structured_data = []
        for review in page_obj:
            # Get latest version data
            latest_version_key = list(review['versions'].keys())[0]
            latest_picos = review['versions'][latest_version_key]
            
            # Count evidence gaps (Low, Very Low, No Evidence Yet)
            evidence_gaps_count = sum(1 for pico in latest_picos 
                                    if pico['grade_rating'] in ['Low', 'Very Low', 'No Evidence Yet'])
            
            # Structure older versions
            older_versions_data = []
            for version_key in list(review['versions'].keys())[1:]:  # Skip first (latest)
                version_picos = review['versions'][version_key]
                if version_picos:  # Only add if has PICOs
                    older_versions_data.append({
                        'review_id': version_key,
                        'publication_year': version_picos[0].get('year', ''),
                        'doi': version_picos[0].get('doi', ''),
                        'picos': version_picos
                    })
            
            structured_data.append({
                'current': {
                    'review_id': latest_version_key,
                    'review_title': review['latest_title'],
                    'publication_year': review['latest_year'],
                    'doi': review['latest_doi']
                },
                'current_picos': latest_picos,
                'evidence_gaps_count': evidence_gaps_count,
                'older_versions': older_versions_data
            })
        
        context = {
            'evidence_gaps': structured_data,
            'page_obj': page_obj,
            'total_outcomes': total_outcomes,
            'base_reviews': base_reviews,
            'grade_counts': grade_counts,
            'downgrade_reasons': downgrade_reasons,
            'populations': populations,
            'interventions': interventions,
            'current_search': request.GET.get('q', ''),
            'current_grade': request.GET.get('grade', ''),
            'current_population': request.GET.get('population', ''),
            'current_intervention': request.GET.get('intervention', ''),
            'current_order': request.GET.get('order_by', 'review_title'),
        }
        
    except Exception as e:
        # Handle database errors gracefully
        context = {
            'evidence_gaps': [],
            'error': f"Database error: {str(e)}",
            'total_outcomes': 0,
            'base_reviews': 0,
            'grade_counts': {},
            'downgrade_reasons': {},
            'populations': [],
            'interventions': [],
            'current_search': request.GET.get('q', ''),
            'current_grade': request.GET.get('grade', ''),
            'current_population': request.GET.get('population', ''),
            'current_intervention': request.GET.get('intervention', ''),
            'current_order': request.GET.get('order_by', 'review_title'),
        }
    
    return render(request, 'papers/evidence_gaps.html', context)