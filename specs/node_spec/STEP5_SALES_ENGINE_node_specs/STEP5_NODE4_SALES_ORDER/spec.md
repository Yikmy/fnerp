
# Sales Order Specification

## SalesOrder

Fields:

id
company_id
doc_no
customer_id
delivery_date
total_amount
special_terms
status

## SalesOrderLine

Fields:

so_id
material_id
qty
price
warehouse_id
reserved_qty

## Integration

SalesOrder confirmation triggers reservation.
