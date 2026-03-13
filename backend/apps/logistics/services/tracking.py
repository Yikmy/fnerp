from django.db import transaction
from apps.inventory.models import StockLedger
from apps.inventory.services import StockLedgerService
from apps.material.models import Material, Warehouse
from apps.sales.models import Customer, SalesOrder, Shipment
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from .workflow import LogisticsDomainService
from ..models import (
    ContainerRecoveryLine,
    ContainerRecoveryPlan,
    FreightCharge,
    InsurancePolicy,
    ShipmentTrackingEvent,
    TransportOrder,
    TransportRecoveryLine,
)

class ShipmentTrackingService(LogisticsDomainService):
    PERM_CREATE = PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_CREATE
    PERM_UPDATE = PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_UPDATE
    PERM_CANCEL = PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_CANCEL

    @transaction.atomic
    def create_tracking_event(self, *, user, company_id, shipment_id, status, event_time, location="", note="", request=None) -> ShipmentTrackingEvent:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        row = ShipmentTrackingEvent(
            company_id=company_id,
            shipment=self._shipment(company_id=company_id, shipment_id=shipment_id),
            status=status,
            location=location,
            note=note,
            event_time=event_time,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        row.full_clean()
        row.save()

        self.audit_crud(user=user, company_id=company_id, operation="create", resource_type="logistics.shipment_tracking_event", resource_id=row.id, request=request)
        return row

    @transaction.atomic
    def update_tracking_event(self, *, user, company_id, event_id, status=None, location=None, note=None, event_time=None, request=None) -> ShipmentTrackingEvent:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_UPDATE)

        row = ShipmentTrackingEvent.objects.active().for_company(company_id).filter(id=event_id).first()
        if row is None:
            raise BusinessRuleError("Shipment tracking event not found in company scope")

        for field, value in {"status": status, "location": location, "note": note, "event_time": event_time}.items():
            if value is not None:
                setattr(row, field, value)
        row.updated_by = self._user_id(user)
        row.full_clean()
        row.save()
        self.audit_crud(user=user, company_id=company_id, operation="update", resource_type="logistics.shipment_tracking_event", resource_id=row.id, request=request)
        return row

    @transaction.atomic
    def cancel_tracking_event(self, *, user, company_id, event_id, request=None) -> ShipmentTrackingEvent:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CANCEL)

        row = ShipmentTrackingEvent.objects.active().for_company(company_id).filter(id=event_id).first()
        if row is None:
            raise BusinessRuleError("Shipment tracking event not found in company scope")

        row.soft_delete()
        self.audit_crud(user=user, company_id=company_id, operation="delete", resource_type="logistics.shipment_tracking_event", resource_id=row.id, request=request)
        return row
