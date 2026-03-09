from django.db import transaction

from apps.material.models import Material
from apps.sales.models import Customer, SalesOrder, Shipment
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
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

    def _sales_order(self, *, company_id, sales_order_id) -> SalesOrder:
        sales_order = SalesOrder.objects.active().for_company(company_id).filter(id=sales_order_id).first()
        if sales_order is None:
            raise BusinessRuleError("Sales order not found in company scope")
        return sales_order

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

    def __init__(self):
        super().__init__()
        self.transition_service = DocumentStateTransitionService()


class TransportOrderService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_TRANSPORT_ORDER_CREATE
    PERM_UPDATE = PERMISSION_CODES.LOGISTICS_TRANSPORT_ORDER_UPDATE
    PERM_CANCEL = PERMISSION_CODES.LOGISTICS_TRANSPORT_ORDER_CANCEL

    @transaction.atomic
    def create_transport_order(self, *, user, company_id, shipment_id, carrier, sales_order_id=None, vehicle_no="", driver_name="", driver_contact="", status=DOC_STATUS.DRAFT, planned_departure=None, planned_arrival=None, request=None) -> TransportOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        shipment = self._shipment(company_id=company_id, shipment_id=shipment_id)
        sales_order = self._sales_order(company_id=company_id, sales_order_id=sales_order_id or shipment.so_id)
        if shipment.so_id != sales_order.id:
            raise BusinessRuleError("Sales order must match shipment sales order")

        row = TransportOrder(
            company_id=company_id,
            shipment=shipment,
            sales_order=sales_order,
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

    @transaction.atomic
    def update_transport_order(self, *, user, company_id, transport_order_id, carrier=None, vehicle_no=None, driver_name=None, driver_contact=None, planned_departure=None, planned_arrival=None, request=None) -> TransportOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)
        row = TransportOrder.objects.active().for_company(company_id).filter(id=transport_order_id).first()
        if row is None:
            raise BusinessRuleError("Transport order not found in company scope")
        if row.status == DOC_STATUS.CANCELLED:
            raise BusinessRuleError("Cancelled transport order cannot be updated")

        for field, value in {
            "carrier": carrier,
            "vehicle_no": vehicle_no,
            "driver_name": driver_name,
            "driver_contact": driver_contact,
            "planned_departure": planned_departure,
            "planned_arrival": planned_arrival,
        }.items():
            if value is not None:
                setattr(row, field, value)

        row.updated_by = self._user_id(user)
        row.full_clean()
        row.save()
        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="logistics.transport_order", resource_id=row.id, request=request)
        return row

    @transaction.atomic
    def transition_transport_order(self, *, user, company_id, transport_order_id, to_status, notes="", request=None) -> TransportOrder:
        self._ensure_module_enabled(company_id=company_id)
        # Update permission guards logistics write capability; transition permission is enforced by shared state machine.
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        row = TransportOrder.objects.active().for_company(company_id).filter(id=transport_order_id).first()
        if row is None:
            raise BusinessRuleError("Transport order not found in company scope")

        row = self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=row,
            document_type="logistics.transport_order",
            to_state=to_status,
            notes=notes,
            request=request,
        )
        row.updated_by = self._user_id(user)
        row.save(update_fields=["updated_by", "updated_at"])
        return row


class ShipmentTrackingService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_CREATE
    PERM_UPDATE = PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_UPDATE
    PERM_CANCEL = PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_CANCEL

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

    @transaction.atomic
    def update_tracking_event(self, *, user, company_id, event_id, status=None, location=None, note=None, event_time=None, request=None) -> ShipmentTrackingEvent:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        row = ShipmentTrackingEvent.objects.active().for_company(company_id).filter(id=event_id).first()
        if row is None:
            raise BusinessRuleError("Shipment tracking event not found in company scope")

        for field, value in {"status": status, "location": location, "note": note, "event_time": event_time}.items():
            if value is not None:
                setattr(row, field, value)
        row.updated_by = self._user_id(user)
        row.full_clean()
        row.save()
        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="logistics.shipment_tracking_event", resource_id=row.id, request=request)
        return row

    @transaction.atomic
    def cancel_tracking_event(self, *, user, company_id, event_id, request=None) -> ShipmentTrackingEvent:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CANCEL)

        row = ShipmentTrackingEvent.objects.active().for_company(company_id).filter(id=event_id).first()
        if row is None:
            raise BusinessRuleError("Shipment tracking event not found in company scope")

        row.soft_delete()
        self.audit_crud(user=user, company_id=company_id, operation="delete", resource_type="logistics.shipment_tracking_event", resource_id=row.id, request=request)
        return row


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
