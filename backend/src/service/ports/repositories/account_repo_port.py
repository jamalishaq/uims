from uuid import UUID
from abc import ABC, abstractmethod

from src.domain.models import Account

class AccountReporsitoyPort(ABC):
    @abstractmethod
    def create(account: Account) -> Account:
        pass
    
    @abstractmethod
    def find_by_linked_entity(entity_id: UUID, entity_type: str) -> Account:
        pass
    
    @abstractmethod
    def find_by_id(account_id: UUID) -> Account:
        pass
    
    @abstractmethod
    def find_by_email(email: str) -> Account:
        pass

    @abstractmethod
    def update_last_login(account: Account) -> Account:
        pass
    
    @abstractmethod
    def update_active_role(account: Account) -> Account:
        pass

    @abstractmethod
    def update_roles(account: Account) -> Account:
        pass
    