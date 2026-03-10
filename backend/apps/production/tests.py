from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Lot, Reservation, StockBalance, StockLedger
from apps.inventory.services import StockLedgerService
from apps.material.models import Material, MaterialCategory, UoM, Warehouse
from apps.production.models import IoTMetric, ManufacturingOrder, ProductionQC
from apps.production.services import (
    IoTDeviceService,
    IoTMetricService,
    ManufacturingOrderService,
    ProductionPlanService,
    ProductionQCService,
)
from apps.sales.models import Customer, SalesOrder, SalesOrderLine
from company.models import Company, CompanyMembership, CompanyModule
from rbac.models import Permission, Role, RolePermission
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError


class ProductionEngineTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="prod_user", password="pwd")

        self.company = Company.objects.create(name="Production Co")
        for module in ["production", "inventory", "sales"]:
            CompanyModule.objects.create(company=self.company, module_code=module, is_enabled=True)

        self.role = Role.objects.create(code="prod-role", name="Production Role")
        for code in [
            PERMISSION_CODES.PRODUCTION_BOM_CREATE,
            PERMISSION_CODES.PRODUCTION_MO_CREATE,
            PERMISSION_CODES.PRODUCTION_MO_ISSUE,
            PERMISSION_CODES.PRODUCTION_MO_RECEIPT,
            PERMISSION_CODES.PRODUCTION_PLAN_CREATE,
            PERMISSION_CODES.PRODUCTION_PLAN_UPDATE,
            PERMISSION_CODES.PRODUCTION_QC_CREATE,
            PERMISSION_CODES.PRODUCTION_IOT_DEVICE_CREATE,
            PERMISSION_CODES.PRODUCTION_IOT_METRIC_CREATE,
            PERMISSION_CODES.INVENTORY_STOCK_LEDGER_WRITE,
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
        self.customer = Customer.objects.create(company_id=self.company.id, code="C1", name="Customer 1")

        self.sales_order = SalesOrder.objects.create(company_id=self.company.id, doc_no="SO-1", customer=self.customer)
        self.so_line = SalesOrderLine.objects.create(
            company_id=self.company.id,
            so=self.sales_order,
            material=self.fg,
            qty=Decimal("5"),
            price=Decimal("10"),
            warehouse=self.warehouse,
        )

        self.other_company = Company.objects.create(name="Other Co")
        for module in ["production", "inventory", "sales"]:
            CompanyModule.objects.create(company=self.other_company, module_code=module, is_enabled=True)
        self.other_uom = UoM.objects.create(company_id=self.other_company.id, name="EA", symbol="ea", ratio_to_base=Decimal("1"))
        self.other_category = MaterialCategory.objects.create(company_id=self.other_company.id, name="FG")
        self.other_material = Material.objects.create(
            company_id=self.other_company.id,
            code="O-FG",
            name="Other FG",
            category=self.other_category,
            uom=self.other_uom,
        )
        self.other_warehouse = Warehouse.objects.create(company_id=self.other_company.id, code="OWH", name="Other WH")

    def _seed_rm_stock(self, qty=Decimal("20")):
        StockLedgerService().record_movement(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            material_id=self.rm.id,
            movement_type=StockLedger.MovementType.IN,
            qty=qty,
            uom_id=self.uom.id,
        )

    def test_mto_requires_sales_order_material_alignment(self):
        service = ManufacturingOrderService()

        with self.assertRaises(BusinessRuleError):
            service.create_order(
                user=self.user,
                company_id=self.company.id,
                doc_no="MO-MTO-BAD",
                product_material_id=self.rm.id,
                planned_qty=Decimal("2"),
                warehouse_id=self.warehouse.id,
                production_mode=ManufacturingOrder.ProductionMode.MAKE_TO_ORDER,
                sales_order_id=self.sales_order.id,
            )

        mo = service.create_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="MO-MTO-OK",
            product_material_id=self.fg.id,
            planned_qty=Decimal("2"),
            warehouse_id=self.warehouse.id,
            production_mode=ManufacturingOrder.ProductionMode.MAKE_TO_ORDER,
            sales_order_id=self.sales_order.id,
        )
        self.assertEqual(mo.production_mode, ManufacturingOrder.ProductionMode.MAKE_TO_ORDER)

    def test_mto_issue_requires_reservation_qty_exact_match(self):
        self._seed_rm_stock()
        mo = ManufacturingOrderService().create_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="MO-MTO-I",
            product_material_id=self.fg.id,
            planned_qty=Decimal("3"),
            warehouse_id=self.warehouse.id,
            production_mode=ManufacturingOrder.ProductionMode.MAKE_TO_ORDER,
            sales_order_id=self.sales_order.id,
        )
        reservation = Reservation.objects.create(
            company_id=self.company.id,
            warehouse=self.warehouse,
            material=self.rm,
            qty=Decimal("3"),
            status=Reservation.Status.ACTIVE,
        )
        balance = StockBalance.objects.get(
            company_id=self.company.id,
            warehouse=self.warehouse,
            material=self.rm,
            lot__isnull=True,
            serial__isnull=True,
        )
        balance.reserved_qty = Decimal("3")
        balance.save()

        with self.assertRaises(BusinessRuleError):
            ManufacturingOrderService().issue_material(
                user=self.user,
                company_id=self.company.id,
                mo_id=mo.id,
                component_material_id=self.rm.id,
                required_qty=Decimal("3"),
                issued_qty=Decimal("2"),
                reservation_id=reservation.id,
            )

        ManufacturingOrderService().issue_material(
            user=self.user,
            company_id=self.company.id,
            mo_id=mo.id,
            component_material_id=self.rm.id,
            required_qty=Decimal("3"),
            issued_qty=Decimal("3"),
            reservation_id=reservation.id,
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CONSUMED)

    def test_mts_issue_can_work_without_reservation(self):
        self._seed_rm_stock(qty=Decimal("8"))
        mo = ManufacturingOrderService().create_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="MO-MTS",
            product_material_id=self.fg.id,
            planned_qty=Decimal("2"),
            warehouse_id=self.warehouse.id,
            production_mode=ManufacturingOrder.ProductionMode.MAKE_TO_STOCK,
        )

        ManufacturingOrderService().issue_material(
            user=self.user,
            company_id=self.company.id,
            mo_id=mo.id,
            component_material_id=self.rm.id,
            required_qty=Decimal("2"),
            issued_qty=Decimal("2"),
        )
        self.assertTrue(StockLedger.objects.filter(ref_doc_type="production.mo_issue").exists())

    def test_plan_qc_iot_services_have_guarded_paths(self):
        mo = ManufacturingOrderService().create_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="MO-SVC",
            product_material_id=self.fg.id,
            planned_qty=Decimal("1"),
            warehouse_id=self.warehouse.id,
            production_mode=ManufacturingOrder.ProductionMode.MAKE_TO_STOCK,
        )

        plan = ProductionPlanService().create_plan(
            user=self.user,
            company_id=self.company.id,
            plan_date=timezone.now().date(),
            capacity_json={"line_1": 100},
            mrp_result_json={"rm": 10},
        )
        updated = ProductionPlanService().update_plan(
            user=self.user,
            company_id=self.company.id,
            plan_id=plan.id,
            status="planned",
        )

        qc = ProductionQCService().create_qc_record(
            user=self.user,
            company_id=self.company.id,
            mo_id=mo.id,
            stage=ProductionQC.Stage.IPQC,
            result=ProductionQC.Result.PASS,
            inspector_id=self.user.id,
        )

        device = IoTDeviceService().register_device(
            user=self.user,
            company_id=self.company.id,
            device_code="D-1",
            name="Device 1",
            type="esp32",
            bound_mo_id=mo.id,
        )
        metric = IoTMetricService().record_metric(
            user=self.user,
            company_id=self.company.id,
            device_id=device.id,
            metric_key="temperature",
            value=Decimal("23.5"),
            recorded_at=timezone.now(),
        )

        self.assertEqual(updated.status, "planned")
        self.assertEqual(qc.mo_id, mo.id)
        self.assertEqual(metric.device_id, device.id)

    def test_cross_company_references_are_rejected(self):
        service = ManufacturingOrderService()
        with self.assertRaises(BusinessRuleError):
            service.create_order(
                user=self.user,
                company_id=self.company.id,
                doc_no="MO-XCOMP",
                product_material_id=self.other_material.id,
                planned_qty=Decimal("1"),
                warehouse_id=self.warehouse.id,
            )

        mo = service.create_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="MO-OWN",
            product_material_id=self.fg.id,
            planned_qty=Decimal("1"),
            warehouse_id=self.warehouse.id,
        )

        other_device_owner_company = Company.objects.create(name="Third Co")
        CompanyModule.objects.create(company=other_device_owner_company, module_code="production", is_enabled=True)

        other_lot = Lot.objects.create(company_id=self.other_company.id, material=self.other_material, lot_code="LOT-O")
        with self.assertRaises(DjangoValidationError):
            ManufacturingOrderService().receipt_finished_goods(
                user=self.user,
                company_id=self.company.id,
                mo_id=mo.id,
                received_qty=Decimal("1"),
                lot_id=other_lot.id,
            )

        qc = ProductionQC(
            company_id=self.other_company.id,
            mo=mo,
            stage=ProductionQC.Stage.FQC,
            result=ProductionQC.Result.FAIL,
            inspector_id=self.user.id,
        )
        with self.assertRaises(DjangoValidationError):
            qc.save()

        device = IoTDeviceService().register_device(
            user=self.user,
            company_id=self.company.id,
            device_code="D-X",
            name="Device X",
            type="esp32",
        )
        bad_metric = IoTMetric(
            company_id=self.other_company.id,
            device=device,
            metric_key="pressure",
            value=Decimal("1.5"),
            recorded_at=timezone.now(),
        )
        with self.assertRaises(DjangoValidationError):
            bad_metric.save()
