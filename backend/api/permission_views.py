from django.views.decorators.http import require_GET

from rbac.guards import require_permission

from .base import ensure_authenticated
from .exceptions import api_exception_handler
from .responses import success_response
from .services import PermissionProbeService


@require_GET
@api_exception_handler
@require_permission(PermissionProbeService.PERM_READ)
def permission_probe_view(request):
    user = ensure_authenticated(request)
    PermissionProbeService().ensure_read_access(user=user, company_id=request.current_company_id)
    return success_response(data={"ok": True, "permission": PermissionProbeService.PERM_READ})
