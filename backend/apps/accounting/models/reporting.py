from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils import timezone
from apps.material.models import Material
from apps.production.models import ManufacturingOrder
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder
from shared.models.base import BaseModel

class FinancialReportSnapshot(BaseModel):
    class ReportType(models.TextChoices):
        BS = "BS", "Balance Sheet"
        PL = "PL", "Profit and Loss"
        CF = "CF", "Cash Flow"

    period = models.CharField(max_length=32)
    report_type = models.CharField(max_length=8, choices=ReportType.choices)
    payload_json = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "acct_financial_report_snapshot"
        unique_together = (("company_id", "period", "report_type"),)
