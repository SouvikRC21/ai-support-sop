from datetime import timedelta

from intake.models import CustomerTier, Queue, RoutingDecision, Severity
from intake.sla import add_business_days, overdue_triage, start_timers
from tests.conftest import NOW

ROUTED = RoutingDecision("R5", Queue.L1_PAYMENTS)


def test_first_response_matrix():
    expected = {
        Severity.SEV1: (15, 30), Severity.SEV2: (60, 120), Severity.SEV3: (240, 480), Severity.SEV4: (480, 1440),
    }
    for sev, (ent, other) in expected.items():
        assert start_timers(NOW, sev, CustomerTier.ENTERPRISE, ROUTED).first_response_due == NOW + timedelta(minutes=ent)
        assert start_timers(NOW, sev, CustomerTier.SMB, ROUTED).first_response_due == NOW + timedelta(minutes=other)


def test_resolution_uses_business_days():
    # Wednesday + 3 business days = Monday; + 5 = Wednesday next week.
    assert start_timers(NOW, Severity.SEV3, CustomerTier.SMB, ROUTED).resolution_due.weekday() == 0
    assert start_timers(NOW, Severity.SEV4, CustomerTier.SMB, ROUTED).resolution_due == NOW + timedelta(days=7)
    assert add_business_days(NOW, 2) == NOW + timedelta(days=2)


def test_overdue_triage():
    t = start_timers(NOW, Severity.SEV3, CustomerTier.SMB, RoutingDecision("R8", Queue.TRIAGE))
    assert overdue_triage({"A": t}, NOW + timedelta(minutes=10)) == []
    assert overdue_triage({"A": t}, NOW + timedelta(minutes=16)) == ["A"]
