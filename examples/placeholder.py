"""Generic example receipt formatter for WFWH.

Use within `wfwh.format_lines_to_print`:

    from examples.placeholder import format_receipt
    return format_receipt(request_body)

The JSON `id` field is illustrative; not all webhook providers include it.
Consult the provider's documentation when writing your own formatter.
"""
def format_receipt(request_body: dict) -> str:
    # CUSTOMISE THIS FUNCTION
    lines = []
    lines.append("Webhook received!")
    lines.append(str(request_body.get("id", "Unknown ID")))

    return "\n".join(lines)