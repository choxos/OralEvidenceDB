"""
Views for the oral health papers application.

This module contains Django views for displaying and managing
oral health research papers, PICO extractions, and related data.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch, Max, Sum
from django.http import JsonResponse
from django.views.generic import ListView, DetailView
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse_lazy

from .models import Paper, Author, Journal, PICOExtraction, MeshTerm, DataImportLog
from .llm_extractors import PICOExtractionService, LLMExtractorFactory


class PaperListView(ListView):
    """Comprehensive search interface for oral health papers like an academic indexing website."""
    
    model = Paper
    template_name = 'papers/search.html'
    context_object_name = 'papers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Paper.objects.select_related('journal').prefetch_related(
            'authors',
            'mesh_terms',
            'pico_extractions'  # Prefetch PICO data
        ).annotate(
            author_count=Count('authors', distinct=True),
            mesh_count=Count('mesh_terms', distinct=True)
        )
        
        # General search functionality
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(abstract__icontains=search_query) |
                Q(authors__first_name__icontains=search_query) |
                Q(authors__last_name__icontains=search_query) |
                Q(journal__name__icontains=search_query) |
                Q(journal__abbreviation__icontains=search_query) |
                Q(mesh_terms__descriptor_name__icontains=search_query)
            ).distinct()
        
        # Specific field searches
        title_search = self.request.GET.get('title', '').strip()
        if title_search:
            queryset = queryset.filter(title__icontains=title_search)
        
        pmid_search = self.request.GET.get('pmid', '').strip()
        if pmid_search:
            try:
                queryset = queryset.filter(pmid=int(pmid_search))
            except ValueError:
                queryset = queryset.none()  # Invalid PMID
        
        pmcid_search = self.request.GET.get('pmcid', '').strip()
        if pmcid_search:
            queryset = queryset.filter(pmc__icontains=pmcid_search)
        
        doi_search = self.request.GET.get('doi', '').strip()
        if doi_search:
            queryset = queryset.filter(doi__icontains=doi_search)
        
        nct_id_search = self.request.GET.get('nct_id', '').strip()
        if nct_id_search:
            try:
                # Search for papers linked to clinical trials with this NCT ID
                queryset = queryset.filter(clinical_trials__clinical_trial__nct_id__icontains=nct_id_search)
            except Exception:
                # clinical_trials relationship doesn't exist yet (migrations not run)
                # Return empty queryset to avoid breaking the search
                queryset = queryset.none()
        
        author_search = self.request.GET.get('author', '').strip()
        if author_search:
            queryset = self._filter_by_author(queryset, author_search)
        
        mesh_search = self.request.GET.get('mesh', '').strip()
        if mesh_search:
            queryset = queryset.filter(
                mesh_terms__descriptor_name__icontains=mesh_search
            ).distinct()
        
        publication_type = self.request.GET.get('publication_type', '').strip()
        if publication_type:
            queryset = queryset.filter(publication_types__icontains=publication_type)
        
        language = self.request.GET.get('language', '').strip()
        if language:
            queryset = queryset.filter(language__icontains=language)
        
        # Filter by journal
        journal_name = self.request.GET.get('journal_name', '').strip()
        if journal_name:
            queryset = queryset.filter(
                Q(journal__name__icontains=journal_name) |
                Q(journal__abbreviation__icontains=journal_name)
            )
            
        journal_id = self.request.GET.get('journal')
        if journal_id:
            queryset = queryset.filter(journal_id=journal_id)
        
        # Date range filters
        year = self.request.GET.get('year')
        if year:
            queryset = queryset.filter(publication_year=year)
        
        year_from = self.request.GET.get('year_from')
        if year_from:
            try:
                queryset = queryset.filter(publication_year__gte=int(year_from))
            except ValueError:
                pass
        
        year_to = self.request.GET.get('year_to')
        if year_to:
            try:
                queryset = queryset.filter(publication_year__lte=int(year_to))
            except ValueError:
                pass
        
        # Filter by PICO status
        has_pico = self.request.GET.get('has_pico')
        if has_pico == 'true':
            queryset = queryset.filter(pico_extractions__isnull=False).distinct()
        elif has_pico == 'false':
            queryset = queryset.filter(pico_extractions__isnull=True)
        
        # Filter by shared data availability
        has_data = self.request.GET.get('has_data')
        if has_data == 'true':
            try:
                from .models_shared_data import DatasetPaperLink
                queryset = queryset.filter(dataset_links__isnull=False).distinct()
            except ImportError:
                # Dataset models not available
                pass
        elif has_data == 'false':
            try:
                from .models_shared_data import DatasetPaperLink
                queryset = queryset.filter(dataset_links__isnull=True)
            except ImportError:
                # Dataset models not available
                pass
        
        # Filter by retraction status
        retraction_status = self.request.GET.get('retraction_status')
        if retraction_status == 'retracted':
            # Filter for papers that have retraction records
            from .models_retraction import RetractedPaper
            retracted_pmids = RetractedPaper.objects.values_list('original_pubmed_id', flat=True)
            queryset = queryset.filter(pmid__in=retracted_pmids)
        elif retraction_status == 'not_retracted':
            # Filter for papers that do NOT have retraction records
            from .models_retraction import RetractedPaper
            retracted_pmids = RetractedPaper.objects.values_list('original_pubmed_id', flat=True)
            queryset = queryset.exclude(pmid__in=retracted_pmids)
        
        # Study type filter (using new study type classifications)
        study_type = self.request.GET.get('study_type')
        if study_type:
            # Filter papers where the study_type_classifications JSONField contains the selected study type
            queryset = queryset.filter(
                Q(study_type_classifications__isnull=False) &
                Q(study_type_classifications__regex=rf'"classification":\s*"{study_type}"')
            )
        
        # Ordering
        order_by = self.request.GET.get('order_by', '-publication_date')
        valid_orders = ['-publication_date', 'publication_date', '-pmid', 'pmid', 'title', '-title', 'journal__name']
        if order_by in valid_orders:
            queryset = queryset.order_by(order_by)
        
        return queryset.distinct()
    
    def _filter_by_author(self, queryset, author_search):
        """Enhanced author search that handles full names, initials, and partial matches."""
        import re
        
        # Clean the search term
        author_search = author_search.strip()
        
        # Split the search term into parts
        name_parts = re.split(r'[\s,]+', author_search)
        name_parts = [part.strip() for part in name_parts if part.strip()]
        
        if not name_parts:
            return queryset
        
        # Priority-based search strategies (from most specific to least)
        author_query = Q()
        
        if len(name_parts) == 1:
            # Single name - could be first or last name
            single_name = name_parts[0]
            if len(single_name) == 1:
                # Single letter - treat as initial
                author_query = (
                    Q(authors__first_name__istartswith=single_name) |
                    Q(authors__last_name__istartswith=single_name) |
                    Q(authors__middle_initials__icontains=single_name)
                )
            else:
                # Full word - search first and last names
                author_query = (
                    Q(authors__first_name__icontains=single_name) |
                    Q(authors__last_name__icontains=single_name)
                )
        
        elif len(name_parts) == 2:
            first_part, second_part = name_parts[0], name_parts[1]
            
            # Strategy 1: Exact first + last name match (highest priority)
            author_query |= Q(authors__first_name__iexact=first_part) & Q(authors__last_name__iexact=second_part)
            
            # Strategy 2: Case-insensitive exact matches
            author_query |= Q(authors__first_name__iexact=first_part) & Q(authors__last_name__iexact=second_part)
            
            # Strategy 3: Handle initials + last name (e.g., "S Park" or "Park S")
            if len(first_part) == 1:
                # First initial + last name: "S Park"
                author_query |= Q(authors__first_name__istartswith=first_part) & Q(authors__last_name__iexact=second_part)
            elif len(second_part) == 1:
                # Last name + first initial: "Park S"
                author_query |= Q(authors__last_name__iexact=first_part) & Q(authors__first_name__istartswith=second_part)
            
            # Strategy 4: Partial matches (only if parts are substantial)
            if len(first_part) > 2 and len(second_part) > 2:
                author_query |= Q(authors__first_name__icontains=first_part) & Q(authors__last_name__icontains=second_part)
        
        elif len(name_parts) == 3:
            first_part, middle_part, last_part = name_parts[0], name_parts[1], name_parts[2]
            
            # Strategy 1: First + Middle + Last
            author_query |= (
                Q(authors__first_name__iexact=first_part) &
                Q(authors__middle_initials__icontains=middle_part.replace('.', '')) &
                Q(authors__last_name__iexact=last_part)
            )
            
            # Strategy 2: First + Last (ignore middle)
            author_query |= Q(authors__first_name__iexact=first_part) & Q(authors__last_name__iexact=last_part)
            
            # Strategy 3: Partial matches for substantial names
            if all(len(part) > 2 for part in [first_part, last_part]):
                author_query |= Q(authors__first_name__icontains=first_part) & Q(authors__last_name__icontains=last_part)
        
        else:
            # Handle more complex names (4+ parts)
            # Assume first part is first name, last part is last name
            first_name = name_parts[0]
            last_name = name_parts[-1]
            middle_parts = name_parts[1:-1]
            
            # Exact match for first and last
            author_query |= Q(authors__first_name__iexact=first_name) & Q(authors__last_name__iexact=last_name)
            
            # Include middle initials if present
            for middle in middle_parts:
                if middle and len(middle) <= 3:
                    author_query |= (
                        Q(authors__first_name__iexact=first_name) &
                        Q(authors__last_name__iexact=last_name) &
                        Q(authors__middle_initials__icontains=middle.replace('.', ''))
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
        context['filtered_count'] = context['paginator'].count if hasattr(context, 'paginator') else 0
        context['has_active_filters'] = bool(any(self.request.GET.values()))
        
        # Add hierarchical study type options from our enhanced classifier
        from .study_type_classifier import StudyClassification
        
        # Define categories and their study types for oral health research
        study_type_categories = {
            'Observational Studies': [
                'cohort_study',
                'case_control_study', 
                'cross_sectional_study',
                'target_trial_emulation',
                'case_series'
            ],
            'Interventional Studies': [
                'clinical_trial',  # Meta-category for all clinical trials
                'pilot_study',
                'single_arm_trial'
            ],
            'Evidence Synthesis': [
                'systematic_review',
                'meta_analysis',
                'network_meta_analysis',
                'matching_adjusted_indirect_comparison',
                'simulated_treatment_comparison',
                'multilevel_network_meta_regression'
            ],
            'Other Study Types': [
                'animal_studies',
                'economic_evaluations', 
                'guidelines',
                'patient_perspectives',
                'qualitative_studies',
                'surveys_questionnaires'
            ]
        }
        
        # Clinical trial sub-types for hierarchical selection
        clinical_trial_subtypes = [
            {'value': 'randomized_controlled_trial', 'label': 'Randomized Controlled Trial (RCT)', 'group': 'randomization'},
            {'value': 'controlled_clinical_trial', 'label': 'Controlled Clinical Trial (CCT)', 'group': 'randomization'},
            {'value': 'placebo_controlled_rct', 'label': 'Placebo-Controlled', 'group': 'control'},
            {'value': 'single_blind_rct', 'label': 'Single-Blind', 'group': 'blinding'},
            {'value': 'double_blind_rct', 'label': 'Double-Blind', 'group': 'blinding'},
            {'value': 'triple_blind_rct', 'label': 'Triple-Blind', 'group': 'blinding'},
            {'value': 'open_label_rct', 'label': 'Open-Label', 'group': 'blinding'}
        ]
        
        def get_human_readable_label(value):
            """Convert classification value to human-readable label"""
            label = value.replace('_', ' ').title()
            # Fix specific capitalization
            replacements = {
                'Rct': 'RCT', 'Cct': 'CCT', 'Meta Analysis': 'Meta-Analysis', 
                'Network Meta Analysis': 'Network Meta-Analysis',
                'Multilevel Network Meta Regression': 'Multilevel Network Meta-Regression',
                'Maic': 'MAIC', 'Stc': 'STC', 'Mlnmr': 'MLNMR', 'Pico': 'PICO'
            }
            for old, new in replacements.items():
                label = label.replace(old, new)
            return label
        
        # Build categorized options
        categorized_options = []
        for category, study_types in study_type_categories.items():
            category_options = []
            for study_type in study_types:
                if study_type == 'clinical_trial':
                    # Special handling for clinical trial meta-category
                    category_options.append({
                        'value': 'clinical_trial',
                        'label': 'Clinical Trial'
                    })
                else:
                    # Check if this study type exists in our classifier
                    try:
                        from .study_type_classifier import StudyClassification
                        for classification in StudyClassification:
                            if classification.value == study_type:
                                category_options.append({
                                    'value': study_type,
                                    'label': get_human_readable_label(study_type)
                                })
                                break
                    except ImportError:
                        # Fallback if classifier is not available
                        category_options.append({
                            'value': study_type,
                            'label': get_human_readable_label(study_type)
                        })
            
            if category_options:  # Only add categories that have options
                categorized_options.append({
                    'category': category,
                    'options': category_options
                })
        
        context['study_type_categories'] = categorized_options
        context['clinical_trial_subtypes'] = clinical_trial_subtypes
        
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
            from .models import DatasetPaperLink, SharedDataset
            dataset_links = DatasetPaperLink.objects.filter(
                paper_id=self.object.pmid
            ).select_related(
                'dataset', 'dataset__repository'
            ).filter(
                confidence_score__gt=0.3  # Only show confident matches
            ).order_by('-confidence_score', '-created_at')[:10]  # Show top 10
            
            if dataset_links:
                associated_data['shared_datasets']['count'] = dataset_links.count()
                associated_data['shared_datasets']['items'] = []
                
                for link in dataset_links:
                    dataset_item = {
                        'title': link.dataset.title or 'Untitled Dataset',
                        'url': link.dataset.url,
                        'repository': link.dataset.repository.display_name if link.dataset.repository else 'Unknown',
                        'repository_name': link.dataset.repository.name if link.dataset.repository else 'unknown',
                        'confidence': link.confidence_score,
                        'link_type': link.link_type.replace('_', ' ').title(),
                        'access_status': getattr(link.dataset, 'access_status', 'unknown'),
                        'license': getattr(link.dataset, 'license', None),
                        'resource_type': getattr(link.dataset, 'resource_type', None),
                        'file_count': getattr(link.dataset, 'file_count', None),
                        'storage_size': getattr(link.dataset, 'storage_size', None)
                    }
                    associated_data['shared_datasets']['items'].append(dataset_item)
        except Exception as e:
            # Dataset relationship doesn't exist or other error
            pass
        
        context['associated_data'] = associated_data
        
        return context


def dashboard(request):
    """Dashboard view with statistics and recent activity for oral health research."""
    from django.core.cache import cache
    from .models_retraction import RetractedPaper
    
    # Cache expensive statistics for 5 minutes
    stats = None
    try:
        stats = cache.get('dashboard_stats')
    except Exception:
        # Cache is not available, continue without caching
        pass
        
    if stats is None:
        # Use efficient aggregate queries instead of counting all rows
        stats = {
            'total_papers': Paper.objects.count(),
            'papers_with_pico': Paper.objects.filter(pico_extractions__isnull=False).distinct().count(),
            'total_journals': Journal.objects.count(),
        }
        
        # Add papers with shared datasets count
        try:
            from .models_shared_data import DatasetPaperLink
            stats['papers_with_datasets'] = Paper.objects.filter(
                dataset_links__isnull=False
            ).distinct().count()
        except ImportError:
            # Dataset models not available
            stats['papers_with_datasets'] = 0
        
        # More efficient retraction count using subquery
        retracted_count = RetractedPaper.objects.filter(
            original_pubmed_id__in=Paper.objects.values('pmid')
        ).count()
        stats['retracted_papers'] = retracted_count
        
        try:
            cache.set('dashboard_stats', stats, 300)  # Cache for 5 minutes
        except Exception:
            # Cache set failed, continue without caching
            pass
    
    # Recent papers with optimized query
    recent_papers = Paper.objects.select_related('journal').prefetch_related(
        'pico_extractions'
    ).order_by('-created_at')[:10]
    
    # Recent PICO papers with optimized query and limited joins
    recent_pico_papers = Paper.objects.filter(
        pico_extractions__isnull=False
    ).select_related('journal').prefetch_related(
        Prefetch('pico_extractions', 
                queryset=PICOExtraction.objects.select_related('llm_provider').order_by('-extracted_at'))
    ).annotate(
        latest_pico_date=Max('pico_extractions__extracted_at'),
        pico_count=Count('pico_extractions', distinct=True)
    ).distinct().order_by('-latest_pico_date')[:10]
    
    # Add recent retractions only if there are any
    recent_retractions = None
    if stats['retracted_papers'] > 0:
        recent_retractions = RetractedPaper.objects.filter(
            original_pubmed_id__in=Paper.objects.values('pmid')
        ).order_by('-retraction_date')[:6]  # Limit to 6 most recent
    
    context = {
        'stats': stats,
        'recent_papers': recent_papers,
        'recent_pico_papers': recent_pico_papers,
        'recent_retractions': recent_retractions,
    }
    
    return render(request, 'papers/dashboard.html', context)


@login_required
def bookmark_paper(request, pmid):
    """Toggle bookmark status for a paper."""
    if request.method == 'POST':
        paper = get_object_or_404(Paper, pmid=pmid)
        
        try:
            profile = request.user.profile
        except:
            from .models import UserProfile
            profile = UserProfile.objects.create(user=request.user)
        
        if profile.bookmarked_papers.filter(pmid=pmid).exists():
            profile.bookmarked_papers.remove(paper)
            is_bookmarked = False
            message = "Paper removed from bookmarks"
        else:
            profile.bookmarked_papers.add(paper)
            is_bookmarked = True
            message = "Paper added to bookmarks"
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_bookmarked': is_bookmarked,
                'message': message
            })
        else:
            messages.success(request, message)
            return redirect('papers:detail', pmid=pmid)
    
    return redirect('papers:detail', pmid=pmid)


@csrf_exempt
def extract_pico_ajax(request, pmid):
    """AJAX endpoint for extracting PICO elements from oral health papers."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    paper = get_object_or_404(Paper, pmid=pmid)
    
    if not paper.abstract:
        return JsonResponse({'error': 'Paper has no abstract'}, status=400)
    
    try:
        service = PICOExtractionService()
        pico_extractions = service.extract_pico_for_paper(paper)
        
        # Format multiple PICO extractions for response
        pico_list = []
        for pico_extraction in pico_extractions:
            pico_list.append({
                'population': pico_extraction.population,
                'intervention': pico_extraction.intervention,
                'comparison': pico_extraction.comparison,
                'outcome': pico_extraction.outcome,
                'results': pico_extraction.results,
                'setting': pico_extraction.setting,
                'study_type': pico_extraction.study_type,
                'timeframe': pico_extraction.timeframe,
                'study_design': pico_extraction.study_design,
                'confidence': pico_extraction.extraction_confidence,
                'llm_provider': pico_extraction.llm_provider.display_name if pico_extraction.llm_provider else None,
            })
        
        return JsonResponse({
            'success': True,
            'pico_count': len(pico_extractions),
            'pico_extractions': pico_list
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def search_suggestions(request):
    """AJAX endpoint for search suggestions."""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    suggestions = []
    
    # Paper titles
    paper_titles = Paper.objects.filter(
        title__icontains=query
    ).values_list('title', 'pmid')[:5]
    
    for title, pmid in paper_titles:
        suggestions.append({
            'type': 'paper',
            'text': title[:100] + '...' if len(title) > 100 else title,
            'url': f'/papers/{pmid}/'
        })
    
    # Authors
    authors = Author.objects.filter(
        Q(first_name__icontains=query) | Q(last_name__icontains=query)
    ).distinct()[:5]
    
    for author in authors:
        suggestions.append({
            'type': 'author',
            'text': author.full_name,
            'url': f'/papers/?search={author.full_name}'
        })
    
    # Journals
    journals = Journal.objects.filter(
        name__icontains=query
    )[:5]
    
    for journal in journals:
        suggestions.append({
            'type': 'journal',
            'text': journal.name,
            'url': f'/papers/?journal={journal.id}'
        })
    
    # MeSH terms
    mesh_terms = MeshTerm.objects.filter(
        descriptor_name__icontains=query
    )[:5]
    
    for mesh in mesh_terms:
        suggestions.append({
            'type': 'mesh',
            'text': mesh.descriptor_name,
            'url': f'/papers/?search={mesh.descriptor_name}'
        })
    
    return JsonResponse({'suggestions': suggestions})


class PICOSearchView(ListView):
    """Comprehensive PICO search view for oral health researchers - grouped by paper."""
    
    model = Paper
    template_name = 'papers/pico_search.html'
    context_object_name = 'papers_with_picos'
    paginate_by = 20
    
    def get_queryset(self):
        # Start with PICO filtering
        pico_filters = Q()
        
        # General search across all PICO elements
        search = self.request.GET.get('search')
        if search:
            pico_filters &= Q(
                Q(pico_extractions__population__icontains=search) |
                Q(pico_extractions__intervention__icontains=search) |
                Q(pico_extractions__comparison__icontains=search) |
                Q(pico_extractions__outcome__icontains=search) |
                Q(pico_extractions__setting__icontains=search) |
                Q(pico_extractions__timeframe__icontains=search) |
                Q(title__icontains=search) |
                Q(abstract__icontains=search)
            )
        
        # Specific PICO element searches
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
        
        # Journal filter
        journal = self.request.GET.get('journal')
        if journal:
            pico_filters &= Q(journal_id=journal)
        
        # Get papers that match the PICO filters
        queryset = Paper.objects.filter(
            pico_extractions__isnull=False
        ).filter(pico_filters).select_related('journal').prefetch_related(
            'pico_extractions__llm_provider'
        ).annotate(
            latest_pico_date=Max('pico_extractions__extracted_at'),
            pico_count=Count('pico_extractions', distinct=True)
        ).distinct().order_by('-latest_pico_date')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.core.cache import cache
        
        # Add filter options for the template
        context['study_types'] = PICOExtraction.STUDY_TYPE_CHOICES
        
        # Safe cache handling with fallbacks
        def safe_cache_get_set(key, query_func, timeout=600):
            try:
                value = cache.get(key)
                if value is None:
                    value = query_func()
                    cache.set(key, value, timeout)
                return value
            except Exception:
                # Cache is not available, just run the query
                return query_func()
        
        # Cache expensive filter queries for 10 minutes
        context['llm_providers'] = safe_cache_get_set(
            'pico_llm_providers',
            lambda: list(PICOExtraction.objects.values_list(
                'llm_provider__name', flat=True
            ).distinct().order_by('llm_provider__name'))
        )
        
        # Cache years for PICO papers
        context['years'] = safe_cache_get_set(
            'pico_years',
            lambda: list(Paper.objects.filter(
                pico_extractions__isnull=False
            ).values_list(
                'publication_year', flat=True
            ).distinct().order_by('-publication_year')[:20])
        )
        
        # Cache journals with PICO data
        context['journals'] = safe_cache_get_set(
            'pico_journals',
            lambda: list(Journal.objects.filter(
                papers__pico_extractions__isnull=False
            ).distinct().order_by('name')[:50])
        )
        
        # Cache basic statistics
        pico_stats = safe_cache_get_set(
            'pico_basic_stats',
            lambda: {
                'total_papers_with_pico': Paper.objects.filter(pico_extractions__isnull=False).distinct().count(),
                'total_picos': PICOExtraction.objects.count(),
            },
            timeout=300  # 5 minutes
        )
        
        context['total_papers_with_pico'] = pico_stats['total_papers_with_pico']
        context['total_picos'] = pico_stats['total_picos']
        
        # Only calculate filtered counts if we have filters (expensive operation)
        if self.request.GET:
            context['filtered_count'] = context['paginator'].count if hasattr(context, 'paginator') else 0
            # Approximate PICO count to avoid expensive sum operation
            context['filtered_pico_count'] = context['filtered_count'] * 1.2  # Estimate 1.2 PICOs per paper
        else:
            context['filtered_count'] = pico_stats['total_papers_with_pico']
            context['filtered_pico_count'] = pico_stats['total_picos']
        
        context['has_filters'] = bool(self.request.GET)
        
        # Cache popular study types
        context['popular_study_types'] = safe_cache_get_set(
            'popular_study_types',
            lambda: list(PICOExtraction.objects.values(
                'study_type'
            ).annotate(count=Count('id')).order_by('-count')[:10])
        )
        
        return context


@csrf_exempt
def toggle_theme(request):
    """Toggle user's theme preference."""
    if request.method == 'POST':
        if request.user.is_authenticated:
            # For logged-in users, save to profile
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
    """List view for retracted oral health papers."""
    
    model = None  # We'll override get_queryset instead
    template_name = 'papers/retractions_list.html'
    context_object_name = 'retractions'
    paginate_by = 20
    
    def get_queryset(self):
        from .models_retraction import RetractedPaper
        
        # Start with all retractions that have matching papers in our database
        queryset = RetractedPaper.objects.filter(
            original_pubmed_id__in=Paper.objects.values('pmid')
        ).order_by('-retraction_date')
        
        # Add search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(original_title__icontains=search) |
                Q(journal__icontains=search) |
                Q(authors__icontains=search) |
                Q(reason__icontains=search)
            )
        
        # Add journal filter
        journal = self.request.GET.get('journal')
        if journal:
            queryset = queryset.filter(journal__icontains=journal)
        
        # Add year filter
        year = self.request.GET.get('year')
        if year:
            queryset = queryset.filter(retraction_date__year=year)
        
        # Add retraction nature filter
        nature = self.request.GET.get('nature')
        if nature:
            queryset = queryset.filter(retraction_nature=nature)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        from .models_retraction import RetractedPaper
        from .models_citation import CitationData
        context = super().get_context_data(**kwargs)
        
        # Get filter options
        context['retraction_natures'] = RetractedPaper.objects.filter(
            original_pubmed_id__in=Paper.objects.values('pmid')
        ).values_list('retraction_nature', flat=True).distinct().order_by('retraction_nature')
        
        context['retraction_years'] = RetractedPaper.objects.filter(
            original_pubmed_id__in=Paper.objects.values('pmid')
        ).dates('retraction_date', 'year', order='DESC')[:10]
        
        # Get popular journals with retractions
        context['popular_journals'] = RetractedPaper.objects.filter(
            original_pubmed_id__in=Paper.objects.values('pmid')
        ).values('journal').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Get most problematic retracted papers (those with highest citation impact)
        try:
            context['most_problematic_papers'] = CitationData.objects.select_related(
                'retracted_paper'
            ).order_by('-problematic_score')[:10]
            
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
    """Evidence Gaps page showing Cochrane SoF analysis with consolidated reviews for oral health."""
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
        
        # Check if evidence_gaps table exists - PostgreSQL/SQLite compatible
        try:
            # Try PostgreSQL first
            cursor.execute("""SELECT COUNT(*) FROM information_schema.tables 
                             WHERE table_name = 'evidence_gaps';""")
            table_exists = cursor.fetchone()[0] > 0
        except:
            # Fallback for SQLite
            try:
                cursor.execute("""SELECT COUNT(*) FROM sqlite_master 
                                 WHERE type='table' AND name='evidence_gaps';""")
                table_exists = cursor.fetchone()[0] > 0
            except:
                table_exists = False
        
        if not table_exists:
            # Table doesn't exist yet - show placeholder
            context = {
                'evidence_gaps': [],
                'error': None,
                'placeholder_mode': True,
                'total_outcomes': 0,
                'base_reviews': 0,
                'grade_counts': {},
                'populations': [],
                'interventions': [],
                'current_search': '',
                'current_grade': '',
                'current_population': '',
                'current_intervention': '',
                'current_order': 'review_title',
            }
            return render(request, 'papers/evidence_gaps.html', context)
        
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
            consolidated_reviews.append((base_id, review_data))
        
        # Sort by title for consistent ordering
        consolidated_reviews.sort(key=lambda x: x[1]['latest_title'].lower())
        
        # Calculate summary statistics
        total_outcomes = len(evidence_gaps)
        base_reviews = len(consolidated_reviews)
        
        # Grade counts
        cursor.execute("""
            SELECT grade_rating, COUNT(*) as count, 
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM evidence_gaps), 1) as percentage
            FROM evidence_gaps 
            GROUP BY grade_rating 
            ORDER BY 
                CASE grade_rating 
                    WHEN 'High' THEN 1 
                    WHEN 'Moderate' THEN 2 
                    WHEN 'Low' THEN 3 
                    WHEN 'Very Low' THEN 4 
                    WHEN 'No Evidence Yet' THEN 5 
                    ELSE 6 
                END
        """)
        
        grade_counts = {}
        for row in cursor.fetchall():
            grade_counts[row[0]] = {'count': row[1], 'percentage': row[2]}
        
        # Get filter options
        cursor.execute("SELECT DISTINCT population FROM evidence_gaps WHERE population IS NOT NULL AND population != '' ORDER BY population")
        populations = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT intervention FROM evidence_gaps WHERE intervention IS NOT NULL AND intervention != '' ORDER BY intervention")
        interventions = [row[0] for row in cursor.fetchall()]
        
        # Prepare context
        context = {
            'evidence_gaps': consolidated_reviews,
            'total_outcomes': total_outcomes,
            'base_reviews': base_reviews,
            'grade_counts': grade_counts,
            'populations': populations,
            'interventions': interventions,
            'current_search': search,
            'current_grade': grade,
            'current_population': population,
            'current_intervention': intervention,
            'current_order': request.GET.get('order_by', 'review_title'),
            'placeholder_mode': False,
        }
        
        return render(request, 'papers/evidence_gaps.html', context)
    
    except Exception as e:
        return render(request, 'papers/evidence_gaps.html', {
            'evidence_gaps': [],
            'error': f'Database error: {str(e)}',
            'placeholder_mode': True,
            'total_outcomes': 0,
            'base_reviews': 0,
            'grade_counts': {},
            'populations': [],
            'interventions': [],
        })
