from .enum_compat import StrEnum


class MODULE_CODES(StrEnum):
    CORE = "core"
    COMPANY = "company"
    AUTH = "auth"
    DOC = "doc"
    AUDIT = "audit"
    CONFIG = "config"
    MATERIAL = "material"
    INVENTORY = "inventory"
    PURCHASE = "purchase"
    SALES = "sales"
