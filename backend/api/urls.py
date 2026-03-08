from django.urls import path

from .auth_views import login_view, logout_view, session_view

app_name = "api"

urlpatterns = [
    path("auth/login/", login_view, name="auth-login"),
    path("auth/logout/", logout_view, name="auth-logout"),
    path("auth/session/", session_view, name="auth-session"),
    # Future extension points:
    # path("company/", include("apps.company.api.urls")),
    # path("material/", include("apps.material.api.urls")),
    # path("inventory/", include("apps.inventory.api.urls")),
]
