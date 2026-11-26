import pytest
import re

from pathlib import Path

# === Environment configuration ===

def test_log_environment_settings_and_run_filename(monkeypatch: pytest.MonkeyPatch):
    import config
    import importlib

    original = (config.PRINT_LOG_TO_SCREEN, config.WRITE_LOG, config.WRITE_LOG_TO_FILE)
    try:
        with monkeypatch.context() as m:
            m.delenv("WFWH_WRITE_LOG_TO_FILE", raising=False)
            m.setenv("WFWH_PRINT_LOG_TO_SCREEN", "true")
            m.setenv("WFWH_WRITE_LOG", "true")
            importlib.reload(config)
            assert config.PRINT_LOG_TO_SCREEN
            assert config.WRITE_LOG
            assert config.WRITE_LOG_TO_FILE.parent == Path("logs")
            assert re.fullmatch(r"wfwh-\d{8}T\d{12}Z\.log", config.WRITE_LOG_TO_FILE.name)

        with monkeypatch.context() as m:
            m.setenv("WFWH_WRITE_LOG_TO_FILE", "./custom/receiver.log")
            importlib.reload(config)
            assert config.WRITE_LOG_TO_FILE == Path("custom/receiver.log")
    finally:
        importlib.reload(config)
        (config.PRINT_LOG_TO_SCREEN,
         config.WRITE_LOG,
         config.WRITE_LOG_TO_FILE) = original

def test_retry_code_environment_variable(monkeypatch):
    import importlib
    import config
    baseline = config.RETRY_STATUS_CODE
    try:
        with monkeypatch.context() as m:
            m.setenv("WFWH_RETRY_STATUS_CODE", "502")
            importlib.reload(config)
            assert config.RETRY_STATUS_CODE == 502
    finally:
        importlib.reload(config)
        assert config.RETRY_STATUS_CODE == baseline

def test_write_mode_environment_and_default(monkeypatch: pytest.MonkeyPatch):
    import config
    import importlib

    original = config.WRITE_MODE
    try:
        with monkeypatch.context() as m:
            m.setenv("WFWH_WRITE_MODE", "ab")
            importlib.reload(config)
            assert config.WRITE_MODE == "ab"

        with monkeypatch.context() as m:
            m.delenv("WFWH_WRITE_MODE", raising=False)
            importlib.reload(config)
            assert config.WRITE_MODE == "w"
    finally:
        importlib.reload(config)
        config.WRITE_MODE = original

def test_host_port_environment_and_default(monkeypatch: pytest.MonkeyPatch):
    import importlib
    import config

    baseline = config.HOST, config.PORT
    try:
        with monkeypatch.context() as m:
            m.setenv("WFWH_HOST", "127.0.0.1")
            m.setenv("WFWH_PORT", "8765")
            importlib.reload(config)
            assert config.HOST == "127.0.0.1"
            assert config.PORT == 8765
        with monkeypatch.context() as m:
            m.delenv("WFWH_HOST", raising=False)
            m.delenv("WFWH_PORT", raising=False)
            importlib.reload(config)
            assert config.HOST == "localhost"
            assert config.PORT == 5000
    finally:
        importlib.reload(config)
        config.HOST, config.PORT = baseline

def test_webhook_header_environment_configuration(monkeypatch):
    import importlib
    import config

    original = config.WEBHOOK_HEADERS.copy()
    try:
        with monkeypatch.context() as m:
            m.setenv("WFWH_WH_ID", "svix-id")
            m.setenv("WFWH_WH_TIMESTAMP", "svix-timestamp")
            m.setenv("WFWH_WH_SIGNATURE", "svix-signature")
            importlib.reload(config)
            assert config.WEBHOOK_HEADERS == {
                "id": "svix-id",
                "timestamp": "svix-timestamp",
                "signature": "svix-signature",
            }
    finally:
        importlib.reload(config)
        assert config.WEBHOOK_HEADERS == original

def test_webhook_headers_default_to_standard_names(monkeypatch):
    import importlib
    import config

    original = config.WEBHOOK_HEADERS.copy()
    try:
        with monkeypatch.context() as m:
            m.delenv("WFWH_WH_ID", raising=False)
            m.delenv("WFWH_WH_TIMESTAMP", raising=False)
            m.delenv("WFWH_WH_SIGNATURE", raising=False)
            importlib.reload(config)
            assert config.WEBHOOK_HEADERS == {
                "id": "webhook-id",
                "timestamp": "webhook-timestamp",
                "signature": "webhook-signature",
            }
    finally:
        importlib.reload(config)
        assert config.WEBHOOK_HEADERS == original
