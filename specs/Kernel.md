# ERP Kernel Freeze Specification

Version: 1.0  
Status: **FROZEN**  
Scope: `STEP1_KERNEL`  
Location: `/backend/apps/*` and `/backend/shared/*`

---

# 1. Purpose

This document defines the **Kernel Freeze Policy** for the ERP backend.

The Kernel implemented in **STEP1** is considered **architecturally stable** and must serve as the **permanent foundation of the system**.

From this point forward:

- Kernel modules **must not be modified**
- All future development must **depend on the Kernel**
- Kernel architecture must remain **stable and unchanged**

This ensures long-term system stability and prevents architectural drift.

---

# 2. Kernel Scope

The ERP Kernel consists of the following modules.

```

backend/
apps/
core/
company/
auth/
doc/
audit/
config/

```
shared/
```

```

These directories together form the **ERP Kernel Layer**.

Kernel responsibilities include:

- multi-company isolation
- RBAC permission system
- module enablement guard
- document state machine
- audit logging
- shared infrastructure
- service layer base classes

---

# 3. Kernel Capabilities

The Kernel provides the following core infrastructure.

---

## 3.1 Multi-Company Isolation

The system is **multi-tenant** where each tenant is a **Company**.

All requests must operate under a **single company scope**.

Company scope resolution sources:

X-Company-ID header
Session context
JWT payload
URL path parameter


Validation rule:

User must belong to CompanyMembership


If validation fails:

HTTP 403


All business tables must contain:

company_id


All queries must enforce company filtering.

---

## 3.2 RBAC Permission System

The system implements **Role-Based Access Control (RBAC)**.

Core models:

User
Role
Permission
RolePermission


Permission naming format:

module.resource.action


Examples:

purchase.po.create
purchase.po.submit
inventory.stock.adjust
sales.order.confirm


Permission validation requires:

Module enabled
AND
Role permission exists


---

## 3.3 Module Enablement Guard

Companies may enable or disable system modules.

Model:

```

CompanyModule

```

Fields:

```

company_id
module_code
is_enabled

```

Request processing must include module validation.

Request flow:

```

Authentication
→ CompanyScope
→ ModuleGuard
→ PermissionGuard
→ Service

```

---

## 3.4 Document State Machine

All ERP documents must follow a unified lifecycle.

Standard states:

```

DRAFT
SUBMITTED
CONFIRMED
COMPLETED
CANCELLED

```

Transitions:

```

DRAFT → SUBMITTED
SUBMITTED → CONFIRMED
CONFIRMED → COMPLETED
ANY → CANCELLED
COMPLETED → CANCELLED (requires permission)

```

Each transition **must define a permission_code**.

Example:

```

doc.submit
doc.confirm
doc.complete
doc.cancel
doc.cancel.completed

```

All transitions must generate:

```

DocumentTransitionLog

```

---

## 3.5 Audit System

All critical operations must be audited.

Audit components:

```

AuditEvent
AuditFieldDiff

```

Audit events include:

```

RequestAudit
CRUD operations
Document state transitions
Configuration changes

```

Recorded fields:

```

actor
action
resource
timestamp
field changes

```

---

## 3.6 Service Layer Architecture

Business logic must reside in the **Service Layer**.

Required flow:

```

View / Controller
↓
Service Layer
↓
Domain Models
↓
Database

```

Direct View → Model access is **not allowed**.

Base infrastructure:

```

BaseService

```

---

## 3.7 Shared Infrastructure

Kernel provides shared base components.

```

BaseModel
BaseService
CompanyQuerySet
ApiException
constants

```

All business modules must depend on these shared components.

---

# 4. Dependency Rules

System dependency direction must always be:

```

Kernel
↓
Business Modules
↓
API Layer

```

Forbidden dependency:

```

Kernel → Business Modules

```

Business modules may depend on Kernel.

Kernel must remain independent.

---

# 5. Kernel Freeze Policy

The Kernel is **frozen**.

The following changes are **NOT allowed**:

- modifying Kernel models
- changing middleware logic
- altering permission architecture
- modifying the document state machine
- changing audit infrastructure
- refactoring shared base classes

Allowed modifications:

```

critical bug fixes
security patches

```

No architectural changes are permitted.

---

# 6. API Layer Policy

The Kernel does not implement API endpoints.

API implementation will be introduced in a later development phase.

Future API structure:

```

backend/api/
router.py
urls.py

```

Each business module will expose:

```

apps/<module>/api_router.py

```

All routers will be registered centrally.

---

# 7. Future Development Phases

The next development phase after Kernel Freeze is:

```

STEP2_MASTER_DATA

```

Modules to implement:

```

UOM
MaterialCategory
Material
Warehouse
BinLocation

```

These modules must depend on the Kernel infrastructure.

Kernel must not be modified during these implementations.

---

# 8. AI Development Rule

All AI coding agents must follow this rule.

Before implementing any feature, AI must:

1. Read `/specs/kernel_freeze.md`
2. Understand the Kernel architecture
3. Use Kernel infrastructure
4. Avoid modifying Kernel modules

If a task requires Kernel modification, it must be rejected.

---

# 9. Final Statement

The ERP Kernel represents the **stable operating foundation** of the backend architecture.

Its stability ensures:

- architectural consistency
- safe modular expansion
- long-term maintainability

All future modules must build upon this Kernel without altering its design.

```

---
