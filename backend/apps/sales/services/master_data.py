from decimal import Decimal
from django.db import models, transaction
from apps.inventory.models import Reservation, StockLedger
from apps.inventory.services import ReservationService, StockLedgerService
from apps.material.models import Material, Warehouse
from doc.services import DocumentStateTransitionService
from shared.constants.document import DOC_STATUS
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from .workflow import SalesDomainService
from ..models import (
    Customer,
    CustomerPriceList,
    PricingRule,
    RMA,
    RMALine,
    SalesOrder,
    SalesOrderLine,
    SalesQuote,
    SalesQuoteLine,
    Shipment,
    ShipmentLine,
)

class CustomerService(SalesDomainService):
    PERM_CREATE = PERMISSION_CODES.SALES_CUSTOMER_CREATE

    @transaction.atomic
    def create_customer(self, *, user, company_id, code, name, contact_json=None, credit_limit=Decimal("0"), notes="", request=None):
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        customer = Customer(
            company_id=company_id,
            code=code,
            name=name,
            contact_json=contact_json or {},
            credit_limit=credit_limit,
            notes=notes,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        customer.full_clean()
        customer.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.customer",
            resource_id=customer.id,
            request=request,
        )
        return customer

class PricingService(SalesDomainService):
    PERM_CREATE = PERMISSION_CODES.SALES_PRICING_CREATE

    @transaction.atomic
    def create_customer_price(
        self,
        *,
        user,
        company_id,
        customer_id,
        material_id,
        price,
        currency,
        valid_from,
        valid_to=None,
        request=None,
    ) -> CustomerPriceList:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        row = CustomerPriceList(
            company_id=company_id,
            customer=self._customer(company_id=company_id, customer_id=customer_id),
            material=self._material(company_id=company_id, material_id=material_id),
            price=price,
            currency=currency,
            valid_from=valid_from,
            valid_to=valid_to,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        row.full_clean()
        row.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.customer_price_list",
            resource_id=row.id,
            request=request,
        )
        return row

    @transaction.atomic
    def create_pricing_rule(self, *, user, company_id, name, rule_json=None, enabled=True, request=None) -> PricingRule:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        rule = PricingRule(
            company_id=company_id,
            name=name,
            rule_json=rule_json or {},
            enabled=enabled,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        rule.full_clean()
        rule.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="sales.pricing_rule",
            resource_id=rule.id,
            request=request,
        )
        return rule
