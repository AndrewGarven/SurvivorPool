from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Signup
    path("signup/", views.signup, name="signup"),

    # Login / logout
    path("login/", auth_views.LoginView.as_view(
        template_name="accounts/login.html"
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Existing dashboard
    path("dashboard/", views.dashboard, name="dashboard"),
]
