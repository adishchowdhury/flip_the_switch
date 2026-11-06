"""Client for the (simulated) payment provider, API v1.

`charge` returns the provider's JSON response as a dict. A real client would
make an HTTP call; here it is deterministic so tests and demos are repeatable.
"""

DECLINED_CARD = "4000000000000002"


def charge(card_number: str, amount_cents: int, currency: str = "usd") -> dict:
    if card_number == DECLINED_CARD:
        return {"status": "declined", "reason": "card_declined"}
    return {
        "status": "succeeded",
        "transaction_id": f"txn_{amount_cents}_{card_number[-4:]}",
        "amount_cents": amount_cents,
        "currency": currency,
    }
