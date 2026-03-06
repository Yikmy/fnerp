
# Bin Location Specification

## Purpose
Support fine-grained warehouse storage.

## Models

WarehouseZone

Fields:
id
warehouse_id
code
name

BinLocation

Fields:
id
warehouse_id
zone_id
code
name

## Usage

Used by:

Inventory
StockLedger
StockBalance
