"""
URL configuration for oral_evidence_db project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('custom-admin/', include('custom_admin.urls')),
    path('', include('papers.urls')),
    path('api/', include('api.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin site customization
admin.site.site_header = "OralEvidenceDB Administration"
admin.site.site_title = "OralEvidenceDB Admin"
admin.site.index_title = "Welcome to OralEvidenceDB Administration"
