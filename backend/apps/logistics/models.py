from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models

from apps.material.models import Material
from apps.sales.models import Customer, Shipment
from shared.models.base import BaseModel


class TransportOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ASSIGNED = "assigned", "Assigned"
        IN_TRANSIT = "in_transit", "In Transit"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    shipment = models.ForeignKey(Shipment, on_delete=models.PROTECT, related_name="transport_orders")
    carrier = models.CharField(max_length=120)
    vehicle_no = models.CharField(max_length=64, blank=True)
    driver_name = models.CharField(max_length=120, blank=True)
    driver_contact = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    planned_departure = models.DateTimeField(null=True, blank=True)
    planned_arrival = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "log_transport_order"

    def clean(self):
        errors = {}
        if self.shipment_id and self.shipment.company_id != self.company_id:
            errors["shipment"] = "Shipment company must match transport order company."
        if self.planned_departure and self.planned_arrival and self.planned_arrival < self.planned_departure:
            errors["planned_arrival"] = "planned_arrival cannot be earlier than planned_departure."
        if errors:
            raise DjangoValidationError(errors)


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


class ContainerRecoveryPlan(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="container_recovery_plans")
    planned_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        db_table = "log_container_recovery_plan"

    def clean(self):
        if self.customer_id and self.customer.company_id != self.company_id:
            raise DjangoValidationError({"customer": "Customer company must match recovery plan company."})


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
        if self.amount is not None and self.amount < 0:
            errors["amount"] = "amount cannot be negative."
        if errors:
            raise DjangoValidationError(errors)


class InsurancePolicy(BaseModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.PROTECT, related_name="insurance_policies")
    provider = models.CharField(max_length=255)
    policy_no = models.CharField(max_length=120)
    insured_amount = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    premium = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))

    class Meta:
        db_table = "log_insurance_policy"
        unique_together = (("company_id", "policy_no"),)

    def clean(self):
        errors = {}
        if self.shipment_id and self.shipment.company_id != self.company_id:
            errors["shipment"] = "Shipment company must match insurance policy company."
        if self.insured_amount is not None and self.insured_amount < 0:
            errors["insured_amount"] = "insured_amount cannot be negative."
        if self.premium is not None and self.premium < 0:
            errors["premium"] = "premium cannot be negative."
        if errors:
            raise DjangoValidationError(errors)
