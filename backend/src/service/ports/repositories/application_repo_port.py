from uuid import UUID
from abc import ABC, abstractmethod

from backend.src.domain.models import Application, ScreeningStatus

class ApplicationRepositoryPort(ABC):
    @abstractmethod
    def create(self, application: Application) -> Application:
        pass

    @abstractmethod
    def find_by_id(self, application_id: UUID) -> Application | None:
        pass

    @abstractmethod
    def find_by_jamb_registration_number(self, jamb_registration_number: str) -> Application | None:
        pass

    @abstractmethod
    def find_by_program_and_screening_status(self, program_id: UUID, screening_status: ScreeningStatus) -> list[Application]:
        pass

    @abstractmethod
    def find_by_program_and_indigene_status(self, program_id: UUID, is_indegene: bool) -> list[Application]:
        pass

    @abstractmethod
    def find_by_program(self, program_id: UUID) -> list[Application]:
        pass

    @abstractmethod
    def count_by_program_and_indegene_claim(self, program_id: UUID, indigene_status: bool) -> int:       
        pass

    @abstractmethod
    def update_applicant_info(self, application: Application) -> Application:
        pass

    @abstractmethod
    def update_screening_status(self, application: Application) -> Application:
        pass

    @abstractmethod
    def delete(self, application_id: UUID) -> bool:
        pass