# Company Scope & Multi-Tenant Spec

## 1. Purpose

Define how the ERP system enforces **multi-company isolation**.

This document ensures:

- strict data separation
- secure multi-tenant architecture
- consistent company context across requests

---

# 2. Multi-Tenant Concept

The ERP system is a **multi-tenant system**.

Tenant = Company

Each company operates as an isolated data domain.

All business records must belong to a company.

Example tables:

- purchase_order
- sales_order
- stock_ledger
- inventory_balance

Each must contain:

company_id

---

# 3. Company Scope

Each request operates under a **single active company**.

This context is called:

Company Scope

Example:

User: Tom

Membership:
- Company A
- Company B

Active Scope:
Company A

All operations run within this scope.

---

# 4. Request Processing Flow

Frontend Request

↓

Authentication

↓

Resolve Company Scope

↓

Verify Company Membership

↓

Permission Guard

↓

Service Layer

↓

Database Query

---

# 5. Company Scope Resolution

Company scope can be provided by:

Header:
X-Company-ID

Example:

X-Company-ID: company_uuid

Alternative sources:

- JWT payload
- session context
- API path parameter

---

# 6. Security Verification

Company scope must NEVER be trusted directly.

After receiving the company_id the system must verify:

User ∈ CompanyMembership

If user does not belong to that company:

Return HTTP 403.

This prevents users from manually modifying headers to access other companies.

---

# 7. Database Isolation Rule

All queries must include:

WHERE company_id = current_company

Example:

SELECT * FROM purchase_order
WHERE company_id = current_company

This rule prevents:

- cross-company data leaks
- accidental query mistakes
- developer errors

---

# 8. Model Design Requirement

All business tables must contain:

company_id

Example model fields:

id
company_id
created_at
created_by
updated_at

System-level tables may omit company_id.

Examples:

- user
- permission
- role

---

# 9. Company Membership Model

Relationship structure:

User
↓
CompanyMembership
↓
Company
↓
Role

Example:

User Tom

CompanyMembership:
- Company A → SalesManager
- Company B → WarehouseAdmin

---

# 10. Company Switching

Frontend should provide **company switch UI**.

Example:

Top Navigation:

Current Company: A

User selects:

Switch → Company B

After switching:

All API requests use:

X-Company-ID = B

---

# 11. Cross-Company Operations

Cross-company queries are normally forbidden.

Exceptions:

System Admin
Group Reports
Multi-company dashboards

These features must explicitly specify:

company_ids[]

Example:

GET /reports/sales?companies=A,B,C

---

# 12. Logging

Every request log should include:

user_id
company_id
action
timestamp

This ensures traceability.

---

# 13. Design Goals

This mechanism guarantees:

- strong tenant isolation
- scalable SaaS architecture
- safe multi-company operations
- developer-friendly query patterns
