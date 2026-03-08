from decimal import Decimal

from django.db import transaction

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

from .models import (
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


class SalesDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.SALES

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("sales module is disabled for this company")

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

    def _warehouse(self, *, company_id, warehouse_id) -> Warehouse:
        warehouse = Warehouse.objects.active().for_company(company_id).filter(id=warehouse_id, is_active=True).first()
        if warehouse is None:
            raise BusinessRuleError("Warehouse not found in company scope")
        return warehouse


class CustomerService(SalesDomainService):
    PERM_CREATE = PERMISSION_CODES.SALES_CUSTOMER_CREATE

    @transaction.atomic
    def create_customer(self, *, user, company_id, code, name, contact_json=None, credit_limit=Decimal("0"), notes="", request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        customer = Customer(
            company_id=company_id,
            code=code,
            name=name,
            contact_json=contact_json or {},
            credit_limit=credit_limit,
            notes=notes,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        customer.full_clean()
        customer.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.customer",
            resource_id=customer.id,
            request=request,
        )
        return customer


class PricingService(SalesDomainService):
    PERM_CREATE = PERMISSION_CODES.SALES_PRICING_CREATE

    @transaction.atomic
    def create_customer_price(
        self,
        *,
        user,
        company_id,
        customer_id,
        material_id,
        price,
        currency,
        valid_from,
        valid_to=None,
        request=None,
    ) -> CustomerPriceList:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        row = CustomerPriceList(
            company_id=company_id,
            customer=self._customer(company_id=company_id, customer_id=customer_id),
            material=self._material(company_id=company_id, material_id=material_id),
            price=price,
            currency=currency,
            valid_from=valid_from,
            valid_to=valid_to,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        row.full_clean()
        row.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.customer_price_list",
            resource_id=row.id,
            request=request,
        )
        return row

    @transaction.atomic
    def create_pricing_rule(self, *, user, company_id, name, rule_json=None, enabled=True, request=None) -> PricingRule:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        rule = PricingRule(
            company_id=company_id,
            name=name,
            rule_json=rule_json or {},
            enabled=enabled,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        rule.full_clean()
        rule.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.pricing_rule",
            resource_id=rule.id,
            request=request,
        )
        return rule


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
                quote=quote,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=line["qty"],
                price=line["price"],
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

            shipment_line = ShipmentLine(
                company_id=company_id,
                shipment=shipment,
                so_line=so_line,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=line["qty"],
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
            if reservation:
                self.reservation_service.consume_reservation(
                    user=user,
                    company_id=company_id,
                    reservation_id=reservation.id,
                    request=request,
                )
                so_line = line.so_line
                so_line.reserved_qty = Decimal("0")
                so_line.updated_by = self._user_id(user)
                so_line.full_clean()
                so_line.save(update_fields=["reserved_qty", "updated_by", "updated_at"])


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
