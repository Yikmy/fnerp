from django.core.cache import cache

from system_config.models import SystemConfig


class SystemConfigService:
    """Configuration retrieval service with cache-first strategy.

    Caching strategy:
    - key format: system_config:{scope}:{company_id or global}:{key}
    - cache TTL: 300 seconds
    - company-scope fallback to global scope when company value missing
    """

    CACHE_TTL_SECONDS = 300

    @classmethod
    def _cache_key(cls, *, key: str, scope: str, company_id=None) -> str:
        company_token = str(company_id) if company_id else "global"
        return f"system_config:{scope}:{company_token}:{key}"

    @classmethod
    def get(cls, *, key: str, company_id=None, default=None):
        if company_id:
            company_cache_key = cls._cache_key(
                key=key,
                scope=SystemConfig.SCOPE_COMPANY,
                company_id=company_id,
            )
            cached_company_value = cache.get(company_cache_key)
            if cached_company_value is not None:
                return cached_company_value

            company_config = (
                SystemConfig.objects.filter(
                    key=key,
                    scope=SystemConfig.SCOPE_COMPANY,
                    company_id=company_id,
                    is_active=True,
                )
                .only("value")
                .first()
            )
            if company_config is not None:
                cache.set(company_cache_key, company_config.value, timeout=cls.CACHE_TTL_SECONDS)
                return company_config.value

        global_cache_key = cls._cache_key(
            key=key,
            scope=SystemConfig.SCOPE_GLOBAL,
            company_id=None,
        )
        cached_global_value = cache.get(global_cache_key)
        if cached_global_value is not None:
            return cached_global_value

        global_config = (
            SystemConfig.objects.filter(
                key=key,
                scope=SystemConfig.SCOPE_GLOBAL,
                company_id__isnull=True,
                is_active=True,
            )
            .only("value")
            .first()
        )
        if global_config is not None:
            cache.set(global_cache_key, global_config.value, timeout=cls.CACHE_TTL_SECONDS)
            return global_config.value

        return default

    @classmethod
    def set_global(cls, *, key: str, value, description: str = "") -> SystemConfig:
        config, _ = SystemConfig.objects.update_or_create(
            key=key,
            scope=SystemConfig.SCOPE_GLOBAL,
            company_id=None,
            defaults={"value": value, "description": description, "is_active": True},
        )
        cache.delete(cls._cache_key(key=key, scope=SystemConfig.SCOPE_GLOBAL, company_id=None))
        return config

    @classmethod
    def set_for_company(cls, *, key: str, company_id, value, description: str = "") -> SystemConfig:
        config, _ = SystemConfig.objects.update_or_create(
            key=key,
            scope=SystemConfig.SCOPE_COMPANY,
            company_id=company_id,
            defaults={"value": value, "description": description, "is_active": True},
        )
        cache.delete(
            cls._cache_key(
                key=key,
                scope=SystemConfig.SCOPE_COMPANY,
                company_id=company_id,
            )
        )
        return config
