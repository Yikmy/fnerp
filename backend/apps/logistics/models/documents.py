from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.material.models import Material, Warehouse
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
    actual_departure_at = models.DateTimeField(null=True, blank=True)
    actual_arrival_at = models.DateTimeField(null=True, blank=True)
    receiver_name = models.CharField(max_length=120, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    completion_note = models.TextField(blank=True)
    signoff_meta = models.JSONField(default=dict, blank=True)

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
        if self.actual_departure_at and self.actual_arrival_at and self.actual_arrival_at < self.actual_departure_at:
            errors["actual_arrival_at"] = "actual_arrival_at cannot be earlier than actual_departure_at."
        if errors:
            raise DjangoValidationError(errors)

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
