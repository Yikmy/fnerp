import logging

from django.db import transaction

from audit.services import AuditService
from shared.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)


class BaseService:
    """Reusable service base with transaction, permission lookup, audit hooks and structured logging."""

    @staticmethod
    def run_in_transaction(func, *args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)

    def ensure_permission(self, *, user, company_id, permission_code: str):
        from rbac.services import PermissionService

        allowed = PermissionService.has_permission(
            user=user,
            company_id=company_id,
            permission_code=permission_code,
        )
        if not allowed:
            raise PermissionDeniedError(f"Missing permission: {permission_code}")

    def audit_crud(
        self,
        *,
        user,
        company_id,
        operation: str,
        resource_type: str,
        resource_id,
        request=None,
        field_diffs: list[dict] | None = None,
    ):
        return AuditService.log_crud(
            actor_id=getattr(user, "id", None),
            company_id=company_id,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            request=request,
            field_diffs=field_diffs,
        )

    def log_info(self, message: str, **extra):
        logger.info(message, extra=extra)

    def log_error(self, message: str, **extra):
        logger.error(message, extra=extra)
