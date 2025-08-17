"""
URL configuration for custom admin interface.
"""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'custom_admin'

urlpatterns = [
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='custom_admin/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Admin dashboard
    path('', views.admin_dashboard, name='dashboard'),
]
