from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone
from apps.material.models import Material
from apps.production.models import ManufacturingOrder
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder
from shared.models.base import BaseModel
from .documents import AccountingInvoice

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
        if self.invoice_id and self.currency and self.currency != self.invoice.currency:
            errors["currency"] = "Payment currency must match invoice currency."
        if errors:
            raise DjangoValidationError(errors)

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
