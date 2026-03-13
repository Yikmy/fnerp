from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from apps.inventory.models import StockLedger
from apps.inventory.services import StockLedgerService
from apps.material.models import Material, Warehouse
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from .workflow import PurchaseDomainService
from ..models import (
    GoodsReceipt,
    GoodsReceiptLine,
    InvoiceMatch,
    IQCRecord,
    PurchaseOrder,
    PurchaseOrderLine,
    RFQLine,
    RFQQuote,
    RFQTask,
    Vendor,
    VendorHistory,
)

class RFQService(PurchaseDomainService):
    PERM_CREATE = PERMISSION_CODES.PURCHASE_RFQ_CREATE

    @transaction.atomic
    def create_rfq(self, *, user, company_id, title, llm_enabled=False, schedule_json=None, lines=None, request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        rfq = RFQTask(
            company_id=company_id,
            title=title,
            llm_enabled=llm_enabled,
            schedule_json=schedule_json or {},
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        rfq.full_clean()
        rfq.save()

        for line in lines or []:
            rfq_line = RFQLine(
                rfq=rfq,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=line["qty"],
                target_date=line["target_date"],
            )
            rfq_line.full_clean()
            rfq_line.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="purchase.rfq",
            resource_id=rfq.id,
            request=request,
        )
        return rfq

    @transaction.atomic
    def add_quote(
        self,
        *,
        user,
        company_id,
        rfq_id,
        vendor_id,
        material_id,
        price,
        currency,
        lead_time_days,
        valid_until,
        source="",
        raw_payload=None,
        request=None,
    ):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        rfq = RFQTask.objects.active().for_company(company_id).filter(id=rfq_id).first()
        if rfq is None:
            raise BusinessRuleError("RFQ not found in company scope")

        quote = RFQQuote(
            rfq=rfq,
            vendor=self._vendor(company_id=company_id, vendor_id=vendor_id),
            material=self._material(company_id=company_id, material_id=material_id),
            price=price,
            currency=currency,
            lead_time_days=lead_time_days,
            valid_until=valid_until,
            source=source,
            raw_payload=raw_payload or {},
        )
        quote.full_clean()
        quote.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="purchase.rfq_quote",
            resource_id=quote.id,
            request=request,
        )
        return quote

class PurchaseOrderService(PurchaseDomainService):
    PERM_CREATE = PERMISSION_CODES.PURCHASE_ORDER_CREATE

    def __init__(self):
        super().__init__()
        self.transition_service = DocumentStateTransitionService()

    @transaction.atomic
    def create_purchase_order(self, *, user, company_id, doc_no, vendor_id, expected_date=None, currency="USD", lines=None, remark="", request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        po = PurchaseOrder(
            company_id=company_id,
            doc_no=doc_no,
            vendor=self._vendor(company_id=company_id, vendor_id=vendor_id),
            expected_date=expected_date,
            currency=currency,
            remark=remark,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        po.full_clean()
        po.save()

        total_amount = Decimal("0")
        for line in lines or []:
            po_line = PurchaseOrderLine(
                po=po,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                qty=line["qty"],
                price=line["price"],
                tax_rate=line.get("tax_rate", Decimal("0")),
                warehouse=self._warehouse(company_id=company_id, warehouse_id=line["warehouse_id"]),
                suggested_qty=line.get("suggested_qty", line["qty"]),
            )
            po_line.full_clean()
            po_line.save()
            total_amount += po_line.qty * po_line.price

        po.total_amount = total_amount
        po.save(update_fields=["total_amount", "updated_at"])

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="purchase.order",
            resource_id=po.id,
            request=request,
        )
        return po

    @transaction.atomic
    def transition_order(self, *, user, company_id, po_id, to_state, notes="", request=None):
        self._ensure_module_enabled(company_id=company_id)
        po = PurchaseOrder.objects.active().for_company(company_id).filter(id=po_id).first()
        if po is None:
            raise BusinessRuleError("Purchase order not found in company scope")

        return self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=po,
            document_type="purchase.order",
            to_state=to_state,
            notes=notes,
            request=request,
        )

