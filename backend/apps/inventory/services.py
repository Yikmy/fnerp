from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.material.models import Material, UoM, Warehouse
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService

from .models import (
    CostLayer,
    Lot,
    Reservation,
    Serial,
    StockBalance,
    StockCount,
    StockCountLine,
    StockLedger,
    WarehouseTransfer,
    WarehouseTransferLine,
)


class InventoryDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.INVENTORY

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("inventory module is disabled for this company")

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

    def _uom(self, *, company_id, uom_id) -> UoM:
        uom = UoM.objects.active().for_company(company_id).filter(id=uom_id).first()
        if uom is None:
            raise BusinessRuleError("UoM not found in company scope")
        return uom


@dataclass
class MovementResult:
    ledger: StockLedger
    balance: StockBalance


class StockLedgerService(InventoryDomainService):
    PERM_WRITE = PERMISSION_CODES.INVENTORY_STOCK_LEDGER_WRITE

    @transaction.atomic
    def record_movement(
        self,
        *,
        user,
        company_id,
        warehouse_id,
        material_id,
        movement_type,
        qty,
        uom_id,
        lot_id=None,
        serial_id=None,
        bin_location_id=None,
        ref_doc_type="",
        ref_doc_id=None,
        cost_amount=Decimal("0"),
        request=None,
    ) -> MovementResult:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_WRITE)

        material = self._material(company_id=company_id, material_id=material_id)
        warehouse = self._warehouse(company_id=company_id, warehouse_id=warehouse_id)
        uom = self._uom(company_id=company_id, uom_id=uom_id)

        if movement_type in {StockLedger.MovementType.IN, StockLedger.MovementType.OUT, StockLedger.MovementType.TRANSFER_IN, StockLedger.MovementType.TRANSFER_OUT} and qty <= 0:
            raise BusinessRuleError("Movement quantity must be greater than zero")
        if movement_type == StockLedger.MovementType.ADJUST and qty == 0:
            raise BusinessRuleError("Adjust movement quantity cannot be zero")

        lot = None
        if lot_id:
            lot = Lot.objects.active().for_company(company_id).filter(id=lot_id).first()
            if lot is None:
                raise BusinessRuleError("Lot not found in company scope")

        serial = None
        if serial_id:
            serial = Serial.objects.active().for_company(company_id).filter(id=serial_id).first()
            if serial is None:
                raise BusinessRuleError("Serial not found in company scope")

        ledger = StockLedger(
            company_id=company_id,
            warehouse=warehouse,
            material=material,
            movement_type=movement_type,
            qty=qty,
            uom=uom,
            lot=lot,
            serial=serial,
            bin_location_id=bin_location_id,
            ref_doc_type=ref_doc_type,
            ref_doc_id=ref_doc_id,
            cost_amount=cost_amount,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        ledger.full_clean()
        ledger.save()

        signed_qty = qty
        if movement_type in {StockLedger.MovementType.OUT, StockLedger.MovementType.TRANSFER_OUT}:
            signed_qty = -qty
        elif movement_type == StockLedger.MovementType.ADJUST:
            # ADJUST uses signed quantity from caller: positive for gain, negative for shrinkage.
            signed_qty = qty

        balance, _ = StockBalance.objects.select_for_update().get_or_create(
            company_id=company_id,
            warehouse=warehouse,
            material=material,
            lot=lot,
            serial=serial,
            defaults={
                "created_by": self._user_id(user),
                "updated_by": self._user_id(user),
            },
        )
        balance.on_hand_qty += signed_qty
        balance.updated_by = self._user_id(user)
        balance.full_clean()
        balance.save()

        self._apply_fifo_layers(company_id=company_id, ledger=ledger)

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="inventory.stock_ledger",
            resource_id=ledger.id,
            request=request,
        )
        return MovementResult(ledger=ledger, balance=balance)

    def _apply_fifo_layers(self, *, company_id, ledger: StockLedger):
        incoming_types = {StockLedger.MovementType.IN, StockLedger.MovementType.TRANSFER_IN}
        outgoing_types = {StockLedger.MovementType.OUT, StockLedger.MovementType.TRANSFER_OUT}

        if ledger.movement_type == StockLedger.MovementType.ADJUST:
            if ledger.qty > 0:
                incoming_types.add(StockLedger.MovementType.ADJUST)
            else:
                outgoing_types.add(StockLedger.MovementType.ADJUST)

        if ledger.movement_type in incoming_types:
            # Positive ADJUST creates a zero-cost layer for consistency with later FIFO depletion.
            unit_cost = Decimal("0")
            if ledger.qty > 0:
                unit_cost = ledger.cost_amount / ledger.qty if ledger.qty else Decimal("0")
            layer = CostLayer(
                company_id=company_id,
                material=ledger.material,
                warehouse=ledger.warehouse,
                in_qty=abs(ledger.qty),
                remaining_qty=abs(ledger.qty),
                unit_cost=unit_cost,
                source_ledger=ledger,
                created_by=ledger.created_by,
                updated_by=ledger.updated_by,
            )
            layer.full_clean()
            layer.save()
            return

        if ledger.movement_type not in outgoing_types:
            return

        required_qty = abs(ledger.qty)
        layers = CostLayer.objects.select_for_update().active().for_company(company_id).filter(
            material=ledger.material,
            warehouse=ledger.warehouse,
            remaining_qty__gt=0,
        ).order_by("created_at", "id")
        for layer in layers:
            if required_qty <= 0:
                break
            consume_qty = min(required_qty, layer.remaining_qty)
            layer.remaining_qty -= consume_qty
            layer.full_clean()
            layer.save(update_fields=["remaining_qty", "updated_at"])
            required_qty -= consume_qty

        if required_qty > 0:
            raise BusinessRuleError("Insufficient FIFO layers for outgoing movement")


