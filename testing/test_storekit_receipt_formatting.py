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

    assert format_receipt({}) == expected

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

    actual = format_receipt(order)

    assert actual == expected
