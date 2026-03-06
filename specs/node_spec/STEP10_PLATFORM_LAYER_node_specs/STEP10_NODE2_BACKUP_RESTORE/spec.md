
# Backup Restore Specification

## Model: BackupJob

Fields:

id
mode
status
started_at
finished_at
snapshot_meta_json
storage_uri
error

## Model: RestoreJob

Fields:

id
backup_job_id
status
strategy
started_at
finished_at
error

## Modes

full
incremental
