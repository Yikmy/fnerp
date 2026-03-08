from django.contrib import admin

from . import models


admin.site.register(models.Customer)
admin.site.register(models.CustomerPriceList)
admin.site.register(models.PricingRule)
admin.site.register(models.SalesQuote)
admin.site.register(models.SalesQuoteLine)
admin.site.register(models.SalesOrder)
admin.site.register(models.SalesOrderLine)
admin.site.register(models.Shipment)
admin.site.register(models.ShipmentLine)
admin.site.register(models.POD)
admin.site.register(models.ShipmentStatusEvent)
admin.site.register(models.RMA)
admin.site.register(models.RMALine)
