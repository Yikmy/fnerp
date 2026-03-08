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


class RFQTask(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    llm_enabled = models.BooleanField(default=False)
    schedule_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "pur_rfq_task"


class RFQLine(models.Model):
    id = models.BigAutoField(primary_key=True)
    rfq = models.ForeignKey(RFQTask, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="rfq_lines")
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    target_date = models.DateField()

    class Meta:
        db_table = "pur_rfq_line"

    def clean(self):
        errors = {}
        if self.rfq_id and self.material_id and self.rfq.company_id != self.material.company_id:
            errors["material"] = "Material company must match RFQ company."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "qty must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)


class RFQQuote(models.Model):
    id = models.BigAutoField(primary_key=True)
    rfq = models.ForeignKey(RFQTask, on_delete=models.CASCADE, related_name="quotes")
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="quotes")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="rfq_quotes")
    price = models.DecimalField(max_digits=20, decimal_places=6)
    currency = models.CharField(max_length=8)
    lead_time_days = models.IntegerField()
    valid_until = models.DateField()
    source = models.CharField(max_length=32, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "pur_rfq_quote"

    def clean(self):
        errors = {}
        if self.rfq_id and self.vendor_id and self.rfq.company_id != self.vendor.company_id:
            errors["vendor"] = "Vendor company must match RFQ company."
        if self.rfq_id and self.material_id and self.rfq.company_id != self.material.company_id:
            errors["material"] = "Material company must match RFQ company."
        if self.price is not None and self.price < 0:
            errors["price"] = "price cannot be negative."
        if self.lead_time_days is not None and self.lead_time_days < 0:
            errors["lead_time_days"] = "lead_time_days cannot be negative."
        if errors:
            raise DjangoValidationError(errors)


class PurchaseOrder(BaseModel):
    doc_no = models.CharField(max_length=64)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=20, choices=[(s, s) for s in DOC_STATUS], default=DOC_STATUS.DRAFT)
    expected_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=8)
    total_amount = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    remark = models.TextField(blank=True)

    class Meta:
        db_table = "pur_purchase_order"
        unique_together = (("company_id", "doc_no"),)

    def clean(self):
        if self.vendor_id and self.vendor.company_id != self.company_id:
            raise DjangoValidationError({"vendor": "Vendor company must match PO company."})


class PurchaseOrderLine(models.Model):
    id = models.BigAutoField(primary_key=True)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="purchase_order_lines")
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    price = models.DecimalField(max_digits=20, decimal_places=6)
    tax_rate = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0"))
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_order_lines")
    suggested_qty = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))

    class Meta:
        db_table = "pur_purchase_order_line"

    def clean(self):
        errors = {}
        if self.po_id and self.material_id and self.po.company_id != self.material.company_id:
            errors["material"] = "Material company must match PO company."
        if self.po_id and self.warehouse_id and self.po.company_id != self.warehouse.company_id:
            errors["warehouse"] = "Warehouse company must match PO company."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "qty must be greater than zero."
        if self.price is not None and self.price < 0:
            errors["price"] = "price cannot be negative."
        if errors:
            raise DjangoValidationError(errors)


class GoodsReceipt(BaseModel):
    doc_no = models.CharField(max_length=64)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="goods_receipts")
    received_date = models.DateField()
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="goods_receipts")
    is_partial = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=[(s, s) for s in DOC_STATUS], default=DOC_STATUS.DRAFT)

    class Meta:
        db_table = "pur_goods_receipt"
        unique_together = (("company_id", "doc_no"),)

    def clean(self):
        errors = {}
        if self.po_id and self.po.company_id != self.company_id:
            errors["po"] = "Purchase order company must match GRN company."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match GRN company."
        if errors:
            raise DjangoValidationError(errors)


class GoodsReceiptLine(models.Model):
    id = models.BigAutoField(primary_key=True)
    grn = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    po_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT, related_name="goods_receipt_lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="goods_receipt_lines")
    received_qty = models.DecimalField(max_digits=20, decimal_places=6)
    lot = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.PROTECT, related_name="goods_receipt_lines")
    serial = models.ForeignKey(
        Serial,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="goods_receipt_lines",
    )

    class Meta:
        db_table = "pur_goods_receipt_line"

    def clean(self):
        errors = {}
        if self.grn_id and self.po_line_id and self.grn.po_id != self.po_line.po_id:
            errors["po_line"] = "PO line must belong to GRN purchase order."
        if self.grn_id and self.material_id and self.grn.company_id != self.material.company_id:
            errors["material"] = "Material company must match GRN company."
        if self.received_qty is not None and self.received_qty <= 0:
            errors["received_qty"] = "received_qty must be greater than zero."
        if self.lot_id and self.material_id and self.lot.material_id != self.material_id:
            errors["lot"] = "Lot material must match receipt material."
        if self.serial_id and self.material_id and self.serial.material_id != self.material_id:
            errors["serial"] = "Serial material must match receipt material."
        if errors:
            raise DjangoValidationError(errors)


class IQCRecord(BaseModel):
    class Result(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        HOLD = "hold", "Hold"

    grn = models.ForeignKey(GoodsReceipt, on_delete=models.PROTECT, related_name="iqc_records")
    result = models.CharField(max_length=8, choices=Result.choices)
    inspector_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "pur_iqc_record"

    def clean(self):
        if self.grn_id and self.grn.company_id != self.company_id:
            raise DjangoValidationError({"grn": "GRN company must match IQC company."})


class InvoiceMatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.UUIDField(db_index=True)
    invoice_id = models.UUIDField()
    po = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="invoice_matches")
    grn = models.ForeignKey(GoodsReceipt, null=True, blank=True, on_delete=models.PROTECT, related_name="invoice_matches")
    matched_amount = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    rule_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pur_invoice_match"

    def clean(self):
        errors = {}
        if self.po_id and self.po.company_id != self.company_id:
            errors["po"] = "PO company must match invoice match company."
        if self.grn_id and self.grn.company_id != self.company_id:
            errors["grn"] = "GRN company must match invoice match company."
        if self.po_id and self.grn_id and self.po.company_id != self.grn.company_id:
            errors["grn"] = "PO and GRN must be in the same company."
        if self.matched_amount is not None and self.matched_amount < 0:
            errors["matched_amount"] = "matched_amount cannot be negative."
        if errors:
            raise DjangoValidationError(errors)
