from uuid import UUID

from django.http import JsonResponse

from company.models import Company
from company.services import CompanyScopeService


class CompanyScopeMiddleware:
    """Resolve request company scope and validate membership."""

    header_name = "HTTP_X_COMPANY_ID"
    exempt_path_prefixes = ("/health/", "/api/auth/")

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _coerce_company_id(raw_value):
        if not raw_value:
            return None
        try:
            return UUID(str(raw_value))
        except (ValueError, TypeError):
            return None

    def _extract_jwt_company_id(self, request):
        auth_payload = getattr(request, "auth", None)
        if isinstance(auth_payload, dict):
            return auth_payload.get("company_id") or auth_payload.get("company")

        token_payload = getattr(request, "jwt_payload", None)
        if isinstance(token_payload, dict):
            return token_payload.get("company_id") or token_payload.get("company")

        return None

    def _resolve_company_id(self, request):
        candidates = [
            request.META.get(self.header_name),
            getattr(request, "session", {}).get("company_id") if hasattr(request, "session") else None,
            self._extract_jwt_company_id(request),
            getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("company_id"),
        ]

        for raw_value in candidates:
            company_id = self._coerce_company_id(raw_value)
            if company_id is not None:
                return company_id
        return None

    def __call__(self, request):
        if request.path.startswith(self.exempt_path_prefixes):
            return self.get_response(request)

        company_id = self._resolve_company_id(request)
        if company_id is None:
            return JsonResponse({"error": "missing_company_scope"}, status=400)

        if not Company.objects.filter(id=company_id, is_active=True).exists():
            return JsonResponse({"error": "company_not_found"}, status=404)

        if not CompanyScopeService.has_membership(request.user, company_id):
            return JsonResponse({"error": "forbidden_company_scope"}, status=403)

        request.current_company_id = company_id
        request.current_company = Company(id=company_id)

        return self.get_response(request)
