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

class PurchaseDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.PURCHASE

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("purchase module is disabled for this company")

    def _vendor(self, *, company_id, vendor_id) -> Vendor:
        vendor = Vendor.objects.active().for_company(company_id).filter(id=vendor_id, is_active=True).first()
        if vendor is None:
            raise BusinessRuleError("Vendor not found in company scope")
        return vendor

    def _material(self, *, company_id, material_id) -> Material:
        material = Material.objects.active().for_company(company_id).filter(id=material_id, is_active=True).first()
        if material is None:
            raise BusinessRuleError("Material not found in company scope")
        return material

    def _warehouse(self, *, company_id, warehouse_id) -> Warehouse:
        warehouse = Warehouse.objects.active().for_company(company_id).filter(id=warehouse_id, is_active=True).first()
        if warehouse is None:
            raise BusinessRuleError("Warehouse not found in company scope")
        return warehouse
