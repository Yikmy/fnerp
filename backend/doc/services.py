from django.db import transaction

from audit.services import AuditService
from doc.models import DocumentStateMachineDef, DocumentTransitionLog
from shared.constants.document import DOC_STATUS
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError, ValidationError
from shared.services.base import BaseService


class DocumentStateTransitionService(BaseService):
    DEFAULT_TRANSITIONS = {
        DOC_STATUS.DRAFT: {DOC_STATUS.SUBMITTED, DOC_STATUS.CANCELLED},
        DOC_STATUS.SUBMITTED: {DOC_STATUS.CONFIRMED, DOC_STATUS.CANCELLED},
        DOC_STATUS.CONFIRMED: {DOC_STATUS.COMPLETED, DOC_STATUS.CANCELLED},
        DOC_STATUS.COMPLETED: {DOC_STATUS.CANCELLED},
        DOC_STATUS.CANCELLED: set(),
    }

    def validate_transition(self, *, document_type: str, from_state: str, to_state: str) -> DocumentStateMachineDef | None:
        transition = DocumentStateMachineDef.objects.filter(
            document_type=document_type,
            from_state=from_state,
            to_state=to_state,
            is_active=True,
        ).first()
        if transition:
            return transition

        allowed_next_states = self.DEFAULT_TRANSITIONS.get(from_state, set())
        if to_state not in allowed_next_states:
            raise ValidationError(f"Invalid transition: {from_state} -> {to_state}")

        return None

    @transaction.atomic
    def transition(
        self,
        *,
        user,
        company_id,
        document,
        document_type: str,
        to_state: str,
        notes: str = "",
        request=None,
    ):
        from_state = getattr(document, "status", None)
        if from_state is None:
            raise BusinessRuleError("Document has no status field")

        transition_def = self.validate_transition(
            document_type=document_type,
            from_state=from_state,
            to_state=to_state,
        )

        permission_code = transition_def.permission_code if transition_def else ""
        if not permission_code and from_state == DOC_STATUS.COMPLETED and to_state == DOC_STATUS.CANCELLED:
            permission_code = PERMISSION_CODES.DOC_CANCEL_COMPLETED

        if permission_code:
            self.ensure_permission(user=user, company_id=company_id, permission_code=permission_code)

        document.status = to_state
        document.save(update_fields=["status", "updated_at"])

        DocumentTransitionLog.objects.create(
            company_id=company_id,
            document_type=document_type,
            document_id=document.id,
            from_state=from_state,
            to_state=to_state,
            operator_id=getattr(user, "id", None),
            notes=notes,
        )

        AuditService.log_state_transition(
            actor_id=getattr(user, "id", None),
            company_id=company_id,
            resource_type=document_type,
            resource_id=document.id,
            from_state=from_state,
            to_state=to_state,
            request=request,
        )

        return document
