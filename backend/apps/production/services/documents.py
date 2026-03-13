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

class ManufacturingOrderService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_MO_CREATE
    PERM_ISSUE = PERMISSION_CODES.PRODUCTION_MO_ISSUE
    PERM_RECEIPT = PERMISSION_CODES.PRODUCTION_MO_RECEIPT
    PERM_TRANSITION = PERMISSION_CODES.PRODUCTION_MO_TRANSITION

    DOC_TYPE = "production.manufacturing_order"

    def __init__(self):
        super().__init__()
        self.reservation_service = ReservationService()
        self.ledger_service = StockLedgerService()
        self.transition_service = DocumentStateTransitionService()
        self.transition_service.DEFAULT_TRANSITIONS = {
            DOC_STATUS.DRAFT: {
                DOC_STATUS.SUBMITTED: "production.mo.submit",
                DOC_STATUS.CANCELLED: "production.mo.cancel",
            },
            DOC_STATUS.SUBMITTED: {
                DOC_STATUS.CONFIRMED: "production.mo.confirm",
                DOC_STATUS.CANCELLED: "production.mo.cancel",
            },
            DOC_STATUS.CONFIRMED: {
                DOC_STATUS.COMPLETED: "production.mo.complete",
                DOC_STATUS.CANCELLED: "production.mo.cancel",
            },
            DOC_STATUS.COMPLETED: {
                DOC_STATUS.CANCELLED: "production.mo.cancel",
            },
            DOC_STATUS.CANCELLED: {},
        }

    @transaction.atomic
    def create_order(self, *, user, company_id, doc_no, product_material_id, planned_qty, warehouse_id, production_mode=ManufacturingOrder.ProductionMode.MAKE_TO_STOCK, sales_order_id=None, start_date=None, due_date=None, request=None) -> ManufacturingOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        sales_order = None
        if sales_order_id:
            sales_order = self._sales_order(company_id=company_id, sales_order_id=sales_order_id)

        order = ManufacturingOrder(
            company_id=company_id,
            doc_no=doc_no,
            product_material=self._material(company_id=company_id, material_id=product_material_id),
            planned_qty=planned_qty,
            warehouse=self._warehouse(company_id=company_id, warehouse_id=warehouse_id),
            production_mode=production_mode,
            sales_order=sales_order,
            start_date=start_date,
            due_date=due_date,
            status=self._status_value(DOC_STATUS.DRAFT),
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        self._validate_mto_alignment(mo=order)
        order.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type=self.DOC_TYPE, resource_id=order.id, request=request)
        return order

    @transaction.atomic
    def transition_order(self, *, user, company_id, order_id, to_state, notes="", request=None) -> ManufacturingOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_TRANSITION)

        order = ManufacturingOrder.objects.active().for_company(company_id).filter(id=order_id).first()
        if order is None:
            raise BusinessRuleError("Manufacturing order not found in company scope")
        self._validate_mto_alignment(mo=order)

        return self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=order,
            document_type=self.DOC_TYPE,
            to_state=self._status_value(to_state),
            notes=notes,
            request=request,
        )

    @staticmethod
    def _ensure_issue_allowed_state(*, mo: ManufacturingOrder):
        if mo.status in {DOC_STATUS.DRAFT.value, DOC_STATUS.CANCELLED.value, DOC_STATUS.COMPLETED.value}:
            raise BusinessRuleError("Manufacturing order status does not allow material issue")

    @staticmethod
    def _ensure_receipt_allowed_state(*, mo: ManufacturingOrder):
        if mo.status in {DOC_STATUS.DRAFT.value, DOC_STATUS.CANCELLED.value, DOC_STATUS.COMPLETED.value}:
            raise BusinessRuleError("Manufacturing order status does not allow finished goods receipt")

    @transaction.atomic
    def issue_material(self, *, user, company_id, mo_id, component_material_id, required_qty, issued_qty, reservation_id=None, request=None) -> MOIssueLine:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_ISSUE)

        mo = self._mo(company_id=company_id, mo_id=mo_id)
        self._validate_mto_alignment(mo=mo)
        self._ensure_issue_allowed_state(mo=mo)
        material = self._material(company_id=company_id, material_id=component_material_id)

        reservation = None
        if reservation_id:
            reservation = Reservation.objects.active().for_company(company_id).filter(id=reservation_id).first()
            if reservation is None:
                raise BusinessRuleError("Reservation not found in company scope")
            if reservation.material_id != material.id or reservation.warehouse_id != mo.warehouse_id:
                raise BusinessRuleError("Reservation does not match MO warehouse/material")
            if reservation.status != Reservation.Status.ACTIVE:
                raise BusinessRuleError("Reservation must be active before consume")

        if mo.production_mode == ManufacturingOrder.ProductionMode.MAKE_TO_ORDER:
            if reservation is None:
                raise BusinessRuleError("MTO issue requires active reservation")
            if issued_qty != reservation.qty:
                raise BusinessRuleError("MTO issue requires issued_qty equal to reservation.qty")
        else:
            # MTS: reservation is optional; if present, must align with consume semantics.
            if reservation is not None and issued_qty != reservation.qty:
                raise BusinessRuleError("MTS issue with reservation requires issued_qty equal to reservation.qty")

        issue = MOIssueLine(
            company_id=company_id,
            mo=mo,
            component_material=material,
            required_qty=required_qty,
            issued_qty=issued_qty,
            reservation=reservation,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        issue.save()

        if reservation:
            self.reservation_service.consume_reservation(user=user, company_id=company_id, reservation_id=reservation.id, request=request)

        self.ledger_service.record_movement(
            user=user,
            company_id=company_id,
            warehouse_id=mo.warehouse_id,
            material_id=material.id,
            movement_type=StockLedger.MovementType.OUT,
            qty=issued_qty,
            uom_id=material.uom_id,
            ref_doc_type="production.mo_issue",
            ref_doc_id=issue.id,
            request=request,
        )

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.mo_issue_line", resource_id=issue.id, request=request)
        return issue

    @transaction.atomic
    def receipt_finished_goods(self, *, user, company_id, mo_id, received_qty, lot_id=None, request=None) -> MOReceiptLine:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_RECEIPT)

        mo = self._mo(company_id=company_id, mo_id=mo_id)
        self._validate_mto_alignment(mo=mo)
        self._ensure_receipt_allowed_state(mo=mo)

        receipt = MOReceiptLine(
            company_id=company_id,
            mo=mo,
            product_material=mo.product_material,
            received_qty=received_qty,
            lot_id=lot_id,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        receipt.save()

        self.ledger_service.record_movement(
            user=user,
            company_id=company_id,
            warehouse_id=mo.warehouse_id,
            material_id=mo.product_material_id,
            movement_type=StockLedger.MovementType.IN,
            qty=received_qty,
            uom_id=mo.product_material.uom_id,
            lot_id=lot_id,
            ref_doc_type="production.mo_receipt",
            ref_doc_id=receipt.id,
            request=request,
        )

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.mo_receipt_line", resource_id=receipt.id, request=request)
        return receipt
