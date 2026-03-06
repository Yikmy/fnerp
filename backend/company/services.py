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
