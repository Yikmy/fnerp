from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Serial
from apps.material.models import Material, Warehouse
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel
from .master_data import Customer

class SalesQuote(BaseModel):
    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    doc_no = models.CharField(max_length=64)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_quotes")
    valid_until = models.DateField(null=True, blank=True)
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    total_amount = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    status = models.CharField(max_length=20, choices=[(s, s) for s in DOC_STATUS], default=DOC_STATUS.DRAFT)

    class Meta:
        db_table = "sal_sales_quote"
        unique_together = (("company_id", "doc_no"),)

    def clean(self):
        if self.customer_id and self.customer.company_id != self.company_id:
            raise DjangoValidationError({"customer": "Customer company must match quote company."})

class SalesQuoteLine(BaseModel):
    quote = models.ForeignKey(SalesQuote, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="sales_quote_lines")
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    price = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        db_table = "sal_sales_quote_line"

    def clean(self):
        errors = {}
        if self.quote_id and self.quote.company_id != self.company_id:
            errors["quote"] = "Quote company must match line company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match quote company."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "qty must be greater than zero."
        if self.price is not None and self.price < 0:
            errors["price"] = "price cannot be negative."
        if errors:
            raise DjangoValidationError(errors)

class SalesOrder(BaseModel):
    doc_no = models.CharField(max_length=64)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_orders")
    delivery_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    special_terms = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[(s, s) for s in DOC_STATUS], default=DOC_STATUS.DRAFT)

    class Meta:
        db_table = "sal_sales_order"
        unique_together = (("company_id", "doc_no"),)

    def clean(self):
        if self.customer_id and self.customer.company_id != self.company_id:
            raise DjangoValidationError({"customer": "Customer company must match order company."})

class SalesOrderLine(BaseModel):
    so = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="sales_order_lines")
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    price = models.DecimalField(max_digits=20, decimal_places=6)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sales_order_lines")
    reserved_qty = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))

    class Meta:
        db_table = "sal_sales_order_line"

    def clean(self):
        errors = {}
        if self.so_id and self.so.company_id != self.company_id:
            errors["so"] = "Sales order company must match line company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match line company."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match line company."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "qty must be greater than zero."
        if self.reserved_qty is not None and self.reserved_qty < 0:
            errors["reserved_qty"] = "reserved_qty cannot be negative."
        if self.reserved_qty is not None and self.qty is not None and self.reserved_qty > self.qty:
            errors["reserved_qty"] = "reserved_qty cannot exceed qty."
        if errors:
            raise DjangoValidationError(errors)

class Shipment(BaseModel):
    doc_no = models.CharField(max_length=64)
    so = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="shipments")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="shipments")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="shipments")
    ship_date = models.DateField()
    status = models.CharField(max_length=20, choices=[(s, s) for s in DOC_STATUS], default=DOC_STATUS.DRAFT)
    carrier = models.CharField(max_length=120, blank=True)
    tracking_no = models.CharField(max_length=120, blank=True)

    class Meta:
        db_table = "sal_shipment"
        unique_together = (("company_id", "doc_no"),)

    def clean(self):
        errors = {}
        if self.so_id and self.so.company_id != self.company_id:
            errors["so"] = "Sales order company must match shipment company."
        if self.customer_id and self.customer.company_id != self.company_id:
            errors["customer"] = "Customer company must match shipment company."
        if self.so_id and self.customer_id and self.so.customer_id != self.customer_id:
            errors["customer"] = "Shipment customer must match sales order customer."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match shipment company."
        if errors:
            raise DjangoValidationError(errors)

class ShipmentLine(BaseModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="lines")
    so_line = models.ForeignKey(SalesOrderLine, on_delete=models.PROTECT, related_name="shipment_lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="shipment_lines")
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    lot = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.PROTECT, related_name="shipment_lines")
    serial = models.ForeignKey(Serial, null=True, blank=True, on_delete=models.PROTECT, related_name="shipment_lines")

    class Meta:
        db_table = "sal_shipment_line"

    def clean(self):
        errors = {}
        if self.shipment_id and self.shipment.company_id != self.company_id:
            errors["shipment"] = "Shipment company must match line company."
        if self.so_line_id and self.so_line.company_id != self.company_id:
            errors["so_line"] = "Sales order line company must match shipment line company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match shipment line company."
        if self.so_line_id and self.material_id and self.so_line.material_id != self.material_id:
            errors["material"] = "Shipment line material must match sales order line material."
        if self.lot_id and (self.lot.company_id != self.company_id or self.lot.material_id != self.material_id):
            errors["lot"] = "Lot must match company and material."
        if self.serial_id and (self.serial.company_id != self.company_id or self.serial.material_id != self.material_id):
            errors["serial"] = "Serial must match company and material."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "qty must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)

class POD(BaseModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="pods")
    delivered_at = models.DateTimeField()
    receiver_name = models.CharField(max_length=120)
    proof_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "sal_pod"

    def clean(self):
        if self.shipment_id and self.shipment.company_id != self.company_id:
            raise DjangoValidationError({"shipment": "Shipment company must match POD company."})

class ShipmentStatusEvent(BaseModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="status_events")
    event_code = models.CharField(max_length=64)
    event_time = models.DateTimeField()
    payload_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "sal_shipment_status_event"

    def clean(self):
        if self.shipment_id and self.shipment.company_id != self.company_id:
            raise DjangoValidationError({"shipment": "Shipment company must match event company."})

class RMA(BaseModel):
    doc_no = models.CharField(max_length=64)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="rmas")
    so = models.ForeignKey(SalesOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="rmas")
    reason_code = models.CharField(max_length=64)
    reason_text = models.TextField(blank=True)
    quality_issue_flag = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=[(s, s) for s in DOC_STATUS], default=DOC_STATUS.DRAFT)

    class Meta:
        db_table = "sal_rma"
        unique_together = (("company_id", "doc_no"),)

    def clean(self):
        errors = {}
        if self.customer_id and self.customer.company_id != self.company_id:
            errors["customer"] = "Customer company must match RMA company."
        if self.so_id and self.so.company_id != self.company_id:
            errors["so"] = "Sales order company must match RMA company."
        if self.so_id and self.customer_id and self.so.customer_id != self.customer_id:
            errors["customer"] = "RMA customer must match sales order customer."
        if errors:
            raise DjangoValidationError(errors)

class RMALine(BaseModel):
    rma = models.ForeignKey(RMA, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="rma_lines")
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="rma_lines")
    lot = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.PROTECT, related_name="rma_lines")
    serial = models.ForeignKey(Serial, null=True, blank=True, on_delete=models.PROTECT, related_name="rma_lines")

    class Meta:
        db_table = "sal_rma_line"

    def clean(self):
        errors = {}
        if self.rma_id and self.rma.company_id != self.company_id:
            errors["rma"] = "RMA company must match line company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match line company."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match line company."
        if self.lot_id and (self.lot.company_id != self.company_id or self.lot.material_id != self.material_id):
            errors["lot"] = "Lot must match company and material."
        if self.serial_id and (self.serial.company_id != self.company_id or self.serial.material_id != self.material_id):
            errors["serial"] = "Serial must match company and material."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "qty must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)
