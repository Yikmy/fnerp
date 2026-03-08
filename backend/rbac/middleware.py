from django.http import JsonResponse
from django.urls import Resolver404, resolve

from rbac.services import PermissionService


class PermissionGuardMiddleware:
    """Validate request-scoped permission when present."""

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _resolve_permission_code(request):
        permission_code = getattr(request, "required_permission_code", None)
        if permission_code:
            return permission_code

        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match is None:
            try:
                resolver_match = resolve(request.path_info)
                request.resolver_match = resolver_match
            except Resolver404:
                return None

        view_func = getattr(resolver_match, "func", None)
        if view_func is None:
            return None

        permission_code = getattr(view_func, "required_permission_code", None)
        if permission_code:
            return permission_code

        view_class = getattr(view_func, "view_class", None)
        if view_class is not None:
            return getattr(view_class, "required_permission_code", None)

        return None

    def __call__(self, request):
        permission_code = self._resolve_permission_code(request)
        if permission_code:
            request.required_permission_code = permission_code

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
