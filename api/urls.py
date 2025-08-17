"""
URL configuration for OralEvidenceDB API.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'api'

# API Documentation
urlpatterns = [
    # API Documentation
    path('', views.api_documentation, name='documentation'),
    
    # Papers endpoints
    path('papers/', views.PaperListAPIView.as_view(), name='paper-list'),
    path('papers/<int:pmid>/', views.PaperDetailAPIView.as_view(), name='paper-detail'),
    path('papers/<int:pmid>/extract-pico/', views.extract_pico_api, name='extract-pico'),
    
    # PICO extractions
    path('pico/', views.PICOExtractionListAPIView.as_view(), name='pico-list'),
    
    # Authors and Journals
    path('authors/', views.AuthorListAPIView.as_view(), name='author-list'),
    path('journals/', views.JournalListAPIView.as_view(), name='journal-list'),
    
    # Search and statistics
    path('search/', views.search_papers_api, name='search-papers'),
    path('statistics/', views.statistics_api, name='statistics'),
    path('providers/', views.available_providers_api, name='providers'),
]
