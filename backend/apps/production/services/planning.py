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

class ProductionPlanService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_PLAN_CREATE
    PERM_UPDATE = PERMISSION_CODES.PRODUCTION_PLAN_UPDATE

    @transaction.atomic
    def create_plan(self, *, user, company_id, plan_date, status=ProductionPlan.Status.DRAFT, capacity_json=None, mrp_result_json=None, request=None) -> ProductionPlan:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        plan = ProductionPlan(
            company_id=company_id,
            plan_date=plan_date,
            status=status,
            capacity_json=capacity_json or {},
            mrp_result_json=mrp_result_json or {},
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        plan.full_clean()
        plan.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.plan", resource_id=plan.id, request=request)
        return plan

    @transaction.atomic
    def update_plan(self, *, user, company_id, plan_id, capacity_json=None, mrp_result_json=None, status=None, request=None) -> ProductionPlan:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        plan = ProductionPlan.objects.active().for_company(company_id).filter(id=plan_id).first()
        if plan is None:
            raise BusinessRuleError("Production plan not found in company scope")

        if capacity_json is not None:
            plan.capacity_json = capacity_json
        if mrp_result_json is not None:
            plan.mrp_result_json = mrp_result_json
        if status is not None:
            plan.status = status
        plan.updated_by = self._user_id(user)
        plan.full_clean()
        plan.save()

        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="production.plan", resource_id=plan.id, request=request)
        return plan
