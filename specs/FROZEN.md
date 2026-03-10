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

## 5. API_FOUNDATION (Frozen)
### status
frozen

### owned scope
- Root API protocol and aggregation layer in `backend/api/**`.
- Root URL aggregation entrypoint in project URL config (`/api/` include path).
- Unified API success/error response envelope helpers.
- Centralized API exception-to-HTTP mapping contract.
- Minimal shared API helpers for authentication/session/JSON parsing concerns.
- Session/cookie authentication foundation endpoints: `login`, `logout`, `session`.
- Kernel-level API smoke foundation for session-cookie auth flow validation.

### exported infrastructure
- Unified API response contract (`success` envelope and `error` envelope shape).
- Unified API exception mapping contract for API-facing failures.
- Root API aggregation entrypoint for downstream per-app API includes.
- Session/cookie authentication bootstrap for MVP API rollout.
- Authenticated session verification path for smoke and health checks.
- Per-app API include pattern for STEP1–STEP3 domain API exposure.

### allowed downstream usage
- Later steps may add `api/` packages under business apps and include them via root API aggregation.
- Later app APIs may reuse root API response/exception/base helpers.
- Downstream API rollout may depend on session bootstrap and kernel smoke foundation.
- Business domain APIs remain owned by their app boundaries (`company`, `material`, `inventory`, and later steps).

### forbidden downstream changes
- Do not turn root API into a centralized business workflow hub.
- Do not centralize all business views under `backend/api/**`.
- Do not move business orchestration/workflow rules into root API helpers.
- Do not bypass service-layer pattern by embedding workflow logic in API views.
- Do not reinterpret this foundation as “full business API surface is frozen”.
- Do not redefine the current session/cookie foundation into JWT/token architecture without explicit future redesign.
- Do not weaken company-scope enforcement semantics for business routes.

## 6. STEP3_INVENTORY_ENGINE (Frozen)
### status
frozen

### owned scope
- Inventory engine entities and workflows in `backend/apps/inventory/**`.
- Entity ownership includes:
  - `Lot`
  - `Serial`
  - `StockLedger`
  - `StockBalance`
  - `Reservation`
  - `WarehouseTransfer`
  - `WarehouseTransferLine`
  - `StockCount`
  - `StockCountLine`
  - `CostLayer`
- Direct orchestration services for these entities in `backend/apps/inventory/services.py`.

### exported entities / dependencies
- `StockLedger`
  - Immutable append-only inventory movement source of truth.
  - Stable movement types include `in|out|adjust|transfer_in|transfer_out`.
  - Supports reference document linkage (`ref_doc_type`, `ref_doc_id`).
  - Downstream writes must go through inventory service-layer operations.
- `StockBalance`
  - Operational maintained state for real-time inventory quantity.
  - Stable formula: `available_qty = on_hand_qty - reserved_qty`.
  - Downstream treats balance as service-maintained projection, not an independent source of truth.
- `Lot` / `Serial`
  - Operational tracking entities aligned with STEP2 material tracking identity.
  - Used as inventory movement dimensions within STEP3 services.
- `Reservation`
  - Reservation lifecycle baseline includes `active`, `released`, `consumed`.
  - Reserved quantity interactions are maintained through service orchestration.
- `WarehouseTransfer` / `WarehouseTransferLine`
  - Inter-warehouse transfer workflow baseline (`draft -> shipped -> received`).
  - Ship/receive updates are ledger-compatible service-driven movements.
- `StockCount` / `StockCountLine`
  - Physical stock count workflow baseline (`draft -> posted`).
  - Count differences are posted through inventory service orchestration.
- `CostLayer`
  - FIFO valuation layer tracking tied to source ledger movements.
  - Outgoing depletion consumes remaining layers in service-managed FIFO order.

### service boundary
- Stable service boundary is `backend/apps/inventory/services.py`.
- Downstream interaction must happen through inventory service-layer calls and model references.
- This service boundary must preserve:
  - company scope filtering,
  - module enablement checks,
  - permission checks,
  - audit compatibility,
  - inventory consistency rules,
  - ledger-first operational writes.

