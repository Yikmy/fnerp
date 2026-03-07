from decimal import Decimal

from django.db import transaction

from shared.exceptions import BusinessRuleError
from shared.services.base import BaseService
from shared.services.module_guard import ModuleGuardService

from .models import BinLocation, Material, MaterialCategory, UoM, Warehouse, WarehouseZone


class MaterialMasterDataService(BaseService):
    MODULE_CODE = "material"

    PERM_CREATE_UOM = "material.uom.create"
    PERM_CREATE_CATEGORY = "material.category.create"
    PERM_CREATE_MATERIAL = "material.material.create"
    PERM_CREATE_WAREHOUSE = "material.warehouse.create"
    PERM_CREATE_BIN = "material.bin.create"

    def _ensure_module_enabled(self, *, company_id):
        if not ModuleGuardService.check_module_enabled(company_id=company_id, module_code=self.MODULE_CODE):
            raise BusinessRuleError("material module is disabled for this company")

    @transaction.atomic
    def create_uom(self, *, user, company_id, name: str, symbol: str, ratio_to_base: Decimal, request=None) -> UoM:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE_UOM)

        uom = UoM(
            company_id=company_id,
            name=name,
            symbol=symbol,
            ratio_to_base=ratio_to_base,
            created_by=getattr(user, "id", None),
            updated_by=getattr(user, "id", None),
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

    @transaction.atomic
    def create_material_category(self, *, user, company_id, name: str, parent_id=None, request=None) -> MaterialCategory:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE_CATEGORY)

        parent = None
        if parent_id:
            parent = MaterialCategory.objects.active().for_company(company_id).filter(id=parent_id).first()
            if parent is None:
                raise BusinessRuleError("Parent category not found in company scope")

        category = MaterialCategory(
            company_id=company_id,
            name=name,
            parent=parent,
            created_by=getattr(user, "id", None),
            updated_by=getattr(user, "id", None),
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
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE_MATERIAL)

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
            created_by=getattr(user, "id", None),
            updated_by=getattr(user, "id", None),
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

    @transaction.atomic
    def create_warehouse(self, *, user, company_id, code: str, name: str, address: str = "", request=None) -> Warehouse:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE_WAREHOUSE)

        warehouse = Warehouse(
            company_id=company_id,
            code=code,
            name=name,
            address=address,
            created_by=getattr(user, "id", None),
            updated_by=getattr(user, "id", None),
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

    @transaction.atomic
    def create_warehouse_zone(self, *, user, company_id, warehouse_id, code: str, name: str, request=None) -> WarehouseZone:
        self._ensure_module_enabled(company_id=company_id)
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE_BIN)

        warehouse = Warehouse.objects.active().for_company(company_id).filter(id=warehouse_id).first()
        if warehouse is None:
            raise BusinessRuleError("Warehouse not found in company scope")

        zone = WarehouseZone(
            company_id=company_id,
            warehouse=warehouse,
            code=code,
            name=name,
            created_by=getattr(user, "id", None),
            updated_by=getattr(user, "id", None),
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
        self.ensure_permission(user=user, company_id=company_id, permission_code=self.PERM_CREATE_BIN)

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
            created_by=getattr(user, "id", None),
            updated_by=getattr(user, "id", None),
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
