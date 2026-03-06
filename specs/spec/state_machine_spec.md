# Document State Machine Spec

## Purpose

Defines the **standard lifecycle for ERP documents**.

Applies to:

-   purchase orders
-   sales orders
-   shipments
-   manufacturing orders

## Standard States

DRAFT\
SUBMITTED\
CONFIRMED\
COMPLETED\
CANCELLED

## Transition Rules

Typical transitions:

DRAFT → SUBMITTED\
SUBMITTED → CONFIRMED\
CONFIRMED → COMPLETED\
Any → CANCELLED

## Engine Responsibilities

The state engine ensures:

-   transitions are valid
-   user has required permission
-   state changes are logged

## Transition Log

Each change records:

-   document type
-   document id
-   from_state
-   to_state
-   operator
-   timestamp
-   notes
