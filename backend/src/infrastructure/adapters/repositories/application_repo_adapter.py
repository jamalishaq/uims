from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, OperationalError, DBAPIError

from src.service.ports.repositories import ApplicationRepositoryPort
from src.domain.models import Application, ScreeningStatus
from src.domain.exceptions.application_exception import DuplicateApplicationException, ApplicationNotFoundException
from src.infrastructure.database import DatabaseFactory
from src.infrastructure.database.orms import ApplicationORM
from src.infrastructure.exceptions import QueryTimeoutException
from src.infrastructure.database import with_circuit_breaker, retry_on_transient_db_error

class ApplicationRepositoryAdapter(ApplicationRepositoryPort):
    def __init__(self, db_factory: DatabaseFactory):
        self.db_factory = db_factory

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_create")
    async def create(self, application: Application) -> Application:
        async with self.db_factory.session() as session:
            try:
                new_application = self._to_orm(application=application)
                await session.add(new_application)
                await session.commit()
                await session.refresh(new_application)

                return self._to_domain(new_application)
            except IntegrityError as e:
                if "jamb_registration_number" in str(e.orig):
                    raise DuplicateApplicationException(
                        jamb_registration_number=application.jamb_registration_number,
                        existing_application_id="unknown"
                    ) from e
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_create",
                        timeout_seconds=5.0
                    ) from e
                
                raise


    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_find_by_id")
    async def find_by_id(self, application_id: UUID) -> Application | None:
        async with self.db_factory.session() as session:
            try:
                application_orm = await session.get(ApplicationORM, application_id)

                return self._to_domain(application_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_find_by_id",
                        timeout_seconds=5.0
                    ) from e
                
                raise
    
    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_find_by_registration_number")
    async def find_by_jamb_registration_number(self, jamb_registration_number: str) -> Application | None:
        async with self.db_factory.session() as session:
            try:
                query = select(ApplicationORM).where(ApplicationORM.jamb_registration_number == jamb_registration_number)
                result = await session.execute(query)
                
                application_orm = result.scalar_one_or_none()
                
                return self._to_domain(application_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_find_by_registration_number",
                        timeout_seconds=5.0
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_find_by_program_and_screening_status")
    async def find_by_program_and_screening_status(self, program_id: UUID, screening_status: ScreeningStatus) -> list[Application]:
        async with self.db_factory.session() as session:
            try:
                query = (
                select(ApplicationORM)
                .where(ApplicationORM.program_id == program_id)
                .where(ApplicationORM.screening_status == screening_status)
                )
                result = await session.execute(query)
                applications_orm = result.scalars().all()

                return [self._to_domain(application_orm) for application_orm in applications_orm]
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_find_by_program_and_screening_status",
                        timeout_seconds=5.0
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_find_by_program_and_indigene_status")
    async def find_by_program_and_indigene_status(self, program_id: UUID, is_indegene: bool) -> list[Application]:
        async with self.db_factory.session() as session:
            try:
                query = (
                    select(ApplicationORM)
                    .where(ApplicationORM.program_id == program_id)
                    .where(ApplicationORM.is_indegene == is_indegene)
                )
                result = await session.execute(query)
                applications_orm = result.scalars().all()

                return [self._to_domain(application_orm) for application_orm in applications_orm]
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_find_by_program_and_indigene_status",
                        timeout_seconds=5.0
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_find_by_program")
    async def find_by_program(self, program_id: UUID) -> list[Application]:
        async with self.db_factory.session() as session:
            try:
                query = (
                    select(ApplicationORM)
                    .where(ApplicationORM.program_id == program_id)
                )
                result = await session.execute(query)
                applications_orm = result.scalars().all()

                return [self._to_domain(application_orm) for application_orm in applications_orm]
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_find_by_program",
                        timeout_seconds=5.0
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_count_by_program_and_indegene_claim")
    async def count_by_program_and_indegene_claim(self, program_id: UUID, is_indegene: bool) -> int:
        async with self.db_factory.session() as session:
            try:
                query = (
                    select(func.count())
                    .select_from(ApplicationORM)
                    .where(ApplicationORM.program_id == program_id)
                    .where(ApplicationORM.indegene_claim == is_indegene)
                )
                result = await session.execute(query)

                return result.scalar_one()
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_count_by_program_and_indegene_claim",
                        timeout_seconds=5.0
                    ) from e

                raise
        
    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_update_applicant_info")
    async def update_applicant_info(self, application: Application) -> Application:
        async with self.db_factory.session() as session:
            try:
                updated_application_orm = await self._update(session, application)

                return self._to_domain(updated_application_orm)
            except IntegrityError as e:
                await session.rollback()
                if "jamb_registration_number" in str(e.orig):
                    raise DuplicateApplicationException(
                        jamb_registration_number=application.jamb_registration_number,
                        existing_application_id=str(application.id)
                    ) from e
                raise
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_update_applicant_info",
                        timeout_seconds=5.0
                    ) from e

                raise
        
    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_update_screening_status")
    async def update_screening_status(self, application: Application) -> Application:
        async with self.db_factory.session() as session:
            try:
                updated_application_orm = await self._update(session, application)

                return self._to_domain(updated_application_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_update_screening_status",
                        timeout_seconds=5.0
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="application_delete")
    async def delete(self, application_id: UUID) -> bool:
        async with self.db_factory.session() as session:
            try:
                application_orm = await session.get(ApplicationORM, application_id)

                if application_orm is None:
                    raise ApplicationNotFoundException(application_id=str(application_id))

                await session.delete(application_orm)
                await session.commit()
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="application_delete",
                        timeout_seconds=5.0
                    ) from e

                raise

    async def _update(self, session, application: Application)-> ApplicationORM:
            application_orm = self._to_orm(application)
            merged_orm = await session.merge(application_orm)

            await session.commit()
            await session.refresh(merged_orm)

            return merged_orm

    def _to_domain(self, application_orm: ApplicationORM) -> Application:
        if application_orm is None:
            return None
        
        return Application(
            application_id=application_orm.application_id,
            first_name=application_orm.first_name,
            middle_name=application_orm.middle_name,
            last_name=application_orm.last_name,
            address=application_orm.address,
            phone_number=application_orm.phone_number,
            email=application_orm.email,
            jamb_registration_number=application_orm.jamb_registration_number,
            jamb_scores=application_orm.jamb_scores,
            jamb_total_score=application_orm.jamb_total_score,
            jamb_entry_route=application_orm.jamb_entry_route,
            olevel_grades=application_orm.olevel_grades,
            aggregate_score=application_orm.aggregate_score,
            first_choice_confirmed=application_orm.first_choice_confirmed,
            is_indegene=application_orm.is_indegene,
            state_of_origin=application_orm.state_of_origin,
            lga_of_origin=application_orm.lga_of_origin,
            iivc_verification_status=application_orm.iivc_verification_status,
            program_id=application_orm.program_id,
            screening_status=application_orm.screening_status,
            reviewed_at=application_orm.reviewed_at,
            rejection_reason=application_orm.rejection_reason
        )
    
    def _to_orm(self, application: Application) -> ApplicationORM:
        return ApplicationORM(
            application_id=application.application_id,
            first_name=application.first_name,
            last_name=application.last_name,
            address=application.address,
            phone_number=application.phone_number,
            email=application.email,
            is_indegene=application.is_indegene,
            state_of_origin=application.state_of_origin,
            lga_of_origin=application.lga_of_origin,
            jamb_registration_number=application.jamb_registration_number,
            jamb_score=application.jamb_score,
            jamb_total_score=application.jamb_total_score,
            jamb_entry_route=application.jamb_entry_route,
            olevel_grade=application.olevel_grade,
            program_id=application.program_id,
            aggregate_score=application.aggregate_score,
            first_choice_confirmed=application.first_choice_confirmed,
            iivc_verification_status=application.iivc_verification_status,
            screening_status=application.screening_status,
            # Audit / State fields
            reviewed_at=application.reviewed_at,
            rejection_reason=application.rejection_reason
        )
    