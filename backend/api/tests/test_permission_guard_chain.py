from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from company.models import Company, CompanyMembership, CompanyModule
from rbac.models import Permission, Role, RolePermission

from api.services import PermissionProbeService


class PermissionGuardChainTest(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="api_user", password="pwd")

        self.company = Company.objects.create(name="Guard Company")
        CompanyModule.objects.create(company=self.company, module_code="core", is_enabled=True)
        CompanyMembership.objects.create(user=self.user, company=self.company, is_active=True)

        self.client.force_login(self.user)
        session = self.client.session
        session["company_id"] = str(self.company.id)
        session.save()

    def test_permission_guard_rejects_without_route_permission(self):
        response = self.client.get("/api/guard/probe/")

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["error"], "forbidden")
        self.assertEqual(payload["permission"], PermissionProbeService.PERM_READ)

    def test_permission_guard_allows_when_role_has_permission(self):
        role = Role.objects.create(code="core-reader", name="Core Reader")
        permission = Permission.objects.create(
            code=PermissionProbeService.PERM_READ,
            name="Core Permission Read",
        )
        RolePermission.objects.create(role=role, permission=permission)

        membership = CompanyMembership.objects.get(user=self.user, company=self.company)
        membership.role = role
        membership.save(update_fields=["role"])

        response = self.client.get("/api/guard/probe/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["ok"])
        self.assertEqual(payload["data"]["permission"], PermissionProbeService.PERM_READ)
