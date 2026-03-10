from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService

from .models import AccountingInvoice, AccountingPosting, Payment


class AccountingService(BaseService):
    MODULE_CODE = "accounting"
    PERM_POST_INVOICE = "accounting.invoice.post"
    PERM_REVERSE_POSTING = "accounting.posting.reverse"
    PERM_RECORD_PAYMENT = "accounting.payment.record"

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("accounting module is disabled for this company")

    @staticmethod
    def _require_completed(status: str, label: str):
        if status != "COMPLETED":
            raise BusinessRuleError(f"{label} must be COMPLETED before accounting posting")

    @transaction.atomic
    def post_sales_invoice(self, *, user, company_id, sales_order_id, issue_date, due_date=None, request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_POST_INVOICE)

        so = SalesOrder.objects.active().for_company(company_id).filter(id=sales_order_id).first()
        if so is None:
            raise BusinessRuleError("Sales order not found in company scope")
        self._require_completed(so.status, "Sales order")

        posting, created = AccountingPosting.objects.select_for_update().get_or_create(
            company_id=company_id,
            entry_type=AccountingPosting.EntryType.INVOICE,
            source_doc_type="sales.sales_order",
            source_doc_id=so.id,
            defaults={
                "created_by": self._user_id(user),
                "updated_by": self._user_id(user),
                "invoice": AccountingInvoice.objects.create(
                    company_id=company_id,
                    type=AccountingInvoice.InvoiceType.AR,
                    counterparty_type="customer",
                    counterparty_id=so.customer_id,
                    sales_order=so,
                    issue_date=issue_date,
                    due_date=due_date,
                    currency="USD",
                    total_amount=so.total_amount,
                    status=AccountingInvoice.Status.ISSUED,
                    created_by=self._user_id(user),
                    updated_by=self._user_id(user),
                ),
            },
        )
        if created:
            self.audit_crud(
                user=user,
                company_id=company_id,
                operation="create",
                resource_type="accounting.posting",
                resource_id=posting.id,
                request=request,
            )
        return posting.invoice, created

    @transaction.atomic
    def post_purchase_invoice(self, *, user, company_id, purchase_order_id, issue_date, due_date=None, request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_POST_INVOICE)

        po = PurchaseOrder.objects.active().for_company(company_id).filter(id=purchase_order_id).first()
        if po is None:
            raise BusinessRuleError("Purchase order not found in company scope")
        self._require_completed(po.status, "Purchase order")

        posting, created = AccountingPosting.objects.select_for_update().get_or_create(
            company_id=company_id,
            entry_type=AccountingPosting.EntryType.INVOICE,
            source_doc_type="purchase.purchase_order",
            source_doc_id=po.id,
            defaults={
                "created_by": self._user_id(user),
                "updated_by": self._user_id(user),
                "invoice": AccountingInvoice.objects.create(
                    company_id=company_id,
                    type=AccountingInvoice.InvoiceType.AP,
                    counterparty_type="vendor",
                    counterparty_id=po.vendor_id,
                    purchase_order=po,
                    issue_date=issue_date,
                    due_date=due_date,
                    currency=po.currency,
                    total_amount=po.total_amount,
                    status=AccountingInvoice.Status.ISSUED,
                    created_by=self._user_id(user),
                    updated_by=self._user_id(user),
                ),
            },
        )
        if created:
            self.audit_crud(
                user=user,
                company_id=company_id,
                operation="create",
                resource_type="accounting.posting",
                resource_id=posting.id,
                request=request,
            )
        return posting.invoice, created

    @transaction.atomic
    def record_payment(
        self,
        *,
        user,
        company_id,
        invoice_id,
        amount,
        currency,
        direction,
        paid_at=None,
        method="",
        reference="",
        source_ref_type="",
        source_ref_id=None,
        request=None,
    ):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_RECORD_PAYMENT)

        invoice = AccountingInvoice.objects.active().for_company(company_id).filter(id=invoice_id).first()
        if invoice is None:
            raise BusinessRuleError("Invoice not found in company scope")

        if source_ref_type and source_ref_id:
            existing = Payment.objects.active().for_company(company_id).filter(
                source_ref_type=source_ref_type,
                source_ref_id=source_ref_id,
            ).first()
            if existing:
                return existing, False

        paid_total = (
            invoice.payments.filter(is_deleted=False).aggregate(total=Sum("amount")).get("total")
            or 0
        )
        if paid_total + amount > invoice.total_amount:
            raise BusinessRuleError("Payment exceeds invoice total")

        payment = Payment(
            company_id=company_id,
            invoice=invoice,
            amount=amount,
            currency=currency,
            direction=direction,
            paid_at=paid_at or timezone.now(),
            method=method,
            reference=reference,
            source_ref_type=source_ref_type,
            source_ref_id=source_ref_id,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        payment.full_clean()
        payment.save()

        paid_total_after = paid_total + amount
        if paid_total_after == invoice.total_amount:
            invoice.status = AccountingInvoice.Status.PAID
            invoice.updated_by = self._user_id(user)
            invoice.full_clean()
            invoice.save(update_fields=["status", "updated_at", "updated_by"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="accounting.payment",
            resource_id=payment.id,
            request=request,
        )
        return payment, True

    @transaction.atomic
    def reverse_posting(self, *, user, company_id, posting_id, notes="", request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_REVERSE_POSTING)

        posting = AccountingPosting.objects.active().for_company(company_id).filter(id=posting_id).first()
        if posting is None:
            raise BusinessRuleError("Posting not found in company scope")
        if posting.status == AccountingPosting.Status.REVERSED:
            return posting

        posting.status = AccountingPosting.Status.REVERSED
        posting.reversed_at = timezone.now()
        posting.notes = notes
        posting.updated_by = self._user_id(user)
        posting.full_clean()
        posting.save(update_fields=["status", "reversed_at", "notes", "updated_at", "updated_by"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="update",
            resource_type="accounting.posting",
            resource_id=posting.id,
            request=request,
            field_diffs=[{"field_name": "status", "old_value": "posted", "new_value": "reversed"}],
        )
        return posting
