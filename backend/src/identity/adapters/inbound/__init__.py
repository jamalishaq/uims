"""Inbound adapters.

Only HTTP. This context subscribes to no event and publishes none — deliberately, and it is
worth saying why rather than leaving the absence to be read as unfinished work.

**Nothing publishes a credential.** A ``CredentialIssued`` event would be a fact no other
context can act on: none of the seven holds a login, and one that reacted by storing something
about a login would be the second identity system CLAUDE.md section 6 warns against.

**Nothing subscribes, either — including ``StudentMatriculated``.** It is the obvious candidate:
a student is created, so give them a login. It is not wired, because the credential would need a
password, and a password this system invented and never told anybody is not a credential. Who
issues a new student their first password, and how it reaches them, is an institutional fact
nobody has stated (section 6). Until somebody does, credentials are created deliberately —
through ``POST /auth/credentials`` or by the seeder — and a student who has been matriculated
and not yet given a login is a visible, correctable state rather than an invisible one.
"""
