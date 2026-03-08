# API Architecture Specification

## 1. Purpose

This document defines the API architecture for the ERP backend.

Goals:

- add a stable HTTP API layer without breaking frozen kernel boundaries
- keep business logic inside service layer, not inside API views
- unify response structure, error mapping, and session authentication behavior
- support incremental rollout from Kernel -> STEP1 -> STEP3
- enable smoke testing through session/cookie based authentication

This spec is authoritative for API layer design unless a later frozen document explicitly overrides it.

---

## 2. Design Principles

### 2.1 API is an adapter layer
API layer responsibilities are limited to:

- request parsing
- serializer/input validation
- session/auth integration
- company scope extraction
- service invocation
- response formatting
- exception-to-HTTP mapping

API layer must NOT own:

- business rules
- workflow orchestration
- permission semantics
- module guard semantics
- cross-model transactional logic
- audit logic beyond calling service layer

### 2.2 Service-first rule
All non-trivial business behavior must be executed in services.

Views must call service methods.
Views must not implement business workflows directly.

### 2.3 Frozen boundary compatibility
API rollout must preserve existing step ownership:

- STEP1 / Kernel remains foundational
- STEP2 remains master data owner
- STEP3 remains inventory engine owner

API layer may expose these domains, but must not redesign their ownership boundaries.

### 2.4 Minimal kernel intrusion
Root API enablement should require only minimal kernel-level additions:

- root API package and URL wiring
- session/cookie auth wiring
- shared API response helpers
- shared API exception mapping
- optional small API base mixins

Do not move business logic into shared API utilities.

---

## 3. Package Layout

Recommended structure:

```text
backend/
  api/
    __init__.py
    urls.py
    responses.py
    exceptions.py
    base.py

  apps/
    company/
      api/
        __init__.py
        urls.py
        serializers.py
        views.py

    material/
      api/
        __init__.py
        urls.py
        serializers.py
        views.py

    inventory/
      api/
        __init__.py
        urls.py
        serializers.py
        views.py
```

### 3.1 Root `backend/api/`
Root API package is the aggregation and protocol layer only.

Allowed contents:

- global API urls
- response helpers
- API exception mapping
- common base view helpers
- auth/session integration helpers if minimal and generic

Forbidden contents:

- business workflows
- model-specific orchestration for company/material/inventory
- cross-domain God views

### 3.2 Per-app `api/`
Each business app owns its own API adapter layer.

Reason:

- aligns API surface with business boundaries
- prevents one giant `api/views.py`
- keeps serializer and route ownership local to the domain
- avoids later-step backflow into earlier-step modules

---

## 4. URL Architecture

### 4.1 Root URL aggregation
Root API URLs must aggregate per-app routes.

Example shape:

- `/api/auth/...`
- `/api/company/...`
- `/api/material/...`
- `/api/inventory/...`

Root API package should include app URLs, not reimplement app behavior.

### 4.2 Route naming rule
Prefer use-case oriented endpoints over raw CRUD when workflows matter.

Examples:

- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/session/`
- `POST /api/company/companies/`
- `POST /api/material/materials/`
- `POST /api/material/warehouses/`
- `POST /api/inventory/stock-counts/`
- `POST /api/inventory/stock-counts/{id}/lines/`
- `POST /api/inventory/stock-counts/{id}/post/`

### 4.3 No giant global views module
Do not create a single centralized business views file under root API that imports all modules and owns all endpoints.

The root API package aggregates URLs only.

---

## 5. Authentication Strategy

### 5.1 MVP auth mode
MVP API authentication uses Django session authentication with cookies.

Reason:

- already matches current project direction
- lower complexity than JWT
- suitable for admin-style ERP frontend and smoke testing
- easier to validate end-to-end quickly

### 5.2 Required capabilities
The API layer must provide:

- login endpoint that establishes a valid session
- logout endpoint that clears the session
- session introspection endpoint for smoke verification
- cookie-based authenticated requests after login

### 5.3 Session behavior
The system must rely on Django session/cookie behavior rather than ad hoc token transport for MVP.

At minimum:

- successful login returns session-backed authenticated state
- subsequent requests can authenticate through cookies
- logout invalidates the session

### 5.4 CSRF
If session auth is used for browser-style clients, CSRF policy must be explicitly handled.

For MVP, the implementation must choose one of these paths and document it:

- proper CSRF flow for authenticated state-changing endpoints, or
- tightly scoped temporary development/testing handling with clear TODO

Do not silently leave CSRF ambiguous.

---

## 6. Company Scope Handling

### 6.1 Scope source
API requests must carry or resolve company scope consistently according to existing company scope spec.

Preferred request mechanism for app endpoints:

- `X-Company-ID` header

### 6.2 Validation rule
API layer may read company scope input, but must not trust it directly.

Actual enforcement remains in service/domain layer through:

- membership validation
- company-scoped lookups
- service-level checks
- model validation where applicable

### 6.3 API responsibility
Views should extract company_id in a consistent helper/base class.
Views must pass company_id into services explicitly.

Views must not implement custom multi-tenant logic per endpoint.

---

## 7. Permission and Guard Responsibilities

### 7.1 Separation of concerns
The API layer does not own authorization semantics.

Authorization remains split as:

- permission codes: shared constants / RBAC configuration
- permission enforcement: service layer `ensure_permission(...)`
- module availability: service layer module guard
- company isolation: service/domain/model enforcement

### 7.2 API checks
The API layer may require authenticated users, but must not duplicate business permission logic across endpoints.

Views can enforce:

- authenticated session required
- basic request validity

Services must enforce:

- action permission
- module guard
- company scope correctness
- transactional business rules

---

## 8. Response Contract

### 8.1 Success envelope
All successful API responses must use a unified envelope.

Object response:

```json
{
  "success": true,
  "message": "",
  "data": {}
}
```

List response:

```json
{
  "success": true,
  "message": "",
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 0
  }
}
```

### 8.2 Error envelope
All handled API errors must use a unified envelope.

```json
{
  "success": false,
  "error": {
    "code": "business_rule_error",
    "message": "Human readable message",
    "details": {}
  }
}
```

### 8.3 HTTP semantics
Use HTTP status codes correctly in addition to response envelope.

Examples:

- 200 OK: read success / action success
- 201 Created: creation success
- 400 Bad Request: validation/input error
- 401 Unauthorized: unauthenticated
- 403 Forbidden: permission or membership failure
- 404 Not Found: scoped resource missing
- 409 Conflict: business conflict if appropriate

---

## 9. Exception Mapping

A shared API exception mapper must convert core service/domain exceptions into stable HTTP responses.

Examples to map:

- validation errors
- business rule errors
- permission denied
- authentication required
- object not found in scope

Mapping must be centralized in root API layer, not reimplemented per module.

---

## 10. Serializer Rule

Serializers exist to validate and shape HTTP payloads.

Serializers must NOT:

- execute business workflows
- perform multi-step domain orchestration
- replace service validation
- mutate multiple aggregates directly

Serializers may:

- validate request fields
- transform request payload into service kwargs
- shape response data

---

## 11. View Rule

Views should remain thin.

A view should normally:

1. authenticate request
2. parse input serializer
3. extract company scope
4. call one service method
5. format response

Views must not become workflow coordinators.

---

## 12. MVP Rollout Phases

### Phase 1: Root API and session auth
Build only the minimum needed to validate kernel/API foundation:

- root `backend/api/`
- root API URLs
- auth/session endpoints
- shared response helpers
- shared exception mapper

### Phase 2: Kernel smoke
Validate:

- superuser creation
- session login
- authenticated session check
- logout
- company scope transport format

This phase proves API foundation is alive.

### Phase 3: STEP1–STEP3 smoke
Expose only the minimal endpoints required for end-to-end smoke:

- company creation
- material/UoM/category creation as needed
- warehouse creation
- stock count create/add line/post

Do not expose broad CRUD surface before the smoke path is stable.

---

## 13. Kernel Smoke Test Requirements

Before broader business smoke tests, kernel/API smoke must pass.

Minimum smoke path:

1. create superuser
2. login with session/cookie
3. verify authenticated session endpoint
4. logout
5. verify session invalidation

This smoke validates:

- URL wiring
- session auth
- response contract
- root API exception behavior
- minimal kernel/API integration

---

## 14. API Conventions

### 14.1 Naming
- keep route names explicit and domain-oriented
- keep serializer names aligned with use case
- avoid generic names like `CommonView`, `MasterSerializer`, `ApiHandler`

### 14.2 Versioning
For MVP, versioning may be omitted if the API is internal-only and unstable.
If added, prefer `/api/v1/...` at root only.

### 14.3 Pagination
Only list endpoints need `meta`.
Action endpoints should return object envelopes or action-result envelopes.

### 14.4 Dates / UUID / Decimal
Serialization must be stable and frontend-safe.
Do not leak Python-native objects directly.

---

## 15. Forbidden Patterns

The following are explicitly forbidden:

- one giant root API module owning all business views
- business logic in views
- business logic in serializers
- API layer bypassing service layer for workflow actions
- per-module incompatible response shapes
- direct API-layer weakening of company scope enforcement
- duplicating permission logic in views and services
- coupling API rollout to a large auth redesign

---

## 16. Definition of Done for Initial API Foundation

Initial API foundation is considered ready when all are true:

- root `backend/api/` exists
- root URLs aggregate module URLs cleanly
- session login/logout/session-check endpoints exist
- unified success/error response helpers exist
- exception mapping exists
- no business app had to move logic into root API
- kernel smoke test passes

Only after this may STEP1–STEP3 smoke API exposure proceed.

---

## 17. Implementation Guidance Summary

Use this rule of thumb:

- root API = protocol + aggregation
- app API = endpoint ownership
- service layer = business rules
- shared/kernel = foundational primitives only

This preserves modularity while making MVP HTTP validation possible.