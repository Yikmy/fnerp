from shared.services.base import BaseService


class PermissionProbeService(BaseService):
    """Service-layer probe used to keep middleware and service permission checks in sync."""

    PERM_READ = "core.permission.read"

    def ensure_read_access(self, *, user, company_id):
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_READ)
