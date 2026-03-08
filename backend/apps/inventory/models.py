from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models

from apps.material.models import BinLocation, Material, UoM, Warehouse
from shared.models.base import BaseModel



class Lot(BaseModel):
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="lots")
    lot_code = models.CharField(max_length=80)
    mfg_date = models.DateField(null=True, blank=True)
    exp_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "inv_lot"
        unique_together = (("company_id", "material", "lot_code"),)

    def clean(self):
        errors = {}
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match lot company."
        if self.mfg_date and self.exp_date and self.exp_date < self.mfg_date:
            errors["exp_date"] = "Expiration date cannot be earlier than manufacturing date."
        if errors:
            raise DjangoValidationError(errors)


class Serial(BaseModel):
    class Status(models.TextChoices):
        IN_STOCK = "in_stock", "In Stock"
        SHIPPED = "shipped", "Shipped"
        SCRAPPED = "scrapped", "Scrapped"

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="serials")
    serial_code = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_STOCK)

    class Meta:
        db_table = "inv_serial"
        unique_together = (("company_id", "material", "serial_code"),)

    def clean(self):
        if self.material_id and self.material.company_id != self.company_id:
            raise DjangoValidationError({"material": "Material company must match serial company."})


class StockLedger(BaseModel):
    class MovementType(models.TextChoices):
        IN = "in", "In"
        OUT = "out", "Out"
        ADJUST = "adjust", "Adjust"
        TRANSFER_IN = "transfer_in", "Transfer In"
        TRANSFER_OUT = "transfer_out", "Transfer Out"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_ledger_entries")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="stock_ledger_entries")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    uom = models.ForeignKey(UoM, on_delete=models.PROTECT, related_name="stock_ledger_entries")
    lot = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.PROTECT, related_name="stock_ledger_entries")
    serial = models.ForeignKey(
        Serial,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_ledger_entries",
    )
    bin_location = models.ForeignKey(
        BinLocation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_ledger_entries",
    )
    ref_doc_type = models.CharField(max_length=64, blank=True)
    ref_doc_id = models.UUIDField(null=True, blank=True)
    cost_amount = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))

    class Meta:
        db_table = "inv_stock_ledger"

    def clean(self):
        errors = {}
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match ledger company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match ledger company."
        if self.uom_id and self.uom.company_id != self.company_id:
            errors["uom"] = "UoM company must match ledger company."
        if self.lot_id:
            if self.lot.company_id != self.company_id:
                errors["lot"] = "Lot company must match ledger company."
            elif self.lot.material_id != self.material_id:
                errors["lot"] = "Lot material must match ledger material."
        if self.serial_id:
            if self.serial.company_id != self.company_id:
                errors["serial"] = "Serial company must match ledger company."
            elif self.serial.material_id != self.material_id:
                errors["serial"] = "Serial material must match ledger material."
        if self.bin_location_id:
            if self.bin_location.company_id != self.company_id:
                errors["bin_location"] = "Bin company must match ledger company."
            elif self.bin_location.warehouse_id != self.warehouse_id:
                errors["bin_location"] = "Bin must belong to the ledger warehouse."
        if self.qty is not None and self.qty == 0:
            errors["qty"] = "Quantity cannot be zero."
        if errors:
            raise DjangoValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and StockLedger.objects.filter(pk=self.pk).exists():
            raise DjangoValidationError({"id": "StockLedger is append-only and cannot be updated."})
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise DjangoValidationError({"id": "StockLedger is append-only and cannot be deleted."})

    def soft_delete(self):
        raise DjangoValidationError({"id": "StockLedger is append-only and cannot be soft deleted."})


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


class Reservation(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RELEASED = "released", "Released"
        CONSUMED = "consumed", "Consumed"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="reservations")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="reservations")
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    ref_doc_type = models.CharField(max_length=64, blank=True)
    ref_doc_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "inv_reservation"

    def clean(self):
        errors = {}
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match reservation company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match reservation company."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "Reservation quantity must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)


