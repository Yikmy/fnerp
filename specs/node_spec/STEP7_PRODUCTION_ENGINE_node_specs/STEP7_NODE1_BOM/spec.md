
# BOM Specification

## Model: BOM

Fields:

id
company_id
product_material_id
version
status
effective_from
effective_to
notes

Status:

draft
active
retired

## Model: BOMLine

Fields:

bom_id
component_material_id
qty_per_unit
scrap_rate
