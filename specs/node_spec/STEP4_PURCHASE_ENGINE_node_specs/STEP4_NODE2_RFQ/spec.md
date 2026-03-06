
# RFQ Specification

## RFQTask

Fields:

id
company_id
title
status
llm_enabled
schedule_json

## RFQLine

Fields:

rfq_id
material_id
qty
target_date

## RFQQuote

Fields:

rfq_id
vendor_id
material_id
price
currency
lead_time_days
valid_until
source
raw_payload
