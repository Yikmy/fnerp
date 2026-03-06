import uuid

from django.db import models


class SystemConfig(models.Model):
    SCOPE_GLOBAL = "global"
    SCOPE_COMPANY = "company"
    SCOPE_CHOICES = [
        (SCOPE_GLOBAL, SCOPE_GLOBAL),
        (SCOPE_COMPANY, SCOPE_COMPANY),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=120)
    value = models.JSONField(default=dict, blank=True)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_GLOBAL)
    company_id = models.UUIDField(null=True, blank=True, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_config"
        unique_together = ("key", "scope", "company_id")
        indexes = [
            models.Index(fields=["scope", "company_id", "key"]),
        ]
