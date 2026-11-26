import os 
from pathlib import Path
from datetime import datetime, timezone

# === LOGGING === #
# Each process gets a unique UTC timestamp for its default log filename.
RUN_STARTED_AT = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
RECORD_LOGS = os.getenv("WFWH_RECORD_LOGS", "true").lower() == "true"
PRINT_LOG_TO_SCREEN = os.getenv("WFWH_PRINT_LOG_TO_SCREEN", "false").lower() == "true"
WRITE_LOG = os.getenv("WFWH_WRITE_LOG", "false").lower() == "true"
WRITE_LOG_TO_FILE = Path(
    os.getenv(
        "WFWH_WRITE_LOG_TO_FILE",
        str(Path("logs") / f"wfwh-{RUN_STARTED_AT}.log")
    )
).expanduser()

# === PATH === #
SECRET_PATH = Path(
    os.getenv(
        "WFWH_SECRET_PATH",
        str(Path.home() / ".config/wfwh/webhook_secret")
    )
)

OUTPUT_PATH = Path(
    os.getenv("WFWH_OUTPUT_PATH", "output.bin")
).expanduser()

OUTPUT_ENCODING = os.getenv("WFWH_OUTPUT_ENCODING", "utf-8")
WRITE_MODE = os.getenv("WFWH_WRITE_MODE", "w")

# === RECEIPT FORMATTER (filename inside formatters/) === #
FORMATTER_FILE = os.getenv("WFWH_FORMATTER_FILE")

# === WEBHOOK ENDPOINT === #
WEBHOOK_ROUTE = os.getenv("WFWH_WEBHOOK_ROUTE", "/print")
HOST = os.getenv("WFWH_HOST", "localhost")
PORT = int(os.getenv("WFWH_PORT", "5000"))

# Response code for temporary formatting/output failures.
RETRY_STATUS_CODE = int(os.getenv("WFWH_RETRY_STATUS_CODE", "503"))

# === WEBHOOK SIGNATURE (STANDARD WEBHOOKS V1) === #
# Edit the fallback header names below, or override them via environment variables.
WEBHOOK_HEADERS = {
    "id": os.getenv("WFWH_WH_ID", "webhook-id"),
    "timestamp": os.getenv("WFWH_WH_TIMESTAMP", "webhook-timestamp"),
    "signature": os.getenv("WFWH_WH_SIGNATURE", "webhook-signature"),
}
SIGNATURE_VERSION = "v1"
REPLAY_TOLERANCE = 300
