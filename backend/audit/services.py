from audit.models import AuditEvent, AuditFieldDiff


class AuditService:
    @staticmethod
    def _client_ip(request) -> str | None:
        if request is None:
            return None
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    @classmethod
    def log_event(
        cls,
        *,
        actor_id,
        company_id,
        action: str,
        resource_type: str,
        resource_id,
        request=None,
        metadata: dict | None = None,
        field_diffs: list[dict] | None = None,
    ) -> AuditEvent:
        event = AuditEvent.objects.create(
            actor_id=actor_id,
            company_id=company_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            ip=cls._client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
            metadata=metadata or {},
        )

        for diff in field_diffs or []:
            AuditFieldDiff.objects.create(
                event=event,
                field=diff.get("field", ""),
                old_value=str(diff.get("old_value", "")),
                new_value=str(diff.get("new_value", "")),
            )

        return event

    @classmethod
    def log_crud(
        cls,
        *,
        actor_id,
        company_id,
        operation: str,
        resource_type: str,
        resource_id,
        request=None,
        field_diffs: list[dict] | None = None,
    ) -> AuditEvent:
        return cls.log_event(
            actor_id=actor_id,
            company_id=company_id,
            action=f"crud.{operation}",
            resource_type=resource_type,
            resource_id=resource_id,
            request=request,
            field_diffs=field_diffs,
        )

    @classmethod
    def log_state_transition(
        cls,
        *,
        actor_id,
        company_id,
        resource_type: str,
        resource_id,
        from_state: str,
        to_state: str,
        request=None,
    ) -> AuditEvent:
        return cls.log_event(
            actor_id=actor_id,
            company_id=company_id,
            action="state.transition",
            resource_type=resource_type,
            resource_id=resource_id,
            request=request,
            metadata={"from_state": from_state, "to_state": to_state},
            field_diffs=[{"field": "status", "old_value": from_state, "new_value": to_state}],
        )
