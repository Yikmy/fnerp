class ApiException(Exception):
    """Base API exception with machine-readable payload."""

    code = "api_error"
    status_code = 400

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict[str, str | int]:
        return {
            "error": self.code,
            "message": self.message,
            "status_code": self.status_code,
        }


class PermissionDeniedError(ApiException):
    code = "permission_denied"
    status_code = 403


class BusinessRuleError(ApiException):
    code = "business_rule_error"
    status_code = 422


class ValidationError(ApiException):
    code = "validation_error"
    status_code = 400
