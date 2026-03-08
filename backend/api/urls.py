from django.urls import path

from .auth_views import login_view, logout_view, session_view
from .permission_views import permission_probe_view

app_name = "api"

urlpatterns = [
    path("auth/login/", login_view, name="auth-login"),
    path("auth/logout/", logout_view, name="auth-logout"),
    path("auth/session/", session_view, name="auth-session"),
    path("guard/probe/", permission_probe_view, name="guard-probe"),
    # Future extension points:
    # path("company/", include("apps.company.api.urls")),
    # path("material/", include("apps.material.api.urls")),
    # path("inventory/", include("apps.inventory.api.urls")),
]
