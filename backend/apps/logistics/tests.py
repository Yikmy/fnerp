from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.logistics.models import FreightCharge, InsurancePolicy, ShipmentTrackingEvent, TransportOrder
from apps.logistics.services import (
    ContainerRecoveryService,
    FreightChargeService,
    InsurancePolicyService,
    ShipmentTrackingService,
    TransportOrderService,
)
from apps.material.models import Material, MaterialCategory, UoM, Warehouse
from apps.sales.models import Customer, SalesOrder, Shipment
from company.models import Company, CompanyMembership, CompanyModule
from rbac.models import Permission, Role, RolePermission
from shared.constants.permissions import PERMISSION_CODES


class LogisticsStep6Tests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="log_user", password="pwd")

        self.company = Company.objects.create(name="Logistics Co")
        for module in ["material", "sales", "logistics"]:
            CompanyModule.objects.create(company=self.company, module_code=module, is_enabled=True)

        role = Role.objects.create(code="log-role", name="Log Role")
        perms = [
            PERMISSION_CODES.LOGISTICS_TRANSPORT_ORDER_CREATE,
            PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_CREATE,
            PERMISSION_CODES.LOGISTICS_CONTAINER_RECOVERY_CREATE,
            PERMISSION_CODES.LOGISTICS_FREIGHT_CHARGE_CREATE,
            PERMISSION_CODES.LOGISTICS_INSURANCE_POLICY_CREATE,
        ]
        for code in perms:
            perm = Permission.objects.create(code=code, name=code)
            RolePermission.objects.create(role=role, permission=perm)

        CompanyMembership.objects.create(user=self.user, company=self.company, role=role, is_active=True)

        self.uom = UoM.objects.create(company_id=self.company.id, name="EA", symbol="ea", ratio_to_base=Decimal("1"))
        self.category = MaterialCategory.objects.create(company_id=self.company.id, name="Containers")
        self.material = Material.objects.create(
            company_id=self.company.id,
            code="BOX-1",
            name="Returnable Box",
            category=self.category,
            uom=self.uom,
        )
        self.warehouse = Warehouse.objects.create(company_id=self.company.id, code="WH1", name="Main")
        self.customer = Customer.objects.create(company_id=self.company.id, code="C1", name="Customer 1")
        self.order = SalesOrder.objects.create(company_id=self.company.id, doc_no="SO1", customer=self.customer)
        self.shipment = Shipment.objects.create(
            company_id=self.company.id,
            doc_no="SHP1",
            so=self.order,
            customer=self.customer,
            warehouse=self.warehouse,
            ship_date="2026-03-09",
        )

    def test_create_transport_tracking_charge_policy_and_recovery(self):
        to = TransportOrderService().create_transport_order(
            user=self.user,
            company_id=self.company.id,
            shipment_id=self.shipment.id,
            carrier="Carrier A",
            vehicle_no="AB-123",
            driver_name="Driver",
            driver_contact="123",
        )
        event = ShipmentTrackingService().create_tracking_event(
            user=self.user,
            company_id=self.company.id,
            shipment_id=self.shipment.id,
            status="picked_up",
            location="Dock 1",
            note="Loaded",
            event_time=timezone.now(),
        )
        charge = FreightChargeService().create_freight_charge(
            user=self.user,
            company_id=self.company.id,
            shipment_id=self.shipment.id,
            calc_method="manual",
            amount=Decimal("100.50"),
            currency="USD",
        )
        policy = InsurancePolicyService().create_policy(
            user=self.user,
            company_id=self.company.id,
            shipment_id=self.shipment.id,
            provider="InsureCo",
            policy_no="POL-1",
            insured_amount=Decimal("1000"),
            premium=Decimal("10"),
        )
        plan = ContainerRecoveryService().create_plan(
            user=self.user,
            company_id=self.company.id,
            customer_id=self.customer.id,
            lines=[{"container_material_id": self.material.id, "qty": Decimal("5")}],
        )

        self.assertIsInstance(to, TransportOrder)
        self.assertIsInstance(event, ShipmentTrackingEvent)
        self.assertIsInstance(charge, FreightCharge)
        self.assertIsInstance(policy, InsurancePolicy)
        self.assertEqual(plan.lines.count(), 1)
