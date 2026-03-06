from django.db import models


class CompanyQuerySet(models.QuerySet):
    """Standard queryset helpers for company-scoped business records."""

    def for_company(self, company):
        return self.filter(company_id=getattr(company, "id", company))

    def active(self):
        return self.filter(is_deleted=False)
