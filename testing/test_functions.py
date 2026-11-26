import hashlib
import base64
import pytest
import wfwh
import hmac
import io

from types import SimpleNamespace
from flask import Flask
from pathlib import Path

# === Function tests ===

def test_get_secret(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    base_secret = b"secret"
    secret = "whsec_" + base64.b64encode(base_secret).decode()

    path = tmp_path / "secret"
    path.write_text(secret)

    with monkeypatch.context() as m:
        m.setattr(wfwh, "SECRET_PATH", path)
        m.setattr(wfwh, "SIGNING_KEY", None)

        wfwh.get_secret()

        assert wfwh.SIGNING_KEY == base_secret

@pytest.mark.parametrize("filename, error", [
    ("placeholder.py", None),
    ("storekit.py", None),
    ("storekit", ValueError),
    ("other.txt", ValueError),
    ("../storekit.py", ValueError),
    ("nested/storekit.py", ValueError),
    ("__init__.py", ValueError),
    ("formatters/storekit.py", ValueError),
    ("unavailable_formatter.py", FileNotFoundError),
    (None, NotImplementedError),
    ("", NotImplementedError),
    ("no_handler.py", TypeError),
])
def test_load_formatter(monkeypatch, filename, error):
    if filename == "no_handler.py":
        monkeypatch.setattr(wfwh.importlib, "import_module",
                            lambda _: SimpleNamespace())

    if error is None:
        formatter = wfwh.load_formatter(filename)
        assert callable(formatter)
        assert isinstance(formatter({"id": "TEST123"}), (str, bytes))
    else:
        with pytest.raises(error):
            wfwh.load_formatter(filename)

def test_init_app(monkeypatch: pytest.MonkeyPatch):
    if wfwh.APP is not None:
       monkeypatch.setattr(wfwh, 'APP', None) 
    assert wfwh.APP is None

    wfwh.init_app()

    assert isinstance(wfwh.APP, Flask)
    assert 'wfwh_bp' in wfwh.APP.blueprints

    rules = list(wfwh.APP.url_map.iter_rules())
    assert len(rules) == 1

    rule = rules[0]
    assert rule.rule == '/print'
    assert rule.methods == {'POST', 'OPTIONS'}

@pytest.mark.parametrize("setting, value, exception", [
    ("WRITE_MODE", "wb++", ValueError),
    ("WRITE_MODE", "wwb", ValueError),
    ("WRITE_MODE", "wbt", ValueError),
    ("WRITE_MODE", "xbx", ValueError),
    ("WRITE_MODE", "", ValueError),
    ("WRITE_MODE", "WB", ValueError),
    ("WRITE_MODE", "b", ValueError),
    ("WRITE_MODE", "b+", ValueError),
    ("WRITE_MODE", "rtb", ValueError),
    ("WRITE_MODE", "rw", ValueError),
    ("WRITE_MODE", None, ValueError),
    ("RETRY_STATUS_CODE", 200, ValueError),
    ("RETRY_STATUS_CODE", 201, ValueError),
    ("RETRY_STATUS_CODE", 301, ValueError),
    ("RETRY_STATUS_CODE", 400, ValueError),
    ("RETRY_STATUS_CODE", 401, ValueError),
    ("RETRY_STATUS_CODE", 422, ValueError),
    ("RETRY_STATUS_CODE", 600, ValueError),
    ("RETRY_STATUS_CODE", "503", ValueError),
    ("RETRY_STATUS_CODE", True, ValueError),
    ("PORT", 0, ValueError),
    ("PORT", 65536, ValueError),
    ("PORT", -1, ValueError),
    ("PORT", "5000", ValueError),
    ("OUTPUT_ENCODING", "not-a-charset", LookupError),
    ("FORMATTER_FILE", None, NotImplementedError),
    ("FORMATTER_FILE", "unavailable_formatter.py", FileNotFoundError),
])
def test_init_app_failure(monkeypatch, setting, value, exception):
    monkeypatch.setattr(wfwh, setting, value)
    with pytest.raises(exception):
        wfwh.init_app()

def test_report_stderr(monkeypatch, capsys):
    wfwh.report_stderr("Configuration error")
    assert "Configuration error" in capsys.readouterr().err

    def broken_print(*args, **kwargs):
        raise UnicodeEncodeError("cp1252", "❌", 0, 1, "unsupported character")

    with monkeypatch.context() as m:
        m.setattr("builtins.print", broken_print)
        wfwh.report_stderr("❌")

def test_report_failure(monkeypatch, capsys):
    monkeypatch.setattr(wfwh, "RECORD_LOGS", False)
    monkeypatch.setattr(wfwh, "PRINT_LOG_TO_SCREEN", False)
    monkeypatch.setattr(wfwh, "WRITE_LOG", False)

    wfwh.report_failure("Permanent configuration error")
    assert "Permanent configuration error" in capsys.readouterr().err

@pytest.mark.parametrize("output", ["memory", "screen", "file", "both", "disabled", "cp1252", "file_failure"])
def test_logger(monkeypatch, tmp_path, capsys, output):
    path = tmp_path / "log.txt"
    recorded = []
    monkeypatch.setattr(wfwh, "EVENT_LOG", recorded)
    monkeypatch.setattr(wfwh, "RECORD_LOGS", output == "memory")
    monkeypatch.setattr(wfwh, "PRINT_LOG_TO_SCREEN", output in ("screen", "both", "cp1252"))
    monkeypatch.setattr(wfwh, "WRITE_LOG", output in ("file", "both", "file_failure"))
    monkeypatch.setattr(wfwh, "WRITE_LOG_TO_FILE", path)

    if output == "cp1252":
        def cp1252_print(text, **kwargs):
            text.encode("cp1252")
        with monkeypatch.context() as m:
            m.setattr("builtins.print", cp1252_print)
            wfwh.logger("✅ Webhook verified")
        assert recorded == []
        return

    if output == "file_failure":
        path.mkdir()
        wfwh.logger("Test X")
        assert "WFWH log write failed" in capsys.readouterr().err
        assert recorded == []
        return

    wfwh.logger("Test X")
    captured = capsys.readouterr()

    assert recorded == (["Test X"] if output == "memory" else [])
    assert captured.out == ("Test X\n" if output in ("screen", "both") else "")
    if output in ("file", "both"):
        assert path.read_text(encoding="utf-8") == "Test X\n"
    else:
        assert not path.exists()

@pytest.mark.parametrize("mode, encoding, content, original, expected", [
    ("wb", "utf-8", "£5.00", None, b"\xc2\xa35.00"),
    ("wb", "cp437", "£5.00", None, b"\x9c5.00"),
    ("wb", "cp437", "Café", None, b"Caf\x82"),
    ("wb", "utf-8", "Tea ☕", None, "Tea ☕".encode("utf-8")),
    ("wb", "cp437", "Tea ☕", None, b"Tea ?"),
    ("wb", "utf-8", "Hello\x00!", None, b"Hello\x00!"),
    ("wb", "cp437", "€1.50", None, b"?1.50"),
    ("w", "cp437", "£5", None, b"\x9c5"),
    ("wb", "cp437", b"\x1b\x40\x00RAW", None, b"\x1b\x40\x00RAW"),
    ("wb", "utf-8", "new", b"old", b"new"),
    ("ab", "utf-8", "new", b"old", b"oldnew"),
    ("xb", "utf-8", "new", None, b"new"),
    ("wb+", "utf-8", "new", b"old", b"new"),
    ("r+b", "utf-8", "new", b"oldstuff", b"newstuff"),
    ("w", "utf-8", "new", b"old", b"new"),
    ("a", "utf-8", "new", b"old", b"oldnew"),
    ("x", "utf-8", "new", None, b"new"),
    ("r+", "utf-8", "new", b"oldstuff", b"newstuff"),
])
def test_write_to_output(monkeypatch, tmp_path, mode, encoding, content, original, expected):
    path = tmp_path / "output.bin"
    if original is not None:
        path.write_bytes(original)

    monkeypatch.setattr(wfwh, "OUTPUT_PATH", path)
    monkeypatch.setattr(wfwh, "OUTPUT_ENCODING", encoding)
    monkeypatch.setattr(wfwh, "WRITE_MODE", mode)

    wfwh.write_to_output(content)

    assert path.read_bytes() == expected

@pytest.mark.parametrize("mode, content, error", [
    ("w", b"raw bytes", TypeError),
    ("a", b"raw bytes", TypeError),
    ("r", "text", io.UnsupportedOperation),
    ("rb", "text", io.UnsupportedOperation),
    ("rt", "text", io.UnsupportedOperation),
])
def test_write_to_output_failure(monkeypatch, tmp_path, mode, content, error):
    path = tmp_path / "output.txt"
    path.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(wfwh, "OUTPUT_PATH", path)
    monkeypatch.setattr(wfwh, "WRITE_MODE", mode)

    with pytest.raises(error):
        wfwh.write_to_output(content)

    assert path.read_text(encoding="utf-8") == "existing"

def test_format_lines_to_print(monkeypatch):
    monkeypatch.setattr(wfwh, "FORMATTER", lambda data: data["code"])
    assert wfwh.format_lines_to_print({"code": "TEST123"}) == "TEST123"

def test_print_receipt(monkeypatch, webhook_request):
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())
    monkeypatch.setattr(wfwh, "format_lines_to_print", lambda data: "Example receipt")
    printed = []
    monkeypatch.setattr(wfwh, "write_to_output", printed.append)
    wfwh.init_app()

    client = wfwh.APP.test_client()
    request = webhook_request
    first = client.post("/print", data=request["body"], headers=request["headers"])
    second = client.post("/print", data=request["body"], headers=request["headers"])

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json == {"status": "already processed"}
    assert printed == ["Example receipt"]

