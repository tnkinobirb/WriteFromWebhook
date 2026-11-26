import threading
import importlib
import hashlib
import codecs
import base64
import time
import hmac
import sys
import io

from typing import Callable
from pathlib import Path
from waitress import serve
from flask import Flask, Blueprint, request, jsonify
from config import (
    RECORD_LOGS, PRINT_LOG_TO_SCREEN, WRITE_LOG, WRITE_LOG_TO_FILE,
    OUTPUT_PATH, OUTPUT_ENCODING, WRITE_MODE, SECRET_PATH,
    WEBHOOK_HEADERS, SIGNATURE_VERSION, REPLAY_TOLERANCE,
    WEBHOOK_ROUTE, HOST, PORT, FORMATTER_FILE, RETRY_STATUS_CODE,
)

# === Webhook signing key ===
ENCODING = 'utf-8'
PROCESSED_IDS = set()
PROCESSING_LOCK = threading.Lock()
OUTPUT_LOCK = threading.Lock()
LOG_LOCK = threading.Lock()

APP = None
SIGNING_KEY = None
FORMATTER: Callable[[dict], str | bytes] | None = None

def get_secret():
    global SIGNING_KEY

    secret = SECRET_PATH.read_text(encoding="utf-8").rstrip("\r\n")
    SIGNING_KEY = base64.b64decode(
        secret.removeprefix("whsec_"), validate=True
    )
    
    if SIGNING_KEY is None or not SIGNING_KEY:
        raise RuntimeError("Failed to get or set signing key")

def load_formatter(filename: str | None) -> Callable[[dict], str | bytes]:
    """Load a trusted module from the local formatters/ directory."""
    if not filename:
        raise NotImplementedError(
            "WFWH_FORMATTER_FILE is not configured. "
            "Set it to a filename inside formatters/, e.g. 'placeholder.py'"
        )
    path = Path(filename)
    if (
        path.name != filename
        or path.suffix != ".py"
        or not path.stem.isidentifier()
        or path.stem.startswith("_")
    ):
        raise ValueError(
            "WFWH_FORMATTER_FILE must be a filename inside formatters/, "
            "for example 'storekit.py'"
        )

    module_name = f"formatters.{path.stem}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise FileNotFoundError(
                f"Formatter not found: formatters/{filename}"
            ) from exc
        raise

    formatter = getattr(module, "format_receipt", None)
    if not callable(formatter):
        raise TypeError(
            f"formatters/{filename} must define a callable format_receipt(data)"
        )
    return formatter

def init_app():
    global APP, FORMATTER
    if type(RETRY_STATUS_CODE) is not int or (RETRY_STATUS_CODE != 429 and not 500 <= RETRY_STATUS_CODE <= 599):
        raise ValueError("WFWH_RETRY_STATUS_CODE must be 429 or a 5xx HTTP status")
    # Validate Python's built-in open() mode syntax without imposing
    # writable-only or binary-only application-specific restrictions.
    if (
        not isinstance(WRITE_MODE, str)
        or not 1 <= len(WRITE_MODE) <= 3
        or len(set(WRITE_MODE)) != len(WRITE_MODE)
        or set(WRITE_MODE) - set("rwaxbt+")
        or sum(char in WRITE_MODE for char in "rwax") != 1
        or ("b" in WRITE_MODE and "t" in WRITE_MODE)
    ):
        raise ValueError("WFWH_WRITE_MODE must be a valid Python file mode")
    if not HOST.strip():
        raise ValueError("WFWH_HOST must not be empty")
    if type(PORT) is not int or not 1 <= PORT <= 65535:
        raise ValueError("WFWH_PORT must be an integer between 1 and 65535")
    codecs.lookup(OUTPUT_ENCODING)  # Validate the configured encoding before serving.
    if WRITE_LOG:
        # Only create the log directory/file when file logging is enabled.
        WRITE_LOG_TO_FILE.parent.mkdir(parents=True, exist_ok=True)
        WRITE_LOG_TO_FILE.touch(exist_ok=True)
    FORMATTER = None
    FORMATTER = load_formatter(FORMATTER_FILE)
    APP = Flask(__name__, static_folder=None)
    webhook_bp = Blueprint("wfwh_bp", __name__, url_prefix="/")
    webhook_bp.add_url_rule(WEBHOOK_ROUTE, view_func=print_receipt, methods=["POST"])
    APP.register_blueprint(webhook_bp)
    APP.config["MAX_CONTENT_LENGTH"] = 256 * 1024

