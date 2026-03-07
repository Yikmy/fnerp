from .enum_compat import StrEnum


class PERMISSION_CODES(StrEnum):
    DOC_SUBMIT = "doc.submit"
    DOC_CONFIRM = "doc.confirm"
    DOC_COMPLETE = "doc.complete"
    DOC_CANCEL = "doc.cancel"
    DOC_CANCEL_COMPLETED = "doc.cancel.completed"

    MATERIAL_UOM_CREATE = "material.uom.create"
    MATERIAL_CATEGORY_CREATE = "material.category.create"
    MATERIAL_MATERIAL_CREATE = "material.material.create"
    MATERIAL_WAREHOUSE_CREATE = "material.warehouse.create"
    MATERIAL_WAREHOUSE_ZONE_CREATE = "material.warehouse_zone.create"
    MATERIAL_BIN_LOCATION_CREATE = "material.bin_location.create"