@pytest.mark.parametrize("case, status", [
    ("invalid_formatter_output", 422),
    ("formatter_error", 503),
    ("bytes_in_text_mode", 422),
    ("read_only_mode", 422),
    ("unavailable_output", 503),
])
def test_print_receipt_failure(monkeypatch, webhook_request, tmp_path, capsys, case, status):
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())
    monkeypatch.setattr(wfwh, "RECORD_LOGS", False)
    monkeypatch.setattr(wfwh, "PRINT_LOG_TO_SCREEN", False)
    monkeypatch.setattr(wfwh, "WRITE_LOG", False)
    monkeypatch.setattr(wfwh, "OUTPUT_PATH", tmp_path / "output.txt")

    if case == "invalid_formatter_output":
        monkeypatch.setattr(wfwh, "format_lines_to_print", lambda _: None)
    elif case == "formatter_error":
        def broken(_):
            raise RuntimeError("Formatter broke")
        monkeypatch.setattr(wfwh, "format_lines_to_print", broken)
    elif case == "bytes_in_text_mode":
        monkeypatch.setattr(wfwh, "WRITE_MODE", "w")
        monkeypatch.setattr(wfwh, "format_lines_to_print", lambda _: b"raw")
    elif case == "read_only_mode":
        monkeypatch.setattr(wfwh, "WRITE_MODE", "r")
        monkeypatch.setattr(wfwh, "format_lines_to_print", lambda _: "text")
    else:
        monkeypatch.setattr(wfwh, "format_lines_to_print", lambda _: "text")
        def unavailable(_):
            raise OSError("Printer disconnected")
        monkeypatch.setattr(wfwh, "write_to_output", unavailable)

    wfwh.init_app()
    response = wfwh.APP.test_client().post(
        "/print", data=webhook_request["body"], headers=webhook_request["headers"]
    )

    assert response.status_code == status
    assert webhook_request["headers"]["webhook-id"] not in wfwh.PROCESSED_IDS
    assert capsys.readouterr().err

