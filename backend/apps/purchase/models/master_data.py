from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Serial
from apps.material.models import Material, Warehouse
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel

class Vendor(BaseModel):
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    contact_json = models.JSONField(default=dict, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "pur_vendor"
        unique_together = (("company_id", "code"),)

    def clean(self):
        if self.rating is not None and (self.rating < 0 or self.rating > 5):
            raise DjangoValidationError({"rating": "rating must be between 0 and 5."})

class VendorHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="history")
    event_type = models.CharField(max_length=64)
    content = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pur_vendor_history"
