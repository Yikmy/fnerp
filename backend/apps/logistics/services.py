from django.db import transaction

from apps.material.models import Material
from apps.sales.models import Customer, Shipment
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService

from .models import (
    ContainerRecoveryLine,
    ContainerRecoveryPlan,
    FreightCharge,
    InsurancePolicy,
    ShipmentTrackingEvent,
    TransportOrder,
)


class LogisticsDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.LOGISTICS

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("logistics module is disabled for this company")

    def _shipment(self, *, company_id, shipment_id) -> Shipment:
        shipment = Shipment.objects.active().for_company(company_id).filter(id=shipment_id).first()
        if shipment is None:
            raise BusinessRuleError("Shipment not found in company scope")
        return shipment

    def _customer(self, *, company_id, customer_id) -> Customer:
        customer = Customer.objects.active().for_company(company_id).filter(id=customer_id, is_active=True).first()
        if customer is None:
            raise BusinessRuleError("Customer not found in company scope")
        return customer

    def _material(self, *, company_id, material_id) -> Material:
        material = Material.objects.active().for_company(company_id).filter(id=material_id, is_active=True).first()
        if material is None:
            raise BusinessRuleError("Material not found in company scope")
        return material


class TransportOrderService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_TRANSPORT_ORDER_CREATE

    @transaction.atomic
    def create_transport_order(self, *, user, company_id, shipment_id, carrier, vehicle_no="", driver_name="", driver_contact="", status=TransportOrder.Status.DRAFT, planned_departure=None, planned_arrival=None, request=None) -> TransportOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        row = TransportOrder(
            company_id=company_id,
            shipment=self._shipment(company_id=company_id, shipment_id=shipment_id),
            carrier=carrier,
            vehicle_no=vehicle_no,
            driver_name=driver_name,
            driver_contact=driver_contact,
            status=status,
            planned_departure=planned_departure,
            planned_arrival=planned_arrival,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        row.full_clean()
        row.save()

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="logistics.transport_order", resource_id=row.id, request=request)
        return row


class ShipmentTrackingService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_CREATE

    @transaction.atomic
    def create_tracking_event(self, *, user, company_id, shipment_id, status, event_time, location="", note="", request=None) -> ShipmentTrackingEvent:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        row = ShipmentTrackingEvent(
            company_id=company_id,
            shipment=self._shipment(company_id=company_id, shipment_id=shipment_id),
            status=status,
            location=location,
            note=note,
            event_time=event_time,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        row.full_clean()
        row.save()

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="logistics.shipment_tracking_event", resource_id=row.id, request=request)
        return row


class ContainerRecoveryService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_CONTAINER_RECOVERY_CREATE

    @transaction.atomic
    def create_plan(self, *, user, company_id, customer_id, planned_date=None, status=ContainerRecoveryPlan.Status.DRAFT, lines=None, request=None) -> ContainerRecoveryPlan:
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


class FreightChargeService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_FREIGHT_CHARGE_CREATE

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


class InsurancePolicyService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_INSURANCE_POLICY_CREATE

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
