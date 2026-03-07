from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models

from shared.models.base import BaseModel


class UoM(BaseModel):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20)
    ratio_to_base = models.DecimalField(max_digits=20, decimal_places=8)

    class Meta:
        db_table = "md_uom"
        unique_together = (("company_id", "name"), ("company_id", "symbol"))

    def clean(self):
        if self.ratio_to_base is None or self.ratio_to_base <= Decimal("0"):
            raise DjangoValidationError({"ratio_to_base": "ratio_to_base must be greater than zero."})

    @property
    def is_base_unit(self) -> bool:
        return self.ratio_to_base == Decimal("1")


class MaterialCategory(BaseModel):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )

    class Meta:
        db_table = "md_material_category"
        unique_together = (("company_id", "name", "parent"),)

    def clean(self):
        if self.parent_id and self.parent.company_id != self.company_id:
            raise DjangoValidationError({"parent": "Parent category company must match."})


class Material(BaseModel):
    class TrackingType(models.TextChoices):
        NONE = "none", "None"
        LOT = "lot", "Lot"
        SERIAL = "serial", "Serial"

    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(MaterialCategory, on_delete=models.PROTECT, related_name="materials")
    uom = models.ForeignKey(UoM, on_delete=models.PROTECT, related_name="materials")
    spec = models.TextField(blank=True)
    tracking = models.CharField(max_length=16, choices=TrackingType.choices, default=TrackingType.NONE)
    is_container = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "md_material"
        unique_together = (("company_id", "code"),)

    def clean(self):
        errors = {}
        if self.category_id and self.category.company_id != self.company_id:
            errors["category"] = "Category company must match material company."
        if self.uom_id and self.uom.company_id != self.company_id:
            errors["uom"] = "UoM company must match material company."
        if errors:
            raise DjangoValidationError(errors)


class Warehouse(BaseModel):
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "md_warehouse"
        unique_together = (("company_id", "code"),)


class WarehouseZone(BaseModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="zones")
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)

    class Meta:
        db_table = "md_warehouse_zone"
        unique_together = (("company_id", "warehouse", "code"),)

    def clean(self):
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            raise DjangoValidationError({"warehouse": "Warehouse company must match zone company."})


class BinLocation(BaseModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="bins")
    zone = models.ForeignKey(
        WarehouseZone,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bins",
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)

    class Meta:
        db_table = "md_bin_location"
        unique_together = (("company_id", "warehouse", "code"),)

    def clean(self):
        errors = {}
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match bin company."
        if self.zone_id:
            if self.zone.company_id != self.company_id:
                errors["zone"] = "Zone company must match bin company."
            elif self.zone.warehouse_id != self.warehouse_id:
                errors["zone"] = "Zone must belong to the same warehouse as the bin."
        if errors:
            raise DjangoValidationError(errors)
