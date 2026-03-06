from django.apps import AppConfig


class SystemConfigAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "system_config"
    verbose_name = "System Configuration"