# === In-memory event log (cleared when the process restarts) ===
EVENT_LOG: list[str] = []

def report_stderr(message: str) -> None:
    """Always attempt to report failures, independently of logging toggles."""
    try:
        print(message, file=sys.stderr, flush=True)
    except (OSError, UnicodeError):
        pass  # Broken diagnostic streams must not change webhook responses.

def report_failure(message: str) -> None:
    logger(message)  # Keep optional in-memory, screen and file logs.
    report_stderr(message)  # Errors remain visible when optional logs are off.

def logger(message: str) -> None:
    message = str(message)
    with LOG_LOCK:
        if RECORD_LOGS:
            EVENT_LOG.append(message)

        if PRINT_LOG_TO_SCREEN:
            try:
                print(message, flush=True)
            except (OSError, UnicodeError):
                pass  # Logging cannot change a webhook's delivery result.

        if WRITE_LOG:
            try:
                with WRITE_LOG_TO_FILE.open("a", encoding="utf-8") as output:
                    output.write(message + "\n")
            except OSError as exc:
                report_stderr(f"[!] WFWH log write failed: {exc}")
                # An optional diagnostic log failure must not trigger redelivery.

# === Write formatted text or bytes to a file or device === #
def write_to_output(content: str | bytes) -> None:
    with OUTPUT_LOCK:
        # Keep all valid Python file modes; fail clearly if one cannot write.
        if "r" in WRITE_MODE and "+" not in WRITE_MODE:
            raise io.UnsupportedOperation(
                f"WFWH_WRITE_MODE={WRITE_MODE!r} is read-only"
            )
        if "b" not in WRITE_MODE and isinstance(content, bytes):
            raise TypeError(
                f"Formatter returned bytes but WFWH_WRITE_MODE={WRITE_MODE!r} "
                "is text mode; return str or use a binary write mode"
            )

        if "b" in WRITE_MODE:
            payload = (
                content.encode(OUTPUT_ENCODING, errors="replace")
                if isinstance(content, str)
                else content
            )
            with open(OUTPUT_PATH, WRITE_MODE) as output:
                output.write(payload)
        else:
            with open(OUTPUT_PATH, WRITE_MODE, encoding=OUTPUT_ENCODING, errors="replace") as output:
                output.write(content)

# === Verification === #
# === Verify Standard Webhooks V1 HMAC-SHA256 signature === #
def verify_webhook_v1_signature(headers: dict, body: bytes):
    try:
        # === Read configured webhook header names === #
        event_id = headers.get(WEBHOOK_HEADERS["id"])
        event_timestamp = headers.get(WEBHOOK_HEADERS["timestamp"])
        signature_header = headers.get(WEBHOOK_HEADERS["signature"])
        required_headers = [event_id, event_timestamp, signature_header]

        # === Validate header prescence === #
        invalid = False
        for data in required_headers:
            not_str = not isinstance(data, str) or not data
            invalid |= not_str

        if invalid:
            return False

        # === Replay timeout === #
        timestamp = int(event_timestamp)
        if abs(time.time() - timestamp) > REPLAY_TOLERANCE:
            return False

        # === Expected signature === #
        version_prefix = f"{SIGNATURE_VERSION},"
        valid_signatures = [
            s.removeprefix(version_prefix)
            for s in signature_header.split()
            if s.startswith(version_prefix)
        ]

        # === Format info to sign === #
        bytes_to_sign: bytes = f"{event_id}.{event_timestamp}.".encode(ENCODING) + body

        # === Create HMAC object and sign webhook bytes === #
        signed_bytes: bytes = hmac.new(
            SIGNING_KEY, bytes_to_sign, hashlib.sha256
        ).digest()

        # === Encode HMAC bytes into B64 and decode it using ENCODING === #
        base64_signature: bytes = base64.b64encode(signed_bytes)
        computed_signature: str = base64_signature.decode(encoding=ENCODING)

        # === Validate signature === #
        matches = False
        for signature in valid_signatures:
            result = hmac.compare_digest(computed_signature, signature)
            matches |= result

        return matches

    except (ValueError, TypeError):
        return False

