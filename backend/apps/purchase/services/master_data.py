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

class VendorService(PurchaseDomainService):
    PERM_CREATE = PERMISSION_CODES.PURCHASE_VENDOR_CREATE

    @transaction.atomic
    def create_vendor(self, *, user, company_id, code, name, contact_json=None, rating=Decimal("0"), notes="", request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        vendor = Vendor(
            company_id=company_id,
            code=code,
            name=name,
            contact_json=contact_json or {},
            rating=rating,
            notes=notes,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        vendor.full_clean()
        vendor.save()

        VendorHistory.objects.create(vendor=vendor, event_type="created", content={"code": code, "name": name})
        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="purchase.vendor",
            resource_id=vendor.id,
            request=request,
        )
        return vendor
