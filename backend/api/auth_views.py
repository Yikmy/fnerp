from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .base import ensure_authenticated, parse_company_id, parse_json_body
from .exceptions import AuthenticationFailedError, api_exception_handler
from .responses import success_response


@csrf_exempt  # MVP choice per spec: scoped CSRF relaxation for auth endpoints; replace with full CSRF flow later.
@require_POST
@api_exception_handler
def login_view(request):
    payload = parse_json_body(request)
    username = payload.get("username", "")
    password = payload.get("password", "")

    user = authenticate(request, username=username, password=password)
    if user is None:
        raise AuthenticationFailedError("Invalid username or password")

    login(request, user)

    company_id = parse_company_id(payload.get("company_id"))
    if company_id is not None:
        request.session["company_id"] = company_id

    return success_response(
        message="Login successful",
        data={
            "is_authenticated": True,
            "user": {
                "id": user.id,
                "username": user.get_username(),
                "is_superuser": user.is_superuser,
            },
            "company_id": request.session.get("company_id"),
        },
    )


@csrf_exempt  # MVP choice per spec: scoped CSRF relaxation for auth endpoints; replace with full CSRF flow later.
@require_POST
@api_exception_handler
def logout_view(request):
    ensure_authenticated(request)
    logout(request)
    return success_response(message="Logout successful", data={"is_authenticated": False})


@require_GET
@api_exception_handler
def session_view(request):
    user = ensure_authenticated(request)
    return success_response(
        data={
            "is_authenticated": True,
            "user": {
                "id": user.id,
                "username": user.get_username(),
                "is_superuser": user.is_superuser,
            },
            "company_id": request.session.get("company_id"),
        }
    )
