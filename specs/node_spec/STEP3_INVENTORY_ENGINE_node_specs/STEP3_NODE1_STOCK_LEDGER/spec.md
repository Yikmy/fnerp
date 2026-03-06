
# StockLedger Specification

## Purpose
Provide a complete movement history of inventory.

## Model: StockLedger

Fields:

id
company_id
warehouse_id
material_id
movement_type
qty
uom_id
lot_id
serial_id
ref_doc_type
ref_doc_id
cost_amount
created_at

## Movement Types

in
out
adjust
transfer_in
transfer_out