class ReservationService(InventoryDomainService):
    PERM_CREATE = PERMISSION_CODES.INVENTORY_RESERVATION_CREATE
    PERM_RELEASE = PERMISSION_CODES.INVENTORY_RESERVATION_RELEASE
    PERM_CONSUME = PERMISSION_CODES.INVENTORY_RESERVATION_CONSUME

    @transaction.atomic
    def create_reservation(
        self,
        *,
        user,
        company_id,
        warehouse_id,
        material_id,
        qty,
        ref_doc_type="",
        ref_doc_id=None,
        request=None,
    ) -> Reservation:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        material = self._material(company_id=company_id, material_id=material_id)
        warehouse = self._warehouse(company_id=company_id, warehouse_id=warehouse_id)

        balance = (
            StockBalance.objects.select_for_update()
            .active()
            .for_company(company_id)
            .filter(warehouse=warehouse, material=material, lot__isnull=True, serial__isnull=True)
            .first()
        )
        if balance is None or balance.available_qty < qty:
            raise BusinessRuleError("Insufficient available inventory for reservation")

        reservation = Reservation(
            company_id=company_id,
            warehouse=warehouse,
            material=material,
            qty=qty,
            ref_doc_type=ref_doc_type,
            ref_doc_id=ref_doc_id,
            status=Reservation.Status.ACTIVE,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        reservation.full_clean()
        reservation.save()

        balance.reserved_qty += qty
        balance.updated_by = self._user_id(user)
        balance.full_clean()
        balance.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="inventory.reservation",
            resource_id=reservation.id,
            request=request,
        )
        return reservation

    @transaction.atomic
    def release_reservation(self, *, user, company_id, reservation_id, request=None) -> Reservation:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_RELEASE)

        reservation = (
            Reservation.objects.select_for_update()
            .active()
            .for_company(company_id)
            .filter(id=reservation_id)
            .first()
        )
        if reservation is None:
            raise BusinessRuleError("Reservation not found in company scope")
        if reservation.status != Reservation.Status.ACTIVE:
            raise BusinessRuleError("Only active reservations can be released")

        balance = (
            StockBalance.objects.select_for_update()
            .active()
            .for_company(company_id)
            .filter(warehouse=reservation.warehouse, material=reservation.material, lot__isnull=True, serial__isnull=True)
            .first()
        )
        if balance is None:
            raise BusinessRuleError("Stock balance not found for reservation")

        balance.reserved_qty -= reservation.qty
        balance.updated_by = self._user_id(user)
        balance.full_clean()
        balance.save()

        reservation.status = Reservation.Status.RELEASED
        reservation.updated_by = self._user_id(user)
        reservation.full_clean()
        reservation.save(update_fields=["status", "updated_by", "updated_at"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="update",
            resource_type="inventory.reservation",
            resource_id=reservation.id,
            request=request,
            field_diffs=[{"field": "status", "old_value": Reservation.Status.ACTIVE, "new_value": Reservation.Status.RELEASED}],
        )
        return reservation

    @transaction.atomic
    def consume_reservation(self, *, user, company_id, reservation_id, request=None) -> Reservation:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CONSUME)

        reservation = (
            Reservation.objects.select_for_update()
            .active()
            .for_company(company_id)
            .filter(id=reservation_id)
            .first()
        )
        if reservation is None:
            raise BusinessRuleError("Reservation not found in company scope")
        if reservation.status != Reservation.Status.ACTIVE:
            raise BusinessRuleError("Only active reservations can be consumed")

        balance = (
            StockBalance.objects.select_for_update()
            .active()
            .for_company(company_id)
            .filter(warehouse=reservation.warehouse, material=reservation.material, lot__isnull=True, serial__isnull=True)
            .first()
        )
        if balance is None:
            raise BusinessRuleError("Stock balance not found for reservation")

        balance.reserved_qty -= reservation.qty
        balance.updated_by = self._user_id(user)
        balance.full_clean()
        balance.save()

        reservation.status = Reservation.Status.CONSUMED
        reservation.updated_by = self._user_id(user)
        reservation.full_clean()
        reservation.save(update_fields=["status", "updated_by", "updated_at"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="update",
            resource_type="inventory.reservation",
            resource_id=reservation.id,
            request=request,
            field_diffs=[{"field": "status", "old_value": Reservation.Status.ACTIVE, "new_value": Reservation.Status.CONSUMED}],
        )
        return reservation


class WarehouseTransferService(InventoryDomainService):
    PERM_CREATE = PERMISSION_CODES.INVENTORY_TRANSFER_CREATE
    PERM_SHIP = PERMISSION_CODES.INVENTORY_TRANSFER_SHIP
    PERM_RECEIVE = PERMISSION_CODES.INVENTORY_TRANSFER_RECEIVE

    def __init__(self):
        super().__init__()
        self.ledger_service = StockLedgerService()

    @transaction.atomic
    def create_transfer(
        self,
        *,
        user,
        company_id,
        from_warehouse_id,
        to_warehouse_id,
        lines,
        request=None,
    ) -> WarehouseTransfer:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        transfer = WarehouseTransfer(
            company_id=company_id,
            from_warehouse=self._warehouse(company_id=company_id, warehouse_id=from_warehouse_id),
            to_warehouse=self._warehouse(company_id=company_id, warehouse_id=to_warehouse_id),
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        transfer.full_clean()
        transfer.save()

        for line in lines:
            transfer_line = WarehouseTransferLine(
                company_id=company_id,
                transfer=transfer,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=line["qty"],
                lot_id=line.get("lot_id"),
                serial_id=line.get("serial_id"),
                created_by=self._user_id(user),
                updated_by=self._user_id(user),
            )
            transfer_line.full_clean()
            transfer_line.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="inventory.transfer",
            resource_id=transfer.id,
            request=request,
        )
        return transfer

    @transaction.atomic
    def ship_transfer(self, *, user, company_id, transfer_id, request=None) -> WarehouseTransfer:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_SHIP)

        transfer = (
            WarehouseTransfer.objects.select_for_update()
            .active()
            .for_company(company_id)
            .filter(id=transfer_id)
            .first()
        )
        if transfer is None:
            raise BusinessRuleError("Transfer not found in company scope")
        if transfer.status != WarehouseTransfer.Status.DRAFT:
            raise BusinessRuleError("Only draft transfer can be shipped")

        for line in transfer.lines.all():
            self.ledger_service.record_movement(
                user=user,
                company_id=company_id,
                warehouse_id=transfer.from_warehouse_id,
                material_id=line.material_id,
                movement_type=StockLedger.MovementType.TRANSFER_OUT,
                qty=line.qty,
                uom_id=line.material.uom_id,
                lot_id=line.lot_id,
                serial_id=line.serial_id,
                ref_doc_type="warehouse_transfer",
                ref_doc_id=transfer.id,
                request=request,
            )

        transfer.status = WarehouseTransfer.Status.SHIPPED
        transfer.ship_date = timezone.localdate()
        transfer.updated_by = self._user_id(user)
        transfer.full_clean()
        transfer.save(update_fields=["status", "ship_date", "updated_by", "updated_at"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="update",
            resource_type="inventory.transfer",
            resource_id=transfer.id,
            request=request,
            field_diffs=[{"field": "status", "old_value": WarehouseTransfer.Status.DRAFT, "new_value": WarehouseTransfer.Status.SHIPPED}],
        )
        return transfer

    @transaction.atomic
    def receive_transfer(self, *, user, company_id, transfer_id, request=None) -> WarehouseTransfer:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_RECEIVE)

        transfer = (
            WarehouseTransfer.objects.select_for_update()
            .active()
            .for_company(company_id)
            .filter(id=transfer_id)
            .first()
        )
        if transfer is None:
            raise BusinessRuleError("Transfer not found in company scope")
        if transfer.status != WarehouseTransfer.Status.SHIPPED:
            raise BusinessRuleError("Only shipped transfer can be received")

        for line in transfer.lines.all():
            self.ledger_service.record_movement(
                user=user,
                company_id=company_id,
                warehouse_id=transfer.to_warehouse_id,
                material_id=line.material_id,
                movement_type=StockLedger.MovementType.TRANSFER_IN,
                qty=line.qty,
                uom_id=line.material.uom_id,
                lot_id=line.lot_id,
                serial_id=line.serial_id,
                ref_doc_type="warehouse_transfer",
                ref_doc_id=transfer.id,
                request=request,
            )

        transfer.status = WarehouseTransfer.Status.RECEIVED
        transfer.receive_date = timezone.localdate()
        transfer.updated_by = self._user_id(user)
        transfer.full_clean()
        transfer.save(update_fields=["status", "receive_date", "updated_by", "updated_at"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="update",
            resource_type="inventory.transfer",
            resource_id=transfer.id,
            request=request,
            field_diffs=[{"field": "status", "old_value": WarehouseTransfer.Status.SHIPPED, "new_value": WarehouseTransfer.Status.RECEIVED}],
        )
        return transfer


class StockCountService(InventoryDomainService):
    PERM_CREATE = PERMISSION_CODES.INVENTORY_STOCK_COUNT_CREATE
    PERM_POST = PERMISSION_CODES.INVENTORY_STOCK_COUNT_POST

    def __init__(self):
        super().__init__()
        self.ledger_service = StockLedgerService()

    @transaction.atomic
    def create_count(self, *, user, company_id, warehouse_id, count_date, request=None) -> StockCount:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        count = StockCount(
            company_id=company_id,
            warehouse=self._warehouse(company_id=company_id, warehouse_id=warehouse_id),
            count_date=count_date,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        count.full_clean()
        count.save()
        return count

    @transaction.atomic
    def add_count_line(self, *, user, company_id, count_id, material_id, counted_qty, reason="") -> StockCountLine:
        count = StockCount.objects.active().for_company(company_id).filter(id=count_id).first()
        if count is None:
            raise BusinessRuleError("Stock count not found in company scope")

        material = self._material(company_id=company_id, material_id=material_id)
        system_qty = (
            StockBalance.objects.active()
            .for_company(company_id)
            .filter(warehouse=count.warehouse, material=material)
            .aggregate(total=Sum("on_hand_qty"))
            .get("total")
            or Decimal("0")
        )

        line = StockCountLine(
            company_id=company_id,
            count=count,
            material=material,
            system_qty=system_qty,
            counted_qty=counted_qty,
            reason=reason,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        line.full_clean()
        line.save()
        return line

    @transaction.atomic
    def post_count(self, *, user, company_id, count_id, request=None) -> StockCount:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_POST)

        count = (
            StockCount.objects.select_for_update()
            .active()
            .for_company(company_id)
            .filter(id=count_id)
            .first()
        )
        if count is None:
            raise BusinessRuleError("Stock count not found in company scope")

        for line in count.lines.all():
            if line.diff_qty == 0:
                continue
            movement_qty = line.diff_qty
            self.ledger_service.record_movement(
                # ADJUST movement uses signed qty to preserve stock-count direction:
                # positive diff adds stock; negative diff reduces stock.
                user=user,
                company_id=company_id,
                warehouse_id=count.warehouse_id,
                material_id=line.material_id,
                movement_type=StockLedger.MovementType.ADJUST,
                qty=movement_qty,
                uom_id=line.material.uom_id,
                ref_doc_type="stock_count",
                ref_doc_id=count.id,
                request=request,
            )

        count.status = StockCount.Status.POSTED
        count.updated_by = self._user_id(user)
        count.full_clean()
        count.save(update_fields=["status", "updated_by", "updated_at"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="update",
            resource_type="inventory.stock_count",
            resource_id=count.id,
            request=request,
            field_diffs=[{"field": "status", "old_value": StockCount.Status.DRAFT, "new_value": StockCount.Status.POSTED}],
        )
        return count
