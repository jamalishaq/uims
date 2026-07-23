from typing import Literal

from .base import NotFoundException, ConflictException, ValidationException, BusinessRuleViolationException

class ApplicationNotFoundException(NotFoundException):
    code = "ADMISSION_APPLICATION_NOT_FOUND"

    def __init__(self, application_id: str):
        self.application_id = application_id
        super().__init__(f"Admission application {application_id} was not found.")


class DuplicateApplicationException(ConflictException):
    code = "ADMISSION_DUPLICATE_APPLICATION"

    def __init__(self, jamb_registration_number: str, existing_application_id: str):
        self.jamb_registration_number = jamb_registration_number
        self.existing_application_id = existing_application_id
        super().__init__(
            f"An application already exists for JAMB registration number "
            f"{jamb_registration_number} (application {existing_application_id})."
        )


class NotFirstChoiceException(BusinessRuleViolationException):
    code = "ADMISSION_NOT_FIRST_CHOICE"

    def __init__(self, jamb_registration_number: str):
        self.jamb_registration_number = jamb_registration_number
        super().__init__(
            f"Candidate {jamb_registration_number} did not select LASU as their "
            f"first choice and cannot be screened."
        )


class InvalidOLevelGradesException(ValidationException):
    code = "ADMISSION_INVALID_OLEVEL_GRADES"

    def __init__(self, olevel_grades: list[dict], reason: str):
        self.olevel_grades = olevel_grades
        self.reason = reason
        super().__init__(f"O'Level grades are invalid: {reason}")


class AdmissionQuotaExceededException(BusinessRuleViolationException):
    code = "ADMISSION_QUOTA_EXCEEDED"

    def __init__(
        self,
        program_id: str,
        indigene_status: Literal["indigene", "non-indigene"],
        current_count: int,
        quota_limit: int,
    ):
        self.program_id = program_id
        self.indigene_status = indigene_status
        self.current_count = current_count
        self.quota_limit = quota_limit
        super().__init__(
            f"Admitting this applicant would exceed the {indigene_status} "
            f"quota for program {program_id} ({current_count}/{quota_limit})."
        )


class IIVCVerificationPendingException(BusinessRuleViolationException):
    code = "ADMISSION_IIVC_VERIFICATION_PENDING"

    def __init__(self, application_id: str, iivc_status: Literal["pending"] = "pending"):
        self.application_id = application_id
        self.iivc_status = iivc_status
        super().__init__(
            f"Application {application_id} cannot be admitted until IIVC "
            f"indigene verification concludes (current status: {iivc_status})."
        )


class ApplicationAlreadyDecidedException(ConflictException):
    code = "ADMISSION_APPLICATION_ALREADY_DECIDED"

    def __init__(self, application_id: str, current_status: str):
        self.application_id = application_id
        self.current_status = current_status
        super().__init__(
            f"Application {application_id} has already been decided "
            f"(current status: {current_status})."
        )
