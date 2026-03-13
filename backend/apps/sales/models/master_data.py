from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Serial
from apps.material.models import Material, Warehouse
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel

class Customer(BaseModel):
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    contact_json = models.JSONField(default=dict, blank=True)
    credit_limit = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sal_customer"
        unique_together = (("company_id", "code"),)

    def clean(self):
        if self.credit_limit is not None and self.credit_limit < 0:
            raise DjangoValidationError({"credit_limit": "credit_limit cannot be negative."})

class CustomerPriceList(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="price_list_entries")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="customer_price_list_entries")
    price = models.DecimalField(max_digits=20, decimal_places=6)
    currency = models.CharField(max_length=8)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "sal_customer_price_list"

    def clean(self):
        errors = {}
        if self.customer_id and self.customer.company_id != self.company_id:
            errors["customer"] = "Customer company must match price list company."
        if self.material_id and self.material.company_id != self.company_id:
            errors["material"] = "Material company must match price list company."
        if self.price is not None and self.price < 0:
            errors["price"] = "price cannot be negative."
        if self.valid_to and self.valid_from and self.valid_to < self.valid_from:
            errors["valid_to"] = "valid_to cannot be earlier than valid_from."
        if errors:
            raise DjangoValidationError(errors)

class PricingRule(BaseModel):
    name = models.CharField(max_length=120)
    rule_json = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "sal_pricing_rule"
        unique_together = (("company_id", "name"),)
