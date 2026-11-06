"""Client for the (simulated) payment provider, API v2.

v2 renamed response fields: `status` -> `state`, `transaction_id` -> `id`,
`amount_cents` -> `amount`. See docs/provider-api-v2.md.
"""

DECLINED_CARD = "4000000000000002"


def charge(card_number: str, amount_cents: int, currency: str = "usd") -> dict:
    if card_number == DECLINED_CARD:
        return {"state": "declined", "reason": "card_declined"}
    return {
        "state": "succeeded",
        "id": f"txn_{amount_cents}_{card_number[-4:]}",
        "amount": amount_cents,
        "currency": currency,
    }
