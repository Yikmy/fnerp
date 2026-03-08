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
    INVENTORY_STOCK_LEDGER_WRITE = "inventory.stock_ledger.write"
    INVENTORY_RESERVATION_CREATE = "inventory.reservation.create"
    INVENTORY_RESERVATION_RELEASE = "inventory.reservation.release"
    INVENTORY_RESERVATION_CONSUME = "inventory.reservation.consume"
    INVENTORY_TRANSFER_CREATE = "inventory.transfer.create"
    INVENTORY_TRANSFER_SHIP = "inventory.transfer.ship"
    INVENTORY_TRANSFER_RECEIVE = "inventory.transfer.receive"
    INVENTORY_STOCK_COUNT_CREATE = "inventory.stock_count.create"
    INVENTORY_STOCK_COUNT_POST = "inventory.stock_count.post"
    PURCHASE_VENDOR_CREATE = "purchase.vendor.create"
    PURCHASE_RFQ_CREATE = "purchase.rfq.create"
    PURCHASE_ORDER_CREATE = "purchase.order.create"
    PURCHASE_GRN_CREATE = "purchase.grn.create"
    PURCHASE_IQC_CREATE = "purchase.iqc.create"
    PURCHASE_AP_MATCH_CREATE = "purchase.ap_match.create"

    SALES_CUSTOMER_CREATE = "sales.customer.create"
    SALES_PRICING_CREATE = "sales.pricing.create"
    SALES_QUOTE_CREATE = "sales.quote.create"
    SALES_ORDER_CREATE = "sales.order.create"
    SALES_SHIPMENT_CREATE = "sales.shipment.create"
    SALES_RMA_CREATE = "sales.rma.create"

