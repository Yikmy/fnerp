
# Shipment Specification

## Shipment

Fields:

id
company_id
doc_no
so_id
customer_id
warehouse_id
ship_date
status
carrier
tracking_no

## ShipmentLine

Fields:

shipment_id
so_line_id
material_id
qty
lot_id
serial_id

## POD

Proof of delivery record.

## ShipmentStatusEvent

Track shipment status history.