def test_run_server(monkeypatch):
    app = Flask("wfwh-test")
    calls = []
    monkeypatch.setattr(wfwh, "get_secret", lambda: None)
    monkeypatch.setattr(wfwh, "init_app", lambda: None)
    monkeypatch.setattr(wfwh, "SIGNING_KEY", b"secret")
    monkeypatch.setattr(wfwh, "APP", app)
    monkeypatch.setattr(wfwh, "HOST", "127.0.0.1")
    monkeypatch.setattr(wfwh, "PORT", 8765)
    monkeypatch.setattr(wfwh, "serve", lambda app, **kwargs: calls.append((app, kwargs)))

    wfwh.run_server()

    assert calls == [(app, {"host": "127.0.0.1", "port": 8765, "threads": 4})]

# === Relationships ===

def test_output_failure_retry(monkeypatch, webhook_request):
    calls = 0

    def fake_print(text):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("Printer unavailable")

    monkeypatch.setattr(wfwh, "format_lines_to_print", lambda data: "Example receipt")
    monkeypatch.setattr(wfwh, "write_to_output", fake_print)
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())

    wfwh.init_app()
    client = wfwh.APP.test_client()

    headers = webhook_request["headers"].copy()
    body = webhook_request["body"]
    msg_id = headers["webhook-id"]

    first = client.post("/print", data=body, headers=headers)

    assert first.status_code == 503
    assert first.json == {"error": "Output unavailable"}
    assert msg_id not in wfwh.PROCESSED_IDS

    timestamp = str(int(headers["webhook-timestamp"]) + 1)
    content = f"{msg_id}.{timestamp}.".encode() + body

    signature = base64.b64encode(
        hmac.new(wfwh.SIGNING_KEY, content, hashlib.sha256).digest()
    ).decode()

    headers["webhook-timestamp"] = timestamp
    headers["webhook-signature"] = f"v1,{signature}"

    second = client.post("/print", data=body, headers=headers)

    assert second.status_code == 200
    assert msg_id in wfwh.PROCESSED_IDS
    assert calls == 2

