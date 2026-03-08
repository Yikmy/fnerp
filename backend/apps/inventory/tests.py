from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.inventory.models import Reservation, StockBalance, StockLedger
from apps.inventory.services import ReservationService, StockCountService, StockLedgerService
from apps.material.models import Material, MaterialCategory, UoM, Warehouse
from company.models import Company, CompanyMembership, CompanyModule
from rbac.models import Permission, Role, RolePermission
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import PermissionDeniedError


class Step3HealthFixTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="inv_user", password="pwd")
        self.no_perm_user = user_model.objects.create_user(username="no_perm", password="pwd")

        self.company = Company.objects.create(name="C1")
        CompanyModule.objects.create(company=self.company, module_code="inventory", is_enabled=True)

        self.role = Role.objects.create(code="inv-role", name="Inventory Role")
        needed_permissions = [
            PERMISSION_CODES.INVENTORY_STOCK_LEDGER_WRITE,
            PERMISSION_CODES.INVENTORY_RESERVATION_CREATE,
            PERMISSION_CODES.INVENTORY_RESERVATION_RELEASE,
            PERMISSION_CODES.INVENTORY_RESERVATION_CONSUME,
            PERMISSION_CODES.INVENTORY_STOCK_COUNT_CREATE,
            PERMISSION_CODES.INVENTORY_STOCK_COUNT_POST,
        ]
        for code in needed_permissions:
            perm = Permission.objects.create(code=code, name=code)
            RolePermission.objects.create(role=self.role, permission=perm)

        CompanyMembership.objects.create(user=self.user, company=self.company, role=self.role, is_active=True)
        CompanyMembership.objects.create(user=self.no_perm_user, company=self.company, is_active=True)

        self.uom = UoM.objects.create(company_id=self.company.id, name="EA", symbol="ea", ratio_to_base=Decimal("1"))
        self.category = MaterialCategory.objects.create(company_id=self.company.id, name="Raw")
        self.material = Material.objects.create(
            company_id=self.company.id,
            code="M-1",
            name="Material 1",
            category=self.category,
            uom=self.uom,
        )
        self.warehouse = Warehouse.objects.create(company_id=self.company.id, code="W1", name="Main")

    def test_stock_count_negative_diff_reduces_inventory(self):
        ledger_service = StockLedgerService()
        ledger_service.record_movement(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            material_id=self.material.id,
            movement_type=StockLedger.MovementType.IN,
            qty=Decimal("10"),
            uom_id=self.uom.id,
        )

        count_service = StockCountService()
        count = count_service.create_count(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            count_date="2026-03-08",
        )
        count_service.add_count_line(
            user=self.user,
            company_id=self.company.id,
            count_id=count.id,
            material_id=self.material.id,
            counted_qty=Decimal("6"),
        )

        count_service.post_count(user=self.user, company_id=self.company.id, count_id=count.id)

        balance = StockBalance.objects.get(company_id=self.company.id, warehouse=self.warehouse, material=self.material)
        self.assertEqual(balance.on_hand_qty, Decimal("6"))
        adjust = StockLedger.objects.filter(ref_doc_type="stock_count", movement_type=StockLedger.MovementType.ADJUST).latest("created_at")
        self.assertEqual(adjust.qty, Decimal("-4"))

    def test_reservation_consume_releases_reserved_qty(self):
        StockLedgerService().record_movement(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            material_id=self.material.id,
            movement_type=StockLedger.MovementType.IN,
            qty=Decimal("8"),
            uom_id=self.uom.id,
        )
        service = ReservationService()
        reservation = service.create_reservation(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            material_id=self.material.id,
            qty=Decimal("5"),
        )

        service.consume_reservation(user=self.user, company_id=self.company.id, reservation_id=reservation.id)

        reservation.refresh_from_db()
        balance = StockBalance.objects.get(company_id=self.company.id, warehouse=self.warehouse, material=self.material)
        self.assertEqual(reservation.status, Reservation.Status.CONSUMED)
        self.assertEqual(balance.reserved_qty, Decimal("0"))

    def test_release_requires_permission_and_ledger_is_immutable(self):
        StockLedgerService().record_movement(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            material_id=self.material.id,
            movement_type=StockLedger.MovementType.IN,
            qty=Decimal("2"),
            uom_id=self.uom.id,
        )
        reservation = ReservationService().create_reservation(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            material_id=self.material.id,
            qty=Decimal("1"),
        )

        with self.assertRaises(PermissionDeniedError):
            ReservationService().release_reservation(
                user=self.no_perm_user,
                company_id=self.company.id,
                reservation_id=reservation.id,
            )

        ledger = StockLedger.objects.first()
        ledger.cost_amount = Decimal("9")
        with self.assertRaises(ValidationError):
            ledger.save()
        with self.assertRaises(ValidationError):
            ledger.delete()
