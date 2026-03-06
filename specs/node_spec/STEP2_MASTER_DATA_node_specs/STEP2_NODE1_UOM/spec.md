
# UoM Specification

## Purpose
Standardize measurement units across ERP modules.

## Model: UoM

Fields:

id (UUID)
name
symbol
ratio_to_base

## Rules

ratio_to_base defines conversion relative to base unit.

Example:

Base unit: kg

kg = 1
g = 0.001
ton = 1000

## Usage

Used in:
- Material
- Inventory
- PurchaseOrderLine
- SalesOrderLine
