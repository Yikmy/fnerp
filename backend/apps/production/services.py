from decimal import Decimal

from django.db import transaction

from apps.inventory.models import Reservation, StockLedger
from apps.inventory.services import ReservationService, StockLedgerService
from apps.material.models import Material, Warehouse
from apps.sales.models import SalesOrder
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService

from .models import BOM, BOMLine, IoTDevice, IoTMetric, MOIssueLine, MOReceiptLine, ManufacturingOrder, ProductionPlan, ProductionQC


class ProductionDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.PRODUCTION

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    @staticmethod
    def _status_value(status):
        return getattr(status, "value", status)

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

    def _sales_order(self, *, company_id, sales_order_id) -> SalesOrder:
        sales_order = SalesOrder.objects.active().for_company(company_id).filter(id=sales_order_id).first()
        if sales_order is None:
            raise BusinessRuleError("Sales order not found in company scope")
        return sales_order

    def _mo(self, *, company_id, mo_id) -> ManufacturingOrder:
        mo = ManufacturingOrder.objects.active().for_company(company_id).filter(id=mo_id).first()
        if mo is None:
            raise BusinessRuleError("Manufacturing order not found in company scope")
        return mo

    def _validate_mto_alignment(self, *, mo: ManufacturingOrder):
        if mo.production_mode != ManufacturingOrder.ProductionMode.MAKE_TO_ORDER:
            return
        if not mo.sales_order_id:
            raise BusinessRuleError("MTO manufacturing order requires linked sales order")
        if not mo.sales_order.lines.filter(material_id=mo.product_material_id).exists():
            raise BusinessRuleError("MTO product material must exist in linked sales order lines")


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
    PERM_TRANSITION = PERMISSION_CODES.PRODUCTION_MO_TRANSITION

    DOC_TYPE = "production.manufacturing_order"

    def __init__(self):
        super().__init__()
        self.reservation_service = ReservationService()
        self.ledger_service = StockLedgerService()
        self.transition_service = DocumentStateTransitionService()
        self.transition_service.DEFAULT_TRANSITIONS = {
            DOC_STATUS.DRAFT: {
                DOC_STATUS.SUBMITTED: "production.mo.submit",
                DOC_STATUS.CANCELLED: "production.mo.cancel",
            },
            DOC_STATUS.SUBMITTED: {
                DOC_STATUS.CONFIRMED: "production.mo.confirm",
                DOC_STATUS.CANCELLED: "production.mo.cancel",
            },
            DOC_STATUS.CONFIRMED: {
                DOC_STATUS.COMPLETED: "production.mo.complete",
                DOC_STATUS.CANCELLED: "production.mo.cancel",
            },
            DOC_STATUS.COMPLETED: {
                DOC_STATUS.CANCELLED: "production.mo.cancel",
            },
            DOC_STATUS.CANCELLED: {},
        }

    @transaction.atomic
    def create_order(self, *, user, company_id, doc_no, product_material_id, planned_qty, warehouse_id, production_mode=ManufacturingOrder.ProductionMode.MAKE_TO_STOCK, sales_order_id=None, start_date=None, due_date=None, request=None) -> ManufacturingOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        sales_order = None
        if sales_order_id:
            sales_order = self._sales_order(company_id=company_id, sales_order_id=sales_order_id)

        order = ManufacturingOrder(
            company_id=company_id,
            doc_no=doc_no,
            product_material=self._material(company_id=company_id, material_id=product_material_id),
            planned_qty=planned_qty,
            warehouse=self._warehouse(company_id=company_id, warehouse_id=warehouse_id),
            production_mode=production_mode,
            sales_order=sales_order,
            start_date=start_date,
            due_date=due_date,
            status=self._status_value(DOC_STATUS.DRAFT),
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        self._validate_mto_alignment(mo=order)
        order.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type=self.DOC_TYPE, resource_id=order.id, request=request)
        return order

    @transaction.atomic
    def transition_order(self, *, user, company_id, order_id, to_state, notes="", request=None) -> ManufacturingOrder:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_TRANSITION)

        order = ManufacturingOrder.objects.active().for_company(company_id).filter(id=order_id).first()
        if order is None:
            raise BusinessRuleError("Manufacturing order not found in company scope")
        self._validate_mto_alignment(mo=order)

        return self.transition_service.transition(
            user=user,
            company_id=company_id,
            document=order,
            document_type=self.DOC_TYPE,
            to_state=self._status_value(to_state),
            notes=notes,
            request=request,
        )

    @staticmethod
    def _ensure_issue_allowed_state(*, mo: ManufacturingOrder):
        if mo.status in {DOC_STATUS.DRAFT.value, DOC_STATUS.CANCELLED.value, DOC_STATUS.COMPLETED.value}:
            raise BusinessRuleError("Manufacturing order status does not allow material issue")

    @staticmethod
    def _ensure_receipt_allowed_state(*, mo: ManufacturingOrder):
        if mo.status in {DOC_STATUS.DRAFT.value, DOC_STATUS.CANCELLED.value, DOC_STATUS.COMPLETED.value}:
            raise BusinessRuleError("Manufacturing order status does not allow finished goods receipt")

    @transaction.atomic
    def issue_material(self, *, user, company_id, mo_id, component_material_id, required_qty, issued_qty, reservation_id=None, request=None) -> MOIssueLine:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_ISSUE)

        mo = self._mo(company_id=company_id, mo_id=mo_id)
        self._validate_mto_alignment(mo=mo)
        self._ensure_issue_allowed_state(mo=mo)
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

        if mo.production_mode == ManufacturingOrder.ProductionMode.MAKE_TO_ORDER:
            if reservation is None:
                raise BusinessRuleError("MTO issue requires active reservation")
            if issued_qty != reservation.qty:
                raise BusinessRuleError("MTO issue requires issued_qty equal to reservation.qty")
        else:
            # MTS: reservation is optional; if present, must align with consume semantics.
            if reservation is not None and issued_qty != reservation.qty:
                raise BusinessRuleError("MTS issue with reservation requires issued_qty equal to reservation.qty")

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
        self._validate_mto_alignment(mo=mo)
        self._ensure_receipt_allowed_state(mo=mo)

        receipt = MOReceiptLine(
            company_id=company_id,
            mo=mo,
            product_material=mo.product_material,
            received_qty=received_qty,
            lot_id=lot_id,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
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


class ProductionPlanService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_PLAN_CREATE
    PERM_UPDATE = PERMISSION_CODES.PRODUCTION_PLAN_UPDATE

    @transaction.atomic
    def create_plan(self, *, user, company_id, plan_date, status=ProductionPlan.Status.DRAFT, capacity_json=None, mrp_result_json=None, request=None) -> ProductionPlan:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        plan = ProductionPlan(
            company_id=company_id,
            plan_date=plan_date,
            status=status,
            capacity_json=capacity_json or {},
            mrp_result_json=mrp_result_json or {},
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        plan.full_clean()
        plan.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.plan", resource_id=plan.id, request=request)
        return plan

    @transaction.atomic
    def update_plan(self, *, user, company_id, plan_id, capacity_json=None, mrp_result_json=None, status=None, request=None) -> ProductionPlan:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        plan = ProductionPlan.objects.active().for_company(company_id).filter(id=plan_id).first()
        if plan is None:
            raise BusinessRuleError("Production plan not found in company scope")

        if capacity_json is not None:
            plan.capacity_json = capacity_json
        if mrp_result_json is not None:
            plan.mrp_result_json = mrp_result_json
        if status is not None:
            plan.status = status
        plan.updated_by = self._user_id(user)
        plan.full_clean()
        plan.save()

        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="production.plan", resource_id=plan.id, request=request)
        return plan


class ProductionQCService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_QC_CREATE

    @transaction.atomic
    def create_qc_record(self, *, user, company_id, mo_id, stage, result, inspector_id, notes="", measurements_json=None, request=None) -> ProductionQC:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        mo = self._mo(company_id=company_id, mo_id=mo_id)
        if mo.status in {DOC_STATUS.CANCELLED.value, DOC_STATUS.COMPLETED.value}:
            raise BusinessRuleError("QC cannot be recorded for completed or cancelled manufacturing order")

        qc = ProductionQC(
            company_id=company_id,
            mo=mo,
            stage=stage,
            result=result,
            inspector_id=inspector_id,
            notes=notes,
            measurements_json=measurements_json or {},
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        qc.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.qc", resource_id=qc.id, request=request)
        return qc


class IoTDeviceService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_IOT_DEVICE_CREATE

    @transaction.atomic
    def register_device(self, *, user, company_id, device_code, name, type, status=IoTDevice.Status.ACTIVE, bound_mo_id=None, request=None) -> IoTDevice:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        device = IoTDevice(
            company_id=company_id,
            device_code=device_code,
            name=name,
            type=type,
            status=status,
            bound_mo=self._mo(company_id=company_id, mo_id=bound_mo_id) if bound_mo_id else None,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        device.full_clean()
        device.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.iot_device", resource_id=device.id, request=request)
        return device


class IoTMetricService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_IOT_METRIC_CREATE

    @transaction.atomic
    def record_metric(self, *, user, company_id, device_id, metric_key, value, recorded_at, request=None) -> IoTMetric:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        device = IoTDevice.objects.active().for_company(company_id).filter(id=device_id).first()
        if device is None:
            raise BusinessRuleError("IoT device not found in company scope")

        metric = IoTMetric(
            company_id=company_id,
            device=device,
            metric_key=metric_key,
            value=value,
            recorded_at=recorded_at,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        metric.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.iot_metric", resource_id=metric.id, request=request)
        return metric
