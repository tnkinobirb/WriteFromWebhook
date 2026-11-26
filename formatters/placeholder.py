"""Example formatter: explicitly select with WFWH_FORMATTER_FILE=placeholder.py.

Demonstration only; successful requests are acknowledged after printing the
placeholder, so select a real formatter before processing live events.
"""

from examples.placeholder import format_receipt as placeholder_receipt


def format_receipt(request_body: dict) -> str:
    """Use the generic example receipt formatter."""
    return placeholder_receipt(request_body)
