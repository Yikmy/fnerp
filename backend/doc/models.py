import uuid

from django.db import models

from shared.constants.document import DOC_STATUS


class DocumentStateMachineDef(models.Model):
    """State transition definition per document type."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = models.CharField(max_length=80)
    from_state = models.CharField(max_length=20, choices=[(value, value) for value in DOC_STATUS])
    to_state = models.CharField(max_length=20, choices=[(value, value) for value in DOC_STATUS])
    permission_code = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "document_state_machine_def"
        unique_together = ("document_type", "from_state", "to_state")


class DocumentTransitionLog(models.Model):
    """Audit trail for document state transitions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    document_type = models.CharField(max_length=80)
    document_id = models.UUIDField()
    from_state = models.CharField(max_length=20)
    to_state = models.CharField(max_length=20)
    operator_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_transition_log"
        indexes = [
            models.Index(fields=["company_id", "document_type", "document_id"]),
        ]
