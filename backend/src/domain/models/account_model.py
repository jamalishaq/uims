from dataclasses import dataclass
from enum import Enum
from datetime import date

class Role(str, Enum):
    STUDENT = "Student"
    REGISTRAR = "Registrar"
    FINANCE = "Finance"
    ADMIN = "Admin"
    APPLICANT = "Applicant"
    HOD = "HOD"
    Dean = "Dean"
    LIBRARIAN = "Librarian"

@dataclass
class Account:
    account_id: str
    email: str
    password: str
    owner_id: str
    roles: list[Role]
    active_role: Role
    last_login_at: date # timestamp
    is_active: bool
    # add created_at, updated_at to orm

    def switch_role(self, target_role: Role) -> None:
        if target_role not in self.roles:
            print(f"Account does not possess the '{target_role.value}' role.")
        self.active_role = target_role