"""StoreKit-specific WFWH receipt formatter example.

Event reference: https://storekit.com/docs/developers/webhooks/webhook-events

Use within `wfwh.format_lines_to_print`:

    from examples.storekit import format_receipt
    return format_receipt(request_body)

This example assumes StoreKit's `order.created.v2` payload. Other event
types require explicit schema checks and their own formatting logic.
Missing fields may fall back to defaults; review the webhook event docs.
"""

# Example receipt formatter:
from datetime import datetime
from zoneinfo import ZoneInfo

def _mapping(value, field: str, *, nullable: bool = True) -> dict:
    if value is None and nullable:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _list(value, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _minor_units(value, field: str) -> float:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return value / 100


def _order_from_payload(payload: dict) -> dict:
    payload = _mapping(payload, "payload", nullable=False)
    if "event" not in payload:
        # Backwards compatibility with StoreKit's legacy order.created body.
        return payload
    if payload.get("event") != "order.created.v2":
        raise ValueError("expected an order.created.v2 event")
    return _mapping(payload.get("data"), "data", nullable=False)


def format_receipt(payload: dict) -> str:
    data = _order_from_payload(payload)
    lines = []
    pound = "£"  # Encoded as CP437 when printing

    ## === Receipt Data === ##

    # === Venue info === #
    venue = "Make-Donalds"
    venue_data = _mapping(data.get("venue"), "data.venue")
    address = _mapping(venue_data.get("address"), "data.venue.address")

    # === Order info === #
    order_code = data.get("code", "No Code")
    created_at_raw = data.get("createdAt", "")
    if created_at_raw:
        try:
            created_at = datetime.fromisoformat(
                created_at_raw.replace("Z", "+00:00")
            ).astimezone(
                ZoneInfo("Europe/London")
            ).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            created_at = "Invalid Date"
    else:
        created_at = "Unknown"

    # === Customer info === #
    customer = _mapping(data.get("customer"), "data.customer")
    customer_name = f"{customer.get('firstName') or ''} {customer.get('lastName') or ''}".strip()

    # === Delivery-To location === #
    table = _mapping(data.get("table"), "data.table")
    staff_name = table.get("name") or "Unknown"
    area = _mapping(table.get("area"), "data.table.area").get("name") or ""

    # === Pricing info === #
    tip = _minor_units(data.get("tip"), "data.tip")
    total = _minor_units(data.get("total"), "data.total")
    discount = _minor_units(data.get("discountTotal"), "data.discountTotal")
    delivery_fee = _minor_units(data.get("deliveryFee"), "data.deliveryFee")

    ## === Reciept Formatting === ##

    # === Header === #
    lines.append(" /\\_____/\\\n|  o . o  |")
    lines.append(f"=== {venue} ===")

    # === Venue === #
    lines.append(address.get("street1", ""))
    lines.append(address.get("city", "") + " " + address.get("postCode", ""))
    lines.append("")

    # === Customer === #
    if customer_name:
        lines.append(f"Customer: {customer_name}")
    lines.append(f"Order Code: {order_code}")
    lines.append(f"Time: {created_at}")
    lines.append("----------------------")

    # === Deliver-To === #
    lines.append(f"Deliver To: {staff_name} ({area})")
    lines.append("----------------------")

    # === Items === #
    lines.append("Items:")
    for idx, item in enumerate(_list(data.get("items"), "data.items"), start=1):
        item = _mapping(item, f"data.items[{idx - 1}]", nullable=False)
        # === Name, Quantity and Price === #
        name = item.get("name", "")
        qty = item.get("quantity", 1)
        base_price = _minor_units(item.get("price"), f"data.items[{idx - 1}].price")
        lines.append(f"{idx}. {name} x{qty} - {pound}{base_price:.2f}")

        # === Price modifiers (discounts/etc) === #
        for mod_idx, mod in enumerate(_list(item.get("modifiers"), f"data.items[{idx - 1}].modifiers")):
            mod = _mapping(
                mod,
                f"data.items[{idx - 1}].modifiers[{mod_idx}]",
                nullable=False,
            )
            mod_name = mod.get("name", "")
            mod_price = _minor_units(
                mod.get("price"),
                f"data.items[{idx - 1}].modifiers[{mod_idx}].price",
            )
            lines.append(f"  + {mod_name} - {pound}{mod_price:.2f}")

        # === Item notes === #
        item_note = item.get("note", "")
        if item_note:
            lines.append(f"  [Note: {item_note}]")
        lines.append("")

    # === Order notes === #
    order_notes = data.get("notes", "")
    if order_notes:
        lines.append("----------------------")
        lines.append(f"Order Note: {order_notes}")
        lines.append("")

    # === Order summary === #
    lines.append("----------------------")

    # === Conditional information === #
    if tip:
        lines.append(f"Tip: {pound}{tip:.2f}")
    if discount:
        lines.append(f"Discount: -{pound}{abs(discount):.2f}")
    if delivery_fee:
        lines.append(f"Delivery Fee: {pound}{delivery_fee:.2f}")

    # === Total price === #
    lines.append(f"TOTAL: {pound}{total:.2f}")

    # === Feed paper for reciept cut === #
    lines.append("\n\n\n")

    return "\n".join(lines)