### current stable behaviors
- Stock movement recording writes ledger entries and updates stock balance through service orchestration.
- Reservation create/release/consume updates reservation status and reserved quantity consistently.
- Stock count posting writes signed adjust movements through inventory movement services.
- Transfer ship/receive executes transfer-out/transfer-in movement orchestration through ledger writes.
- FIFO layer creation/consumption follows current service implementation baseline.
- Inventory module guard and permission compatibility follow current repaired baseline.
- Append-only ledger, reservation consume correction, stock-count direction correction, and related audit-compatible service behavior are baseline dependencies (not optional guidance).

### allowed downstream usage
- Later steps may read inventory balances and ledger traces.
- Later steps may reference lot/serial/reservation/transfer/count/cost-layer records.
- Later steps may invoke STEP3 service-layer operations for inventory movement workflows.
- Later steps may attach document workflows to STEP3 reference-document linkage patterns.
- Later steps may expose STEP3 capabilities through per-app `api/` adapters without redefining inventory ownership.

### forbidden downstream changes
- Do not duplicate STEP3 inventory engine models in later steps.
- Do not move STEP3 workflow logic into `backend/apps/material/**`.
- Do not bypass ledger/service-layer pattern with direct balance mutation in controllers/views/APIs.
- Do not redesign stock balance as a parallel source of truth independent from STEP3 service behavior.
- Do not create reverse dependency from STEP3 to later operational steps.
- Do not weaken company-scope, permission, module-guard, audit, or append-only inventory semantics.
- Do not treat unfinished future inventory capabilities as already frozen.

## 7. STEP4_PURCHASE_ENGINE (Frozen)
### status
frozen

### owned scope
- Purchase app ownership in `backend/apps/purchase/**`.
- Entity ownership includes:
  - `Vendor`
  - `VendorHistory`
  - `RFQTask`
  - `RFQLine`
  - `RFQQuote`
  - `PurchaseOrder`
  - `PurchaseOrderLine`
  - `GoodsReceipt`
  - `GoodsReceiptLine`
  - `IQCRecord`
  - `InvoiceMatch` (purchase-side matching support / placeholder scope only; not accounting ownership)

### depends on
- STEP1_KERNEL:
  - company scope and RBAC contracts,
  - module guard,
  - audit pipeline,
  - shared service-layer base,
  - document-state lifecycle contracts.
- STEP2_MASTER_DATA:
  - `Material`, `Warehouse`, and related master data by reference only.
- STEP3_INVENTORY_ENGINE:
  - inventory service boundary for stock side effects,
  - ledger posting and inventory consistency ownership.

### forbidden downstream behavior
- Do not duplicate STEP2 master data in STEP4.
- Do not create parallel `Material` / `Warehouse` / `BinLocation`-like master tables in STEP4.
- Do not move purchase workflow ownership into STEP2 or STEP3 apps.
- Do not implement direct stock-balance mutation or inventory-calculation logic inside STEP4.
- Do not take over accounting ownership beyond AP matching placeholder/support scope.
- Do not introduce reverse dependency from STEP1/STEP2/STEP3 back to STEP4.
- Do not bypass shared document lifecycle conventions with isolated ad hoc workflow semantics.

### document / workflow contract
- Purchase documents must remain company-scoped.
- Permission and module-guard compatibility with STEP1 contracts is required.
- Audit compatibility for purchase workflows is required.
- `PurchaseOrder`, `GoodsReceipt`, and related documents must remain compatible with shared document-state transition patterns.
- `GoodsReceipt` stock effects must go through STEP3 inventory ownership boundary and service orchestration.

### downstream rule
- STEP5+ may depend on STEP4 purchase entities/services.
- STEP5+ must not rewrite STEP4 ownership boundaries.
- STEP5+ integration with purchase records must use references and service boundaries.
- STEP5+ must not move STEP4 purchase workflows into non-purchase domains.

