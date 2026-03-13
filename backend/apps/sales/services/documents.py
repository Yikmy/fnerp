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

class SalesQuoteService(SalesDomainService):
    PERM_CREATE = PERMISSION_CODES.SALES_QUOTE_CREATE

    def __init__(self):
        super().__init__()
        self.transition_service = DocumentStateTransitionService()

    @transaction.atomic
    def create_quote(self, *, user, company_id, doc_no, customer_id, valid_until=None, lines=None, request=None) -> SalesQuote:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        quote = SalesQuote(
            company_id=company_id,
            doc_no=doc_no,
            customer=self._customer(company_id=company_id, customer_id=customer_id),
            valid_until=valid_until,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        quote.full_clean()
        quote.save()

        total_amount = Decimal("0")
        for line in lines or []:
            quote_line = SalesQuoteLine(
                company_id=company_id,
                quote=quote,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=line["qty"],
                price=line["price"],
                created_by=self._user_id(user),
                updated_by=self._user_id(user),
            )
            quote_line.full_clean()
            quote_line.save()
            total_amount += quote_line.qty * quote_line.price

        quote.total_amount = total_amount
        quote.save(update_fields=["total_amount", "updated_at"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.quote",
            resource_id=quote.id,
            request=request,
        )
        return quote

    @transaction.atomic
    def transition_quote(self, *, user, company_id, quote_id, to_state, notes="", request=None) -> SalesQuote:
        self._ensure_module_enabled(company_id=company_id)
        quote = SalesQuote.objects.active().for_company(company_id).filter(id=quote_id).first()
        if quote is None:
            raise BusinessRuleError("Sales quote not found in company scope")

        return self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=quote,
            document_type="sales.quote",
            to_state=to_state,
            notes=notes,
            request=request,
        )

class SalesOrderService(SalesDomainService):
    PERM_CREATE = PERMISSION_CODES.SALES_ORDER_CREATE

    def __init__(self):
        super().__init__()
        self.transition_service = DocumentStateTransitionService()
        self.reservation_service = ReservationService()

    @transaction.atomic
    def create_order(
        self,
        *,
        user,
        company_id,
        doc_no,
        customer_id,
        delivery_date=None,
        special_terms="",
        lines=None,
        request=None,
    ) -> SalesOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        order = SalesOrder(
            company_id=company_id,
            doc_no=doc_no,
            customer=self._customer(company_id=company_id, customer_id=customer_id),
            delivery_date=delivery_date,
            special_terms=special_terms,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        order.full_clean()
        order.save()

        total_amount = Decimal("0")
        for line in lines or []:
            so_line = SalesOrderLine(
                company_id=company_id,
                so=order,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=line["qty"],
                price=line["price"],
                warehouse=self._warehouse(company_id=company_id, warehouse_id=line["warehouse_id"]),
                created_by=self._user_id(user),
                updated_by=self._user_id(user),
            )
            so_line.full_clean()
            so_line.save()
            total_amount += so_line.qty * so_line.price

        order.total_amount = total_amount
        order.save(update_fields=["total_amount", "updated_at"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.order",
            resource_id=order.id,
            request=request,
        )
        return order

    @transaction.atomic
    def transition_order(self, *, user, company_id, order_id, to_state, notes="", request=None) -> SalesOrder:
        self._ensure_module_enabled(company_id=company_id)
        order = SalesOrder.objects.active().for_company(company_id).filter(id=order_id).first()
        if order is None:
            raise BusinessRuleError("Sales order not found in company scope")

        if to_state == DOC_STATUS.CONFIRMED:
            self._create_reservations(user=user, company_id=company_id, order=order, request=request)

        return self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=order,
            document_type="sales.order",
            to_state=to_state,
            notes=notes,
            request=request,
        )

    def _create_reservations(self, *, user, company_id, order: SalesOrder, request=None):
        if order.status != DOC_STATUS.SUBMITTED:
            raise BusinessRuleError("Sales order must be submitted before confirmation")

        for line in order.lines.select_for_update().all():
            existing = Reservation.objects.active().for_company(company_id).filter(
                ref_doc_type="sales.order.line",
                ref_doc_id=line.id,
            )
            if existing.exists():
                continue
            reservation = self.reservation_service.create_reservation(
                user=user,
                company_id=company_id,
                warehouse_id=line.warehouse_id,
                material_id=line.material_id,
                qty=line.qty,
                ref_doc_type="sales.order.line",
                ref_doc_id=line.id,
                request=request,
            )
            line.reserved_qty = reservation.qty
            line.updated_by = self._user_id(user)
            line.full_clean()
            line.save(update_fields=["reserved_qty", "updated_by", "updated_at"])
