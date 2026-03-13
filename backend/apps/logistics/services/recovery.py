from django.db import transaction
from apps.inventory.models import StockLedger
from apps.inventory.services import StockLedgerService
from apps.material.models import Material, Warehouse
from apps.sales.models import Customer, SalesOrder, Shipment
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from .workflow import LogisticsDomainService
from ..models import (
    ContainerRecoveryLine,
    ContainerRecoveryPlan,
    FreightCharge,
    InsurancePolicy,
    ShipmentTrackingEvent,
    TransportOrder,
    TransportRecoveryLine,
)

class ContainerRecoveryService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_CONTAINER_RECOVERY_CREATE
    PERM_UPDATE = PERMISSION_CODES.LOGISTICS_CONTAINER_RECOVERY_UPDATE
    PERM_CANCEL = PERMISSION_CODES.LOGISTICS_CONTAINER_RECOVERY_CANCEL

    @transaction.atomic
    def create_plan(self, *, user, company_id, customer_id, planned_date=None, status=DOC_STATUS.DRAFT, lines=None, request=None) -> ContainerRecoveryPlan:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        plan = ContainerRecoveryPlan(
            company_id=company_id,
            customer=self._customer(company_id=company_id, customer_id=customer_id),
            planned_date=planned_date,
            status=status,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        plan.full_clean()
        plan.save()

        for line in lines or []:
            row = ContainerRecoveryLine(
                company_id=company_id,
                plan=plan,
                container_material=self._material(company_id=company_id, material_id=line["container_material_id"]),
                qty=line["qty"],
                created_by=self._user_id(user),
                updated_by=self._user_id(user),
            )
            row.full_clean()
            row.save()

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="logistics.container_recovery_plan", resource_id=plan.id, request=request)
        return plan

    @transaction.atomic
    def update_plan(self, *, user, company_id, plan_id, planned_date=None, request=None) -> ContainerRecoveryPlan:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        plan = ContainerRecoveryPlan.objects.active().for_company(company_id).filter(id=plan_id).first()
        if plan is None:
            raise BusinessRuleError("Container recovery plan not found in company scope")
        if plan.status in {DOC_STATUS.COMPLETED, DOC_STATUS.CANCELLED}:
            raise BusinessRuleError("Completed or cancelled recovery plan cannot be updated")

        if planned_date is not None:
            plan.planned_date = planned_date
        plan.updated_by = self._user_id(user)
        plan.full_clean()
        plan.save()
        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="logistics.container_recovery_plan", resource_id=plan.id, request=request)
        return plan

    @transaction.atomic
    def transition_plan(self, *, user, company_id, plan_id, to_status, notes="", request=None) -> ContainerRecoveryPlan:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        plan = ContainerRecoveryPlan.objects.active().for_company(company_id).filter(id=plan_id).first()
        if plan is None:
            raise BusinessRuleError("Container recovery plan not found in company scope")

        plan = self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=plan,
            document_type="logistics.container_recovery_plan",
            to_state=to_status,
            notes=notes,
            request=request,
        )
        plan.updated_by = self._user_id(user)
        plan.save(update_fields=["updated_by", "updated_at"])
        return plan
