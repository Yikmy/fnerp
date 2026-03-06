# Base Infrastructure Specification

## Purpose

Provide reusable infrastructure shared by all ERP modules.

## BaseModel

All business tables inherit BaseModel.

Standard fields:

id (UUID)
company_id (FK)
created_at
created_by
updated_at
updated_by
is_deleted

## QuerySet

Provide standard filters.

Functions:

for_company(company)
active()

Ensure:

is_deleted = false

## BaseService

Provide:

transaction handling
error handling
logging hooks

## Exceptions

Define standard API exceptions.

Examples:

PermissionDenied
BusinessRuleError
ValidationError

## Constants

Define shared constants.

Examples:

DOC_STATUS
MODULE_CODES
PERMISSION_CODES