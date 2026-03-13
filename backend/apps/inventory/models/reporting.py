from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.material.models import BinLocation, Material, UoM, Warehouse
from shared.models.base import BaseModel
from .transactions import Lot, Serial

class StockBalance(BaseModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_balances")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="stock_balances")
    on_hand_qty = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    reserved_qty = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    available_qty = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    lot = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.PROTECT, related_name="stock_balances")
    serial = models.ForeignKey(Serial, null=True, blank=True, on_delete=models.PROTECT, related_name="stock_balances")

    class Meta:
        db_table = "inv_stock_balance"
        unique_together = (("company_id", "warehouse", "material", "lot", "serial"),)

    def clean(self):
        errors = {}
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match stock balance company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match stock balance company."
        if self.lot_id:
            if self.lot.company_id != self.company_id:
                errors["lot"] = "Lot company must match stock balance company."
            elif self.lot.material_id != self.material_id:
                errors["lot"] = "Lot material must match stock balance material."
        if self.serial_id:
            if self.serial.company_id != self.company_id:
                errors["serial"] = "Serial company must match stock balance company."
            elif self.serial.material_id != self.material_id:
                errors["serial"] = "Serial material must match stock balance material."
        if self.on_hand_qty < 0:
            errors["on_hand_qty"] = "On-hand quantity cannot be negative."
        if self.reserved_qty < 0:
            errors["reserved_qty"] = "Reserved quantity cannot be negative."
        if self.reserved_qty > self.on_hand_qty:
            errors["reserved_qty"] = "Reserved quantity cannot exceed on-hand quantity."
        if errors:
            raise DjangoValidationError(errors)

    def save(self, *args, **kwargs):
        self.available_qty = self.on_hand_qty - self.reserved_qty
        super().save(*args, **kwargs)
