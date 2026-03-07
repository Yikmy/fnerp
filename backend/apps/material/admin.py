from django.contrib import admin

from .models import BinLocation, Material, MaterialCategory, UoM, Warehouse, WarehouseZone


@admin.register(UoM)
class UoMAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "ratio_to_base", "company_id", "is_deleted")
    search_fields = ("name", "symbol")


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "company_id", "is_deleted")
    search_fields = ("name",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "uom", "tracking", "is_active", "company_id")
    list_filter = ("tracking", "is_active")
    search_fields = ("code", "name")


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "company_id")
    search_fields = ("code", "name")


@admin.register(WarehouseZone)
class WarehouseZoneAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "code", "name", "company_id")
    search_fields = ("code", "name")


@admin.register(BinLocation)
class BinLocationAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "zone", "code", "name", "company_id")
    search_fields = ("code", "name")
