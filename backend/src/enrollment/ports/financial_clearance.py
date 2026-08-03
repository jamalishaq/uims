"""Query port into Billing, for the one thing Enrollment is allowed to know about money.

A yes or a no, and nothing else. CLAUDE.md section 3 is explicit that the clearance rule
"lives entirely behind ``FinancialClearancePort``; Enrollment only ever sees yes/no" — the
confirmed rule being that ≥70% of the session fee is needed to register for first semester
and 100% for second. Not one of those numbers appears in this context, and none should:
they are Billing policy, and when they change, only the adapter behind this port changes.
That is also why nothing here returns a balance, a percentage or an amount outstanding. A
caller holding a balance would eventually compare it to something, and the rule would have
leaked.

**The term is in the signature, and CLAUDE.md section 3 has been updated to match.** It
was specified as ``is_cleared_for_registration(student_id, session)``, which cannot express
a rule whose whole content is the difference between the two semesters of a session: an
adapter given only the session would have to work out which semester was being registered
for, which means reading the academic calendar — a dependency Billing has no other reason
to acquire. :class:`Term` is Enrollment's own value object, so this remains a port typed in
the consuming context's language.

There is no event here and there must not be one. Fees are flat per session, there are no
per-unit carry-over charges, and registering for a course tells Billing nothing it needs to
know (CLAUDE.md section 3: "Do not add one"). The traffic is Enrollment asking, once, at
the moment it has to decide.
"""

from abc import ABC, abstractmethod

from enrollment.domain.values import Term


class FinancialClearancePort(ABC):
    """Asks Billing whether a student may register in a given term."""

    @abstractmethod
    async def is_cleared_for_registration(self, student_id: str, term: Term) -> bool:
        """Whether the student has settled enough to register for this term.

        A bare boolean rather than an outcome type, because there is nothing to carry: the
        reason behind a no is a ledger this context may not see, and a caller cannot act on
        it beyond telling the student to go and see the bursary.
        """
