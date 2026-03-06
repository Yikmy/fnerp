
# Material Category Specification

## Purpose
Organize materials into hierarchical groups.

## Model: MaterialCategory

Fields:

id
name
parent_id (self FK)

## Example

Chemicals
  ├─ Solvents
  ├─ Additives

Containers
  ├─ Drums
  ├─ Bottles
