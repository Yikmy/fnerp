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
from .workflow import ProductionDomainService

class BOMService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_BOM_CREATE

    @transaction.atomic
    def create_bom(self, *, user, company_id, product_material_id, version=1, status=BOM.Status.DRAFT, notes="", lines=None, request=None) -> BOM:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        bom = BOM(
            company_id=company_id,
            product_material=self._material(company_id=company_id, material_id=product_material_id),
            version=version,
            status=status,
            notes=notes,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        bom.full_clean()
        bom.save()

        for line in lines or []:
            bom_line = BOMLine(
                company_id=company_id,
                bom=bom,
                component_material=self._material(company_id=company_id, material_id=line["component_material_id"]),
                qty_per_unit=line["qty_per_unit"],
                scrap_rate=line.get("scrap_rate", Decimal("0")),
                component_bom_id=line.get("component_bom_id"),
                created_by=self._user_id(user),
                updated_by=self._user_id(user),
            )
            bom_line.full_clean()
            bom_line.save()

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.bom", resource_id=bom.id, request=request)
        return bom
