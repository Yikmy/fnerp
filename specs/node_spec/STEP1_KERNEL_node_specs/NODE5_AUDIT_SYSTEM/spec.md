# Audit System Specification

## Purpose

Provide full traceability.

## AuditEvent

Fields:

actor
action
resource_type
resource_id
timestamp
ip
user_agent

## AuditFieldDiff

Records field changes.

Fields:

field
old_value
new_value