from django.db import transaction

from audit.services import AuditService
from doc.models import DocumentStateMachineDef, DocumentTransitionLog
from shared.constants.document import DOC_STATUS
from shared.constants.permissions import PERMISSION_CODES
from shared.exceptions import BusinessRuleError, ValidationError
from shared.services.base import BaseService


class DocumentStateTransitionService(BaseService):
    DEFAULT_TRANSITIONS = {
        DOC_STATUS.DRAFT: {
            DOC_STATUS.SUBMITTED: PERMISSION_CODES.DOC_SUBMIT,
            DOC_STATUS.CANCELLED: PERMISSION_CODES.DOC_CANCEL,
        },
        DOC_STATUS.SUBMITTED: {
            DOC_STATUS.CONFIRMED: PERMISSION_CODES.DOC_CONFIRM,
            DOC_STATUS.CANCELLED: PERMISSION_CODES.DOC_CANCEL,
        },
        DOC_STATUS.CONFIRMED: {
            DOC_STATUS.COMPLETED: PERMISSION_CODES.DOC_COMPLETE,
            DOC_STATUS.CANCELLED: PERMISSION_CODES.DOC_CANCEL,
        },
        DOC_STATUS.COMPLETED: {
            DOC_STATUS.CANCELLED: PERMISSION_CODES.DOC_CANCEL_COMPLETED,
        },
        DOC_STATUS.CANCELLED: {},
    }

    def validate_transition(self, *, document_type: str, from_state: str, to_state: str) -> str:
        transition = DocumentStateMachineDef.objects.filter(
            document_type=document_type,
            from_state=from_state,
            to_state=to_state,
            is_active=True,
        ).first()
        if transition:
            if not transition.permission_code:
                raise ValidationError(
                    f"Transition permission_code is required: {from_state} -> {to_state}"
                )
            return transition.permission_code

        default_transitions = self.DEFAULT_TRANSITIONS.get(from_state, {})
        permission_code = default_transitions.get(to_state)
        if not permission_code:
            raise ValidationError(f"Invalid transition: {from_state} -> {to_state}")

        return permission_code

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

        permission_code = self.validate_transition(
            document_type=document_type,
            from_state=from_state,
            to_state=to_state,
        )
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
