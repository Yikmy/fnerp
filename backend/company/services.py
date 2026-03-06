from uuid import UUID

from django.contrib.auth.models import AnonymousUser

from company.models import CompanyMembership


class CompanyScopeService:
    @staticmethod
    def has_membership(user, company_id: UUID) -> bool:
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return False

        return CompanyMembership.objects.filter(
            user_id=user.id,
            company_id=company_id,
            is_active=True,
            company__is_active=True,
        ).exists()


class MembershipService:
    """Abstraction layer for company membership lookups."""

    @staticmethod
    def get_user_companies(user_id):
        return (
            CompanyMembership.objects.filter(
                user_id=user_id,
                is_active=True,
                company__is_active=True,
            )
            .values_list("company_id", flat=True)
            .distinct()
        )

    @staticmethod
    def get_user_roles(user_id, company_id):
        return (
            CompanyMembership.objects.select_related("role")
            .filter(
                user_id=user_id,
                company_id=company_id,
                is_active=True,
                company__is_active=True,
                role__isnull=False,
                role__is_active=True,
            )
            .values_list("role_id", flat=True)
            .distinct()
        )
