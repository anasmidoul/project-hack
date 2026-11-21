"""Unit B4 tests.

Must prove:
- double booking fails and leaves the state unchanged
- a cancellation creates exactly one offer and one applicant notification
- deadline is min(now + 30 min, starts_at)
- decline and expiry pass the offer on
- an empty waitlist frees the slot
"""
