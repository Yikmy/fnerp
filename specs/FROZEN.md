# FROZEN CONTRACT

## 1. Purpose
- This file records frozen outputs from completed steps.
- Later steps must treat these outputs as stable dependencies.
- If a later step requires changing a frozen-step ownership boundary, stop implementation and report a boundary conflict.

## 2. Global Rules
- Kernel architecture is foundational and remains the base layer for all later steps.
- Later steps may depend on earlier steps.
- Earlier steps must not depend on later steps.
- Frozen steps are read/reuse references, not redesign targets.
- Reverse dependency is forbidden.
- Workflow logic from later operational steps must not leak back into earlier frozen ownership domains.
- When extension is needed, add new apps/services in later steps instead of modifying frozen ownership boundaries.

## 3. STEP1_KERNEL (Frozen)
### status
frozen

### owned scope
- Shared infrastructure layer in `backend/shared/**`:
  - `BaseModel`, `CompanyQuerySet`, `BaseService`, API exception types, shared constants, scope/audit middleware.
- Company scope and module enablement domain:
  - `Company`, `CompanyMembership`, `CompanyModule`, membership lookup and scope validation services.
- RBAC domain:
  - `Role`, `Permission`, `RolePermission`, permission guard and permission service.
- Document state engine domain:
  - `DocumentStateMachineDef`, `DocumentTransitionLog`, state transition service.
- Audit domain:
  - `AuditEvent`, `AuditFieldDiff`, audit logging service.
- System configuration domain:
  - `SystemConfig`, config retrieval/update service with scope fallback.

### exported infrastructure
- Company scope: request-level company resolution and membership enforcement.
- RBAC: permission format `module.resource.action`, role-permission checks, middleware/decorator compatibility.
- Module guard: company-module enablement checks before business operations.
- Audit: request/CRUD/state-transition audit event pipeline.
- Document state machine: standard status model and guarded transitions.
- Service layer: `BaseService` permission and audit hooks for downstream services.
- Shared base components: base model/queryset/exception/constants conventions used by business modules.

### allowed downstream usage
- Reuse shared base classes and middleware contracts as-is.
- Reuse company scope context (`current_company_id`) and company membership checks.
- Reuse RBAC permission checks and module enablement checks in downstream services.
- Reuse document transition service for document-status workflows.
- Reuse audit APIs for request, CRUD, and transition traceability.
- Reuse system config retrieval for company/global configuration lookups.

### forbidden downstream changes
- Do not redesign company-scope resolution, membership semantics, or company isolation contract.
- Do not redesign RBAC model structure or permission-code architecture.
- Do not redesign module-guard semantics.
- Do not redesign document state-machine lifecycle contract.
- Do not redesign audit model/service contract.
- Do not bypass service-layer pattern with direct workflow logic in controllers/views.
- Do not create reverse dependency from STEP1 domains to STEP3+ domains.

## 4. STEP2_MASTER_DATA (Frozen)
### status
frozen

### owned scope
- UoM
- MaterialCategory
- Material
- Warehouse
- WarehouseZone
- BinLocation

### exported entities / dependencies
- `UoM`
  - Purpose: standardize quantity units and conversion baseline.
  - Key relations: referenced by `Material`; company-scoped uniqueness by name/symbol.
  - Downstream usage expectation: reference for quantity/unit validation and conversions; do not duplicate unit catalogs.
- `MaterialCategory`
  - Purpose: hierarchical material classification.
  - Key relations: self-parent tree; parent and child must remain in same company scope.
  - Downstream usage expectation: reference for categorization and filtering; do not replace with parallel category trees.
- `Material`
  - Purpose: shared master definition for stocked/sold/produced items.
  - Key relations: belongs to `MaterialCategory` and `UoM`; tracking type constrained to `none|lot|serial`; company-code uniqueness.
  - Downstream usage expectation: reference material identity and tracking policy in operational documents.
- `Warehouse`
  - Purpose: physical storage master.
  - Key relations: parent for `WarehouseZone` and `BinLocation`; company-code uniqueness.
  - Downstream usage expectation: reference warehouse for inventory, transfer, receipt, shipment, and production records.
- `WarehouseZone`
  - Purpose: optional intra-warehouse zoning.
  - Key relations: belongs to `Warehouse`; company/warehouse/code uniqueness.
  - Downstream usage expectation: optional granular storage segmentation; preserve warehouse ownership.
- `BinLocation`
  - Purpose: optional fine-grained storage slot.
  - Key relations: belongs to `Warehouse`; optional `WarehouseZone`; zone must belong to same warehouse; company/warehouse/code uniqueness.
  - Downstream usage expectation: reference for stock placement and movement granularity; do not replace with parallel bin systems.

### service boundary
- Stable service boundary is `MaterialMasterDataService` in `backend/apps/material/services.py`.
- Downstream interaction must happen through service-layer calls and model references, not by redefining master-data logic.
- Service boundary enforces:
  - company scope filtering (`for_company`, `active`),
  - module enablement checks,
  - permission checks,
  - audit hooks,
  - master-data validation constraints.

### allowed downstream usage
- Read and reference STEP2 material masters in later workflows.
- Validate `Material`, `Warehouse`, `WarehouseZone`, and `BinLocation` existence/scope before operational writes.
- Attach downstream operational records to STEP2 master-data identifiers.
- Reuse STEP2 identifiers and relationships as foreign-key dependencies in STEP3+.

### forbidden downstream behavior
- Do not duplicate STEP2 master-data models in later steps.
- Do not move STEP3+ workflow orchestration into `backend/apps/material/**`.
- Do not redesign STEP2 ownership boundaries or entity semantics.
- Do not create reverse dependency from STEP2 to later operational steps.
- Do not weaken company-scope and validation constraints on STEP2 entities.

## 5. Inherited Rules for All Later Steps
- Dependency direction is one-way: earlier frozen steps -> later steps only.
- Company scope is mandatory for business records and request handling.
- Service-layer pattern is required; downstream business logic belongs in services.
- Permission and module guard compatibility must be maintained.
- Audit compatibility is required for critical operations and transitions.
- Frozen entities must be reused as stable references instead of re-modeled.
- Workflow backflow into earlier frozen domains is prohibited.

## 6. Downstream Implementation Rule
- STEP3+ must use completed steps as frozen dependencies.
- Extend capabilities through new apps and new services in later steps.
- Do not rewrite earlier-step ownership boundaries unless a compatibility fix is explicitly required and reported.
