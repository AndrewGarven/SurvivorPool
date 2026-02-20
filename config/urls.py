"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

def root_redirect(request):
    return redirect("/login", permanent=False)



urlpatterns = [
    path("", root_redirect),
    
    path("admin/", admin.site.urls),

    # account-level routes (dashboard now lives here)
    path("", include("accounts.urls")),

    # pool features
    path("", include("pools.urls")),

    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login"
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