def format_lines_to_print(request_body: dict) -> str | bytes:
    """Return text or bytes using the configured receipt formatter."""
    formatter = FORMATTER if FORMATTER is not None else load_formatter(FORMATTER_FILE)
    return formatter(request_body)

# === Endpoint for incoming webhooks ===
def print_receipt() -> str:
    # === Get request data === #
    headers = request.headers
    raw_body = request.get_data()

    # === Verify signature === #
    if not verify_webhook_v1_signature(headers, raw_body):
        logger("❌ Invalid webhook signature.\n")
        return jsonify({"error": "Invalid signature"}), 401
    else:
        logger("✅ Webhook signature verified successfully.\n")

    # === Record incoming request information === #
    logger("\n=== WEBHOOK ===")
    logger(f"Message ID: {headers.get(WEBHOOK_HEADERS['id'])!r}")
    logger(f"Body size: {len(raw_body)} bytes")
    logger("=== END WEBHOOK ===\n")

    # === Parse JSON === #
    try:
        data = request.get_json(force=True)

        if not isinstance(data, dict):
            return jsonify({"error": "Expected a JSON object"}), 400

        logger("=== PARSED JSON ===")
        logger(f"Payload keys: {list(data)}")
        logger("=== END PARSED ===\n")
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger(f"[!] Invalid receipt data: {e}")
        return jsonify({"error": "Invalid request data"}), 400

    try:
        receipt_text = format_lines_to_print(data)
    except Exception as e:
        report_failure(f"[!] Retryable formatting failure: {type(e).__name__}: {e}")
        return jsonify({"error": "Request formatting error!"}), RETRY_STATUS_CODE

    if not isinstance(receipt_text, (str, bytes)):
        report_failure(
            "[!] Permanent configuration error: format_receipt(data) must "
            f"return str or bytes, not {type(receipt_text).__name__}"
        )
        return jsonify({"error": "Permanent configuration error"}), 422

    # === Check replay and send receipt === #
    event_id = headers.get(WEBHOOK_HEADERS["id"])
    with PROCESSING_LOCK:
        # === Per-session replay guard === #
        if event_id in PROCESSED_IDS:
            logger("[!] Duplicate webhook. Already processed.")
            return jsonify({"status": "already processed"}), 200
        elif event_id is None:
            logger(f"[!] Invalid event_id")
            return jsonify({"error": "Invalid receipt data"}), 400
        
        # === Print receipt === #
        try:
            write_to_output(receipt_text)
            logger("Output written successfully!")
        except (TypeError, io.UnsupportedOperation, FileExistsError, IsADirectoryError) as e:
            report_failure(f"[!] Permanent output configuration error: {type(e).__name__}: {e}")
            return jsonify({"error": "Permanent configuration error"}), 422
        except OSError as e:
            report_failure(f"[!] Retryable output failure: {type(e).__name__}: {e}")
            return jsonify({"error": "Output unavailable"}), RETRY_STATUS_CODE

        # === Record successfully processed webhook === #
        PROCESSED_IDS.add(event_id)

    # === Return success === #
    return jsonify({}), 200

# === Run the service ===
def run_server():
    get_secret()
    init_app()

    if not SIGNING_KEY:
        raise RuntimeError("Missing signing key!")
    if not APP:
        raise RuntimeError("Missing Flask APP!")

    serve(APP, host=HOST, port=PORT, threads=4)

if __name__ == "__main__":
    run_server()
