from django.contrib import admin

from .models import (
    ContainerRecoveryLine,
    ContainerRecoveryPlan,
    FreightCharge,
    InsurancePolicy,
    ShipmentTrackingEvent,
    TransportOrder,
)

admin.site.register(TransportOrder)
admin.site.register(ShipmentTrackingEvent)
admin.site.register(ContainerRecoveryPlan)
admin.site.register(ContainerRecoveryLine)
admin.site.register(FreightCharge)
admin.site.register(InsurancePolicy)
