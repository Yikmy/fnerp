import uuid

from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    company_id = models.UUIDField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=64)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_event"
        indexes = [
            models.Index(fields=["company_id", "resource_type", "resource_id"]),
            models.Index(fields=["actor_id", "timestamp"]),
        ]


class AuditFieldDiff(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(AuditEvent, on_delete=models.CASCADE, related_name="field_diffs")
    field = models.CharField(max_length=120)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)

    class Meta:
        db_table = "audit_field_diff"
