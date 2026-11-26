# ============================================
# WFWH v0.0.1 — POWERSHELL DEFAULTS
# ============================================
# Source this file directly: . .\wfwh.windows.ps1
# Configure your own formatter before accepting live events.
#
# --- Webhook verification ---
$Env:WFWH_SECRET_PATH = "$HOME/.config/wfwh/webhook_secret"
$Env:WFWH_WEBHOOK_ROUTE = "/print"
$Env:WFWH_HOST = "localhost"  # Listen address: hostname or IP
$Env:WFWH_PORT = "5000"
$Env:WFWH_RETRY_STATUS_CODE = "503"

# --- Standard Webhooks v1 headers ---
$Env:WFWH_WH_ID = "webhook-id"
$Env:WFWH_WH_TIMESTAMP = "webhook-timestamp"
$Env:WFWH_WH_SIGNATURE = "webhook-signature"

# --- Formatter (required) ---
#! Placeholder is for testing only; it will not handle request data; replace with your trusted formatter.
$Env:WFWH_FORMATTER_FILE = "placeholder.py"

# --- Output destination / encoding / write mode ---
$Env:WFWH_OUTPUT_PATH = "output.bin"
$Env:WFWH_OUTPUT_ENCODING = "utf-8"
$Env:WFWH_WRITE_MODE = "w"  # Python open() mode; text needs str, binary accepts bytes

# --- Logging toggles ---
$Env:WFWH_RECORD_LOGS = "true"
$Env:WFWH_PRINT_LOG_TO_SCREEN = "false"
$Env:WFWH_WRITE_LOG = "false"

# --- Optional log path override ---
# With no override, the default is logs/wfwh-<run timestamp>.log
# Only used when WFWH_WRITE_LOG=true.
# $Env:WFWH_WRITE_LOG_TO_FILE = "$HOME/wfwh-receiver.log"

# ============================================
# OPTIONAL EXAMPLE: STOREKIT HEADERS AND FORMATTER
# ============================================
# Uncomment these to override the defaults above.
# $Env:WFWH_WH_ID = "svix-id"
# $Env:WFWH_WH_TIMESTAMP = "svix-timestamp"
# $Env:WFWH_WH_SIGNATURE = "svix-signature"
# $Env:WFWH_FORMATTER_FILE = "storekit.py"