def test_load_configured_formatter(monkeypatch: pytest.MonkeyPatch, webhook_request):
    from examples.storekit import format_receipt

    monkeypatch.setattr(wfwh, "FORMATTER_FILE", "storekit.py")
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())
    monkeypatch.setattr(wfwh, "APP", None)
    printed = []
    monkeypatch.setattr(wfwh, "write_to_output", printed.append)

    wfwh.init_app()
    assert wfwh.FORMATTER({"code": "TEST123"}) == format_receipt({"code": "TEST123"})

    response = wfwh.APP.test_client().post(
        "/print", data=webhook_request["body"], headers=webhook_request["headers"]
    )
    assert response.status_code == 200
    assert printed == [format_receipt({"code": "TEST123"})]

@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_retry_status_on_formatter_failure(monkeypatch, webhook_request, status_code):
    monkeypatch.setattr(wfwh, "RETRY_STATUS_CODE", status_code)
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())

    def broken(_):
        raise RuntimeError("broken formatter")

    monkeypatch.setattr(wfwh, "format_lines_to_print", broken)
    monkeypatch.setattr(wfwh, "write_to_output", lambda _: pytest.fail("unexpected output"))
    wfwh.init_app()
    response = wfwh.APP.test_client().post("/print", data=webhook_request["body"], headers=webhook_request["headers"])
    assert response.status_code == status_code
    assert webhook_request["headers"]["webhook-id"] not in wfwh.PROCESSED_IDS

def test_retry_status_on_output_failure(monkeypatch, webhook_request):
    monkeypatch.setattr(wfwh, "RETRY_STATUS_CODE", 502)
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())
    monkeypatch.setattr(wfwh, "format_lines_to_print", lambda _: "text")

    def broken(_):
        raise OSError("unavailable")

    monkeypatch.setattr(wfwh, "write_to_output", broken)
    wfwh.init_app()
    response = wfwh.APP.test_client().post("/print", data=webhook_request["body"], headers=webhook_request["headers"])
    assert response.status_code == 502
    assert webhook_request["headers"]["webhook-id"] not in wfwh.PROCESSED_IDS

def test_stdout_cp1252_failure_does_not_change_webhook_delivery(
    monkeypatch: pytest.MonkeyPatch, webhook_request
):
    monkeypatch.setattr(wfwh, "PRINT_LOG_TO_SCREEN", True)
    monkeypatch.setattr(wfwh, "WRITE_LOG", False)
    monkeypatch.setattr(wfwh, "PROCESSED_IDS", set())
    monkeypatch.setattr(wfwh, "format_lines_to_print", lambda _: "Receipt")

    writes = []
    monkeypatch.setattr(wfwh, "write_to_output", writes.append)
    wfwh.init_app()

    def cp1252_console_print(message, **kwargs):
        message.encode("cp1252")

    with monkeypatch.context() as m:
        m.setattr("builtins.print", cp1252_console_print)
        response = wfwh.APP.test_client().post(
            "/print", data=webhook_request["body"], headers=webhook_request["headers"]
        )

    assert response.status_code == 200
    assert writes == ["Receipt"]
    assert webhook_request["headers"]["webhook-id"] in wfwh.PROCESSED_IDS

# === Example formatter ===

def test_placeholder():
    order = {
        "id": "TEST123"
    }

    expected_lines = []
    expected_lines.append("Webhook received!")
    expected_lines.append(str(order.get("id", "Unknown ID")))
    expected_receipt = "\n".join(expected_lines)
    
    from examples.placeholder import format_receipt
    receipt = format_receipt(order)

    assert receipt == expected_receipt