class GoodsReceiptService(PurchaseDomainService):
    PERM_CREATE = PERMISSION_CODES.PURCHASE_GRN_CREATE

    def __init__(self):
        super().__init__()
        self.transition_service = DocumentStateTransitionService()
        self.stock_ledger_service = StockLedgerService()

    @transaction.atomic
    def create_goods_receipt(
        self,
        *,
        user,
        company_id,
        doc_no,
        po_id,
        received_date,
        warehouse_id,
        is_partial=False,
        lines=None,
        request=None,
    ):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        po = PurchaseOrder.objects.active().for_company(company_id).filter(id=po_id).first()
        if po is None:
            raise BusinessRuleError("Purchase order not found in company scope")
        if po.status not in {DOC_STATUS.CONFIRMED, DOC_STATUS.COMPLETED}:
            raise BusinessRuleError("Goods receipt requires a confirmed purchase order")

        grn = GoodsReceipt(
            company_id=company_id,
            doc_no=doc_no,
            po=po,
            received_date=received_date,
            warehouse=self._warehouse(company_id=company_id, warehouse_id=warehouse_id),
            is_partial=is_partial,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        grn.full_clean()
        grn.save()

        for line in lines or []:
            po_line = PurchaseOrderLine.objects.filter(po=po, id=line["po_line_id"]).first()
            if po_line is None:
                raise BusinessRuleError("PO line not found in purchase order")

            existing_received = (
                GoodsReceiptLine.objects.filter(po_line=po_line)
                .aggregate(total=Sum("received_qty"))
                .get("total")
                or Decimal("0")
            )
            requested_qty = line["received_qty"]
            if existing_received + requested_qty > po_line.qty:
                raise BusinessRuleError("Received quantity cannot exceed PO line quantity")

            grn_line = GoodsReceiptLine(
                grn=grn,
                po_line=po_line,
                material=self._material(company_id=company_id, material_id=line["material_id"]),
                received_qty=requested_qty,
                lot_id=line.get("lot_id"),
                serial_id=line.get("serial_id"),
            )
            grn_line.full_clean()
            grn_line.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="purchase.goods_receipt",
            resource_id=grn.id,
            request=request,
        )
        return grn

    @transaction.atomic
    def transition_goods_receipt(self, *, user, company_id, grn_id, to_state, notes="", request=None):
        self._ensure_module_enabled(company_id=company_id)
        grn = GoodsReceipt.objects.active().for_company(company_id).filter(id=grn_id).first()
        if grn is None:
            raise BusinessRuleError("Goods receipt not found in company scope")

        if to_state == DOC_STATUS.COMPLETED:
            grn = GoodsReceipt.objects.select_for_update().active().for_company(company_id).filter(id=grn_id).first()
            if grn is None:
                raise BusinessRuleError("Goods receipt not found in company scope")
            if grn.status == DOC_STATUS.COMPLETED:
                return grn
            if grn.status != DOC_STATUS.CONFIRMED:
                raise BusinessRuleError("Goods receipt must be confirmed before completion")
            if StockLedger.objects.filter(
                company_id=company_id,
                ref_doc_type="purchase.goods_receipt",
                ref_doc_id=grn.id,
            ).exists():
                raise BusinessRuleError("Goods receipt inventory already posted")
            self._post_inventory(user=user, company_id=company_id, grn=grn, request=request)

        return self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=grn,
            document_type="purchase.goods_receipt",
            to_state=to_state,
            notes=notes,
            request=request,
        )

    def _post_inventory(self, *, user, company_id, grn: GoodsReceipt, request=None):
        for line in grn.lines.select_related("material"):
            self.stock_ledger_service.record_movement(
                user=user,
                company_id=company_id,
                warehouse_id=grn.warehouse_id,
                material_id=line.material_id,
                movement_type=StockLedger.MovementType.IN,
                qty=line.received_qty,
                uom_id=line.material.uom_id,
                lot_id=line.lot_id,
                serial_id=line.serial_id,
                ref_doc_type="purchase.goods_receipt",
                ref_doc_id=grn.id,
                request=request,
            )
