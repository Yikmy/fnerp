from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.material.models import Material, Warehouse
from apps.sales.models import Customer, SalesOrder, Shipment
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel

class InsurancePolicy(BaseModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.PROTECT, related_name="insurance_policies")
    provider = models.CharField(max_length=255)
    policy_no = models.CharField(max_length=120)
    insured_amount = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    premium = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))

    class Meta:
        db_table = "log_insurance_policy"
        unique_together = (("company_id", "policy_no"),)

    def clean(self):
        errors = {}
        if self.shipment_id and self.shipment.company_id != self.company_id:
            errors["shipment"] = "Shipment company must match insurance policy company."
        if self.insured_amount is not None and self.insured_amount <= 0:
            errors["insured_amount"] = "insured_amount must be greater than zero."
        if self.premium is not None and self.premium <= 0:
            errors["premium"] = "premium must be greater than zero."
        if errors:
            raise DjangoValidationError(errors)
