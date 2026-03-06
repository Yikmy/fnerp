from django.contrib.auth.models import AnonymousUser

from company.services import MembershipService
from rbac.models import RolePermission
from shared.services.module_guard import ModuleGuardService


class PermissionService:
    @staticmethod
    def has_permission(*, user, company_id, permission_code: str) -> bool:
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return False

        module_code = permission_code.split(".", 1)[0]
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=module_code):
            return False

        role_ids = MembershipService.get_user_roles(user_id=user.id, company_id=company_id)
        return RolePermission.objects.filter(
            role_id__in=role_ids,
            permission__code=permission_code,
            permission__is_active=True,
        ).exists()
