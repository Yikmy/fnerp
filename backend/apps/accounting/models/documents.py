from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone
from apps.material.models import Material
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
