# WriteFromWebhook (WFWH)

A configurable Standard Webhooks v1 receiver that verifies incoming webhooks, formats their contents, and writes to a file or device (via Flask).

Note:
- Pre-alpha currently supports only a single endpoint -> formatter -> output pipeline to be configured.

## Getting started

### 0. Installation and configuration

#### Install WFWH dependencies

```bash
pip install -r requirements.txt
```
#### Configuring WFWH

WFWH uses environment variables for configuration. Set them directly in your terminal, or edit and load the included configuration file for your platform:

**Unix (Bash):**

```bash
source ./wfwh.unix.conf
```

**Windows (PowerShell):**

```powershell
. .\wfwh.windows.ps1
```

The examples throughout this README use Unix shell syntax unless otherwise noted. The quick configuration reference at the bottom includes both Unix and Windows syntax.

For example, to set the webhook endpoint to `/print`:

```bash
export WFWH_WEBHOOK_ROUTE="/print"
```

The following sections explain each setting.
### 1. Choose your endpoint

Where should your webhook provider send requests?

| Setting              | Default  | Purpose                          |
| -------------------- | -------- | -------------------------------- |
| `WFWH_WEBHOOK_ROUTE` | `/print` | HTTP endpoint receiving webhooks |
| `WFWH_HOST` | `localhost` | Network interface/hostname to bind |
| `WFWH_PORT` | `5000` | Listening TCP port |

WFWH listens on `localhost:5000` by default. Your endpoint must be reachable by your webhook provider (for example, via a tunnel or reverse proxy).

### 2. Verification

Which webhook provider are you using?

WFWH supports Standard Webhooks v1 signatures. Configure the header names used by your provider.

| Setting             | Default             |
| ------------------- | ------------------- |
| `WFWH_WH_ID`        | `webhook-id`        |
| `WFWH_WH_TIMESTAMP` | `webhook-timestamp` |
| `WFWH_WH_SIGNATURE` | `webhook-signature` |

For example, Svix uses `svix-id`, `svix-timestamp` and `svix-signature`.

**Where is your signing secret?**

| Setting | Default |
|---|---|
| `WFWH_SECRET_PATH` | `~/.config/wfwh/webhook_secret` |

Store your provider's `whsec_...` signing secret in this file.

### 3. Retry behaviour

What HTTP status should WFWH return when formatting or writing fails?

| Setting | Default |
|---|---|
| `WFWH_RETRY_STATUS_CODE` | `503` |

Accepts `429` or any 5xx status code. Whether a failed delivery is retried depends on your webhook provider.

| Failure | Response | Behaviour |
|---|---|---|
| Printer/device unavailable | `503` (configurable) | Retryable operational failure |
| Formatter returns bytes for text mode | `422` | Permanent configuration error; reported to stderr |
| Output mode cannot write | `422` | Permanent configuration error; reported to stderr |
| Invalid file mode | Startup error | Refuse to start |
| Invalid webhook signature | `401` | Reject request |

A `422` does not guarantee your provider will stop retrying. Other failures, including formatting exceptions and temporarily inaccessible output paths, use the configured retry status. Correct a permanent configuration error before redelivery.

### 4. Formatting

How should the webhook data be formatted?

| Setting               | Default | Purpose            |
| --------------------- | ------- | ------------------ |
| `WFWH_FORMATTER_FILE` | Unset   | Formatter filename |

Create a Python file inside `formatters/` containing a `format_receipt(data)` function that returns text or bytes.

Set `WFWH_FORMATTER_FILE` to its filename.

See `placeholder.py` for a simple demonstration.

### 5. Writing

Where should the formatted webhook data go, and how should it be written?

| Setting                | Default      | Purpose                                 |
| ---------------------- | ------------ | --------------------------------------- |
| `WFWH_OUTPUT_PATH`     | `output.bin` | Destination file or device              |
| `WFWH_WRITE_MODE`      | `w`          | Python file mode (`w`, `a`, `wb`, etc.) |
| `WFWH_OUTPUT_ENCODING` | `utf-8`      | Text encoding                           |

