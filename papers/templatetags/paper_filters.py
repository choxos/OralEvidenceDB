"""
Template filters for paper display and formatting.
"""

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import format_html
import re

register = template.Library()


@register.filter
def format_study_type_classification(classification):
    """Format study type classification for display."""
    if not classification:
        return "Not specified"
    
    # Convert underscore-separated values to human-readable format
    formatted = classification.replace('_', ' ').title()
    
    # Fix specific abbreviations and terms
    replacements = {
        'Rct': 'RCT',
        'Cct': 'CCT',
        'Meta Analysis': 'Meta-Analysis',
        'Network Meta Analysis': 'Network Meta-Analysis',
        'In Vitro': 'In Vitro',
        'In Vivo': 'In Vivo'
    }
    
    for old, new in replacements.items():
        formatted = formatted.replace(old, new)
    
    return formatted


@register.filter
def highlight_search_term(text, search_term):
    """Highlight search terms in text."""
    if not search_term or not text:
        return text
    
    # Escape HTML in both text and search term
    from django.utils.html import escape
    text = escape(text)
    search_term = escape(search_term)
    
    # Create case-insensitive regex pattern
    pattern = re.compile(re.escape(search_term), re.IGNORECASE)
    
    # Replace with highlighted version
    highlighted = pattern.sub(
        lambda m: format_html('<mark class="search-highlight">{}</mark>', m.group()),
        text
    )
    
    return mark_safe(highlighted)


@register.filter
def truncate_abstract(abstract, max_length=300):
    """Truncate abstract to specified length while preserving word boundaries."""
    if not abstract or len(abstract) <= max_length:
        return abstract
    
    # Find the last space before max_length
    truncated = abstract[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + '...'


@register.filter
def format_author_list(authors, max_authors=3):
    """Format author list for display."""
    if not authors:
        return "No authors listed"
    
    author_names = []
    for author_paper in authors.all()[:max_authors]:
        author_names.append(f"{author_paper.author.last_name}, {author_paper.author.first_name[:1]}")
    
    if authors.count() > max_authors:
        author_names.append("et al.")
    
    return "; ".join(author_names)


@register.filter
def format_mesh_terms(mesh_terms, max_terms=5):
    """Format MeSH terms for display."""
    if not mesh_terms:
        return "No MeSH terms"
    
    terms = list(mesh_terms.all()[:max_terms])
    term_names = [term.descriptor_name for term in terms]
    
    if mesh_terms.count() > max_terms:
        term_names.append(f"and {mesh_terms.count() - max_terms} more")
    
    return "; ".join(term_names)


@register.filter
def format_pmid_link(pmid):
    """Format PMID as a clickable PubMed link."""
    if not pmid:
        return ""
    
    return format_html(
        '<a href="https://pubmed.ncbi.nlm.nih.gov/{}" target="_blank" rel="noopener">{}</a>',
        pmid, f"PMID:{pmid}"
    )


@register.filter
def format_doi_link(doi):
    """Format DOI as a clickable link."""
    if not doi:
        return ""
    
    # Clean DOI (remove doi: prefix if present)
    clean_doi = doi.replace('doi:', '').strip()
    
    return format_html(
        '<a href="https://doi.org/{}" target="_blank" rel="noopener">{}</a>',
        clean_doi, clean_doi
    )


@register.filter
def oral_health_badge(paper):
    """Generate badge indicating if paper is oral health related."""
    # Check if paper has oral health related MeSH terms
    oral_health_mesh_terms = [
        'stomatognathic diseases', 'dentistry', 'oral health', 'dental caries',
        'periodontal diseases', 'oral medicine', 'oral surgery', 'orthodontics',
        'endodontics', 'prosthodontics', 'oral pathology'
    ]
    
    if paper.mesh_terms.filter(
        descriptor_name__iregex=r'\b(' + '|'.join(oral_health_mesh_terms) + r')\b'
    ).exists():
        return format_html('<span class="badge bg-success">Oral Health</span>')
    
    return ""


@register.filter
def retraction_status(paper):
    """Show retraction status if paper is retracted."""
    try:
        if paper.is_retracted:
            return format_html(
                '<span class="badge bg-danger" title="This paper has been retracted">'
                '<i class="bi bi-exclamation-triangle"></i> Retracted</span>'
            )
    except AttributeError:
        pass
    
    return ""


@register.filter
def pico_completeness_indicator(pico_extraction):
    """Show PICO completeness indicator."""
    if not pico_extraction:
        return ""
    
    completeness_count = sum([
        bool(pico_extraction.population),
        bool(pico_extraction.intervention),
        bool(pico_extraction.comparison),
        bool(pico_extraction.outcome)
    ])
    
    if completeness_count == 4:
        return format_html('<span class="badge bg-success">Complete PICO</span>')
    elif completeness_count >= 3:
        return format_html('<span class="badge bg-warning">Partial PICO</span>')
    else:
        return format_html('<span class="badge bg-secondary">Incomplete PICO</span>')


@register.filter
def confidence_indicator(confidence):
    """Show confidence score as colored indicator."""
    if confidence is None:
        return ""
    
    if confidence >= 0.8:
        color = "success"
    elif confidence >= 0.6:
        color = "warning"
    else:
        color = "danger"
    
    return format_html(
        '<span class="badge bg-{}" title="Confidence: {:.1%}">{:.0%}</span>',
        color, confidence, confidence
    )


@register.filter
def study_type_icon(study_type):
    """Get icon for study type."""
    icons = {
        'systematic_review': 'bi-search',
        'meta_analysis': 'bi-bar-chart',
        'randomized_controlled_trial': 'bi-shuffle',
        'cohort_study': 'bi-people',
        'case_control_study': 'bi-person-check',
        'cross_sectional_study': 'bi-graph-up',
        'case_series': 'bi-file-medical',
        'case_report': 'bi-file-person',
        'clinical_trial': 'bi-clipboard-pulse',
        'pilot_study': 'bi-rocket',
        'animal_studies': 'bi-bug',
        'in_vitro_study': 'bi-eyedropper',
        'qualitative_studies': 'bi-chat-quote',
        'guidelines': 'bi-book'
    }
    
    icon = icons.get(study_type, 'bi-file-text')
    return format_html('<i class="{}"></i>', icon)


@register.filter
def format_publication_year(paper):
    """Format publication year with fallback to created date."""
    if paper.publication_year:
        return paper.publication_year
    elif paper.publication_date:
        return paper.publication_date.year
    elif paper.created_at:
        return paper.created_at.year
    else:
        return "Unknown"


@register.filter
def oral_health_category_badge(category):
    """Format oral health category as a styled badge."""
    if not category:
        return ""
    
    # Color mapping for different oral health categories
    colors = {
        'dental_caries': 'primary',
        'periodontal_disease': 'success',
        'oral_cancer': 'danger',
        'orthodontics': 'info',
        'endodontics': 'warning',
        'prosthodontics': 'secondary',
        'oral_surgery': 'dark',
        'preventive_dentistry': 'success',
        'pediatric_dentistry': 'info',
        'oral_medicine': 'primary'
    }
    
    color = colors.get(category, 'secondary')
    label = category.replace('_', ' ').title()
    
    return format_html('<span class="badge bg-{}">{}</span>', color, label)


@register.simple_tag
def pagination_url(request, page_num):
    """Generate pagination URL preserving current query parameters."""
    params = request.GET.copy()
    params['page'] = page_num
    return f"?{params.urlencode()}"
