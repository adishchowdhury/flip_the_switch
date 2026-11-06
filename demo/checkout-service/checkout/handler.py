"""Checkout request handler: validates an order, charges it, maps the result."""

from . import provider


def handle_checkout(order: dict) -> tuple[int, dict]:
    """Return (http_status, response_body) for a checkout request."""
    if not order.get("items"):
        return 400, {"error": "empty_cart"}

    total = sum(i["price_cents"] * i["qty"] for i in order["items"])
    resp = provider.charge(order["card_number"], total, order.get("currency", "usd"))

    if resp.get("status") == "declined":
        return 402, {"error": "card_declined"}
    if resp.get("status") != "succeeded":
        return 502, {"error": "payment_provider_error"}

    return 200, {
        "status": "confirmed",
        "transaction_id": resp["transaction_id"],
        "total_cents": total,
    }
