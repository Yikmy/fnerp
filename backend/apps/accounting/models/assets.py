from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone
from apps.material.models import Material
from apps.production.models import ManufacturingOrder
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder
from shared.models.base import BaseModel

class FixedAsset(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISPOSED = "disposed", "Disposed"

    asset_code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=20, decimal_places=6)
    depreciation_method = models.CharField(max_length=32)
    useful_life_months = models.IntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    source_purchase_order = models.ForeignKey(
        PurchaseOrder,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fixed_assets",
    )

    class Meta:
        db_table = "acct_fixed_asset"
        unique_together = (("company_id", "asset_code"),)

    def clean(self):
        errors = {}
        if self.source_purchase_order_id and self.source_purchase_order.company_id != self.company_id:
            errors["source_purchase_order"] = "Purchase order company must match fixed asset company."
        if self.purchase_cost is not None and self.purchase_cost < 0:
            errors["purchase_cost"] = "Purchase cost cannot be negative."
        if self.useful_life_months is not None and self.useful_life_months <= 0:
            errors["useful_life_months"] = "Useful life must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)

class AssetMaintenance(BaseModel):
    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name="maintenances")
    date = models.DateField()
    content = models.TextField()
    cost = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        db_table = "acct_asset_maintenance"

    def clean(self):
        errors = {}
        if self.asset_id and self.asset.company_id != self.company_id:
            errors["asset"] = "Asset company must match maintenance company."
        if self.cost is not None and self.cost < 0:
            errors["cost"] = "Cost cannot be negative."
        if errors:
            raise DjangoValidationError(errors)
