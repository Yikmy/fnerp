from company.models import CompanyModule


class ModuleGuardService:
    """Checks whether a module is enabled for a company."""

    @staticmethod
    def check_module_enabled(*, company_id, module_code: str) -> bool:
        return CompanyModule.objects.filter(
            company_id=company_id,
            module_code=module_code,
            is_enabled=True,
            company__is_active=True,
        ).exists()
