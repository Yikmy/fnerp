from decimal import Decimal
from django.db import transaction
from apps.inventory.models import Reservation, StockLedger
from apps.inventory.services import ReservationService, StockLedgerService
from apps.material.models import Material, Warehouse
from apps.sales.models import SalesOrder
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from ..models import BOM, BOMLine, IoTDevice, IoTMetric, MOIssueLine, MOReceiptLine, ManufacturingOrder, ProductionPlan, ProductionQC
from .workflow import ProductionDomainService

class IoTDeviceService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_IOT_DEVICE_CREATE

    @transaction.atomic
    def register_device(self, *, user, company_id, device_code, name, type, status=IoTDevice.Status.ACTIVE, bound_mo_id=None, request=None) -> IoTDevice:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        device = IoTDevice(
            company_id=company_id,
            device_code=device_code,
            name=name,
            type=type,
            status=status,
            bound_mo=self._mo(company_id=company_id, mo_id=bound_mo_id) if bound_mo_id else None,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        device.full_clean()
        device.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.iot_device", resource_id=device.id, request=request)
        return device

class IoTMetricService(ProductionDomainService):
    PERM_CREATE = PERMISSION_CODES.PRODUCTION_IOT_METRIC_CREATE

    @transaction.atomic
    def record_metric(self, *, user, company_id, device_id, metric_key, value, recorded_at, request=None) -> IoTMetric:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        device = IoTDevice.objects.active().for_company(company_id).filter(id=device_id).first()
        if device is None:
            raise BusinessRuleError("IoT device not found in company scope")

        metric = IoTMetric(
            company_id=company_id,
            device=device,
            metric_key=metric_key,
            value=value,
            recorded_at=recorded_at,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        metric.save()
        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="production.iot_metric", resource_id=metric.id, request=request)
        return metric
