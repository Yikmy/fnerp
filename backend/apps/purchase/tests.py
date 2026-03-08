from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.inventory.models import StockBalance, StockLedger
from apps.material.models import Material, MaterialCategory, UoM, Warehouse
from apps.purchase.models import GoodsReceiptLine, InvoiceMatch
from apps.purchase.services import APMatchingService, GoodsReceiptService, PurchaseOrderService, VendorService
from company.models import Company, CompanyMembership, CompanyModule
from doc.models import DocumentStateMachineDef
from rbac.models import Permission, Role, RolePermission
from shared.constants.document import DOC_STATUS
from shared.constants.permissions import PERMISSION_CODES


class PurchaseEngineTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="pur_user", password="pwd")

        self.company = Company.objects.create(name="Purchasing Co")
        CompanyModule.objects.create(company=self.company, module_code="purchase", is_enabled=True)
        CompanyModule.objects.create(company=self.company, module_code="inventory", is_enabled=True)

        self.role = Role.objects.create(code="purchase-role", name="Purchase Role")
        for code in [
            PERMISSION_CODES.PURCHASE_VENDOR_CREATE,
            PERMISSION_CODES.PURCHASE_ORDER_CREATE,
            PERMISSION_CODES.PURCHASE_GRN_CREATE,
            PERMISSION_CODES.PURCHASE_AP_MATCH_CREATE,
            "purchase.order.submit",
            "purchase.order.confirm",
            "purchase.grn.submit",
            "purchase.grn.confirm",
            "purchase.grn.complete",
            PERMISSION_CODES.INVENTORY_STOCK_LEDGER_WRITE,
        ]:
            perm = Permission.objects.create(code=code, name=code)
            RolePermission.objects.create(role=self.role, permission=perm)

        CompanyMembership.objects.create(user=self.user, company=self.company, role=self.role, is_active=True)

        DocumentStateMachineDef.objects.create(document_type="purchase.order", from_state=DOC_STATUS.DRAFT, to_state=DOC_STATUS.SUBMITTED, permission_code="purchase.order.submit")
        DocumentStateMachineDef.objects.create(document_type="purchase.order", from_state=DOC_STATUS.SUBMITTED, to_state=DOC_STATUS.CONFIRMED, permission_code="purchase.order.confirm")
        DocumentStateMachineDef.objects.create(document_type="purchase.goods_receipt", from_state=DOC_STATUS.DRAFT, to_state=DOC_STATUS.SUBMITTED, permission_code="purchase.grn.submit")
        DocumentStateMachineDef.objects.create(document_type="purchase.goods_receipt", from_state=DOC_STATUS.SUBMITTED, to_state=DOC_STATUS.CONFIRMED, permission_code="purchase.grn.confirm")
        DocumentStateMachineDef.objects.create(document_type="purchase.goods_receipt", from_state=DOC_STATUS.CONFIRMED, to_state=DOC_STATUS.COMPLETED, permission_code="purchase.grn.complete")

        self.uom = UoM.objects.create(company_id=self.company.id, name="EA", symbol="ea", ratio_to_base=Decimal("1"))
        self.category = MaterialCategory.objects.create(company_id=self.company.id, name="Raw")
        self.material = Material.objects.create(
            company_id=self.company.id,
            code="MAT-1",
            name="Material 1",
            category=self.category,
            uom=self.uom,
        )
        self.warehouse = Warehouse.objects.create(company_id=self.company.id, code="W1", name="Main")

    def test_grn_completion_posts_stock_ledger(self):
        vendor = VendorService().create_vendor(
            user=self.user,
            company_id=self.company.id,
            code="V001",
            name="Vendor 1",
        )

        po_service = PurchaseOrderService()
        po = po_service.create_purchase_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="PO-001",
            vendor_id=vendor.id,
            lines=[
                {
                    "material_id": self.material.id,
                    "qty": Decimal("5"),
                    "price": Decimal("10"),
                    "warehouse_id": self.warehouse.id,
                }
            ],
        )
        po_service.transition_order(user=self.user, company_id=self.company.id, po_id=po.id, to_state=DOC_STATUS.SUBMITTED)
        po_service.transition_order(user=self.user, company_id=self.company.id, po_id=po.id, to_state=DOC_STATUS.CONFIRMED)

        grn_service = GoodsReceiptService()
        grn = grn_service.create_goods_receipt(
            user=self.user,
            company_id=self.company.id,
            doc_no="GRN-001",
            po_id=po.id,
            received_date="2026-03-08",
            warehouse_id=self.warehouse.id,
            lines=[
                {
                    "po_line_id": po.lines.first().id,
                    "material_id": self.material.id,
                    "received_qty": Decimal("5"),
                }
            ],
        )

        grn_service.transition_goods_receipt(
            user=self.user,
            company_id=self.company.id,
            grn_id=grn.id,
            to_state=DOC_STATUS.SUBMITTED,
        )
        grn_service.transition_goods_receipt(
            user=self.user,
            company_id=self.company.id,
            grn_id=grn.id,
            to_state=DOC_STATUS.CONFIRMED,
        )
        grn_service.transition_goods_receipt(
            user=self.user,
            company_id=self.company.id,
            grn_id=grn.id,
            to_state=DOC_STATUS.COMPLETED,
        )

        ledger = StockLedger.objects.get(ref_doc_type="purchase.goods_receipt", ref_doc_id=grn.id)
        balance = StockBalance.objects.get(company_id=self.company.id, warehouse=self.warehouse, material=self.material)
        self.assertEqual(ledger.qty, Decimal("5"))
        self.assertEqual(balance.on_hand_qty, Decimal("5"))


    def test_grn_line_requires_same_material_as_po_line(self):
        vendor = VendorService().create_vendor(
            user=self.user,
            company_id=self.company.id,
            code="V002",
            name="Vendor 2",
        )
        other_material = Material.objects.create(
            company_id=self.company.id,
            code="MAT-2",
            name="Material 2",
            category=self.category,
            uom=self.uom,
        )

        po_service = PurchaseOrderService()
        po = po_service.create_purchase_order(
            user=self.user,
            company_id=self.company.id,
            doc_no="PO-002",
            vendor_id=vendor.id,
            lines=[
                {
                    "material_id": self.material.id,
                    "qty": Decimal("2"),
                    "price": Decimal("3"),
                    "warehouse_id": self.warehouse.id,
                }
            ],
        )
        po_service.transition_order(user=self.user, company_id=self.company.id, po_id=po.id, to_state=DOC_STATUS.SUBMITTED)
        po_service.transition_order(user=self.user, company_id=self.company.id, po_id=po.id, to_state=DOC_STATUS.CONFIRMED)

        grn = GoodsReceiptService().create_goods_receipt(
            user=self.user,
            company_id=self.company.id,
            doc_no="GRN-002",
            po_id=po.id,
            received_date="2026-03-08",
            warehouse_id=self.warehouse.id,
            lines=[],
        )

        grn_line = GoodsReceiptLine(
            grn=grn,
            po_line=po.lines.first(),
            material=other_material,
            received_qty=Decimal("1"),
        )

        with self.assertRaises(ValidationError):
            grn_line.full_clean()

    def test_invoice_match_placeholder_model(self):
        match = APMatchingService().create_invoice_match(
            user=self.user,
            company_id=self.company.id,
            invoice_id="00000000-0000-0000-0000-000000000123",
            matched_amount=Decimal("10"),
            rule_json={"mode": "3way"},
        )
        self.assertIsInstance(match, InvoiceMatch)
        self.assertEqual(match.rule_json["mode"], "3way")
