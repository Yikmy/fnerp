from decimal import Decimal

from django.db import transaction

from apps.inventory.models import Reservation, StockLedger
from apps.inventory.services import ReservationService, StockLedgerService
from apps.material.models import Material, Warehouse
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService

from .models import BOM, BOMLine, MOIssueLine, MOReceiptLine, ManufacturingOrder


class ProductionDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.PRODUCTION

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("production module is disabled for this company")

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

    def _mo(self, *, company_id, mo_id) -> ManufacturingOrder:
        mo = ManufacturingOrder.objects.active().for_company(company_id).filter(id=mo_id).first()
        if mo is None:
            raise BusinessRuleError("Manufacturing order not found in company scope")
        return mo


class BOMService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_BOM_CREATE

    @transaction.atomic
    def create_bom(self, *, user, company_id, product_material_id, version=1, status=BOM.Status.DRAFT, notes="", lines=None, request=None) -> BOM:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        bom = BOM(
            company_id=company_id,
            product_material=self._material(company_id=company_id, material_id=product_material_id),
            version=version,
            status=status,
            notes=notes,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        bom.full_clean()
        bom.save()

        for line in lines or []:
            bom_line = BOMLine(
                company_id=company_id,
                bom=bom,
                component_material=self._material(company_id=company_id, material_id=line["component_material_id"]),
                qty_per_unit=line["qty_per_unit"],
                scrap_rate=line.get("scrap_rate", Decimal("0")),
                component_bom_id=line.get("component_bom_id"),
                created_by=self._user_id(user),
                updated_by=self._user_id(user),
            )
            bom_line.full_clean()
            bom_line.save()

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.bom", resource_id=bom.id, request=request)
        return bom


class ManufacturingOrderService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_MO_CREATE
    PERM_ISSUE = PERMISSION_CODES.PRODUCTION_MO_ISSUE
    PERM_RECEIPT = PERMISSION_CODES.PRODUCTION_MO_RECEIPT

    def __init__(self):
        super().__init__()
        self.reservation_service = ReservationService()
        self.ledger_service = StockLedgerService()

    @transaction.atomic
    def create_order(self, *, user, company_id, doc_no, product_material_id, planned_qty, warehouse_id, start_date=None, due_date=None, request=None) -> ManufacturingOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        order = ManufacturingOrder(
            company_id=company_id,
            doc_no=doc_no,
            product_material=self._material(company_id=company_id, material_id=product_material_id),
            planned_qty=planned_qty,
            warehouse=self._warehouse(company_id=company_id, warehouse_id=warehouse_id),
            start_date=start_date,
            due_date=due_date,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        order.full_clean()
        order.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.manufacturing_order", resource_id=order.id, request=request)
        return order

    @transaction.atomic
    def issue_material(self, *, user, company_id, mo_id, component_material_id, required_qty, issued_qty, reservation_id=None, request=None) -> MOIssueLine:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_ISSUE)

        mo = self._mo(company_id=company_id, mo_id=mo_id)
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
        issue.full_clean()
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

        receipt = MOReceiptLine(
            company_id=company_id,
            mo=mo,
            product_material=mo.product_material,
            received_qty=received_qty,
            lot_id=lot_id,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        receipt.full_clean()
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
