# ERP Kernel Design Spec

## Purpose

Defines the **core system infrastructure** that all ERP modules depend
on.\
Kernel components are designed to remain stable long-term and rarely
change.

## Kernel Modules

-   core
-   company
-   auth
-   doc
-   audit
-   config

## Responsibilities

### core

System-level services and rules. - permission service - module
enablement checks - company scope utilities

### company

Handles multi-company structure. Entities: - Company -
CompanyMembership - CompanyModule

### auth

RBAC permission model. Entities: - User - Role - Permission -
RolePermission

### doc

Unified document lifecycle engine.

Standard states: DRAFT → SUBMITTED → CONFIRMED → COMPLETED → CANCELLED

Responsibilities: - validate transitions - enforce state permissions -
log transitions

### audit

Records all critical operations.

Data captured: - actor - action - resource - timestamp - field changes

### config

Stores configurable system rules.

Examples: - allow_negative_stock - default_currency -
approval_requirements

## Dependency Rule

Business modules may depend on Kernel modules. Kernel modules must never
depend on business modules.
