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

class RMAService(SalesDomainService):
    PERM_CREATE = PERMISSION_CODES.SALES_RMA_CREATE

    def __init__(self):
        super().__init__()
        self.transition_service = DocumentStateTransitionService()
        self.ledger_service = StockLedgerService()

    @transaction.atomic
    def create_rma(
        self,
        *,
        user,
        company_id,
        doc_no,
        customer_id,
        reason_code,
        reason_text="",
        quality_issue_flag=False,
        so_id=None,
        lines=None,
        request=None,
    ) -> RMA:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        order = None
        if so_id:
            order = SalesOrder.objects.active().for_company(company_id).filter(id=so_id).first()
            if order is None:
                raise BusinessRuleError("Sales order not found in company scope")

        rma = RMA(
            company_id=company_id,
            doc_no=doc_no,
            customer=self._customer(company_id=company_id, customer_id=customer_id),
            so=order,
            reason_code=reason_code,
            reason_text=reason_text,
            quality_issue_flag=quality_issue_flag,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        rma.full_clean()
        rma.save()

        for line in lines or []:
            rma_line = RMALine(
                company_id=company_id,
                rma=rma,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=line["qty"],
                warehouse=self._warehouse(company_id=company_id, warehouse_id=line["warehouse_id"]),
                lot_id=line.get("lot_id"),
                serial_id=line.get("serial_id"),
                created_by=self._user_id(user),
                updated_by=self._user_id(user),
            )
            rma_line.full_clean()
            rma_line.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.rma",
            resource_id=rma.id,
            request=request,
        )
        return rma

    @transaction.atomic
    def transition_rma(self, *, user, company_id, rma_id, to_state, notes="", request=None) -> RMA:
        self._ensure_module_enabled(company_id=company_id)
        rma = RMA.objects.active().for_company(company_id).filter(id=rma_id).first()
        if rma is None:
            raise BusinessRuleError("RMA not found in company scope")

        if to_state == DOC_STATUS.COMPLETED:
            self._post_return_inventory(user=user, company_id=company_id, rma=rma, request=request)

        return self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=rma,
            document_type="sales.rma",
            to_state=to_state,
            notes=notes,
            request=request,
        )

    def _post_return_inventory(self, *, user, company_id, rma: RMA, request=None):
        if rma.status != DOC_STATUS.CONFIRMED:
            raise BusinessRuleError("RMA must be confirmed before completion")
        if StockLedger.objects.filter(company_id=company_id, ref_doc_type="sales.rma", ref_doc_id=rma.id).exists():
            raise BusinessRuleError("RMA inventory already posted")

        for line in rma.lines.select_for_update().all():
            self.ledger_service.record_movement(
                user=user,
                company_id=company_id,
                warehouse_id=line.warehouse_id,
                material_id=line.material_id,
                movement_type=StockLedger.MovementType.IN,
                qty=line.qty,
                uom_id=line.material.uom_id,
                lot_id=line.lot_id,
                serial_id=line.serial_id,
                ref_doc_type="sales.rma",
                ref_doc_id=rma.id,
                request=request,
            )
