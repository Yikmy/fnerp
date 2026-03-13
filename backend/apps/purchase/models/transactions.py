from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Serial
from apps.material.models import Material, Warehouse
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel
from .documents import GoodsReceipt, PurchaseOrder

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
