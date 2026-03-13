from decimal import Decimal
from django.db import models, transaction
from apps.inventory.models import Reservation, StockLedger
from apps.inventory.services import ReservationService, StockLedgerService
from apps.material.models import Material, Warehouse
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from .workflow import SalesDomainService
from ..models import (
    Customer,
    CustomerPriceList,
    PricingRule,
    RMA,
    RMALine,
    SalesOrder,
    SalesOrderLine,
    SalesQuote,
    SalesQuoteLine,
    Shipment,
    ShipmentLine,
)

class ShipmentService(SalesDomainService):
    PERM_CREATE = PERMISSION_CODES.SALES_SHIPMENT_CREATE

    def __init__(self):
        super().__init__()
        self.transition_service = DocumentStateTransitionService()
        self.ledger_service = StockLedgerService()
        self.reservation_service = ReservationService()

    @transaction.atomic
    def create_shipment(
        self,
        *,
        user,
        company_id,
        doc_no,
        so_id,
        customer_id,
        warehouse_id,
        ship_date,
        carrier="",
        tracking_no="",
        lines=None,
        request=None,
    ) -> Shipment:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        order = SalesOrder.objects.active().for_company(company_id).filter(id=so_id).first()
        if order is None:
            raise BusinessRuleError("Sales order not found in company scope")

        shipment = Shipment(
            company_id=company_id,
            doc_no=doc_no,
            so=order,
            customer=self._customer(company_id=company_id, customer_id=customer_id),
            warehouse=self._warehouse(company_id=company_id, warehouse_id=warehouse_id),
            ship_date=ship_date,
            carrier=carrier,
            tracking_no=tracking_no,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        shipment.full_clean()
        shipment.save()

        for line in lines or []:
            so_line = SalesOrderLine.objects.active().for_company(company_id).filter(so=order, id=line["so_line_id"]).first()
            if so_line is None:
                raise BusinessRuleError("Sales order line not found in sales order")

            requested_qty = line["qty"]
            already_shipped_qty = (
                ShipmentLine.objects.active()
                .for_company(company_id)
                .filter(so_line=so_line, shipment__status__in=[DOC_STATUS.CONFIRMED, DOC_STATUS.COMPLETED])
                .exclude(shipment=shipment)
                .aggregate(total=models.Sum("qty"))
                .get("total")
                or Decimal("0")
            )
            remaining_qty = so_line.qty - already_shipped_qty
            if requested_qty > remaining_qty:
                raise BusinessRuleError("Shipment quantity cannot exceed remaining sales order quantity")
            if requested_qty > so_line.reserved_qty:
                raise BusinessRuleError("Shipment quantity cannot exceed reserved quantity")

            shipment_line = ShipmentLine(
                company_id=company_id,
                shipment=shipment,
                so_line=so_line,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=requested_qty,
                lot_id=line.get("lot_id"),
                serial_id=line.get("serial_id"),
                created_by=self._user_id(user),
                updated_by=self._user_id(user),
            )
            shipment_line.full_clean()
            shipment_line.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.shipment",
            resource_id=shipment.id,
            request=request,
        )
        return shipment

    @transaction.atomic
    def transition_shipment(self, *, user, company_id, shipment_id, to_state, notes="", request=None) -> Shipment:
        self._ensure_module_enabled(company_id=company_id)
        shipment = Shipment.objects.active().for_company(company_id).filter(id=shipment_id).first()
        if shipment is None:
            raise BusinessRuleError("Shipment not found in company scope")

        if to_state == DOC_STATUS.COMPLETED:
            self._post_shipment_inventory(user=user, company_id=company_id, shipment=shipment, request=request)

        return self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=shipment,
            document_type="sales.shipment",
            to_state=to_state,
            notes=notes,
            request=request,
        )

    def _post_shipment_inventory(self, *, user, company_id, shipment: Shipment, request=None):
        if shipment.status != DOC_STATUS.CONFIRMED:
            raise BusinessRuleError("Shipment must be confirmed before completion")
        if StockLedger.objects.filter(company_id=company_id, ref_doc_type="sales.shipment", ref_doc_id=shipment.id).exists():
            raise BusinessRuleError("Shipment inventory already posted")

        for line in shipment.lines.select_for_update().all():
            self.ledger_service.record_movement(
                user=user,
                company_id=company_id,
                warehouse_id=shipment.warehouse_id,
                material_id=line.material_id,
                movement_type=StockLedger.MovementType.OUT,
                qty=line.qty,
                uom_id=line.material.uom_id,
                lot_id=line.lot_id,
                serial_id=line.serial_id,
                ref_doc_type="sales.shipment",
                ref_doc_id=shipment.id,
                request=request,
            )
            reservation = (
                Reservation.objects.active()
                .for_company(company_id)
                .filter(ref_doc_type="sales.order.line", ref_doc_id=line.so_line_id, status=Reservation.Status.ACTIVE)
                .first()
            )
            if reservation is None:
                raise BusinessRuleError("Active reservation is required before shipment completion")
            if line.qty > reservation.qty:
                raise BusinessRuleError("Shipment quantity cannot exceed reserved quantity")

            so_line = line.so_line
            remaining_reserved = reservation.qty - line.qty
            if remaining_reserved == 0:
                self.reservation_service.consume_reservation(
                    user=user,
                    company_id=company_id,
                    reservation_id=reservation.id,
                    request=request,
                )
            else:
                self.reservation_service.release_reservation(
                    user=user,
                    company_id=company_id,
                    reservation_id=reservation.id,
                    request=request,
                )
                self.reservation_service.create_reservation(
                    user=user,
                    company_id=company_id,
                    warehouse_id=so_line.warehouse_id,
                    material_id=so_line.material_id,
                    qty=remaining_reserved,
                    ref_doc_type="sales.order.line",
                    ref_doc_id=so_line.id,
                    request=request,
                )

            so_line.reserved_qty = remaining_reserved
            so_line.updated_by = self._user_id(user)
            so_line.full_clean()
            so_line.save(update_fields=["reserved_qty", "updated_by", "updated_at"])
