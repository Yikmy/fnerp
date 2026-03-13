from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.material.models import Material, Warehouse
from apps.sales.models import Customer, SalesOrder, Shipment
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel
from .documents import ContainerRecoveryPlan, TransportOrder

class TransportRecoveryLine(BaseModel):
    transport_order = models.ForeignKey(TransportOrder, on_delete=models.CASCADE, related_name="recovery_lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="transport_recovery_lines")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="transport_recovery_lines")
    qty_actual = models.DecimalField(max_digits=20, decimal_places=6)
    unit_price = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    line_amount = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    condition_code = models.CharField(max_length=64, blank=True)
    remark = models.TextField(blank=True)

    class Meta:
        db_table = "log_transport_recovery_line"

    def clean(self):
        errors = {}
        if self.transport_order_id and self.transport_order.company_id != self.company_id:
            errors["transport_order"] = "Transport order company must match recovery line company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match recovery line company."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match recovery line company."
        if self.qty_actual is not None and self.qty_actual <= 0:
            errors["qty_actual"] = "qty_actual must be greater than zero."
        if self.transport_order_id and self.warehouse_id and self.transport_order.company_id != self.warehouse.company_id:
            errors["warehouse"] = "Warehouse company must match transport order company."
        if errors:
            raise DjangoValidationError(errors)

    def save(self, *args, **kwargs):
        self.line_amount = (self.qty_actual or Decimal("0")) * (self.unit_price or Decimal("0"))
        super().save(*args, **kwargs)

class ShipmentTrackingEvent(BaseModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="logistics_tracking_events")
    status = models.CharField(max_length=64)
    location = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    event_time = models.DateTimeField()

    class Meta:
        db_table = "log_shipment_tracking_event"

    def clean(self):
        if self.shipment_id and self.shipment.company_id != self.company_id:
            raise DjangoValidationError({"shipment": "Shipment company must match tracking event company."})

class ContainerRecoveryLine(BaseModel):
    plan = models.ForeignKey(ContainerRecoveryPlan, on_delete=models.CASCADE, related_name="lines")
    container_material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="container_recovery_lines")
    qty = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        db_table = "log_container_recovery_line"

    def clean(self):
        errors = {}
        if self.plan_id and self.plan.company_id != self.company_id:
            errors["plan"] = "Plan company must match line company."
        if self.container_material_id and self.container_material.company_id != self.company_id:
            errors["container_material"] = "Container material company must match line company."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "qty must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)

class FreightCharge(BaseModel):
    class CalcMethod(models.TextChoices):
        RULE = "rule", "Rule"
        MANUAL = "manual", "Manual"

    shipment = models.ForeignKey(Shipment, on_delete=models.PROTECT, related_name="freight_charges")
    calc_method = models.CharField(max_length=16, choices=CalcMethod.choices)
    amount = models.DecimalField(max_digits=20, decimal_places=6)
    currency = models.CharField(max_length=8)

    class Meta:
        db_table = "log_freight_charge"

    def clean(self):
        errors = {}
        if self.shipment_id and self.shipment.company_id != self.company_id:
            errors["shipment"] = "Shipment company must match freight charge company."
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "amount must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)
