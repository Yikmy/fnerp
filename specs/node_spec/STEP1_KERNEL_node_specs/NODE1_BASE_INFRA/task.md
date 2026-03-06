# NODE1_BASE_INFRA

## Goal

Build the shared infrastructure layer used by all ERP modules.

This layer provides:

- BaseModel
- BaseQuerySet
- BaseService
- common constants
- API exception structure

All future modules must depend on this layer.

## Output

Create directory:

backend/shared/

Submodules:

models
querysets
services
exceptions
constants

Implement:

BaseModel
CompanyQuerySet
BaseService
ApiException

Ensure BaseModel includes system fields.