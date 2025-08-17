"""
Views for custom admin interface.
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from papers.models import Paper, Journal, Author, PICOExtraction, DataImportLog


@staff_member_required
def admin_dashboard(request):
    """Custom admin dashboard with statistics."""
    stats = {
        'total_papers': Paper.objects.count(),
        'total_journals': Journal.objects.count(),
        'total_authors': Author.objects.count(),
        'total_pico_extractions': PICOExtraction.objects.count(),
        'recent_imports': DataImportLog.objects.filter(status='completed').count(),
    }
    
    # Recent activity
    recent_papers = Paper.objects.select_related('journal').order_by('-created_at')[:10]
    recent_imports = DataImportLog.objects.order_by('-started_at')[:5]
    
    context = {
        'stats': stats,
        'recent_papers': recent_papers,
        'recent_imports': recent_imports,
    }
    
    return render(request, 'custom_admin/dashboard.html', context)
