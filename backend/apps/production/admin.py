from django.contrib import admin

from . import models


admin.site.register(models.BOM)
admin.site.register(models.BOMLine)
admin.site.register(models.ProductionPlan)
admin.site.register(models.ManufacturingOrder)
admin.site.register(models.MOIssueLine)
admin.site.register(models.MOReceiptLine)
admin.site.register(models.ProductionQC)
admin.site.register(models.IoTDevice)
admin.site.register(models.IoTMetric)
