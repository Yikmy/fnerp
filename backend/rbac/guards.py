from functools import wraps

from django.http import JsonResponse

from rbac.services import PermissionService


def require_permission(permission_code: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            company_id = getattr(request, "current_company_id", None)
            if company_id is None:
                return JsonResponse({"error": "missing_company_scope"}, status=400)

            if not PermissionService.has_permission(
                user=request.user,
                company_id=company_id,
                permission_code=permission_code,
            ):
                return JsonResponse({"error": "forbidden", "permission": permission_code}, status=403)

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
