import pytest

from examples.storekit import format_receipt

'''
    Note: Theses tests only verify expected `order.created.v2` webhook events shape handling.
    Event: https://storekit.com/docs/developers/webhooks/webhook-events#order-created-v2
'''

def test_format_receipt_defaults():
    expected = "\n".join([
        " /\\_____/\\",
        "|  o . o  |",
        "=== Make-Donalds ===",
        "",
        " ",
        "",
        "Order Code: No Code",
        "Time: Unknown",
        "----------------------",
        "Deliver To: Unknown ()",
        "----------------------",
        "Items:",
        "----------------------",
        "TOTAL: £0.00",
        "\n\n\n",
    ])

    payload = {"event": "order.created.v2", "data": {}}

    assert format_receipt(payload) == expected

def test_format_receipt_golden():
    order = {
        "code": "TEST123",
        "createdAt": "2026-11-23T11:25:40.566Z",
        "venue": {
            "address": {
                "street1": "1 Example Street",
                "city": "Example Town",
                "postCode": "ZZ0 0ZZ",
            }
        },
        "customer": {
            "firstName": "Name",
            "lastName": "Here",
        },
        "table": {
            "name": "1",
            "area": {"name": "Colour Zone"},
        },
        "items": [
            {
                "name": "Rombouts Coffee",
                "quantity": 1,
                "price": 350,
                "modifiers": [
                    {"name": "Cow's Milk", "price": 0},
                    {"name": "Decaffeinated", "price": 0},
                ],
                "note": "Request",
            },
            {
                "name": "Double Espresso",
                "quantity": 1,
                "price": 350,
            },
        ],
        "notes": "Order notes",
        "discountTotal": 700,
        "total": 0,
    }

    expected = "\n".join([
        " /\\_____/\\",
        "|  o . o  |",
        "=== Make-Donalds ===",
        "1 Example Street",
        "Example Town ZZ0 0ZZ",
        "",
        "Customer: Name Here",
        "Order Code: TEST123",
        "Time: 2026-11-23 11:25",
        "----------------------",
        "Deliver To: 1 (Colour Zone)",
        "----------------------",
        "Items:",
        "1. Rombouts Coffee x1 - £3.50",
        "  + Cow's Milk - £0.00",
        "  + Decaffeinated - £0.00",
        "  [Note: Request]",
        "",
        "2. Double Espresso x1 - £3.50",
        "",
        "----------------------",
        "Order Note: Order notes",
        "",
        "----------------------",
        "Discount: -£7.00",
        "TOTAL: £0.00",
        "\n\n\n",
    ])

    actual = format_receipt({"event": "order.created.v2", "data": order})

    assert actual == expected


def test_format_receipt_supports_legacy_order_created_shape():
    order = {"code": "LEGACY", "total": 1234}

    assert format_receipt(order) == format_receipt({
        "event": "order.created.v2",
        "data": order,
    })


def test_format_receipt_tolerates_nullable_optional_fields():
    payload = {
        "event": "order.created.v2",
        "data": {
            "venue": None,
            "customer": None,
            "table": None,
            "items": None,
            "tip": None,
            "total": None,
            "discountTotal": None,
            "deliveryFee": None,
        },
    }

    receipt = format_receipt(payload)

    assert "Deliver To: Unknown ()" in receipt
    assert "TOTAL: £0.00" in receipt


def test_format_receipt_tolerates_nested_nullable_fields():
    payload = {
        "event": "order.created.v2",
        "data": {
            "table": {"name": None, "area": None},
            "items": [{"name": "Example", "price": None, "modifiers": None}],
        },
    }

    receipt = format_receipt(payload)

    assert "Deliver To: Unknown ()" in receipt
    assert "1. Example x1 - £0.00" in receipt


@pytest.mark.parametrize("payload", [
    {"event": "order.created.v2", "data": None},
    {"event": "order.completed", "data": {}},
])
def test_format_receipt_rejects_wrong_event_shape(payload):
    with pytest.raises(ValueError):
        format_receipt(payload)

