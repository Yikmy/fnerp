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
from ..models import (
    ContainerRecoveryLine,
    ContainerRecoveryPlan,
    FreightCharge,
    InsurancePolicy,
    ShipmentTrackingEvent,
    TransportOrder,
    TransportRecoveryLine,
)

class LogisticsDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.LOGISTICS

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("logistics module is disabled for this company")

    def _shipment(self, *, company_id, shipment_id) -> Shipment:
        shipment = Shipment.objects.active().for_company(company_id).filter(id=shipment_id).first()
        if shipment is None:
            raise BusinessRuleError("Shipment not found in company scope")
        return shipment

    def _sales_order(self, *, company_id, sales_order_id) -> SalesOrder:
        sales_order = SalesOrder.objects.active().for_company(company_id).filter(id=sales_order_id).first()
        if sales_order is None:
            raise BusinessRuleError("Sales order not found in company scope")
        return sales_order

    def _customer(self, *, company_id, customer_id) -> Customer:
        customer = Customer.objects.active().for_company(company_id).filter(id=customer_id, is_active=True).first()
        if customer is None:
            raise BusinessRuleError("Customer not found in company scope")
        return customer

    def _warehouse(self, *, company_id, warehouse_id) -> Warehouse:
        warehouse = Warehouse.objects.active().for_company(company_id).filter(id=warehouse_id, is_active=True).first()
        if warehouse is None:
            raise BusinessRuleError("Warehouse not found in company scope")
        return warehouse

    def _material(self, *, company_id, material_id) -> Material:
        material = Material.objects.active().for_company(company_id).filter(id=material_id, is_active=True).first()
        if material is None:
            raise BusinessRuleError("Material not found in company scope")
        return material

    def __init__(self):
        super().__init__()
        self.transition_service = DocumentStateTransitionService()
        self.ledger_service = StockLedgerService()
