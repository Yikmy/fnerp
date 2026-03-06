from uuid import UUID

from django.http import JsonResponse

from company.models import Company
from company.services import CompanyScopeService


class CompanyScopeMiddleware:
    """Resolve request company scope via X-Company-ID and validate membership."""

    header_name = "HTTP_X_COMPANY_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw_company_id = request.META.get(self.header_name)
        if not raw_company_id:
            return JsonResponse({"error": "missing_company_scope"}, status=400)

        try:
            company_id = UUID(raw_company_id)
        except ValueError:
            return JsonResponse({"error": "invalid_company_scope"}, status=400)

        if not Company.objects.filter(id=company_id, is_active=True).exists():
            return JsonResponse({"error": "company_not_found"}, status=404)

        if not CompanyScopeService.has_membership(request.user, company_id):
            return JsonResponse({"error": "forbidden_company_scope"}, status=403)

        request.current_company_id = company_id
        request.current_company = Company(id=company_id)

        return self.get_response(request)
