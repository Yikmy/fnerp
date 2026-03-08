import json
from uuid import UUID

from shared.exceptions.api import ValidationError

from .exceptions import AuthenticationRequiredError


def ensure_authenticated(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        raise AuthenticationRequiredError("Authentication required")
    return user


def parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid JSON payload") from exc


def parse_company_id(value):
    if not value:
        return None
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError) as exc:
        raise ValidationError("Invalid company_id format") from exc