Note: Returning bytes from `format_receipt` with a text write mode (e.g. `w`) results in a `422` error.

### 6. Logging

How much diagnostic information would you like to keep?

| Setting                    | Default                     | Purpose                  |
| -------------------------- | --------------------------- | ------------------------ |
| `WFWH_RECORD_LOGS`         | `true`                      | Keep logs in memory      |
| `WFWH_PRINT_LOG_TO_SCREEN` | `false`                     | Show logs in terminal    |
| `WFWH_WRITE_LOG`           | `false`                     | Save logs to files       |
| `WFWH_WRITE_LOG_TO_FILE`   | Timestamped file in `logs/` | Optional log destination |

File logging creates a new timestamped log for each run. Configuration and processing failures are also reported to **stderr**, even if the optional logging switches are disabled.

### 7. Run WFWH

Configure the settings above in the configuration file for your platform, then run WFWH from the same terminal:

**Unix (Bash):**

```bash
source ./wfwh.unix.conf
python wfwh.py
```

**Windows (PowerShell):**

```powershell
. .\wfwh.windows.ps1
python wfwh.py
```

You're ready to receive signed webhooks.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q testing
```

## Quick configuration reference

All settings at a glance. These are the defaults unless otherwise noted.

### Unix (Bash)

```bash
# ENDPOINT
export WFWH_WEBHOOK_ROUTE="/print"
export WFWH_HOST="localhost"
export WFWH_PORT="5000"

# VERIFICATION
export WFWH_WH_ID="webhook-id"
export WFWH_WH_TIMESTAMP="webhook-timestamp"
export WFWH_WH_SIGNATURE="webhook-signature"
export WFWH_SECRET_PATH="$HOME/.config/wfwh/webhook_secret"

# RETRY
export WFWH_RETRY_STATUS_CODE="503"

# FORMATTING (required; no default)
export WFWH_FORMATTER_FILE="placeholder.py"

# WRITING
export WFWH_OUTPUT_PATH="output.bin"
export WFWH_WRITE_MODE="w"
export WFWH_OUTPUT_ENCODING="utf-8"

# LOGGING
export WFWH_RECORD_LOGS="true"
export WFWH_PRINT_LOG_TO_SCREEN="false"
export WFWH_WRITE_LOG="false"
# WFWH_WRITE_LOG_TO_FILE defaults to logs/wfwh-<timestamp>.log
```

### Windows (PowerShell)

```powershell
# ENDPOINT
$Env:WFWH_WEBHOOK_ROUTE = "/print"
$Env:WFWH_HOST = "localhost"
$Env:WFWH_PORT = "5000"

# VERIFICATION
$Env:WFWH_WH_ID = "webhook-id"
$Env:WFWH_WH_TIMESTAMP = "webhook-timestamp"
$Env:WFWH_WH_SIGNATURE = "webhook-signature"
$Env:WFWH_SECRET_PATH = "$HOME/.config/wfwh/webhook_secret"

# RETRY
$Env:WFWH_RETRY_STATUS_CODE = "503"

# FORMATTING (required; no default)
$Env:WFWH_FORMATTER_FILE = "placeholder.py"

# WRITING
$Env:WFWH_OUTPUT_PATH = "output.bin"
$Env:WFWH_WRITE_MODE = "w"
$Env:WFWH_OUTPUT_ENCODING = "utf-8"

# LOGGING
$Env:WFWH_RECORD_LOGS = "true"
$Env:WFWH_PRINT_LOG_TO_SCREEN = "false"
$Env:WFWH_WRITE_LOG = "false"
# WFWH_WRITE_LOG_TO_FILE defaults to logs/wfwh-<timestamp>.log
```

The formatter `placeholder.py` shown may be used for temporary testing use. Replace it with your own implementation before using WFWH with real events.
