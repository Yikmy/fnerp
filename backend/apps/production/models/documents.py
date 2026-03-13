from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Reservation
from apps.material.models import Material, Warehouse
from apps.sales.models import SalesOrder
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel

class ManufacturingOrder(BaseModel):
    class ProductionMode(models.TextChoices):
        MAKE_TO_STOCK = "mts", "Make To Stock"
        MAKE_TO_ORDER = "mto", "Make To Order"

    doc_no = models.CharField(max_length=64)
    product_material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="manufacturing_orders")
    planned_qty = models.DecimalField(max_digits=20, decimal_places=6)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="manufacturing_orders")
    production_mode = models.CharField(
        max_length=16,
        choices=ProductionMode.choices,
        default=ProductionMode.MAKE_TO_STOCK,
    )
    sales_order = models.ForeignKey(
        SalesOrder,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="manufacturing_orders",
    )
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=[(value.value, value.value) for value in DOC_STATUS], default=DOC_STATUS.DRAFT.value)

    class Meta:
        db_table = "prd_manufacturing_order"
        unique_together = (("company_id", "doc_no"),)

    def clean(self):
        errors = {}
        if self.product_material_id and self.product_material.company_id != self.company_id:
            errors["product_material"] = "Product material company must match manufacturing order company."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match manufacturing order company."
        if self.sales_order_id and self.sales_order.company_id != self.company_id:
            errors["sales_order"] = "Sales order company must match manufacturing order company."
        if self.production_mode == self.ProductionMode.MAKE_TO_ORDER:
            if not self.sales_order_id:
                errors["sales_order"] = "MTO manufacturing order requires sales_order."
            elif self.product_material_id and not self.sales_order.lines.filter(material_id=self.product_material_id).exists():
                errors["product_material"] = "MTO product material must exist in linked sales order lines."
        elif self.production_mode == self.ProductionMode.MAKE_TO_STOCK and self.sales_order_id:
            errors["sales_order"] = "MTS manufacturing order cannot link a sales_order."
        if self.planned_qty is not None and self.planned_qty <= 0:
            errors["planned_qty"] = "planned_qty must be greater than zero."
        if self.progress_percent is not None and (self.progress_percent < 0 or self.progress_percent > 100):
            errors["progress_percent"] = "progress_percent must be between 0 and 100."
        if self.start_date and self.due_date and self.due_date < self.start_date:
            errors["due_date"] = "due_date cannot be earlier than start_date."
        if errors:
            raise DjangoValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
