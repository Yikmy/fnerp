from decimal import Decimal
from django.db import transaction
from shared.constants.modules import MODULE_CODES
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService
from ..models import BinLocation, Material, MaterialCategory, UoM, Warehouse, WarehouseZone

class MaterialDomainService(BaseService):
    MODULE_CODE = MODULE_CODES.MATERIAL

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("material module is disabled for this company")

    @staticmethod
    def _user_id(user):
        return getattr(user, "id", None)

class UomService(MaterialDomainService):
    PERM_CREATE = PERMISSION_CODES.MATERIAL_UOM_CREATE

    @transaction.atomic
    def create_uom(self, *, user, company_id, name: str, symbol: str, ratio_to_base: Decimal, request=None) -> UoM:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        uom = UoM(
            company_id=company_id,
            name=name,
            symbol=symbol,
            ratio_to_base=ratio_to_base,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        uom.full_clean()
        uom.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="material.uom",
            resource_id=uom.id,
            request=request,
        )
        return uom

    @staticmethod
    def convert_quantity(*, quantity: Decimal, from_uom: UoM, to_uom: UoM) -> Decimal:
        if from_uom.company_id != to_uom.company_id:
            raise BusinessRuleError("Cannot convert across different company scopes")

        base_quantity = quantity * from_uom.ratio_to_base
        return base_quantity / to_uom.ratio_to_base

class MaterialCategoryService(MaterialDomainService):
    PERM_CREATE = PERMISSION_CODES.MATERIAL_CATEGORY_CREATE

    @transaction.atomic
    def create_material_category(self, *, user, company_id, name: str, parent_id=None, request=None) -> MaterialCategory:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        parent = None
        if parent_id:
            parent = MaterialCategory.objects.active().for_company(company_id).filter(id=parent_id).first()
            if parent is None:
                raise BusinessRuleError("Parent category not found in company scope")

        category = MaterialCategory(
            company_id=company_id,
            name=name,
            parent=parent,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        category.full_clean()
        category.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="material.category",
            resource_id=category.id,
            request=request,
        )
        return category

    def get_category_descendants(self, *, company_id, category_id):
        descendants = []
        pending_ids = [category_id]
        while pending_ids:
            children = list(
                MaterialCategory.objects.active()
                .for_company(company_id)
                .filter(parent_id__in=pending_ids)
                .only("id", "name", "parent_id")
            )
            descendants.extend(children)
            pending_ids = [item.id for item in children]
        return descendants

    def get_category_ancestors(self, *, company_id, category_id):
        category = (
            MaterialCategory.objects.active()
            .for_company(company_id)
            .filter(id=category_id)
            .only("id", "name", "parent_id")
            .first()
        )
        if category is None:
            raise BusinessRuleError("Category not found in company scope")

        ancestors = []
        parent_id = category.parent_id
        while parent_id is not None:
            parent = (
                MaterialCategory.objects.active()
                .for_company(company_id)
                .filter(id=parent_id)
                .only("id", "name", "parent_id")
                .first()
            )
            if parent is None:
                break
            ancestors.append(parent)
            parent_id = parent.parent_id
        return ancestors

    def get_category_tree(self, *, company_id, category_id):
        root = (
            MaterialCategory.objects.active()
            .for_company(company_id)
            .filter(id=category_id)
            .only("id", "name", "parent_id")
            .first()
        )
        if root is None:
            raise BusinessRuleError("Category not found in company scope")

        descendants = self.get_category_descendants(company_id=company_id, category_id=category_id)
        nodes = [root, *descendants]
        nodes_by_parent = {}
        for node in nodes:
            nodes_by_parent.setdefault(node.parent_id, []).append(node)

        def _build(node):
            children = [_build(child) for child in nodes_by_parent.get(node.id, [])]
            return {
                "id": str(node.id),
                "name": node.name,
                "parent_id": str(node.parent_id) if node.parent_id else None,
                "children": children,
            }

        return _build(root)

class MaterialService(MaterialDomainService):
    PERM_CREATE = PERMISSION_CODES.MATERIAL_MATERIAL_CREATE

    @transaction.atomic
    def create_material(
        self,
        *,
        user,
        company_id,
        code: str,
        name: str,
        category_id,
        uom_id,
        spec: str = "",
        tracking: str = Material.TrackingType.NONE,
        is_container: bool = False,
        is_active: bool = True,
        request=None,
    ) -> Material:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        category = MaterialCategory.objects.active().for_company(company_id).filter(id=category_id).first()
        if category is None:
            raise BusinessRuleError("Category not found in company scope")

        uom = UoM.objects.active().for_company(company_id).filter(id=uom_id).first()
        if uom is None:
            raise BusinessRuleError("UoM not found in company scope")

        material = Material(
            company_id=company_id,
            code=code,
            name=name,
            category=category,
            uom=uom,
            spec=spec,
            tracking=tracking,
            is_container=is_container,
            is_active=is_active,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        material.full_clean()
        material.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="material.material",
            resource_id=material.id,
            request=request,
        )
        return material

