from django.db import models


class CompanyQuerySet(models.QuerySet):
    """Standard queryset helpers for company-scoped business records."""

    def for_company(self, company):
        return self.filter(company_id=getattr(company, "id", company))

    def for_request(self, request):
        company_id = getattr(request, "current_company_id", None)
        if company_id is None:
            return self.none()
        return self.for_company(company_id)

    def active(self):
        return self.filter(is_deleted=False)
