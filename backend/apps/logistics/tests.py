from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone

from apps.logistics.models import FreightCharge, InsurancePolicy, ShipmentTrackingEvent
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
from doc.models import DocumentStateMachineDef, DocumentTransitionLog
from rbac.models import Permission, Role, RolePermission
from shared.constants.document import DOC_STATUS
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError, PermissionDeniedError, ValidationError


class LogisticsStep6Tests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="log_user", password="pwd")
        self.no_perm_user = user_model.objects.create_user(username="log_user_no_perm", password="pwd")

        self.company = Company.objects.create(name="Logistics Co")
        self.other_company = Company.objects.create(name="Other Co")
        for module in ["material", "sales", "logistics"]:
            CompanyModule.objects.create(company=self.company, module_code=module, is_enabled=True)
            CompanyModule.objects.create(company=self.other_company, module_code=module, is_enabled=True)

        role = Role.objects.create(code="log-role", name="Log Role")
        perms = [
            PERMISSION_CODES.LOGISTICS_TRANSPORT_ORDER_CREATE,
            PERMISSION_CODES.LOGISTICS_TRANSPORT_ORDER_UPDATE,
            PERMISSION_CODES.LOGISTICS_TRANSPORT_ORDER_CANCEL,
            PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_CREATE,
            PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_UPDATE,
            PERMISSION_CODES.LOGISTICS_SHIPMENT_TRACKING_CANCEL,
            PERMISSION_CODES.LOGISTICS_CONTAINER_RECOVERY_CREATE,
            PERMISSION_CODES.LOGISTICS_CONTAINER_RECOVERY_UPDATE,
            PERMISSION_CODES.LOGISTICS_CONTAINER_RECOVERY_CANCEL,
            PERMISSION_CODES.LOGISTICS_FREIGHT_CHARGE_CREATE,
            PERMISSION_CODES.LOGISTICS_FREIGHT_CHARGE_UPDATE,
            PERMISSION_CODES.LOGISTICS_FREIGHT_CHARGE_CANCEL,
            PERMISSION_CODES.LOGISTICS_INSURANCE_POLICY_CREATE,
            PERMISSION_CODES.LOGISTICS_INSURANCE_POLICY_UPDATE,
            PERMISSION_CODES.LOGISTICS_INSURANCE_POLICY_CANCEL,
            "logistics.transport_order.submit_state",
            "logistics.transport_order.confirm_state",
            "logistics.transport_order.complete_state",
            "logistics.transport_order.cancel_state",
            "logistics.transport_order.cancel_completed_state",
            "logistics.container_recovery_plan.submit_state",
            "logistics.container_recovery_plan.confirm_state",
            "logistics.container_recovery_plan.complete_state",
            "logistics.container_recovery_plan.cancel_state",
            "logistics.container_recovery_plan.cancel_completed_state",
        ]
        for code in perms:
            perm = Permission.objects.create(code=code, name=code)
            RolePermission.objects.create(role=role, permission=perm)

        CompanyMembership.objects.create(user=self.user, company=self.company, role=role, is_active=True)
        CompanyMembership.objects.create(user=self.no_perm_user, company=self.company, is_active=True)

        self._seed_document_transitions()

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

        other_uom = UoM.objects.create(company_id=self.other_company.id, name="EA2", symbol="ea2", ratio_to_base=Decimal("1"))
        other_category = MaterialCategory.objects.create(company_id=self.other_company.id, name="Other")
        self.other_material = Material.objects.create(
            company_id=self.other_company.id,
            code="BOX-O",
            name="Other Box",
            category=other_category,
            uom=other_uom,
        )
        other_wh = Warehouse.objects.create(company_id=self.other_company.id, code="WH2", name="WH2")
        self.other_customer = Customer.objects.create(company_id=self.other_company.id, code="C2", name="Customer 2")
        self.other_order = SalesOrder.objects.create(company_id=self.other_company.id, doc_no="SO2", customer=self.other_customer)
        self.other_shipment = Shipment.objects.create(
            company_id=self.other_company.id,
            doc_no="SHP2",
            so=self.other_order,
            customer=self.other_customer,
            warehouse=other_wh,
            ship_date="2026-03-09",
        )

    def _seed_document_transitions(self):
        transition_specs = {
            "logistics.transport_order": [
                (DOC_STATUS.DRAFT, DOC_STATUS.SUBMITTED, "logistics.transport_order.submit_state"),
                (DOC_STATUS.SUBMITTED, DOC_STATUS.CONFIRMED, "logistics.transport_order.confirm_state"),
                (DOC_STATUS.CONFIRMED, DOC_STATUS.COMPLETED, "logistics.transport_order.complete_state"),
                (DOC_STATUS.DRAFT, DOC_STATUS.CANCELLED, "logistics.transport_order.cancel_state"),
                (DOC_STATUS.SUBMITTED, DOC_STATUS.CANCELLED, "logistics.transport_order.cancel_state"),
                (DOC_STATUS.CONFIRMED, DOC_STATUS.CANCELLED, "logistics.transport_order.cancel_state"),
                (DOC_STATUS.COMPLETED, DOC_STATUS.CANCELLED, "logistics.transport_order.cancel_completed_state"),
            ],
            "logistics.container_recovery_plan": [
                (DOC_STATUS.DRAFT, DOC_STATUS.SUBMITTED, "logistics.container_recovery_plan.submit_state"),
                (DOC_STATUS.SUBMITTED, DOC_STATUS.CONFIRMED, "logistics.container_recovery_plan.confirm_state"),
                (DOC_STATUS.CONFIRMED, DOC_STATUS.COMPLETED, "logistics.container_recovery_plan.complete_state"),
                (DOC_STATUS.DRAFT, DOC_STATUS.CANCELLED, "logistics.container_recovery_plan.cancel_state"),
                (DOC_STATUS.SUBMITTED, DOC_STATUS.CANCELLED, "logistics.container_recovery_plan.cancel_state"),
                (DOC_STATUS.CONFIRMED, DOC_STATUS.CANCELLED, "logistics.container_recovery_plan.cancel_state"),
                (DOC_STATUS.COMPLETED, DOC_STATUS.CANCELLED, "logistics.container_recovery_plan.cancel_completed_state"),
            ],
        }
        for document_type, transitions in transition_specs.items():
            for from_state, to_state, permission_code in transitions:
                DocumentStateMachineDef.objects.create(
                    document_type=document_type,
                    from_state=from_state,
                    to_state=to_state,
                    permission_code=permission_code,
                    is_active=True,
                )

    def test_transport_order_create_update_transition_and_sales_link(self):
        svc = TransportOrderService()
        row = svc.create_transport_order(
            user=self.user,
            company_id=self.company.id,
            shipment_id=self.shipment.id,
            sales_order_id=self.order.id,
            carrier="Carrier A",
        )
        self.assertEqual(row.sales_order_id, self.order.id)

        row = svc.update_transport_order(user=self.user, company_id=self.company.id, transport_order_id=row.id, vehicle_no="AB-123")
        self.assertEqual(row.vehicle_no, "AB-123")

        row = svc.transition_transport_order(user=self.user, company_id=self.company.id, transport_order_id=row.id, to_status=DOC_STATUS.SUBMITTED)
        row = svc.transition_transport_order(user=self.user, company_id=self.company.id, transport_order_id=row.id, to_status=DOC_STATUS.CONFIRMED)
        row = svc.transition_transport_order(user=self.user, company_id=self.company.id, transport_order_id=row.id, to_status=DOC_STATUS.COMPLETED)
        self.assertEqual(row.status, DOC_STATUS.COMPLETED)

        self.assertTrue(
            DocumentTransitionLog.objects.filter(
                company_id=self.company.id,
                document_type="logistics.transport_order",
                document_id=row.id,
            ).exists()
        )

    def test_invalid_transition_and_invalid_dates_rejected(self):
        svc = TransportOrderService()
        with self.assertRaises(DjangoValidationError):
            svc.create_transport_order(
                user=self.user,
                company_id=self.company.id,
                shipment_id=self.shipment.id,
                carrier="Carrier A",
                planned_departure=timezone.now(),
                planned_arrival=timezone.now() - timedelta(hours=1),
            )

        row = svc.create_transport_order(user=self.user, company_id=self.company.id, shipment_id=self.shipment.id, carrier="Carrier A")
        with self.assertRaises(ValidationError):
            svc.transition_transport_order(
                user=self.user,
                company_id=self.company.id,
                transport_order_id=row.id,
                to_status=DOC_STATUS.COMPLETED,
            )

    def test_permission_denied_for_update_and_transition(self):
        svc = TransportOrderService()
        row = svc.create_transport_order(user=self.user, company_id=self.company.id, shipment_id=self.shipment.id, carrier="Carrier A")

        with self.assertRaises(PermissionDeniedError):
            svc.update_transport_order(user=self.no_perm_user, company_id=self.company.id, transport_order_id=row.id, vehicle_no="X")
        with self.assertRaises(PermissionDeniedError):
            svc.transition_transport_order(user=self.no_perm_user, company_id=self.company.id, transport_order_id=row.id, to_status=DOC_STATUS.CANCELLED)

    def test_company_scope_enforced(self):
        with self.assertRaises(BusinessRuleError):
            TransportOrderService().create_transport_order(
                user=self.user,
                company_id=self.company.id,
                shipment_id=self.other_shipment.id,
                carrier="X",
            )
        with self.assertRaises(BusinessRuleError):
            ContainerRecoveryService().create_plan(
                user=self.user,
                company_id=self.company.id,
                customer_id=self.customer.id,
                lines=[{"container_material_id": self.other_material.id, "qty": Decimal("1")}],
            )

    def test_module_disabled_rejected(self):
        CompanyModule.objects.filter(company=self.company, module_code="logistics").update(is_enabled=False)
        with self.assertRaises(BusinessRuleError):
            TransportOrderService().create_transport_order(
                user=self.user,
                company_id=self.company.id,
                shipment_id=self.shipment.id,
                carrier="Carrier A",
            )

    def test_recovery_state_flow(self):
        svc = ContainerRecoveryService()
        plan = svc.create_plan(
            user=self.user,
            company_id=self.company.id,
            customer_id=self.customer.id,
            lines=[{"container_material_id": self.material.id, "qty": Decimal("5")}],
        )
        plan = svc.transition_plan(user=self.user, company_id=self.company.id, plan_id=plan.id, to_status=DOC_STATUS.SUBMITTED)
        plan = svc.transition_plan(user=self.user, company_id=self.company.id, plan_id=plan.id, to_status=DOC_STATUS.CONFIRMED)
        plan = svc.transition_plan(user=self.user, company_id=self.company.id, plan_id=plan.id, to_status=DOC_STATUS.COMPLETED)
        self.assertEqual(plan.status, DOC_STATUS.COMPLETED)

        self.assertTrue(
            DocumentTransitionLog.objects.filter(
                company_id=self.company.id,
                document_type="logistics.container_recovery_plan",
                document_id=plan.id,
            ).exists()
        )

    def test_financial_and_qty_validations(self):
        with self.assertRaises(DjangoValidationError):
            FreightChargeService().create_freight_charge(
                user=self.user,
                company_id=self.company.id,
                shipment_id=self.shipment.id,
                calc_method=FreightCharge.CalcMethod.MANUAL,
                amount=Decimal("0"),
                currency="USD",
            )

        with self.assertRaises(DjangoValidationError):
            InsurancePolicyService().create_policy(
                user=self.user,
                company_id=self.company.id,
                shipment_id=self.shipment.id,
                provider="Insure",
                policy_no="P-0",
                insured_amount=Decimal("0"),
                premium=Decimal("10"),
            )

        with self.assertRaises(DjangoValidationError):
            ContainerRecoveryService().create_plan(
                user=self.user,
                company_id=self.company.id,
                customer_id=self.customer.id,
                lines=[{"container_material_id": self.material.id, "qty": Decimal("0")}],
            )

    def test_tracking_freight_insurance_update_cancel(self):
        tracking_svc = ShipmentTrackingService()
        event = tracking_svc.create_tracking_event(
            user=self.user,
            company_id=self.company.id,
            shipment_id=self.shipment.id,
            status="picked_up",
            event_time=timezone.now(),
        )
        tracking_svc.update_tracking_event(user=self.user, company_id=self.company.id, event_id=event.id, note="updated")
        tracking_svc.cancel_tracking_event(user=self.user, company_id=self.company.id, event_id=event.id)
        self.assertFalse(ShipmentTrackingEvent.objects.active().for_company(self.company.id).filter(id=event.id).exists())

        freight_svc = FreightChargeService()
        freight = freight_svc.create_freight_charge(
            user=self.user,
            company_id=self.company.id,
            shipment_id=self.shipment.id,
            calc_method=FreightCharge.CalcMethod.MANUAL,
            amount=Decimal("100"),
            currency="USD",
        )
        freight_svc.update_freight_charge(user=self.user, company_id=self.company.id, freight_charge_id=freight.id, amount=Decimal("120"))
        freight_svc.cancel_freight_charge(user=self.user, company_id=self.company.id, freight_charge_id=freight.id)
        self.assertFalse(FreightCharge.objects.active().for_company(self.company.id).filter(id=freight.id).exists())

        ins_svc = InsurancePolicyService()
        policy = ins_svc.create_policy(
            user=self.user,
            company_id=self.company.id,
            shipment_id=self.shipment.id,
            provider="InsureCo",
            policy_no="POL-1",
            insured_amount=Decimal("1000"),
            premium=Decimal("10"),
        )
        ins_svc.update_policy(user=self.user, company_id=self.company.id, policy_id=policy.id, premium=Decimal("11"))
        ins_svc.cancel_policy(user=self.user, company_id=self.company.id, policy_id=policy.id)
        self.assertFalse(InsurancePolicy.objects.active().for_company(self.company.id).filter(id=policy.id).exists())
