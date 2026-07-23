from service import ApplicationService, AccountService
from infrastructure.adapters.repositories import (
    ApplicationRepositoryAdapter, 
    ProgramRepositoryAdapter,
    AccountRepositoryAdapter
)
from infrastructure.database import DatabaseFactory

class DependencyRegistry:
    """A thread-safe configuration container that holds running infrastructure factories."""
    def __init__(self):
        self._db_factory: DatabaseFactory | None = None

    def set_db_factory(self, factory: DatabaseFactory):
        self._db_factory = factory

    def get_db_factory(self) -> DatabaseFactory:
        if not self._db_factory:
            raise RuntimeError("DependencyRegistry requested before initialization.")
        return self._db_factory

dependency_registry = DependencyRegistry()


# FastAPI Dependency Injection Functions
def get_application_service() -> ApplicationService:
    db_factory = dependency_registry.get_db_factory()
    application_repo = ApplicationRepositoryAdapter(db_factory=db_factory)
    program_repo = ProgramRepositoryAdapter(db_factory=db_factory)

    return ApplicationService(application_repo=application_repo, program_repo=program_repo)

def get_account_service() -> AccountService:
    db_factory = dependency_registry.get_db_factory()
    account_repo = AccountRepositoryAdapter(db_factory=db_factory)

    return AccountService(account_repo=account_repo)