## 8. STEP5_SALES_ENGINE (Frozen)
### status
frozen

### owned scope
- Sales app ownership in `backend/apps/sales/**`.
- Entity and workflow ownership includes:
  - `Customer`
  - `CustomerPriceList`
  - `PricingRule`
  - `SalesQuote`
  - `SalesQuoteLine`
  - `SalesOrder`
  - `SalesOrderLine`
  - `Shipment`
  - `ShipmentLine`
  - `POD`
  - `ShipmentStatusEvent`
  - `RMA`
  - `RMALine`

### depends on
- STEP1_KERNEL:
  - company scope and RBAC contracts,
  - module guard,
  - audit pipeline,
  - shared service-layer base,
  - document-state lifecycle contracts.
- STEP2_MASTER_DATA:
  - reference-only usage of `Material`, `Warehouse`, `WarehouseZone`, and `BinLocation`.
- STEP3_INVENTORY_ENGINE:
  - reservation and stock-ledger services,
  - inventory updates triggered by shipment and RMA workflows.
- STEP4_PURCHASE_ENGINE:
  - optional purchase-record references (for example, Sales Order linkage to Purchase Order) without taking accounting ownership.

### forbidden downstream behavior
- Do not duplicate `Material` / `Warehouse` / `BinLocation` or related STEP2 master-data entities.
- Do not move purchase, inventory, or material workflow ownership into STEP5.
- Do not implement direct stock-balance mutation or inventory-calculation logic inside STEP5.
- Do not take over accounting ownership beyond sales-domain scope (including purchase- or inventory-side financial ownership).
- Do not introduce reverse dependency from STEP1/STEP2/STEP3/STEP4 back to STEP5.

### document / workflow contract
- Sales documents must remain company-scoped.
- Permission and module-guard compatibility with STEP1 contracts is required.
- Audit compatibility for sales workflows is required.
- `SalesQuote`, `SalesOrder`, `Shipment`, and `RMA` must use the shared document-state transition service for lifecycle transitions.

### downstream rule
- STEP6+ may depend on STEP5 sales entities and workflows.
- STEP6+ must not rewrite STEP5 ownership boundaries.
- STEP6+ integration with STEP5 records must use references and service boundaries.
- STEP6+ must not move STEP5 workflows into non-sales domains or other business areas.
- Once STEP5 is frozen, ownership boundaries and fundamental sales workflows are stable unless explicitly revised by a future frozen-contract update.

## 9. STEP6_LOGISTICS_ENGINE (Frozen)
### status
frozen

### owned scope
- Logistics app ownership in `backend/apps/logistics/**`.
- Entity and workflow ownership includes:
  - `TransportOrder`
  - `TransportRecoveryLine`
  - `ShipmentTrackingEvent`
  - `ContainerRecoveryPlan`
  - `ContainerRecoveryLine`
  - `FreightCharge`
  - `InsurancePolicy`

### depends on
- STEP1_KERNEL:
  - company scope and RBAC contracts,
  - module guard,
  - audit pipeline,
  - shared service-layer base,
  - shared document-state lifecycle contracts and transition logging infrastructure.
- STEP2_MASTER_DATA:
  - `Material`, `Warehouse`, `WarehouseZone`, and `BinLocation` by reference only where required.
- STEP3_INVENTORY_ENGINE:
  - inventory service boundary for logistics-triggered stock side effects,
  - reservation / ledger / movement consistency ownership remains in STEP3.
- STEP4_PURCHASE_ENGINE:
  - purchase-side references only where required by freight, inbound logistics, or procurement-linked logistics scenarios,
  - no purchase workflow takeover.
- STEP5_SALES_ENGINE:
  - sales-side references for sales-to-logistics linkage (including shipment and sales-order orchestration) by reference only,
  - no sales workflow takeover.

