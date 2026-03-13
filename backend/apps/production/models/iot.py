from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Reservation
from apps.material.models import Material, Warehouse
from apps.sales.models import SalesOrder
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel
from .documents import ManufacturingOrder

class IoTDevice(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        MAINTENANCE = "maintenance", "Maintenance"

    device_code = models.CharField(max_length=64)
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    bound_mo = models.ForeignKey(ManufacturingOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="iot_devices")

    class Meta:
        db_table = "prd_iot_device"
        unique_together = (("company_id", "device_code"),)

    def clean(self):
        if self.bound_mo_id and self.bound_mo.company_id != self.company_id:
            raise DjangoValidationError({"bound_mo": "Manufacturing order company must match IoT device company."})

class IoTMetric(BaseModel):
    device = models.ForeignKey(IoTDevice, on_delete=models.CASCADE, related_name="metrics")
    metric_key = models.CharField(max_length=64)
    value = models.DecimalField(max_digits=20, decimal_places=6)
    recorded_at = models.DateTimeField()

    class Meta:
        db_table = "prd_iot_metric"

    def clean(self):
        if self.device_id and self.device.company_id != self.company_id:
            raise DjangoValidationError({"device": "Device company must match metric company."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
