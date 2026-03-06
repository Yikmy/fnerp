import logging

from django.db import transaction

logger = logging.getLogger(__name__)


class BaseService:
    """Reusable service base with transaction and structured logging hooks."""

    @staticmethod
    def run_in_transaction(func, *args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)

    def log_info(self, message: str, **extra):
        logger.info(message, extra=extra)

    def log_error(self, message: str, **extra):
        logger.error(message, extra=extra)
