# RBAC Specification

## Role Model

User → Role → Permission

## Permission Code Structure

module.resource.action

Example:

inventory.stock.adjust
sales.order.submit

## Permission Guard

Before executing business logic:

Check role permissions.

If user lacks permission:

Return HTTP 403.