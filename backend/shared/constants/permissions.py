from enum import StrEnum


class PERMISSION_CODES(StrEnum):
    DOC_SUBMIT = "doc.submit"
    DOC_CONFIRM = "doc.confirm"
    DOC_COMPLETE = "doc.complete"
    DOC_CANCEL = "doc.cancel"
    DOC_CANCEL_COMPLETED = "doc.cancel.completed"
