from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Reservation
from apps.material.models import Material, Warehouse
from apps.sales.models import SalesOrder
from shared.constants.document import DOC_STATUS
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
