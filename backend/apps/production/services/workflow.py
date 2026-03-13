from decimal import Decimal
from django.db import transaction
from apps.inventory.models import Reservation, StockLedger
from apps.inventory.services import ReservationService, StockLedgerService
from apps.material.models import Material, Warehouse
from apps.sales.models import SalesOrder
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from ..models import BOM, BOMLine, IoTDevice, IoTMetric, MOIssueLine, MOReceiptLine, ManufacturingOrder, ProductionPlan, ProductionQC

class ProductionDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.PRODUCTION

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    @staticmethod
    def _status_value(status):
        return getattr(status, "value", status)

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("production module is disabled for this company")

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

    def _sales_order(self, *, company_id, sales_order_id) -> SalesOrder:
        sales_order = SalesOrder.objects.active().for_company(company_id).filter(id=sales_order_id).first()
        if sales_order is None:
            raise BusinessRuleError("Sales order not found in company scope")
        return sales_order

    def _mo(self, *, company_id, mo_id) -> ManufacturingOrder:
        mo = ManufacturingOrder.objects.active().for_company(company_id).filter(id=mo_id).first()
        if mo is None:
            raise BusinessRuleError("Manufacturing order not found in company scope")
        return mo

    def _validate_mto_alignment(self, *, mo: ManufacturingOrder):
        if mo.production_mode != ManufacturingOrder.ProductionMode.MAKE_TO_ORDER:
            return
        if not mo.sales_order_id:
            raise BusinessRuleError("MTO manufacturing order requires linked sales order")
        if not mo.sales_order.lines.filter(material_id=mo.product_material_id).exists():
            raise BusinessRuleError("MTO product material must exist in linked sales order lines")
