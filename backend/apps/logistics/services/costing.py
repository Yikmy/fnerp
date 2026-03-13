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

class FreightChargeService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_FREIGHT_CHARGE_CREATE
    PERM_UPDATE = PERMISSION_CODES.LOGISTICS_FREIGHT_CHARGE_UPDATE
    PERM_CANCEL = PERMISSION_CODES.LOGISTICS_FREIGHT_CHARGE_CANCEL

    @transaction.atomic
    def create_freight_charge(self, *, user, company_id, shipment_id, calc_method, amount, currency, request=None) -> FreightCharge:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        row = FreightCharge(
            company_id=company_id,
            shipment=self._shipment(company_id=company_id, shipment_id=shipment_id),
            calc_method=calc_method,
            amount=amount,
            currency=currency,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        row.full_clean()
        row.save()

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="logistics.freight_charge", resource_id=row.id, request=request)
        return row

    @transaction.atomic
    def update_freight_charge(self, *, user, company_id, freight_charge_id, calc_method=None, amount=None, currency=None, request=None) -> FreightCharge:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        row = FreightCharge.objects.active().for_company(company_id).filter(id=freight_charge_id).first()
        if row is None:
            raise BusinessRuleError("Freight charge not found in company scope")
        for field, value in {"calc_method": calc_method, "amount": amount, "currency": currency}.items():
            if value is not None:
                setattr(row, field, value)
        row.updated_by = self._user_id(user)
        row.full_clean()
        row.save()
        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="logistics.freight_charge", resource_id=row.id, request=request)
        return row

    @transaction.atomic
    def cancel_freight_charge(self, *, user, company_id, freight_charge_id, request=None) -> FreightCharge:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CANCEL)

        row = FreightCharge.objects.active().for_company(company_id).filter(id=freight_charge_id).first()
        if row is None:
            raise BusinessRuleError("Freight charge not found in company scope")

        row.soft_delete()
        self.audit_crud(user=user, company_id=company_id, operation="delete", resource_type="logistics.freight_charge", resource_id=row.id, request=request)
        return row

class InsurancePolicyService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_INSURANCE_POLICY_CREATE
    PERM_UPDATE = PERMISSION_CODES.LOGISTICS_INSURANCE_POLICY_UPDATE
    PERM_CANCEL = PERMISSION_CODES.LOGISTICS_INSURANCE_POLICY_CANCEL

    @transaction.atomic
    def create_policy(self, *, user, company_id, shipment_id, provider, policy_no, insured_amount, premium, request=None) -> InsurancePolicy:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        row = InsurancePolicy(
            company_id=company_id,
            shipment=self._shipment(company_id=company_id, shipment_id=shipment_id),
            provider=provider,
            policy_no=policy_no,
            insured_amount=insured_amount,
            premium=premium,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        row.full_clean()
        row.save()

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="logistics.insurance_policy", resource_id=row.id, request=request)
        return row

    @transaction.atomic
    def update_policy(self, *, user, company_id, policy_id, provider=None, policy_no=None, insured_amount=None, premium=None, request=None) -> InsurancePolicy:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        row = InsurancePolicy.objects.active().for_company(company_id).filter(id=policy_id).first()
        if row is None:
            raise BusinessRuleError("Insurance policy not found in company scope")
        for field, value in {"provider": provider, "policy_no": policy_no, "insured_amount": insured_amount, "premium": premium}.items():
            if value is not None:
                setattr(row, field, value)
        row.updated_by = self._user_id(user)
        row.full_clean()
        row.save()
        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="logistics.insurance_policy", resource_id=row.id, request=request)
        return row

    @transaction.atomic
    def cancel_policy(self, *, user, company_id, policy_id, request=None) -> InsurancePolicy:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CANCEL)

        row = InsurancePolicy.objects.active().for_company(company_id).filter(id=policy_id).first()
        if row is None:
            raise BusinessRuleError("Insurance policy not found in company scope")

        row.soft_delete()
        self.audit_crud(user=user, company_id=company_id, operation="delete", resource_type="logistics.insurance_policy", resource_id=row.id, request=request)
        return row
