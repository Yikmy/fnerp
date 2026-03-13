from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from apps.inventory.models import Lot, Reservation
from apps.material.models import Material, Warehouse
from apps.sales.models import SalesOrder
from shared.constants.document import DOC_STATUS
from shared.models.base import BaseModel

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
