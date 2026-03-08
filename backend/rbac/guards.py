def require_permission(permission_code: str):
    """Attach route-level required permission metadata for middleware enforcement."""

    def decorator(view_func):
        setattr(view_func, "required_permission_code", permission_code)
        return view_func

    return decorator