class WarehouseTransfer(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SHIPPED = "shipped", "Shipped"
        RECEIVED = "received", "Received"

    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="outbound_transfers")
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="inbound_transfers")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    ship_date = models.DateField(null=True, blank=True)
    receive_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "inv_warehouse_transfer"

    def clean(self):
        errors = {}
        if self.from_warehouse_id and self.from_warehouse.company_id != self.company_id:
            errors["from_warehouse"] = "From warehouse company must match transfer company."
        if self.to_warehouse_id and self.to_warehouse.company_id != self.company_id:
            errors["to_warehouse"] = "To warehouse company must match transfer company."
        if self.from_warehouse_id and self.to_warehouse_id and self.from_warehouse_id == self.to_warehouse_id:
            errors["to_warehouse"] = "Destination warehouse must differ from source warehouse."
        if errors:
            raise DjangoValidationError(errors)


class WarehouseTransferLine(BaseModel):
    transfer = models.ForeignKey(WarehouseTransfer, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="transfer_lines")
    qty = models.DecimalField(max_digits=20, decimal_places=6)
    lot = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.PROTECT, related_name="transfer_lines")
    serial = models.ForeignKey(Serial, null=True, blank=True, on_delete=models.PROTECT, related_name="transfer_lines")

    class Meta:
        db_table = "inv_warehouse_transfer_line"

    def clean(self):
        errors = {}
        if self.transfer_id and self.transfer.company_id != self.company_id:
            errors["transfer"] = "Transfer company must match transfer line company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match transfer line company."
        if self.lot_id and (self.lot.company_id != self.company_id or self.lot.material_id != self.material_id):
            errors["lot"] = "Lot must match company and material."
        if self.serial_id and (self.serial.company_id != self.company_id or self.serial.material_id != self.material_id):
            errors["serial"] = "Serial must match company and material."
        if self.qty is not None and self.qty <= 0:
            errors["qty"] = "Transfer quantity must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)


class StockCount(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COUNTED = "counted", "Counted"
        POSTED = "posted", "Posted"

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_counts")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    count_date = models.DateField()

    class Meta:
        db_table = "inv_stock_count"

    def clean(self):
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            raise DjangoValidationError({"warehouse": "Warehouse company must match stock count company."})


class StockCountLine(BaseModel):
    count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="stock_count_lines")
    system_qty = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    counted_qty = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    diff_qty = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "inv_stock_count_line"

    def clean(self):
        errors = {}
        if self.count_id and self.count.company_id != self.company_id:
            errors["count"] = "Stock count company must match stock count line company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match stock count line company."
        if errors:
            raise DjangoValidationError(errors)

    def save(self, *args, **kwargs):
        self.diff_qty = self.counted_qty - self.system_qty
        super().save(*args, **kwargs)


class CostLayer(BaseModel):
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="cost_layers")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="cost_layers")
    in_qty = models.DecimalField(max_digits=20, decimal_places=6)
    remaining_qty = models.DecimalField(max_digits=20, decimal_places=6)
    unit_cost = models.DecimalField(max_digits=20, decimal_places=6)
    source_ledger = models.ForeignKey(StockLedger, on_delete=models.PROTECT, related_name="cost_layers")

    class Meta:
        db_table = "inv_cost_layer"

    def clean(self):
        errors = {}
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match cost layer company."
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            errors["warehouse"] = "Warehouse company must match cost layer company."
        if self.source_ledger_id and self.source_ledger.company_id != self.company_id:
            errors["source_ledger"] = "Ledger company must match cost layer company."
        if self.remaining_qty < 0:
            errors["remaining_qty"] = "Remaining quantity cannot be negative."
        if self.in_qty < 0:
            errors["in_qty"] = "In quantity cannot be negative."
        if self.remaining_qty > self.in_qty:
            errors["remaining_qty"] = "Remaining quantity cannot exceed layer in quantity."
        if errors:
            raise DjangoValidationError(errors)
