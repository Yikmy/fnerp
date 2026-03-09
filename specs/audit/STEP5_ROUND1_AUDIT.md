# STEP5 Round-1 Audit Report

## Scope
- Repository: `Yikmy/fnerp`
- Evaluated implementation: first STEP5 sales app submission (`backend/apps/sales/**` and minimal wiring constants/settings)
- Inputs reviewed (priority): `specs/FROZEN.md`, STEP5 node specs/tasks/checklists.

## 1. Compliance Summary
- **Conclusion:** STEP5 is **mostly structurally aligned** with frozen boundaries.
- **Main risk:** missing STEP5-specific tests and missing API-level permission guard validation for sales endpoints (no sales endpoints currently exist).

## 2. Frozen Contract Compliance
### Respected
- Implemented STEP5 in a **new app** (`apps.sales`).
- Reused STEP1 patterns (service layer, module guard, RBAC checks, audit hooks, doc transition service).
- Reused STEP2 masters by FK reference (Material/Warehouse), without duplicating STEP2 ownership.
- Reused STEP3 inventory behavior via service boundary (`ReservationService`, `StockLedgerService`) rather than direct stock mutation.
- No workflow logic introduced into STEP2/STEP3/STEP4 ownership folders.

### Drift / Gaps
- No direct STEP4 linkage is required by current STEP5 specs; none implemented (acceptable).
- Sales line model consistency differs (`SalesQuoteLine` uses `models.Model` while others use `BaseModel`). This is not a hard spec violation, but it weakens uniform audit/company metadata posture.

## 3. Security & Permissions
### Good
- Sales services perform module checks and permission checks before writes.
- Company-scoped lookup patterns are used in services.
- Cross-company validation exists on model `clean()` methods.

### Risks
- No sales API routes are implemented, so endpoint guard behavior is not yet auditable for STEP5 API surface.
- Reservation/shipment partial-consume semantics are simplistic and may cause business-level mismatch in multi-shipment scenarios.

## 4. Functional Coverage
- Implemented entities per node specs:
  - Customer
  - CustomerPriceList / PricingRule
  - SalesQuote / SalesQuoteLine
  - SalesOrder / SalesOrderLine
  - Shipment / ShipmentLine / POD / ShipmentStatusEvent
  - RMA / RMALine
- Required fields from specs are present.
- SalesOrder confirmation integrates reservation creation.
- Shipment and RMA integrate stock ledger postings through STEP3 services.

## 5. Documentation & Workflow Compliance
- Uses shared document state transition service for quote/order/shipment/rma transitions.
- No custom parallel state machine introduced.
- `approval_status` exists for quote as requested.

## 6. Testing Validation
- **Gap:** no sales-domain tests were added for models/services/workflows.
- **Gap:** no permission security tests for sales flows.
- Existing project tests do not cover STEP5 behavior.

## 7. Minimal Fixes (Actionable)
1. Add `backend/apps/sales/tests.py` with service-flow tests:
   - order confirm creates reservations,
   - shipment complete writes stock ledger + consumes reservation,
   - rma complete writes stock ledger IN,
   - invalid state transition rejection.
2. Add permission-denied tests for each sales service create/transition action.
3. Add company-scope leakage tests (cannot access cross-company customer/material/order).
4. Optional hardening: convert `SalesQuoteLine` to `BaseModel` for consistent audit/company metadata.
5. Optional hardening: enforce non-overship against reserved/order remaining quantities for multi-shipment scenarios.

## 8. Final Decision
- **Not yet ready for next phase without follow-up hardening.**
- Architecture/boundary alignment is acceptable, but security/test assurance is insufficient for a stable frozen-step baseline.
