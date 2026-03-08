from functools import wraps

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404

from shared.exceptions.api import ApiException, BusinessRuleError, PermissionDeniedError, ValidationError

from .responses import error_response


class AuthenticationRequiredError(ApiException):
    code = "authentication_required"
    status_code = 401


class AuthenticationFailedError(ApiException):
    code = "authentication_failed"
    status_code = 401


class NotFoundError(ApiException):
    code = "not_found"
    status_code = 404


def map_exception_to_response(exc: Exception):
    if isinstance(exc, ApiException):
        return error_response(
            code=exc.code,
            message=exc.message,
            status=exc.status_code,
        )

    if isinstance(exc, (ValidationError,)):
        return error_response(code="validation_error", message=str(exc), status=400)

    if isinstance(exc, (PermissionDeniedError, PermissionDenied)):
        return error_response(code="permission_denied", message=str(exc) or "Permission denied", status=403)

    if isinstance(exc, BusinessRuleError):
        return error_response(code="business_rule_error", message=str(exc), status=422)

    if isinstance(exc, (ObjectDoesNotExist, Http404)):
        return error_response(code="not_found", message="Resource not found", status=404)

    return error_response(code="internal_server_error", message="Internal server error", status=500)


def api_exception_handler(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as exc:  # centralized API exception mapping
            return map_exception_to_response(exc)

    return _wrapped
