# ERP Permission & Role Model Spec

## Overview

The system uses **Role Based Access Control (RBAC)**.

Hierarchy:

System → Company → Role → Permission

## User Membership

Users belong to companies via CompanyMembership.

User → CompanyMembership → Role

A user may belong to multiple companies.

## Role Groups

Roles define sets of permissions.

Examples:

ProductionAdmin\
SalesManager\
ReadOnlyUser

## Permission Codes

Permission format:

module.resource.action

Examples:

sales.order.create\
sales.order.submit\
sales.order.confirm\
inventory.stock.adjust

## Permission Guard

Before executing an operation the system verifies:

1.  company module enabled
2.  role permission exists
3.  document state allows operation

Only if all checks pass → operation allowed.
