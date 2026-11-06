import unittest

from checkout.handler import handle_checkout

GOOD_CARD = "4242424242424242"
DECLINED_CARD = "4000000000000002"
ORDER = {"items": [{"price_cents": 2500, "qty": 2}], "card_number": GOOD_CARD}


class CheckoutTests(unittest.TestCase):
    def test_empty_cart_is_rejected(self):
        status, body = handle_checkout({"items": [], "card_number": GOOD_CARD})
        self.assertEqual((status, body), (400, {"error": "empty_cart"}))

    def test_successful_checkout_is_confirmed(self):
        status, body = handle_checkout(ORDER)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "confirmed")
        self.assertEqual(body["total_cents"], 5000)
        self.assertTrue(body["transaction_id"].startswith("txn_"))

    def test_declined_card_returns_402(self):
        status, body = handle_checkout({**ORDER, "card_number": DECLINED_CARD})
        self.assertEqual((status, body), (402, {"error": "card_declined"}))


if __name__ == "__main__":
    unittest.main()
