"""
Context processors for the oral health papers application.

This module provides global context variables available in all templates.
"""

from django.conf import settings
from .models_retraction import RetractedPaper


def retraction_context(request):
    """
    Add retraction-related context to all templates.
    This helps display retraction warnings and statistics globally.
    """
    try:
        # Get count of retracted papers in our database
        retracted_count = RetractedPaper.objects.filter(
            original_pubmed_id__isnull=False
        ).count()
        
        # Check if there are recent retractions (last 30 days)
        from django.utils import timezone
        import datetime
        
        thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
        recent_retractions_count = RetractedPaper.objects.filter(
            retraction_date__gte=thirty_days_ago,
            original_pubmed_id__isnull=False
        ).count()
        
    except Exception:
        # Handle case where retraction models aren't available yet
        retracted_count = 0
        recent_retractions_count = 0
    
    return {
        'retracted_papers_count': retracted_count,
        'recent_retractions_count': recent_retractions_count,
        'has_retractions': retracted_count > 0,
        'has_recent_retractions': recent_retractions_count > 0,
    }
