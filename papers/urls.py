"""
URL configuration for oral health papers app.
"""

from django.urls import path
from . import views

app_name = 'papers'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Paper views
    path('papers/', views.PaperListView.as_view(), name='list'),
    path('papers/<int:pmid>/', views.PaperDetailView.as_view(), name='detail'),
    
    # PICO search page
    path('pico/', views.PICOSearchView.as_view(), name='pico_search'),
    
    # Retractions
    path('retractions/', views.RetractionsListView.as_view(), name='retractions_list'),
    
    # User features
    path('papers/<int:pmid>/bookmark/', views.bookmark_paper, name='bookmark_paper'),
    
    # PICO extraction
    path('papers/<int:pmid>/extract-pico/', views.extract_pico_ajax, name='extract_pico'),
    
    # AJAX endpoints
    path('search-suggestions/', views.search_suggestions, name='search_suggestions'),
    path('toggle-theme/', views.toggle_theme, name='toggle_theme'),
    
    # About page
    path('about/', views.about, name='about'),
]
