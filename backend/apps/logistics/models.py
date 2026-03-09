from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models

from apps.material.models import Material
from apps.sales.models import Customer, SalesOrder, Shipment
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel


class TransportOrder(BaseModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.PROTECT, related_name="transport_orders")
    sales_order = models.ForeignKey(SalesOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="transport_orders")
    carrier = models.CharField(max_length=120)
    vehicle_no = models.CharField(max_length=64, blank=True)
    driver_name = models.CharField(max_length=120, blank=True)
    driver_contact = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=[(s, s) for s in DOC_STATUS], default=DOC_STATUS.DRAFT)
    planned_departure = models.DateTimeField(null=True, blank=True)
    planned_arrival = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "log_transport_order"

    def clean(self):
        errors = {}
        if self.shipment_id and self.shipment.company_id != self.company_id:
            errors["shipment"] = "Shipment company must match transport order company."
        if self.sales_order_id and self.sales_order.company_id != self.company_id:
            errors["sales_order"] = "Sales order company must match transport order company."
        if self.shipment_id and self.sales_order_id and self.shipment.so_id != self.sales_order_id:
            errors["sales_order"] = "Sales order must match shipment sales order."
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
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="container_recovery_plans")
    planned_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[(s, s) for s in DOC_STATUS], default=DOC_STATUS.DRAFT)

    class Meta:
        db_table = "log_container_recovery_plan"

    def clean(self):
        errors = {}
        if self.customer_id and self.customer.company_id != self.company_id:
            errors["customer"] = "Customer company must match recovery plan company."
        if self.pk and self.status == DOC_STATUS.COMPLETED and not self.lines.exists():
            errors["status"] = "Cannot complete container recovery plan without lines."
        if errors:
            raise DjangoValidationError(errors)


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
        if self.insured_amount is not None and self.insured_amount <= 0:
            errors["insured_amount"] = "insured_amount must be greater than zero."
        if self.premium is not None and self.premium <= 0:
            errors["premium"] = "premium must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)
