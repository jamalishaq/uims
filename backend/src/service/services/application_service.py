from uuid import UUID, uuid4
from typing import Any

from backend.src.domain.models import Application, EntryRoute, IIVCVerificationStatus, ScreeningStatus
from service.ports.repositories import ApplicationRepositoryPort, ProgramRepositoryPort
from domain.exceptions import (
    # ApplicationAlreadyDecidedException,
    ApplicationNotFoundException,
    # AdmissionQuotaExceededException,
    # DuplicateApplicationException,
    # InvalidOLevelGradesException,
    # IIVCVerificationPendingException,
    # NotFirstChoiceException
)

class ApplicationService:
    def __init__(self, application_repo: ApplicationRepositoryPort, program_repo: ProgramRepositoryPort):
        self.application_repo = application_repo
        self.program_repo = program_repo

    # --- Public API Methods ---

    async def submit_application(
        self,
        applicant_details: dict[str, Any], 
        jamb_details: dict[str, Any],
        olevel_grades: dict[str, int], 
        program_id: UUID,
    ) -> Application:
        
        met_requirement = self._verify_requirements(program_id=program_id, jamb_subjects=jamb_details["jamb_scores"].keys(), olevel_subjects=olevel_grades.keys())
        if not met_requirement:
            print("You cannot apply")

        is_indegene = applicant_details["state_of_origin"].upper() == "LAGOS"
        
        new_application = Application(
            application_id=uuid4(),  
            first_name=applicant_details["first_name"],
            last_name=applicant_details["last_name"],
            address=applicant_details["address"],
            phone_number=applicant_details["phone_number"],
            email=applicant_details["email"],
            state_of_origin=applicant_details["state_of_origin"],
            lga_of_origin=applicant_details["lga_of_origin"],
            is_indegene=is_indegene,

            program_id=program_id,
            
            jamb_registration_number=jamb_details["jamb_registration_number"],
            jamb_scores=jamb_details["jamb_scores"],
            jamb_total_score=self._calculate_jamb_total_score(jamb_details["jamb_scores"]),
            jamb_entry_route=EntryRoute(jamb_details["jamb_entry_route"]),
            first_choice_confirmed=jamb_details.get("first_choice_confirmed", True),
            
            olevel_grades=olevel_grades,
            
            aggregate_score=self._calculate_aggregate(jamb_details["jamb_scores"], olevel_grades),
            
            iivc_verification_status=IIVCVerificationStatus.PENDING,
            screening_status=ScreeningStatus.PENDING
        )

        saved_application = await self.application_repo.create(new_application)
        
        return saved_application
    
    async def reject_application(self, application_id: UUID, reason: str) -> Application:
        application = await self.application_repo.find_by_id(application_id)
        if not application:
            raise ApplicationNotFoundException(application_id=str(application_id))

        application.reject_application(reason=reason)

        updated_application = await self.application_repo.update_screening_status(application)

        return updated_application
    
    async def accept_application(self, application_id: UUID) -> Application:
        application = await self.application_repo.find_by_id(application_id)
        if not application:
            raise ApplicationNotFoundException(application_id=str(application_id))

        application.accept_application()

        updated_application = await self.application_repo.update_screening_status(application)

        return updated_application

    async def confrim_application(self, application_id: UUID) -> Application:
        application = await self.application_repo.find_by_id(application_id)
        if not application:
            raise ApplicationNotFoundException(application_id=str(application_id))
        
        application.confrim_application()

        updated_application = await self.application_repo.update_screening_status(application)

        return updated_application
    
    async def waitlist_application(self, application_id: UUID) -> Application:
        application = await self.application_repo.find_by_id(application_id)
        if not application:
            raise ApplicationNotFoundException(application_id=str(application_id))
        
        application.waitlist_application()

        updated_application = await self.application_repo.update_screening_status(application)

        return updated_application
    
    async def edit_application(self, application_id: UUID, changes: dict[str, Any]) -> Application:
        application = await self.application_repo.find_by_id(application_id)
        if not application:
            raise ApplicationNotFoundException(application_id=str(application_id))

        application.edit_application(changes)

        updated_application = await self.application_repo.update_applicant_info(application)

        return updated_application
    
    async def list_applications(self, program_id: UUID, screening_status: str | None = None, is_indegene: bool = False) -> list[Application]:
        if screening_status:
            applications = await self.application_repo.find_by_program_and_screening_status(program_id, ScreeningStatus(screening_status))
        elif is_indegene:
            applications = await self.application_repo.find_by_program_and_screening_status(program_id, is_indegene)
        else:
            applications = self.application_repo.find_by_program(program_id)
        
        return applications

    # --- Helper Methods ---

    def _calculate_jamb_total_score(self, jamb_scores: dict[str, int]) -> int:
        return sum(jamb_scores.values())

    def _calculate_aggregate(self, program_id: UUID, jamb_scores: dict[str, int], olevel_grades: dict[str, int]) -> float:
        program = self.program_repo.get_program_by_id(program_id)
        if not program:
            print("Program do not exist")

        # 1. JAMB Points Calculation
        jamb_total_score = self._calculate_jamb_total_score(jamb_scores)
        jamb_point = jamb_total_score / 8.0 

        # O'Level Grade-to-Point Scale
        grade_scale = {
            "A1": 8, "B2": 7, "B3": 6, "C4": 5, "C5": 4, "C6": 3,
            "D7": 0, "E8": 0, "F9": 0, "ABS": 0
        }

        # Normalize required core subjects for case-insensitive matching
        olevel_required_subjects = {sub.strip().lower() for sub in program.olevel_subject_required}

        # Separators for our two pools
        olevel_required_subjects_points = []
        olevel_elective_subjects_points = []

        # 2. Distribute student grades into Required vs. Elective pools
        for subject, grade in olevel_grades.items():
            points = grade_scale.get(grade.strip().upper(), 0)

            if subject.strip().lower() in olevel_required_subjects:
                olevel_required_subjects_points.append(points)
            else:
                olevel_elective_subjects_points.append(points)

        # 3. Fill the remaining spots from the best of the elective pool
        # For example, if 3 cores are met, we need (5 - 3) = 2 best electives.
        spots_to_fill = max(0, 5 - len(olevel_required_subjects_points))
        
        olevel_elective_subjects_points.sort(reverse=True)
        chosen_electives = olevel_elective_subjects_points[:spots_to_fill]

        # Combine them to get the best 5 relevant subjects total and calculate sum
        final_5_subject_points = olevel_required_subjects_points + chosen_electives
        olevel_points = sum(final_5_subject_points)
        
        # 4. Final Aggregate Calculation
        aggregate = jamb_point + olevel_points

        return round(aggregate, 2)

    def _verify_requirements(
            self, program_id: UUID, 
            jamb_subjects: list[str],
            olevel_subjects: list[str]
    ) -> bool:
        program = self.program_repo.get_program_by_id(program_id)
        
        if not program:
            print("Program do not exist")

        jamb_subjects_required = program.jamb_subject_required
        olevel_subjects_required = program.olevel_subject_required
        
        # Standardize strings to lowercase to prevent case-sensitivity bugs (e.g., "Mathematics" vs "mathematics")
        user_jamb_set = {subject.strip().lower() for subject in jamb_subjects}
        required_jamb_set = {subject.strip().lower() for subject in jamb_subjects_required}
        
        user_olevel_set = {subject.strip().lower() for subject in olevel_subjects}
        required_olevel_set = {subject.strip().lower() for subject in olevel_subjects_required}
        
        # Check if the required subjects are a subset of what the student provided
        jamb_satisfied = required_jamb_set.issubset(user_jamb_set)
        olevel_satisfied = required_olevel_set.issubset(user_olevel_set)
        
        return jamb_satisfied and olevel_satisfied