import pytest

from know_your_project.ingestion.webhooks import parse_push_event, verify_webhook_secret


def test_bad_secret_is_rejected() -> None:
    with pytest.raises(PermissionError):
        verify_webhook_secret("wrong", "expected")


def test_push_event_extracts_ref() -> None:
    event = parse_push_event({"resource": {
        "repository": {"id": "repo"},
        "refUpdates": [{
            "name": "refs/heads/main",
            "oldObjectId": "a" * 40,
            "newObjectId": "b" * 40,
        }],
    }})
    assert event.new_sha == "b" * 40
