import pytest
import wfwh

# === Request verification ===

def test_webhook_expired(monkeypatch, webhook_request):
    headers = webhook_request["headers"]
    body = webhook_request["body"]

    signed_at = int(headers["webhook-timestamp"])

    with monkeypatch.context() as m:
        m.setattr(wfwh.time, "time", lambda: signed_at + 301)

        assert not wfwh.verify_webhook_v1_signature(headers, body)

@pytest.mark.parametrize("header", [
    "webhook-id",
    "webhook-timestamp",
    "webhook-signature",
])
@pytest.mark.parametrize("value", ["missing", None])
def test_webhook_invalid_headers(webhook_request, header, value):
    headers = webhook_request["headers"].copy()

    if value == "missing":
        headers.pop(header)
    else:
        headers[header] = None

    assert not wfwh.verify_webhook_v1_signature(
        headers, webhook_request["body"]
    )

def test_webhook_tampered_body(webhook_request):
    headers = webhook_request["headers"]
    body = webhook_request["body"]

    assert wfwh.verify_webhook_v1_signature(headers, body)

    tampered_body = b'{"code": "CHANGED"}'

    assert not wfwh.verify_webhook_v1_signature(
        headers, tampered_body
    )

def test_webhook_duplicate_id(monkeypatch, webhook_request):
    printed = []

    monkeypatch.setattr(wfwh, "APP", None)
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())
    monkeypatch.setattr(wfwh, "format_lines_to_print", lambda data: "Example receipt")
    monkeypatch.setattr(
        wfwh,
        "write_to_output",
        lambda receipt: printed.append(receipt)
    )

    wfwh.init_app()
    client = wfwh.APP.test_client()

    headers = webhook_request["headers"]
    body = webhook_request["body"]

    first = client.post("/print", data=body, headers=headers)
    second = client.post("/print", data=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json == {"status": "already processed"}
    assert len(printed) == 1

def test_configured_webhook_headers(monkeypatch, webhook_request):
    aliases = {
        "id": "svix-id",
        "timestamp": "svix-timestamp",
        "signature": "svix-signature",
    }
    headers = {
        aliases["id"]: webhook_request["headers"]["webhook-id"],
        aliases["timestamp"]: webhook_request["headers"]["webhook-timestamp"],
        aliases["signature"]: webhook_request["headers"]["webhook-signature"],
    }
    printed = []

    monkeypatch.setattr(wfwh, "WEBHOOK_HEADERS", aliases)
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())
    monkeypatch.setattr(wfwh, "format_lines_to_print", lambda data: "Example receipt")
    monkeypatch.setattr(wfwh, "APP", None)
    monkeypatch.setattr(wfwh, "write_to_output", printed.append)
    wfwh.init_app()
    client = wfwh.APP.test_client()

    first = client.post("/print", data=webhook_request["body"], headers=headers)
    duplicate = client.post("/print", data=webhook_request["body"], headers=headers)

    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json == {"status": "already processed"}
    assert len(printed) == 1
