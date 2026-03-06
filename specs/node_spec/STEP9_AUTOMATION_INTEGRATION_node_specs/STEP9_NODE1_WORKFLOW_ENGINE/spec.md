
# Workflow Engine Specification

## WorkflowDef

Fields:

id
name
doc_type
definition_json
enabled

## WorkflowInstance

Fields:

id
workflow_def_id
doc_type
doc_id
status
current_node

## Purpose

Provide configurable approval processes for documents.
