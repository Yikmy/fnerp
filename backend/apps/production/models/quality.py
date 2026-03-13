from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Reservation
from apps.material.models import Material, Warehouse
from apps.sales.models import SalesOrder
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel
from .documents import ManufacturingOrder

class ProductionQC(BaseModel):
    class Stage(models.TextChoices):
        IPQC = "ipqc", "IPQC"
        FQC = "fqc", "FQC"

    class Result(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        HOLD = "hold", "Hold"

    mo = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE, related_name="qc_records")
    stage = models.CharField(max_length=16, choices=Stage.choices)
    result = models.CharField(max_length=16, choices=Result.choices)
    inspector_id = models.UUIDField()
    notes = models.TextField(blank=True)
    measurements_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "prd_production_qc"

    def clean(self):
        if self.mo_id and self.mo.company_id != self.company_id:
            raise DjangoValidationError({"mo": "Manufacturing order company must match QC record company."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
