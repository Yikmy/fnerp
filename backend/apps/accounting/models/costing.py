from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone
from apps.material.models import Material
from apps.production.models import ManufacturingOrder
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder
from shared.models.base import BaseModel

class PeriodProductCost(BaseModel):
    period = models.CharField(max_length=7)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="period_product_costs")
    currency = models.CharField(max_length=8)
    total_in_qty = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    total_in_cost = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    ending_qty = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    ending_cost = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    layer_count = models.IntegerField(default=0)

    class Meta:
        db_table = "acct_period_product_cost"
        unique_together = (("company_id", "period", "material"),)

    def clean(self):
        errors = {}
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match period product cost company."
        if self.total_in_qty < 0:
            errors["total_in_qty"] = "Total in qty cannot be negative."
        if self.total_in_cost < 0:
            errors["total_in_cost"] = "Total in cost cannot be negative."
        if self.ending_qty < 0:
            errors["ending_qty"] = "Ending qty cannot be negative."
        if self.ending_cost < 0:
            errors["ending_cost"] = "Ending cost cannot be negative."
        if self.layer_count < 0:
            errors["layer_count"] = "Layer count cannot be negative."
        if errors:
            raise DjangoValidationError(errors)
