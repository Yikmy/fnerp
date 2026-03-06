import logging

from django.db import transaction

from shared.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)


class BaseService:
    """Reusable service base with transaction, permission lookup and structured logging hooks."""

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

    def log_info(self, message: str, **extra):
        logger.info(message, extra=extra)

    def log_error(self, message: str, **extra):
        logger.error(message, extra=extra)
