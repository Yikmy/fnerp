# Company Scope Specification

## Multi-Tenant Design

Tenant = Company

All business data belongs to a company.

Each request must resolve:

current_company

## Scope Resolution

Source:

Header: X-Company-ID

## Security Rule

The system must verify:

User ∈ CompanyMembership

If not:

HTTP 403

## Query Isolation

All queries must include:

company_id = current_company