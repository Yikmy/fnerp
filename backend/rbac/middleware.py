from django.http import JsonResponse

from rbac.services import PermissionService


class PermissionGuardMiddleware:
    """Validate request-scoped permission when present."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        permission_code = getattr(request, "required_permission_code", None)
        if not permission_code:
            return self.get_response(request)

        company_id = getattr(request, "current_company_id", None)
        if company_id is None:
            return JsonResponse({"error": "missing_company_scope"}, status=400)

        if not PermissionService.has_permission(
            user=request.user,
            company_id=company_id,
            permission_code=permission_code,
        ):
            return JsonResponse({"error": "forbidden", "permission": permission_code}, status=403)

        return self.get_response(request)
