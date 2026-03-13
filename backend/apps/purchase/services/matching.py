from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from apps.inventory.models import StockLedger
from apps.inventory.services import StockLedgerService
from apps.material.models import Material, Warehouse
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from .workflow import PurchaseDomainService
from ..models import (
    GoodsReceipt,
    GoodsReceiptLine,
    InvoiceMatch,
    IQCRecord,
    PurchaseOrder,
    PurchaseOrderLine,
    RFQLine,
    RFQQuote,
    RFQTask,
    Vendor,
    VendorHistory,
)

class APMatchingService(PurchaseDomainService):
    PERM_CREATE = PERMISSION_CODES.PURCHASE_AP_MATCH_CREATE

    @transaction.atomic
    def create_invoice_match(self, *, user, company_id, invoice_id, po_id=None, grn_id=None, matched_amount=Decimal("0"), rule_json=None, request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        po = None
        if po_id:
            po = PurchaseOrder.objects.active().for_company(company_id).filter(id=po_id).first()
            if po is None:
                raise BusinessRuleError("Purchase order not found in company scope")
            if po.company_id != company_id:
                raise BusinessRuleError("Purchase order company mismatch")

        grn = None
        if grn_id:
            grn = GoodsReceipt.objects.active().for_company(company_id).filter(id=grn_id).first()
            if grn is None:
                raise BusinessRuleError("Goods receipt not found in company scope")
            if grn.company_id != company_id:
                raise BusinessRuleError("Goods receipt company mismatch")

        if po and grn and po.company_id != grn.company_id:
            raise BusinessRuleError("PO and GRN company mismatch")

        match = InvoiceMatch(
            company_id=company_id,
            invoice_id=invoice_id,
            po=po,
            grn=grn,
            matched_amount=matched_amount,
            rule_json=rule_json or {},
        )
        match.full_clean()
        match.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="purchase.invoice_match",
            resource_id=match.id,
            request=request,
        )
        return match
