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

def format_receipt(data: dict) -> str:
    lines = []
    pound = "£"  # Encoded as CP437 when printing

    ## === Receipt Data === ##

    # === Venue info === #
    venue = "Make-Donalds"
    address = data.get("venue", {}).get("address", {})

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
    customer = data.get("customer", {})
    customer_name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()

    # === Delivery-To location === #
    staff_name = data.get("table", {}).get("name", "Unknown")
    area = data.get("table", {}).get("area", {}).get("name", "")

    # === Pricing info === #
    tip = data.get("tip", 0) / 100
    total = data.get("total", 0) / 100
    discount = data.get("discountTotal", 0) / 100
    delivery_fee = data.get("deliveryFee", 0) / 100

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
    for idx, item in enumerate(data.get("items", []), start=1):
        # === Name, Quantity and Price === #
        name = item.get("name", "")
        qty = item.get("quantity", 1)
        base_price = item.get("price", 0) / 100
        lines.append(f"{idx}. {name} x{qty} - {pound}{base_price:.2f}")

        # === Price modifiers (discounts/etc) === #
        for mod in item.get("modifiers", []):
            mod_name = mod.get("name", "")
            mod_price = mod.get("price", 0) / 100
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
