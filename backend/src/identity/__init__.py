"""Identity: who is calling, and what they are allowed to reach.

The eighth bounded context, and the one CLAUDE.md section 6 described in advance and then
left unbuilt:

    Identity is a separate context holding credentials, role and scope only — never names
    or bio-data, which would make it the second identity system
    ``academic_records/domain/academic_record.py`` warns about.

That sentence is the whole design brief and this package holds to it literally. A
``Credential`` knows a login id, a password hash, a role, a scope and the id of a principal
**some other context owns**. It does not know the lecturer's name, the student's programme or
the faculty's title. Ask this context who somebody is and the honest answer is "principal
``LEC-0007``, role ``lecturer``, scoped to themselves" — the name is Faculty & Department's to
answer, and asking here would be asking the second copy.

**What is deliberately not in this package** is the thing every other context needs from it:
the ability to check a token. That lives in ``src/security.py``, a flat module beside
``http_api.py``, because a router in Billing importing ``identity`` would be a cross-context
import and rule (b) of the fitness test would reject it — rightly. Issuing a token is a use
case and lives here; verifying one is transport and lives there. ``auth.md`` at the repository
root argues the split at length.
"""