### forbidden downstream behavior
- Do not duplicate STEP2 master data in STEP6.
- Do not create parallel material / warehouse / bin / customer / shipment master tables in STEP6.
- Do not move logistics workflow ownership into STEP2, STEP3, STEP4, or STEP5 apps.
- Do not implement direct stock-balance mutation or inventory-calculation logic inside STEP6.
- Do not take over accounting ownership merely because freight or insurance records exist in STEP6.
- Do not introduce reverse dependency from STEP1/STEP2/STEP3/STEP4/STEP5 back to STEP6.
- Do not bypass shared document lifecycle conventions with a parallel kernel-like state machine.
- Do not reinterpret sales, purchase, or inventory records as STEP6-owned documents.

### document / workflow contract
- STEP6 records must remain company-scoped.
- Permission and module-guard compatibility with STEP1 contracts is required.
- Audit compatibility for logistics workflows is required.
- Logistics document/workflow transitions must remain compatible with shared document-state lifecycle conventions.
- STEP6 may implement service-level workflow progression, but must not redefine kernel document-state ownership.
- Any inventory side effects triggered by logistics actions must go through STEP3 inventory ownership boundary and service orchestration.
- Any sales-to-logistics linkage must remain reference/service-boundary based and must not pull STEP5 ownership into STEP6.
- Any purchase-linked freight or inbound logistics linkage must remain reference/service-boundary based and must not pull STEP4 ownership into STEP6.

### downstream rule
- STEP7+ may depend on STEP6 logistics entities/services.
- STEP7+ must not rewrite STEP6 ownership boundaries.
- STEP7+ integration with logistics records must use references and service boundaries.
- STEP7+ must not move STEP6 logistics workflows into non-logistics domains.

## 10. STEP7_PRODUCTION_ENGINE (Frozen)
### status
frozen

### ownership
- STEP7 owns production engine behavior only.
- STEP7 app ownership is `backend/apps/production/**`.
- Earlier steps must not own production workflow logic.
- STEP7 must not leak production workflow logic into material / inventory / purchase / sales / logistics apps.

### stable entities
- Document-like main object:
  - `ManufacturingOrder` (primary production document in STEP7).
- Supporting entities / records:
  - `BOM`
  - `BOMLine`
  - `ProductionPlan`
  - `MOIssueLine`
  - `MOReceiptLine`
  - `ProductionQC`
  - `IoTDevice`
  - `IoTMetric`
- Not currently frozen as unified document-state main objects:
  - `ProductionPlan`
  - `ProductionQC`
  - `IoTDevice`
  - `IoTMetric`

### manufacturing order primary-document contract
- `ManufacturingOrder` is the primary production document for STEP7.
- `ManufacturingOrder.status` is aligned to unified `DOC_STATUS` (`DRAFT`, `SUBMITTED`, `CONFIRMED`, `COMPLETED`, `CANCELLED`).
- `ManufacturingOrder` lifecycle transitions must use `DocumentStateTransitionService`.
- Direct status mutation that bypasses transition service is not an allowed workflow path.
- Later steps must not bypass transition service to manipulate `ManufacturingOrder` status.

### manufacturing order state-machine contract
- Frozen status set: `DRAFT` / `SUBMITTED` / `CONFIRMED` / `COMPLETED` / `CANCELLED`.
- Frozen transition baseline:
  - `DRAFT -> SUBMITTED | CANCELLED`
  - `SUBMITTED -> CONFIRMED | CANCELLED`
  - `CONFIRMED -> COMPLETED | CANCELLED`
  - `COMPLETED -> CANCELLED`
  - `CANCELLED` terminal (no outgoing transition).
- Transition path is guarded by:
  - module guard and company module enablement,
  - permission checks,
  - company scope lookup,
  - transition logging and audit hooks.
- `issue_material` and `receipt_finished_goods` are state-guarded and are blocked at least in `DRAFT`, `COMPLETED`, `CANCELLED`.
- After `COMPLETED` or `CANCELLED`, key inventory-affecting production actions must not continue.

