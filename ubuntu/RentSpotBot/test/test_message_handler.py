"""
Tests for the MessageHandler class
"""
import unittest
from decimal import Decimal
from src.message_handler import MessageHandler, TradeEvent

class TestMessageHandler(unittest.TestCase):
    def setUp(self):
        self.handler = MessageHandler()
        self.sample_message = '''{
            "signature": "5yHeNybe26ZZx52m11jXdLXrWzBkVaPn3ryaZvBrpsrytATxHgvqavqsYoWjHabbRmC9XHAoWBmxcTsNsN6B4uAw",
            "mint": "FvskomUb33LrTbnKa5V8qN6L5XXSC3Rsv1x7ifMKyBRi",
            "traderPublicKey": "CFjYB8ck5435do8HHTip6xvbR67odxmnVUc1keURkyx8",
            "txType": "buy",
            "tokenAmount": 4265342.503241,
            "newTokenBalance": 4265342.503241,
            "bondingCurveKey": "9mdkxq5zZMdT5MVAkA23koZZ6U2nTfY4M6eEVKmGZSBD",
            "vTokensInBondingCurve": 372139540.970454,
            "vSolInBondingCurve": 86.49981110863929,
            "marketCapSol": 232.43918365424906
        }'''

    def test_process_valid_message(self):
        """Test processing a valid trade message"""
        result = self.handler.process_message(self.sample_message)
        self.assertIsInstance(result, TradeEvent)
        self.assertEqual(result.tx_type, "buy")
        self.assertEqual(result.mint, "FvskomUb33LrTbnKa5V8qN6L5XXSC3Rsv1x7ifMKyBRi")
        self.assertEqual(result.token_amount, Decimal('4265342.503241'))
        self.assertEqual(result.market_cap_sol, Decimal('232.43918365424906'))

    def test_process_invalid_json(self):
        """Test processing invalid JSON"""
        result = self.handler.process_message("invalid json")
        self.assertIsNone(result)

    def test_process_missing_fields(self):
        """Test processing message with missing required fields"""
        invalid_message = '{"signature": "test", "mint": "test"}'
        result = self.handler.process_message(invalid_message)
        self.assertIsNone(result)

    def test_handle_trade_event(self):
        """Test trade event handling"""
        result = self.handler.process_message(self.sample_message)
        self.assertIsNotNone(result)
        # This should not raise any exceptions
        self.handler.handle_trade_event(result)

if __name__ == '__main__':
    unittest.main()
