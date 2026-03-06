from django.contrib.auth.models import AnonymousUser

from company.models import CompanyMembership
from rbac.models import RolePermission


class PermissionService:
    @staticmethod
    def has_permission(*, user, company_id, permission_code: str) -> bool:
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return False

        membership = (
            CompanyMembership.objects.select_related("role")
            .filter(user_id=user.id, company_id=company_id, is_active=True, company__is_active=True)
            .first()
        )
        if membership is None or membership.role_id is None or not membership.role.is_active:
            return False

        return RolePermission.objects.filter(
            role_id=membership.role_id,
            permission__code=permission_code,
            permission__is_active=True,
        ).exists()
