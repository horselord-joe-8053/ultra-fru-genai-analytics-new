import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="Phase 7: run manually against local stack")]


def test_health_against_local_stack():
    """Placeholder: curl http://localhost:5000/health when stack is up."""
    assert True
