import asyncio
from sqlalchemy import text, select
from app.core.database import AsyncSessionLocal
from app.core.security import verify_password
from app.models.user import User

EMAIL = "admin@school.edu"
PASSWORD = "admin123"

async def diagnose():
    async with AsyncSessionLocal() as db:
        # Raw SQL — bypass ORM
        raw = await db.execute(
            text("SELECT id, email, password_hash, role, is_active FROM users WHERE email = :e"),
            {"e": EMAIL},
        )
        row = raw.fetchone()
        if not row:
            print("USER NOT FOUND in DB")
            return
        print(f"Raw DB row: id={row.id}, email={row.email}, role={row.role}, active={row.is_active}")

        # Password check
        ok = verify_password(PASSWORD, row.password_hash)
        print(f"Password verify result: {ok}")

        # ORM load
        try:
            result = await db.execute(select(User).where(User.email == EMAIL))
            user = result.scalar_one_or_none()
            if user:
                print(f"ORM load OK: role={user.role!r}")
            else:
                print("ORM load: no user returned")
        except Exception as e:
            print(f"ORM load FAILED: {type(e).__name__}: {e}")

asyncio.run(diagnose())