class WarehouseService(MaterialDomainService):
    PERM_CREATE = PERMISSION_CODES.MATERIAL_WAREHOUSE_CREATE

    @transaction.atomic
    def create_warehouse(self, *, user, company_id, code: str, name: str, address: str = "", request=None) -> Warehouse:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE)

        warehouse = Warehouse(
            company_id=company_id,
            code=code,
            name=name,
            address=address,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        warehouse.full_clean()
        warehouse.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="material.warehouse",
            resource_id=warehouse.id,
            request=request,
        )
        return warehouse

class BinLocationService(MaterialDomainService):
    PERM_CREATE_ZONE = PERMISSION_CODES.MATERIAL_WAREHOUSE_ZONE_CREATE
    PERM_CREATE_BIN_LOCATION = PERMISSION_CODES.MATERIAL_BIN_LOCATION_CREATE

    @transaction.atomic
    def create_warehouse_zone(self, *, user, company_id, warehouse_id, code: str, name: str, request=None) -> WarehouseZone:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE_ZONE)

        warehouse = Warehouse.objects.active().for_company(company_id).filter(id=warehouse_id).first()
        if warehouse is None:
            raise BusinessRuleError("Warehouse not found in company scope")

        zone = WarehouseZone(
            company_id=company_id,
            warehouse=warehouse,
            code=code,
            name=name,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        zone.full_clean()
        zone.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="material.warehouse_zone",
            resource_id=zone.id,
            request=request,
        )
        return zone

    @transaction.atomic
    def create_bin_location(
        self,
        *,
        user,
        company_id,
        warehouse_id,
        code: str,
        name: str,
        zone_id=None,
        request=None,
    ) -> BinLocation:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE_BIN_LOCATION)

        warehouse = Warehouse.objects.active().for_company(company_id).filter(id=warehouse_id).first()
        if warehouse is None:
            raise BusinessRuleError("Warehouse not found in company scope")

        zone = None
        if zone_id:
            zone = WarehouseZone.objects.active().for_company(company_id).filter(id=zone_id).first()
            if zone is None:
                raise BusinessRuleError("Zone not found in company scope")

        bin_location = BinLocation(
            company_id=company_id,
            warehouse=warehouse,
            zone=zone,
            code=code,
            name=name,
            created_by=self._user_id(user),
            updated_by=self._user_id(user),
        )
        bin_location.full_clean()
        bin_location.save()

        self.audit_crud(
            user=user,
            company_id=company_id,
            operation="create",
            resource_type="material.bin_location",
            resource_id=bin_location.id,
            request=request,
        )
        return bin_location

class MaterialMasterDataService(BaseService):
    """Compatibility facade delegating to STEP2 subdomain services."""

    def __init__(self):
        self.uom_service = UomService()
        self.category_service = MaterialCategoryService()
        self.material_service = MaterialService()
        self.warehouse_service = WarehouseService()
        self.bin_location_service = BinLocationService()

    def create_uom(self, **kwargs):
        return self.uom_service.create_uom(**kwargs)

    def convert_quantity(self, **kwargs):
        return self.uom_service.convert_quantity(**kwargs)

    def create_material_category(self, **kwargs):
        return self.category_service.create_material_category(**kwargs)

    def get_category_descendants(self, **kwargs):
        return self.category_service.get_category_descendants(**kwargs)

    def get_category_ancestors(self, **kwargs):
        return self.category_service.get_category_ancestors(**kwargs)

    def get_category_tree(self, **kwargs):
        return self.category_service.get_category_tree(**kwargs)

    def create_material(self, **kwargs):
        return self.material_service.create_material(**kwargs)

    def create_warehouse(self, **kwargs):
        return self.warehouse_service.create_warehouse(**kwargs)

    def create_warehouse_zone(self, **kwargs):
        return self.bin_location_service.create_warehouse_zone(**kwargs)

    def create_bin_location(self, **kwargs):
        return self.bin_location_service.create_bin_location(**kwargs)
