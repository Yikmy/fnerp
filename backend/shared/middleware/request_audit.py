import time

from audit.models import AuditEvent


class RequestAuditMiddleware:
    """Persist request-level audit telemetry for every handled request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        response = self.get_response(request)
        duration_ms = int((time.perf_counter() - started_at) * 1000)

        user = getattr(request, "user", None)
        actor_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None

        AuditEvent.objects.create(
            actor_id=actor_id,
            company_id=getattr(request, "current_company_id", None),
            action="request.processed",
            resource_type="http_request",
            resource_id=request.path,
            metadata={
                "path": request.path,
                "method": request.method,
                "response_status": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response
