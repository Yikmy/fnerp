from enum import StrEnum


class PERMISSION_CODES(StrEnum):
    DOC_SUBMIT = "doc.document.submit"
    DOC_CONFIRM = "doc.document.confirm"
    DOC_COMPLETE = "doc.document.complete"
    DOC_CANCEL = "doc.document.cancel"
