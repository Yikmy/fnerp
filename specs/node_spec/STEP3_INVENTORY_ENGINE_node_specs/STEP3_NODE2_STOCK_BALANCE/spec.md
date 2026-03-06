
# StockBalance Specification

## Purpose
Maintain real-time inventory levels.

## Model: StockBalance

Fields:

id
company_id
warehouse_id
material_id
on_hand_qty
reserved_qty
available_qty
lot_id
serial_id

## Formula

available_qty = on_hand_qty - reserved_qty
