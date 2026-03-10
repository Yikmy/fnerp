from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models

from apps.inventory.models import Lot, Reservation
from apps.material.models import Material, Warehouse
from shared.models.base import BaseModel


class BOM(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    product_material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="production_boms")
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "prd_bom"
        unique_together = (("company_id", "product_material", "version"),)

    def clean(self):
        errors = {}
        if self.product_material_id and self.product_material.company_id != self.company_id:
            errors["product_material"] = "Product material company must match BOM company."
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "effective_to cannot be earlier than effective_from."
        if errors:
            raise DjangoValidationError(errors)


class BOMLine(BaseModel):
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name="lines")
    component_material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="bom_component_lines")
    qty_per_unit = models.DecimalField(max_digits=20, decimal_places=6)
    scrap_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    component_bom = models.ForeignKey(
        BOM,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="used_as_subassembly_lines",
    )

    class Meta:
        db_table = "prd_bom_line"

    def clean(self):
        errors = {}
        if self.bom_id and self.bom.company_id != self.company_id:
            errors["bom"] = "BOM company must match BOM line company."
        if self.component_material_id and self.component_material.company_id != self.company_id:
            errors["component_material"] = "Component material company must match BOM line company."
        if self.qty_per_unit is not None and self.qty_per_unit <= 0:
            errors["qty_per_unit"] = "qty_per_unit must be greater than zero."
        if self.scrap_rate is not None and (self.scrap_rate < 0 or self.scrap_rate >= 1):
            errors["scrap_rate"] = "scrap_rate must be between 0 and less than 1."
        if self.component_bom_id:
            if self.component_bom.company_id != self.company_id:
                errors["component_bom"] = "component_bom company must match BOM line company."
            elif self.component_bom.product_material_id != self.component_material_id:
                errors["component_bom"] = "component_bom product must match component material."
        if errors:
            raise DjangoValidationError(errors)


class ProductionPlan(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PLANNED = "planned", "Planned"
        APPROVED = "approved", "Approved"

    plan_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    capacity_json = models.JSONField(default=dict, blank=True)
    mrp_result_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "prd_production_plan"


class ManufacturingOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        RELEASED = "released", "Released"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    doc_no = models.CharField(max_length=64)
    product_material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="manufacturing_orders")
    planned_qty = models.DecimalField(max_digits=20, decimal_places=6)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="manufacturing_orders")
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        db_table = "prd_manufacturing_order"
        unique_together = (("company_id", "doc_no"),)

    def clean(self):
        errors = {}
        if self.product_material_id and self.product_material.company_id != self.company_id:
            errors["product_material"] = "Product material company must match manufacturing order company."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match manufacturing order company."
        if self.planned_qty is not None and self.planned_qty <= 0:
            errors["planned_qty"] = "planned_qty must be greater than zero."
        if self.progress_percent is not None and (self.progress_percent < 0 or self.progress_percent > 100):
            errors["progress_percent"] = "progress_percent must be between 0 and 100."
        if self.start_date and self.due_date and self.due_date < self.start_date:
            errors["due_date"] = "due_date cannot be earlier than start_date."
        if errors:
            raise DjangoValidationError(errors)


class MOIssueLine(BaseModel):
    mo = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE, related_name="issue_lines")
    component_material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="mo_issue_lines")
    required_qty = models.DecimalField(max_digits=20, decimal_places=6)
    issued_qty = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    reservation = models.ForeignKey(Reservation, null=True, blank=True, on_delete=models.PROTECT, related_name="mo_issue_lines")

    class Meta:
        db_table = "prd_mo_issue_line"

    def clean(self):
        errors = {}
        if self.mo_id and self.mo.company_id != self.company_id:
            errors["mo"] = "Manufacturing order company must match issue line company."
        if self.component_material_id and self.component_material.company_id != self.company_id:
            errors["component_material"] = "Component material company must match issue line company."
        if self.reservation_id:
            if self.reservation.company_id != self.company_id:
                errors["reservation"] = "Reservation company must match issue line company."
            if self.reservation.material_id != self.component_material_id:
                errors["reservation"] = "Reservation material must match component material."
            if self.reservation.warehouse_id != self.mo.warehouse_id:
                errors["reservation"] = "Reservation warehouse must match MO warehouse."
        if self.required_qty is not None and self.required_qty <= 0:
            errors["required_qty"] = "required_qty must be greater than zero."
        if self.issued_qty is not None and self.issued_qty < 0:
            errors["issued_qty"] = "issued_qty cannot be negative."
        if self.issued_qty is not None and self.required_qty is not None and self.issued_qty > self.required_qty:
            errors["issued_qty"] = "issued_qty cannot exceed required_qty."
        if errors:
            raise DjangoValidationError(errors)


class MOReceiptLine(BaseModel):
    mo = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE, related_name="receipt_lines")
    product_material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="mo_receipt_lines")
    received_qty = models.DecimalField(max_digits=20, decimal_places=6)
    lot = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.PROTECT, related_name="mo_receipt_lines")

    class Meta:
        db_table = "prd_mo_receipt_line"

    def clean(self):
        errors = {}
        if self.mo_id and self.mo.company_id != self.company_id:
            errors["mo"] = "Manufacturing order company must match receipt line company."
        if self.product_material_id and self.product_material.company_id != self.company_id:
            errors["product_material"] = "Product material company must match receipt line company."
        if self.mo_id and self.product_material_id and self.mo.product_material_id != self.product_material_id:
            errors["product_material"] = "Receipt product material must match MO product material."
        if self.lot_id:
            if self.lot.company_id != self.company_id:
                errors["lot"] = "Lot company must match receipt line company."
            if self.lot.material_id != self.product_material_id:
                errors["lot"] = "Lot material must match product material."
        if self.received_qty is not None and self.received_qty <= 0:
            errors["received_qty"] = "received_qty must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)


class ProductionQC(BaseModel):
    class Stage(models.TextChoices):
        IPQC = "ipqc", "IPQC"
        FQC = "fqc", "FQC"

    class Result(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        HOLD = "hold", "Hold"

    mo = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE, related_name="qc_records")
    stage = models.CharField(max_length=16, choices=Stage.choices)
    result = models.CharField(max_length=16, choices=Result.choices)
    inspector_id = models.UUIDField()
    notes = models.TextField(blank=True)
    measurements_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "prd_production_qc"

    def clean(self):
        if self.mo_id and self.mo.company_id != self.company_id:
            raise DjangoValidationError({"mo": "Manufacturing order company must match QC record company."})


class IoTDevice(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        MAINTENANCE = "maintenance", "Maintenance"

    device_code = models.CharField(max_length=64)
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    bound_mo = models.ForeignKey(ManufacturingOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="iot_devices")

    class Meta:
        db_table = "prd_iot_device"
        unique_together = (("company_id", "device_code"),)

    def clean(self):
        if self.bound_mo_id and self.bound_mo.company_id != self.company_id:
            raise DjangoValidationError({"bound_mo": "Manufacturing order company must match IoT device company."})


class IoTMetric(BaseModel):
    device = models.ForeignKey(IoTDevice, on_delete=models.CASCADE, related_name="metrics")
    metric_key = models.CharField(max_length=64)
    value = models.DecimalField(max_digits=20, decimal_places=6)
    recorded_at = models.DateTimeField()

    class Meta:
        db_table = "prd_iot_metric"

    def clean(self):
        if self.device_id and self.device.company_id != self.company_id:
            raise DjangoValidationError({"device": "Device company must match metric company."})
