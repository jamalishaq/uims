"""The table behind the credential register.

One aggregate and one table, which makes this the simplest schema in the system — and the one
with the most constraints per column, because every field on it is either a key somebody logs
in with or an answer authorization depends on.
"""

from sqlalchemy import Boolean, Column, Identity, Integer, MetaData, String, Table

SCHEMA = "identity"

metadata = MetaData(schema=SCHEMA)

credentials = Table(
    "credentials",
    metadata,
    Column("credential_id", String, primary_key=True),
    Column("login_id", String, nullable=False, unique=True),
    Column("principal_id", String, nullable=False, unique=True),
    Column("role", String, nullable=False),
    Column("scope_kind", String, nullable=False),
    Column("scope_id", String, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""Two unique constraints, and both of them are doing real work.

``login_id`` is unique because it is what a login flow looks up. Two rows sharing one would
make ``find_by_login_id`` return whichever the database felt like, and a person's password
would work on some requests and not others.

``principal_id`` is unique because a second credential for one principal is a second live
password for one person, with no way to tell which they are using and no way to retire the
other. ``IssueCredential`` checks it first for the sake of the error message; this is the
guarantee, because that check is not atomic against a concurrent caller.

Unlike Student Profile's ``applicant_id`` this one is **not nullable**: a credential with no
principal would authenticate somebody as nobody.

``password_hash`` is the encoded scrypt string, parameters included — never a bare digest and
never a separate salt column. Splitting it would let a row exist with a salt from one hashing
and a digest from another, which is a row that can never authenticate and whose failure looks
exactly like a wrong password.
"""
