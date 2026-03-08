from django.http import JsonResponse


def success_response(*, data=None, message="", status=200, meta=None):
    payload = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
    }
    if meta is not None:
        payload["meta"] = meta
    return JsonResponse(payload, status=status)


def error_response(*, code: str, message: str, status=400, details=None):
    return JsonResponse(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
        status=status,
    )
