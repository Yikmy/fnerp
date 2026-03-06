# NODE3_AUTH_RBAC

## Goal

Implement role-based access control.

## Models

User
Role
Permission
RolePermission

## Permission Format

module.resource.action

Example:

sales.order.create
purchase.po.confirm

## Required Features

permission guard
role permission lookup
integration with company membership