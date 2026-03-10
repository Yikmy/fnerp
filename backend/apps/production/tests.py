from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.inventory.models import Reservation, StockBalance, StockLedger
from apps.inventory.services import StockLedgerService
from apps.material.models import Material, MaterialCategory, UoM, Warehouse
from apps.production.models import BOMLine, ProductionQC
from apps.production.services import BOMService, ManufacturingOrderService
from company.models import Company, CompanyMembership, CompanyModule
from rbac.models import Permission, Role, RolePermission
from shared.constants.permissions import PERMISSION_CODES


class ProductionEngineTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="prod_user", password="pwd")

        self.company = Company.objects.create(name="Production Co")
        for module in ["production", "inventory"]:
            CompanyModule.objects.create(company=self.company, module_code=module, is_enabled=True)

        self.role = Role.objects.create(code="prod-role", name="Production Role")
        for code in [
            PERMISSION_CODES.PRODUCTION_BOM_CREATE,
            PERMISSION_CODES.PRODUCTION_MO_CREATE,
            PERMISSION_CODES.PRODUCTION_MO_ISSUE,
            PERMISSION_CODES.PRODUCTION_MO_RECEIPT,
            PERMISSION_CODES.INVENTORY_STOCK_LEDGER_WRITE,
            PERMISSION_CODES.INVENTORY_RESERVATION_CREATE,
            PERMISSION_CODES.INVENTORY_RESERVATION_CONSUME,
        ]:
            perm = Permission.objects.create(code=code, name=code)
            RolePermission.objects.create(role=self.role, permission=perm)

        CompanyMembership.objects.create(user=self.user, company=self.company, role=self.role, is_active=True)

        self.uom = UoM.objects.create(company_id=self.company.id, name="EA", symbol="ea", ratio_to_base=Decimal("1"))
        self.category = MaterialCategory.objects.create(company_id=self.company.id, name="FG")
        self.rm = Material.objects.create(company_id=self.company.id, code="RM-1", name="Raw", category=self.category, uom=self.uom)
        self.fg = Material.objects.create(company_id=self.company.id, code="FG-1", name="Finished", category=self.category, uom=self.uom)
        self.warehouse = Warehouse.objects.create(company_id=self.company.id, code="WH-1", name="Main")

    def test_create_bom_and_subassembly_reference(self):
        sub_bom = BOMService().create_bom(
            user=self.user,
            company_id=self.company.id,
            product_material_id=self.rm.id,
            lines=[{"component_material_id": self.rm.id, "qty_per_unit": Decimal("1")}],
        )
        bom = BOMService().create_bom(
            user=self.user,
            company_id=self.company.id,
            product_material_id=self.fg.id,
            lines=[
                {
                    "component_material_id": self.rm.id,
                    "qty_per_unit": Decimal("2"),
                    "scrap_rate": Decimal("0.05"),
                    "component_bom_id": sub_bom.id,
                }
            ],
        )
        line = BOMLine.objects.get(bom=bom)
        self.assertEqual(line.component_bom_id, sub_bom.id)

    def test_issue_and_receipt_use_inventory_ledger(self):
        StockLedgerService().record_movement(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            material_id=self.rm.id,
            movement_type=StockLedger.MovementType.IN,
            qty=Decimal("10"),
            uom_id=self.uom.id,
        )
        reservation = Reservation.objects.create(
            company_id=self.company.id,
            warehouse=self.warehouse,
            material=self.rm,
            qty=Decimal("3"),
            status=Reservation.Status.ACTIVE,
        )
        bal = StockBalance.objects.get(company_id=self.company.id, warehouse=self.warehouse, material=self.rm, lot__isnull=True, serial__isnull=True)
        bal.reserved_qty = Decimal("3")
        bal.save()

        mo_service = ManufacturingOrderService()
        mo = mo_service.create_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="MO-1",
            product_material_id=self.fg.id,
            planned_qty=Decimal("3"),
            warehouse_id=self.warehouse.id,
        )
        mo_service.issue_material(
            user=self.user,
            company_id=self.company.id,
            mo_id=mo.id,
            component_material_id=self.rm.id,
            required_qty=Decimal("3"),
            issued_qty=Decimal("3"),
            reservation_id=reservation.id,
        )
        mo_service.receipt_finished_goods(
            user=self.user,
            company_id=self.company.id,
            mo_id=mo.id,
            received_qty=Decimal("3"),
        )

        self.assertTrue(StockLedger.objects.filter(ref_doc_type="production.mo_issue").exists())
        self.assertTrue(StockLedger.objects.filter(ref_doc_type="production.mo_receipt").exists())

    def test_production_qc_stage_enum(self):
        mo = ManufacturingOrderService().create_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="MO-QC",
            product_material_id=self.fg.id,
            planned_qty=Decimal("1"),
            warehouse_id=self.warehouse.id,
        )
        qc = ProductionQC.objects.create(
            company_id=self.company.id,
            mo=mo,
            stage=ProductionQC.Stage.IPQC,
            result=ProductionQC.Result.PASS,
            inspector_id=self.user.id,
            measurements_json={"temperature": 22.1},
        )
        self.assertEqual(qc.stage, "ipqc")
