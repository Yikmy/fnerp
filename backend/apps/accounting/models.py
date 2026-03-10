from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone

from apps.inventory.models import StockLedger
from apps.material.models import Material, Warehouse
from apps.production.models import ManufacturingOrder
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder
from shared.models.base import BaseModel


class AccountingInvoice(BaseModel):
    class InvoiceType(models.TextChoices):
        AR = "AR", "AR"
        AP = "AP", "AP"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    type = models.CharField(max_length=8, choices=InvoiceType.choices)
    counterparty_type = models.CharField(max_length=32)
    counterparty_id = models.UUIDField()
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=8)
    total_amount = models.DecimalField(max_digits=20, decimal_places=6)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    sales_order = models.ForeignKey(SalesOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="accounting_invoices")
    purchase_order = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="accounting_invoices")

    class Meta:
        db_table = "acct_invoice"

    def clean(self):
        errors = {}
        if self.sales_order_id and self.sales_order.company_id != self.company_id:
            errors["sales_order"] = "Sales order company must match invoice company."
        if self.purchase_order_id and self.purchase_order.company_id != self.company_id:
            errors["purchase_order"] = "Purchase order company must match invoice company."
        if self.total_amount is not None and self.total_amount < 0:
            errors["total_amount"] = "Total amount cannot be negative."
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            errors["due_date"] = "Due date cannot be earlier than issue date."
        if errors:
            raise DjangoValidationError(errors)


class Payment(BaseModel):
    class Direction(models.TextChoices):
        IN = "in", "In"
        OUT = "out", "Out"

    invoice = models.ForeignKey(AccountingInvoice, on_delete=models.PROTECT, related_name="payments")
    direction = models.CharField(max_length=8, choices=Direction.choices)
    amount = models.DecimalField(max_digits=20, decimal_places=6)
    currency = models.CharField(max_length=8)
    paid_at = models.DateTimeField(default=timezone.now)
    method = models.CharField(max_length=32, blank=True)
    reference = models.CharField(max_length=120, blank=True)

    source_ref_type = models.CharField(max_length=64, blank=True)
    source_ref_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "acct_payment"
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "source_ref_type", "source_ref_id"],
                condition=~models.Q(source_ref_type="") & models.Q(source_ref_id__isnull=False),
                name="uniq_acct_payment_source_ref",
            )
        ]

    def clean(self):
        errors = {}
        if self.invoice_id and self.invoice.company_id != self.company_id:
            errors["invoice"] = "Invoice company must match payment company."
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "Amount must be greater than zero."
        if self.direction == self.Direction.IN and self.invoice_id and self.invoice.type != AccountingInvoice.InvoiceType.AR:
            errors["direction"] = "Incoming payments require AR invoice."
        if self.direction == self.Direction.OUT and self.invoice_id and self.invoice.type != AccountingInvoice.InvoiceType.AP:
            errors["direction"] = "Outgoing payments require AP invoice."
        if errors:
            raise DjangoValidationError(errors)


class CostLayer(BaseModel):
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="accounting_cost_layers")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="accounting_cost_layers")
    in_qty = models.DecimalField(max_digits=20, decimal_places=6)
    remaining_qty = models.DecimalField(max_digits=20, decimal_places=6)
    unit_cost = models.DecimalField(max_digits=20, decimal_places=6)
    source_ledger = models.OneToOneField(StockLedger, on_delete=models.PROTECT, related_name="accounting_cost_layer")

    class Meta:
        db_table = "acct_cost_layer"

    def clean(self):
        errors = {}
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match cost layer company."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match cost layer company."
        if self.source_ledger_id and self.source_ledger.company_id != self.company_id:
            errors["source_ledger"] = "Source ledger company must match cost layer company."
        if self.remaining_qty < 0:
            errors["remaining_qty"] = "Remaining quantity cannot be negative."
        if self.in_qty < 0:
            errors["in_qty"] = "In quantity cannot be negative."
        if self.remaining_qty > self.in_qty:
            errors["remaining_qty"] = "Remaining quantity cannot exceed in quantity."
        if errors:
            raise DjangoValidationError(errors)


class FixedAsset(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISPOSED = "disposed", "Disposed"

    asset_code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=20, decimal_places=6)
    depreciation_method = models.CharField(max_length=32)
    useful_life_months = models.IntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    source_purchase_order = models.ForeignKey(
        PurchaseOrder,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fixed_assets",
    )

    class Meta:
        db_table = "acct_fixed_asset"
        unique_together = (("company_id", "asset_code"),)

    def clean(self):
        errors = {}
        if self.source_purchase_order_id and self.source_purchase_order.company_id != self.company_id:
            errors["source_purchase_order"] = "Purchase order company must match fixed asset company."
        if self.purchase_cost is not None and self.purchase_cost < 0:
            errors["purchase_cost"] = "Purchase cost cannot be negative."
        if self.useful_life_months is not None and self.useful_life_months <= 0:
            errors["useful_life_months"] = "Useful life must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)


class AssetMaintenance(BaseModel):
    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name="maintenances")
    date = models.DateField()
    content = models.TextField()
    cost = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        db_table = "acct_asset_maintenance"

    def clean(self):
        errors = {}
        if self.asset_id and self.asset.company_id != self.company_id:
            errors["asset"] = "Asset company must match maintenance company."
        if self.cost is not None and self.cost < 0:
            errors["cost"] = "Cost cannot be negative."
        if errors:
            raise DjangoValidationError(errors)


class FinancialReportSnapshot(BaseModel):
    class ReportType(models.TextChoices):
        BS = "BS", "Balance Sheet"
        PL = "PL", "Profit and Loss"
        CF = "CF", "Cash Flow"

    period = models.CharField(max_length=32)
    report_type = models.CharField(max_length=8, choices=ReportType.choices)
    payload_json = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "acct_financial_report_snapshot"
        unique_together = (("company_id", "period", "report_type"),)


class AccountingPosting(BaseModel):
    class EntryType(models.TextChoices):
        INVOICE = "invoice", "Invoice"

    class Status(models.TextChoices):
        POSTED = "posted", "Posted"
        REVERSED = "reversed", "Reversed"

    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    source_doc_type = models.CharField(max_length=64)
    source_doc_id = models.UUIDField()
    invoice = models.ForeignKey(AccountingInvoice, on_delete=models.PROTECT, related_name="postings")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.POSTED)
    posted_at = models.DateTimeField(default=timezone.now)
    reversed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    source_production_order = models.ForeignKey(
        ManufacturingOrder,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounting_postings",
    )

    class Meta:
        db_table = "acct_posting"
        unique_together = (("company_id", "entry_type", "source_doc_type", "source_doc_id"),)

    def clean(self):
        errors = {}
        if self.invoice_id and self.invoice.company_id != self.company_id:
            errors["invoice"] = "Invoice company must match posting company."
        if self.source_production_order_id and self.source_production_order.company_id != self.company_id:
            errors["source_production_order"] = "Manufacturing order company must match posting company."
        if errors:
            raise DjangoValidationError(errors)