### production-mode (MTS / MTO) contract
- `ManufacturingOrder` owns `production_mode` with at least:
  - `MTS` (`mts`, make-to-stock),
  - `MTO` (`mto`, make-to-order).
- `MTO` requires linked `sales_order`.
- `MTO` requires product-material alignment with linked `SalesOrderLine.material`.
- `MTO` issue flow requires active reservation and strict quantity alignment (`issued_qty == reservation.qty`).
- `MTS` cannot masquerade as sales-driven order (`MTS` forbids `sales_order` linkage).
- Later steps must not weaken MTS/MTO constraints above.

### inventory / reservation boundary contract (STEP3 reuse only)
- STEP7 does not own inventory ledger / reservation / balance engine.
- STEP7 must not duplicate or re-implement inventory engine behavior inside production app.
- Inventory side effects from production must go through STEP3 frozen service boundaries.
- `issue_material` and `receipt_finished_goods` must post movements through STEP3 services (`ReservationService`, `StockLedgerService`).
- Reservation consume semantics used by STEP7 are strict-match semantics, not partial-consume semantics:
  - when a reservation is consumed by MO issue, `issued_qty` must strictly match reservation quantity semantics.
- Later steps must not introduce parallel reservation-consume logic inside STEP7.

### service-layer contract
- STEP7 business workflow entrypoints are service-owned boundaries in `backend/apps/production/services.py`.
- Production core workflow logic must not be moved into model `save`, admin, or controller/view layers.
- Frozen service-owned behaviors include:
  - create BOM,
  - create/update `ProductionPlan`,
  - create/transition `ManufacturingOrder`,
  - `issue_material`,
  - `receipt_finished_goods`,
  - create `ProductionQC`,
  - register `IoTDevice`,
  - record `IoTMetric`.

### company-scope contract
- STEP7-related object access must stay inside company scope.
- Service layer must use scoped lookup (`active().for_company(...)`) for referenced entities.
- Cross-company references are invalid for production workflow operations.
- Key models keep minimal data-integrity protection via model validation (`clean` / `full_clean`) to reduce dirty writes that bypass service-level checks.
- Later steps must not depend on cross-company references "accidentally working".

### dependency direction contract
- STEP7 may depend on STEP1–STEP6 contracts.
- STEP1–STEP6 must not depend on STEP7.
- STEP7 may reference STEP2 master data (`Material`, `Warehouse`).
- STEP7 may call STEP3 services for inventory and reservation side effects.
- STEP7 may reference STEP5 sales documents for MTO linkage.
- STEP7 must not back-inject production workflow ownership into earlier-step apps.

### deferred / not frozen in STEP7
- `ProductionPlan` is not frozen as a unified document-state-machine main object in current STEP7 baseline.
- `ProductionQC` is not frozen as a unified document-state-machine main object.
- `IoTDevice` / `IoTMetric` are frozen as entities and service entrypoints only; deep IoT ingestion/automation platform integration is deferred.
- STEP8 accounting postings for production/inventory financial impacts are deferred.
- STEP9 automation/orchestration over production workflow is deferred.
- STEP10 platform-level abstractions and cross-domain orchestration framework are deferred.

## 11. Inherited Rules for All Later Steps
- Dependency direction is one-way: earlier frozen steps -> later steps only.
- Company scope is mandatory for business records and request handling.
- Service-layer pattern is required; downstream business logic belongs in services.
- Permission and module guard compatibility must be maintained.
- Audit compatibility is required for critical operations and transitions.
- Frozen entities must be reused as stable references instead of re-modeled.
- Workflow backflow into earlier frozen domains is prohibited.
- Business app API surfaces are incrementally extensible and are not globally frozen by root API foundation alone.

## 12. Downstream Implementation Rule
- STEP3+ must use completed steps as frozen dependencies.
- Extend capabilities through new apps and new services in later steps.
- Do not rewrite earlier-step ownership boundaries unless a compatibility fix is explicitly required and reported.
