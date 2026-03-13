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

        prior_status = row.status
        row = self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=row,
            document_type="logistics.transport_order",
            to_state=to_status,
            notes=notes,
            request=request,
        )
        if prior_status != DOC_STATUS.COMPLETED and to_status == DOC_STATUS.COMPLETED:
            self._post_transport_recovery_inventory(user=user, company_id=company_id, transport_order=row, request=request)
        row.updated_by = self._user_id(user)
        row.save(update_fields=["updated_by", "updated_at"])
        return row

    def _post_transport_recovery_inventory(self, *, user, company_id, transport_order: TransportOrder, request=None):
        if StockLedger.objects.filter(
            company_id=company_id,
            ref_doc_type="logistics.transport_order_recovery",
            ref_doc_id=transport_order.id,
        ).exists():
            return

        for line in transport_order.recovery_lines.select_for_update().all():
            self.ledger_service.record_movement(
                user=user,
                company_id=company_id,
                warehouse_id=line.warehouse_id,
                material_id=line.material_id,
                movement_type=StockLedger.MovementType.IN,
                qty=line.qty_actual,
                uom_id=line.material.uom_id,
                ref_doc_type="logistics.transport_order_recovery",
                ref_doc_id=transport_order.id,
                request=request,
            )


    def _transport_order_for_line_edit(self, *, company_id, transport_order_id) -> TransportOrder:
        row = TransportOrder.objects.active().for_company(company_id).filter(id=transport_order_id).first()
        if row is None:
            raise BusinessRuleError("Transport order not found in company scope")
        if row.status in {DOC_STATUS.COMPLETED, DOC_STATUS.CANCELLED}:
            raise BusinessRuleError("Completed or cancelled transport order cannot maintain recovery lines")
        return row

    @transaction.atomic
    def add_recovery_line(self, *, user, company_id, transport_order_id, material_id, warehouse_id, qty_actual, unit_price=0, condition_code="", remark="", request=None) -> TransportRecoveryLine:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)
        transport_order = self._transport_order_for_line_edit(company_id=company_id, transport_order_id=transport_order_id)

        line = TransportRecoveryLine(
            company_id=company_id,
            transport_order=transport_order,
            material=self._material(company_id=company_id, material_id=material_id),
            warehouse=self._warehouse(company_id=company_id, warehouse_id=warehouse_id),
            qty_actual=qty_actual,
            unit_price=unit_price,
            condition_code=condition_code,
            remark=remark,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        line.full_clean()
        line.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="logistics.transport_recovery_line", resource_id=line.id, request=request)
        return line

    @transaction.atomic
    def update_recovery_line(self, *, user, company_id, recovery_line_id, qty_actual=None, unit_price=None, condition_code=None, remark=None, warehouse_id=None, request=None) -> TransportRecoveryLine:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)
        line = TransportRecoveryLine.objects.active().for_company(company_id).filter(id=recovery_line_id).select_related("transport_order").first()
        if line is None:
            raise BusinessRuleError("Transport recovery line not found in company scope")
        self._transport_order_for_line_edit(company_id=company_id, transport_order_id=line.transport_order_id)

        if qty_actual is not None:
            line.qty_actual = qty_actual
        if unit_price is not None:
            line.unit_price = unit_price
        if condition_code is not None:
            line.condition_code = condition_code
        if remark is not None:
            line.remark = remark
        if warehouse_id is not None:
            line.warehouse = self._warehouse(company_id=company_id, warehouse_id=warehouse_id)

        line.updated_by = self._user_id(user)
        line.full_clean()
        line.save()
        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="logistics.transport_recovery_line", resource_id=line.id, request=request)
        return line

    @transaction.atomic
    def remove_recovery_line(self, *, user, company_id, recovery_line_id, request=None) -> TransportRecoveryLine:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)
        line = TransportRecoveryLine.objects.active().for_company(company_id).filter(id=recovery_line_id).select_related("transport_order").first()
        if line is None:
            raise BusinessRuleError("Transport recovery line not found in company scope")
        self._transport_order_for_line_edit(company_id=company_id, transport_order_id=line.transport_order_id)

        line.soft_delete()
        self.audit_crud(user=user, company_id=company_id, operation="delete", resource_type="logistics.transport_recovery_line", resource_id=line.id, request=request)
        return line
