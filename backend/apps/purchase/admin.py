from django.contrib import admin

from . import models


admin.site.register(models.Vendor)
admin.site.register(models.VendorHistory)
admin.site.register(models.RFQTask)
admin.site.register(models.RFQLine)
admin.site.register(models.RFQQuote)
admin.site.register(models.PurchaseOrder)
admin.site.register(models.PurchaseOrderLine)
admin.site.register(models.GoodsReceipt)
admin.site.register(models.GoodsReceiptLine)
admin.site.register(models.IQCRecord)
admin.site.register(models.InvoiceMatch)
