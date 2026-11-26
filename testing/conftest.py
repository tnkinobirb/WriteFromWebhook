import hashlib
import pytest
import base64
import wfwh
import time
import json
import hmac

@pytest.fixture(autouse=True)
def configure_formatter_for_tests(monkeypatch):
    monkeypatch.setattr(wfwh, "FORMATTER_FILE", "placeholder.py")

@pytest.fixture
def webhook_request(monkeypatch) -> dict:
    key = b"test-secret"
    monkeypatch.setattr(wfwh, "SIGNING_KEY", key)

    body = json.dumps({"code": "TEST123"}).encode("utf-8")

    msg_id = "msg_test123"
    timestamp = str(int(time.time()))

    signed_content = f"{msg_id}.{timestamp}.".encode() + body
    signature = base64.b64encode(
        hmac.new(key, signed_content, hashlib.sha256).digest()
    ).decode()

    return {
        "headers": {
            "webhook-id": msg_id,
            "webhook-timestamp": timestamp,
            "webhook-signature": f"v1,{signature}",
        },
        "body": body,
    }
