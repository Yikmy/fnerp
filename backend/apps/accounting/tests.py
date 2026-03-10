from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounting.models import AccountingInvoice, AccountingPosting
from apps.accounting.services import AccountingService
from apps.material.models import Material, MaterialCategory, UoM, Warehouse
from apps.purchase.models import PurchaseOrder, Vendor
from apps.sales.models import Customer, SalesOrder
from company.models import Company, CompanyMembership, CompanyModule
from rbac.models import Permission, Role, RolePermission
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError


class AccountingStep8Tests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="acct_user", password="pwd")

        self.company = Company.objects.create(name="Acct Co")
        self.other_company = Company.objects.create(name="Other Co")

        for module in ["material", "purchase", "sales", "accounting"]:
            CompanyModule.objects.create(company=self.company, module_code=module, is_enabled=True)
            CompanyModule.objects.create(company=self.other_company, module_code=module, is_enabled=True)

        role = Role.objects.create(code="acct-role", name="Accounting Role")
        for code in [
            "accounting.invoice.post",
            "accounting.payment.record",
            "accounting.posting.reverse",
            PERMISSION_CODES.SALES_ORDER_CREATE,
            PERMISSION_CODES.PURCHASE_ORDER_CREATE,
        ]:
            perm = Permission.objects.create(code=code, name=code)
            RolePermission.objects.create(role=role, permission=perm)
        CompanyMembership.objects.create(user=self.user, company=self.company, role=role, is_active=True)

        uom = UoM.objects.create(company_id=self.company.id, name="EA", symbol="ea", ratio_to_base=Decimal("1"))
        category = MaterialCategory.objects.create(company_id=self.company.id, name="Raw")
        self.warehouse = Warehouse.objects.create(company_id=self.company.id, code="WH1", name="Main")
        self.material = Material.objects.create(
            company_id=self.company.id,
            code="MAT1",
            name="Material 1",
            category=category,
            uom=uom,
        )

        self.customer = Customer.objects.create(company_id=self.company.id, code="C1", name="Customer 1")
        self.sales_order = SalesOrder.objects.create(
            company_id=self.company.id,
            doc_no="SO1",
            customer=self.customer,
            total_amount=Decimal("100"),
            status="COMPLETED",
        )

        self.vendor = Vendor.objects.create(company_id=self.company.id, code="V1", name="Vendor 1")
        self.purchase_order = PurchaseOrder.objects.create(
            company_id=self.company.id,
            doc_no="PO1",
            vendor=self.vendor,
            total_amount=Decimal("80"),
            status="COMPLETED",
        )

        other_uom = UoM.objects.create(company_id=self.other_company.id, name="EA2", symbol="ea2", ratio_to_base=Decimal("1"))
        other_category = MaterialCategory.objects.create(company_id=self.other_company.id, name="Other")
        Material.objects.create(
            company_id=self.other_company.id,
            code="MATX",
            name="Material X",
            category=other_category,
            uom=other_uom,
        )
        other_customer = Customer.objects.create(company_id=self.other_company.id, code="C2", name="Customer 2")
        self.other_sales_order = SalesOrder.objects.create(
            company_id=self.other_company.id,
            doc_no="SOX",
            customer=other_customer,
            total_amount=Decimal("50"),
            status="COMPLETED",
        )

    def test_posting_creation_for_sales_and_purchase_invoice(self):
        svc = AccountingService()

        sales_invoice, sales_created = svc.post_sales_invoice(
            user=self.user,
            company_id=self.company.id,
            sales_order_id=self.sales_order.id,
            issue_date=date(2026, 1, 1),
        )
        purchase_invoice, purchase_created = svc.post_purchase_invoice(
            user=self.user,
            company_id=self.company.id,
            purchase_order_id=self.purchase_order.id,
            issue_date=date(2026, 1, 2),
        )

        self.assertTrue(sales_created)
        self.assertTrue(purchase_created)
        self.assertEqual(sales_invoice.type, AccountingInvoice.InvoiceType.AR)
        self.assertEqual(purchase_invoice.type, AccountingInvoice.InvoiceType.AP)
        self.assertEqual(AccountingPosting.objects.filter(company_id=self.company.id).count(), 2)

    def test_idempotent_repost_prevention(self):
        svc = AccountingService()
        first_invoice, first_created = svc.post_sales_invoice(
            user=self.user,
            company_id=self.company.id,
            sales_order_id=self.sales_order.id,
            issue_date=date(2026, 1, 1),
        )
        second_invoice, second_created = svc.post_sales_invoice(
            user=self.user,
            company_id=self.company.id,
            sales_order_id=self.sales_order.id,
            issue_date=date(2026, 1, 3),
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_invoice.id, second_invoice.id)
        self.assertEqual(AccountingPosting.objects.filter(company_id=self.company.id, source_doc_id=self.sales_order.id).count(), 1)

    def test_company_scope_protection(self):
        svc = AccountingService()
        with self.assertRaises(BusinessRuleError):
            svc.post_sales_invoice(
                user=self.user,
                company_id=self.company.id,
                sales_order_id=self.other_sales_order.id,
                issue_date=date(2026, 1, 1),
            )

    def test_source_document_eligibility_validation(self):
        svc = AccountingService()
        self.sales_order.status = "DRAFT"
        self.sales_order.save(update_fields=["status"])

        with self.assertRaises(BusinessRuleError):
            svc.post_sales_invoice(
                user=self.user,
                company_id=self.company.id,
                sales_order_id=self.sales_order.id,
                issue_date=date(2026, 1, 1),
            )

    def test_reverse_posting(self):
        svc = AccountingService()
        _, _ = svc.post_purchase_invoice(
            user=self.user,
            company_id=self.company.id,
            purchase_order_id=self.purchase_order.id,
            issue_date=date(2026, 1, 2),
        )
        posting = AccountingPosting.objects.get(company_id=self.company.id, source_doc_id=self.purchase_order.id)

        reversed_posting = svc.reverse_posting(
            user=self.user,
            company_id=self.company.id,
            posting_id=posting.id,
            notes="Reversed for correction",
        )
        self.assertEqual(reversed_posting.status, AccountingPosting.Status.REVERSED)

    def test_payment_recording_idempotency(self):
        svc = AccountingService()
        invoice, _ = svc.post_sales_invoice(
            user=self.user,
            company_id=self.company.id,
            sales_order_id=self.sales_order.id,
            issue_date=date(2026, 1, 1),
        )

        first_payment, first_created = svc.record_payment(
            user=self.user,
            company_id=self.company.id,
            invoice_id=invoice.id,
            amount=Decimal("100"),
            currency="USD",
            direction="in",
            source_ref_type="bank_txn",
            source_ref_id=invoice.id,
        )
        second_payment, second_created = svc.record_payment(
            user=self.user,
            company_id=self.company.id,
            invoice_id=invoice.id,
            amount=Decimal("100"),
            currency="USD",
            direction="in",
            source_ref_type="bank_txn",
            source_ref_id=invoice.id,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_payment.id, second_payment.id)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, AccountingInvoice.Status.PAID)
