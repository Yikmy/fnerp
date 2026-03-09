from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.inventory.models import Reservation, StockLedger
from apps.inventory.services import StockLedgerService
from apps.material.models import Material, MaterialCategory, UoM, Warehouse
from apps.sales.services import RMAService, SalesOrderService, SalesQuoteService, ShipmentService
from company.models import Company, CompanyMembership, CompanyModule
from rbac.models import Permission, Role, RolePermission
from shared.constants.document import DOC_STATUS
from doc.models import DocumentStateMachineDef
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError, PermissionDeniedError, ValidationError


class SalesStep5Tests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="sales_user", password="pwd")
        self.no_perm_user = user_model.objects.create_user(username="sales_no_perm", password="pwd")

        self.company = Company.objects.create(name="Sales Company")
        self.other_company = Company.objects.create(name="Other Sales Company")

        for module in ["sales", "inventory", "material"]:
            CompanyModule.objects.create(company=self.company, module_code=module, is_enabled=True)
            CompanyModule.objects.create(company=self.other_company, module_code=module, is_enabled=True)

        self.role = Role.objects.create(code="sales-role", name="Sales Role")
        permission_codes = [
            PERMISSION_CODES.SALES_CUSTOMER_CREATE,
            PERMISSION_CODES.SALES_PRICING_CREATE,
            PERMISSION_CODES.SALES_QUOTE_CREATE,
            PERMISSION_CODES.SALES_ORDER_CREATE,
            PERMISSION_CODES.SALES_SHIPMENT_CREATE,
            PERMISSION_CODES.SALES_RMA_CREATE,
            PERMISSION_CODES.INVENTORY_STOCK_LEDGER_WRITE,
            PERMISSION_CODES.INVENTORY_RESERVATION_CREATE,
            PERMISSION_CODES.INVENTORY_RESERVATION_RELEASE,
            PERMISSION_CODES.INVENTORY_RESERVATION_CONSUME,
            "sales.quote.submit",
            "sales.quote.confirm",
            "sales.quote.complete",
            "sales.order.submit",
            "sales.order.confirm",
            "sales.order.complete",
            "sales.shipment.submit",
            "sales.shipment.confirm",
            "sales.shipment.complete",
            "sales.rma.submit",
            "sales.rma.confirm",
            "sales.rma.complete",
        ]
        for code in permission_codes:
            perm = Permission.objects.create(code=code, name=code)
            RolePermission.objects.create(role=self.role, permission=perm)

        CompanyMembership.objects.create(user=self.user, company=self.company, role=self.role, is_active=True)
        CompanyMembership.objects.create(user=self.no_perm_user, company=self.company, is_active=True)

        self._seed_document_transition_permissions()

        self.uom = UoM.objects.create(company_id=self.company.id, name="EA", symbol="ea", ratio_to_base=Decimal("1"))
        self.category = MaterialCategory.objects.create(company_id=self.company.id, name="General")
        self.material = Material.objects.create(
            company_id=self.company.id,
            code="MAT-1",
            name="Material 1",
            category=self.category,
            uom=self.uom,
        )
        self.warehouse = Warehouse.objects.create(company_id=self.company.id, code="WH-1", name="Main WH")

        self.other_uom = UoM.objects.create(company_id=self.other_company.id, name="EA", symbol="ea2", ratio_to_base=Decimal("1"))
        self.other_category = MaterialCategory.objects.create(company_id=self.other_company.id, name="Other")
        self.other_material = Material.objects.create(
            company_id=self.other_company.id,
            code="MAT-O1",
            name="Other Material",
            category=self.other_category,
            uom=self.other_uom,
        )
        self.other_warehouse = Warehouse.objects.create(company_id=self.other_company.id, code="WH-O", name="Other WH")

        self.customer = self._create_customer(company_id=self.company.id, code="C-1")
        self.other_customer = self._create_customer(company_id=self.other_company.id, code="C-O1")

    def _create_customer(self, *, company_id, code):
        from apps.sales.models import Customer

        return Customer.objects.create(
            company_id=company_id,
            code=code,
            name=f"Customer {code}",
            contact_json={"email": f"{code.lower()}@example.com"},
            credit_limit=Decimal("1000"),
        )

    def _seed_document_transition_permissions(self):
        transition_specs = {
            "sales.quote": [
                (DOC_STATUS.DRAFT, DOC_STATUS.SUBMITTED, "sales.quote.submit"),
                (DOC_STATUS.SUBMITTED, DOC_STATUS.CONFIRMED, "sales.quote.confirm"),
                (DOC_STATUS.CONFIRMED, DOC_STATUS.COMPLETED, "sales.quote.complete"),
            ],
            "sales.order": [
                (DOC_STATUS.DRAFT, DOC_STATUS.SUBMITTED, "sales.order.submit"),
                (DOC_STATUS.SUBMITTED, DOC_STATUS.CONFIRMED, "sales.order.confirm"),
                (DOC_STATUS.CONFIRMED, DOC_STATUS.COMPLETED, "sales.order.complete"),
            ],
            "sales.shipment": [
                (DOC_STATUS.DRAFT, DOC_STATUS.SUBMITTED, "sales.shipment.submit"),
                (DOC_STATUS.SUBMITTED, DOC_STATUS.CONFIRMED, "sales.shipment.confirm"),
                (DOC_STATUS.CONFIRMED, DOC_STATUS.COMPLETED, "sales.shipment.complete"),
            ],
            "sales.rma": [
                (DOC_STATUS.DRAFT, DOC_STATUS.SUBMITTED, "sales.rma.submit"),
                (DOC_STATUS.SUBMITTED, DOC_STATUS.CONFIRMED, "sales.rma.confirm"),
                (DOC_STATUS.CONFIRMED, DOC_STATUS.COMPLETED, "sales.rma.complete"),
            ],
        }
        for document_type, rows in transition_specs.items():
            for from_state, to_state, permission_code in rows:
                DocumentStateMachineDef.objects.create(
                    document_type=document_type,
                    from_state=from_state,
                    to_state=to_state,
                    permission_code=permission_code,
                    is_active=True,
                )

    def _create_order_and_confirm(self, qty=Decimal("6")):
        order_service = SalesOrderService()
        order = order_service.create_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="SO-001",
            customer_id=self.customer.id,
            lines=[
                {
                    "material_id": self.material.id,
                    "qty": qty,
                    "price": Decimal("10"),
                    "warehouse_id": self.warehouse.id,
                }
            ],
        )
        order_service.transition_order(user=self.user, company_id=self.company.id, order_id=order.id, to_state=DOC_STATUS.SUBMITTED)

        StockLedgerService().record_movement(
            user=self.user,
            company_id=self.company.id,
            warehouse_id=self.warehouse.id,
            material_id=self.material.id,
            movement_type=StockLedger.MovementType.IN,
            qty=Decimal("20"),
            uom_id=self.uom.id,
        )

        order_service.transition_order(user=self.user, company_id=self.company.id, order_id=order.id, to_state=DOC_STATUS.CONFIRMED)
        order.refresh_from_db()
        return order

    def test_order_confirmation_creates_reservation(self):
        order = self._create_order_and_confirm()
        so_line = order.lines.first()

        reservation = Reservation.objects.get(company_id=self.company.id, ref_doc_type="sales.order.line", ref_doc_id=so_line.id)
        self.assertEqual(reservation.status, Reservation.Status.ACTIVE)
        self.assertEqual(reservation.qty, so_line.qty)
        self.assertEqual(so_line.reserved_qty, so_line.qty)

    def test_shipment_completion_writes_ledger_and_consumes_or_reduces_reservation(self):
        order = self._create_order_and_confirm(qty=Decimal("6"))
        so_line = order.lines.first()
        shipment_service = ShipmentService()

        shipment1 = shipment_service.create_shipment(
            user=self.user,
            company_id=self.company.id,
            doc_no="SHP-001",
            so_id=order.id,
            customer_id=self.customer.id,
            warehouse_id=self.warehouse.id,
            ship_date="2026-03-09",
            lines=[{"so_line_id": so_line.id, "material_id": self.material.id, "qty": Decimal("2")}],
        )
        shipment_service.transition_shipment(user=self.user, company_id=self.company.id, shipment_id=shipment1.id, to_state=DOC_STATUS.SUBMITTED)
        shipment_service.transition_shipment(user=self.user, company_id=self.company.id, shipment_id=shipment1.id, to_state=DOC_STATUS.CONFIRMED)
        shipment_service.transition_shipment(user=self.user, company_id=self.company.id, shipment_id=shipment1.id, to_state=DOC_STATUS.COMPLETED)

        self.assertTrue(
            StockLedger.objects.filter(
                company_id=self.company.id,
                ref_doc_type="sales.shipment",
                ref_doc_id=shipment1.id,
                movement_type=StockLedger.MovementType.OUT,
            ).exists()
        )
        so_line.refresh_from_db()
        self.assertEqual(so_line.reserved_qty, Decimal("4"))

        reservation = Reservation.objects.get(company_id=self.company.id, ref_doc_type="sales.order.line", ref_doc_id=so_line.id, status=Reservation.Status.ACTIVE)
        self.assertEqual(reservation.qty, Decimal("4"))

    def test_rma_completion_writes_inbound_ledger(self):
        rma_service = RMAService()
        rma = rma_service.create_rma(
            user=self.user,
            company_id=self.company.id,
            doc_no="RMA-001",
            customer_id=self.customer.id,
            reason_code="damaged",
            lines=[{"material_id": self.material.id, "qty": Decimal("3"), "warehouse_id": self.warehouse.id}],
        )
        rma_service.transition_rma(user=self.user, company_id=self.company.id, rma_id=rma.id, to_state=DOC_STATUS.SUBMITTED)
        rma_service.transition_rma(user=self.user, company_id=self.company.id, rma_id=rma.id, to_state=DOC_STATUS.CONFIRMED)
        rma_service.transition_rma(user=self.user, company_id=self.company.id, rma_id=rma.id, to_state=DOC_STATUS.COMPLETED)

        self.assertTrue(
            StockLedger.objects.filter(
                company_id=self.company.id,
                ref_doc_type="sales.rma",
                ref_doc_id=rma.id,
                movement_type=StockLedger.MovementType.IN,
            ).exists()
        )

    def test_invalid_transition_rejected(self):
        quote = SalesQuoteService().create_quote(
            user=self.user,
            company_id=self.company.id,
            doc_no="SQ-001",
            customer_id=self.customer.id,
            lines=[{"material_id": self.material.id, "qty": Decimal("1"), "price": Decimal("10")}],
        )
        with self.assertRaises(ValidationError):
            SalesQuoteService().transition_quote(
                user=self.user,
                company_id=self.company.id,
                quote_id=quote.id,
                to_state=DOC_STATUS.COMPLETED,
            )

    def test_permission_denied_for_quote_order_shipment_actions(self):
        with self.assertRaises(PermissionDeniedError):
            SalesQuoteService().create_quote(
                user=self.no_perm_user,
                company_id=self.company.id,
                doc_no="SQ-PERM",
                customer_id=self.customer.id,
                lines=[{"material_id": self.material.id, "qty": Decimal("1"), "price": Decimal("1")}],
            )

        with self.assertRaises(PermissionDeniedError):
            SalesOrderService().create_order(
                user=self.no_perm_user,
                company_id=self.company.id,
                doc_no="SO-PERM",
                customer_id=self.customer.id,
                lines=[{"material_id": self.material.id, "qty": Decimal("1"), "price": Decimal("1"), "warehouse_id": self.warehouse.id}],
            )

        order = self._create_order_and_confirm(qty=Decimal("2"))
        so_line = order.lines.first()

        with self.assertRaises(PermissionDeniedError):
            ShipmentService().create_shipment(
                user=self.no_perm_user,
                company_id=self.company.id,
                doc_no="SHP-PERM",
                so_id=order.id,
                customer_id=self.customer.id,
                warehouse_id=self.warehouse.id,
                ship_date="2026-03-09",
                lines=[{"so_line_id": so_line.id, "material_id": self.material.id, "qty": Decimal("1")}],
            )

    def test_permission_denied_for_transitions(self):
        quote = SalesQuoteService().create_quote(
            user=self.user,
            company_id=self.company.id,
            doc_no="SQ-T",
            customer_id=self.customer.id,
            lines=[{"material_id": self.material.id, "qty": Decimal("1"), "price": Decimal("1")}],
        )
        with self.assertRaises(PermissionDeniedError):
            SalesQuoteService().transition_quote(
                user=self.no_perm_user,
                company_id=self.company.id,
                quote_id=quote.id,
                to_state=DOC_STATUS.SUBMITTED,
            )

    def test_company_scope_rejects_cross_company_entities(self):
        with self.assertRaises(BusinessRuleError):
            SalesQuoteService().create_quote(
                user=self.user,
                company_id=self.company.id,
                doc_no="SQ-X",
                customer_id=self.other_customer.id,
                lines=[{"material_id": self.material.id, "qty": Decimal("1"), "price": Decimal("1")}],
            )

        with self.assertRaises(BusinessRuleError):
            SalesOrderService().create_order(
                user=self.user,
                company_id=self.company.id,
                doc_no="SO-X",
                customer_id=self.customer.id,
                lines=[
                    {
                        "material_id": self.other_material.id,
                        "qty": Decimal("1"),
                        "price": Decimal("1"),
                        "warehouse_id": self.warehouse.id,
                    }
                ],
            )

    def test_overship_is_blocked(self):
        order = self._create_order_and_confirm(qty=Decimal("5"))
        so_line = order.lines.first()
        shipment_service = ShipmentService()

        shipment = shipment_service.create_shipment(
            user=self.user,
            company_id=self.company.id,
            doc_no="SHP-OV-1",
            so_id=order.id,
            customer_id=self.customer.id,
            warehouse_id=self.warehouse.id,
            ship_date="2026-03-09",
            lines=[{"so_line_id": so_line.id, "material_id": self.material.id, "qty": Decimal("3")}],
        )
        shipment_service.transition_shipment(user=self.user, company_id=self.company.id, shipment_id=shipment.id, to_state=DOC_STATUS.SUBMITTED)
        shipment_service.transition_shipment(user=self.user, company_id=self.company.id, shipment_id=shipment.id, to_state=DOC_STATUS.CONFIRMED)
        shipment_service.transition_shipment(user=self.user, company_id=self.company.id, shipment_id=shipment.id, to_state=DOC_STATUS.COMPLETED)

        with self.assertRaisesMessage(BusinessRuleError, "Shipment quantity cannot exceed remaining sales order quantity"):
            shipment_service.create_shipment(
                user=self.user,
                company_id=self.company.id,
                doc_no="SHP-OV-2",
                so_id=order.id,
                customer_id=self.customer.id,
                warehouse_id=self.warehouse.id,
                ship_date="2026-03-09",
                lines=[{"so_line_id": so_line.id, "material_id": self.material.id, "qty": Decimal("3")}],
            )

    def test_shipment_must_not_exceed_reserved_qty(self):
        order = self._create_order_and_confirm(qty=Decimal("4"))
        so_line = order.lines.first()
        so_line.reserved_qty = Decimal("1")
        so_line.save(update_fields=["reserved_qty", "updated_at"])

        with self.assertRaisesMessage(BusinessRuleError, "Shipment quantity cannot exceed reserved quantity"):
            ShipmentService().create_shipment(
                user=self.user,
                company_id=self.company.id,
                doc_no="SHP-RSV",
                so_id=order.id,
                customer_id=self.customer.id,
                warehouse_id=self.warehouse.id,
                ship_date="2026-03-09",
                lines=[{"so_line_id": so_line.id, "material_id": self.material.id, "qty": Decimal("2")}],
            )
