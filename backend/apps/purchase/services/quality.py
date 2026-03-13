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

class IQCService(PurchaseDomainService):
    PERM_CREATE = PERMISSION_CODES.PURCHASE_IQC_CREATE

    @transaction.atomic
    def create_iqc_record(self, *, user, company_id, grn_id, result, notes="", request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        grn = GoodsReceipt.objects.active().for_company(company_id).filter(id=grn_id).first()
        if grn is None:
            raise BusinessRuleError("Goods receipt not found in company scope")

        iqc = IQCRecord(
            company_id=company_id,
            grn=grn,
            result=result,
            inspector_id=self._user_id(user),
            notes=notes,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        iqc.full_clean()
        iqc.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="purchase.iqc",
            resource_id=iqc.id,
            request=request,
        )
        return iqc
