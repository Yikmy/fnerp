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

class ProductionQCService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_QC_CREATE

    @transaction.atomic
    def create_qc_record(self, *, user, company_id, mo_id, stage, result, inspector_id, notes="", measurements_json=None, request=None) -> ProductionQC:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        mo = self._mo(company_id=company_id, mo_id=mo_id)
        if mo.status in {DOC_STATUS.CANCELLED.value, DOC_STATUS.COMPLETED.value}:
            raise BusinessRuleError("QC cannot be recorded for completed or cancelled manufacturing order")

        qc = ProductionQC(
            company_id=company_id,
            mo=mo,
            stage=stage,
            result=result,
            inspector_id=inspector_id,
            notes=notes,
            measurements_json=measurements_json or {},
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        qc.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.qc", resource_id=qc.id, request=request)
        return qc
