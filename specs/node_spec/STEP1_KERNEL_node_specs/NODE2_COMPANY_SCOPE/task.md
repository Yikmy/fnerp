# NODE2_COMPANY_SCOPE

## Goal

Implement multi-company isolation.

All requests must operate under a single company scope.

## Required Models

Company
CompanyMembership
CompanyModule

## Required Features

Company scope resolver
Membership validation
Company filtering in QuerySet

## Middleware

Resolve company scope from request header.

Header:

X-Company-ID