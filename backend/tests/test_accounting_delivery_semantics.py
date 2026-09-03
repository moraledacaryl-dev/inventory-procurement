import httpx
import pytest

from app.services.integration_worker import _validate_accounting_response


def response(payload):
    return httpx.Response(200, json=payload, request=httpx.Request("POST", "https://accounting.example/api/integration-review/service-intake"))


def test_accounting_ready_for_review_is_delivered():
    payload = {"id": 42, "status": "ready_for_review", "validation": {"valid": True, "errors": []}}
    assert _validate_accounting_response(response(payload)) == payload


@pytest.mark.parametrize("status", ["accepted", "rejected"])
def test_existing_accounting_review_terminal_status_is_delivered(status):
    payload = {"id": 42, "status": status, "validation": {"valid": True, "errors": []}}
    assert _validate_accounting_response(response(payload)) == payload


def test_accounting_validation_failed_is_not_delivered():
    with pytest.raises(RuntimeError, match="validation_failed.*target_type"):
        _validate_accounting_response(
            response(
                {
                    "id": 42,
                    "status": "validation_failed",
                    "validation": {
                        "valid": False,
                        "errors": ["Reference and folio effects require proposed_links.target_type and target_id."],
                    },
                }
            )
        )


def test_accounting_missing_or_unknown_status_fails_closed():
    with pytest.raises(RuntimeError, match="unexpected status: missing"):
        _validate_accounting_response(response({"id": 42}))
    with pytest.raises(RuntimeError, match="unexpected status: queued"):
        _validate_accounting_response(response({"id": 42, "status": "queued"}))
