import logging
import unittest
from unittest.mock import MagicMock, patch

import requests

from core.stock_fetcher import QuotaExhausted, StockFetcher

QUOTE_PAYLOAD = {
    "Global Quote": {
        "01. symbol": "AAPL",
        "05. price": "150.0000",
        "06. volume": "50000000",
        "10. change percent": "1.2345%",
    }
}

OVERVIEW_PAYLOAD = {
    "Symbol": "AAPL",
    "Name": "Apple Inc",
    "MarketCapitalization": "3000000000000",
}


def _response(payload: dict) -> MagicMock:
    """Build a mock requests.Response returning the given JSON body."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class StockFetcherTestCase(unittest.TestCase):
    """Shared setup: one configured symbol and a stubbed API key."""

    symbols = ["AAPL"]

    def setUp(self):
        self.logger = MagicMock(spec=logging.Logger)
        patcher = patch(
            "core.stock_fetcher.read_json", return_value={"symbols": self.symbols}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        env = patch.dict("core.stock_fetcher.os.environ", {"ALPHA_API_KEY": "test-key"})
        env.start()
        self.addCleanup(env.stop)

        self.fetcher = StockFetcher(self.logger)


class TestFetchSuccess(StockFetcherTestCase):
    @patch("core.stock_fetcher.requests.get")
    def test_returns_parsed_fields(self, mock_get):
        mock_get.side_effect = [_response(QUOTE_PAYLOAD), _response(OVERVIEW_PAYLOAD)]

        data, failures = self.fetcher.fetch()

        self.assertEqual(failures, [])
        self.assertEqual(
            data["AAPL"],
            {
                "price": "150.0000",
                "volume": "50000000",
                # The trailing % must be stripped: the column is DECIMAL.
                "change_percent": "1.2345",
                "name": "Apple Inc",
                "market_cap": "3000000000000",
            },
        )

    @patch("core.stock_fetcher.requests.get")
    def test_costs_two_requests_per_symbol(self, mock_get):
        mock_get.side_effect = [_response(QUOTE_PAYLOAD), _response(OVERVIEW_PAYLOAD)]

        self.fetcher.fetch()

        self.assertEqual(mock_get.call_count, 2)


class TestQuotaExhaustion(StockFetcherTestCase):
    symbols = ["AAPL", "GOOG", "MSFT"]

    @patch("core.stock_fetcher.requests.get")
    def test_information_key_is_detected_not_keyerror(self, mock_get):
        # The quota response arrives as HTTP 200, so raise_for_status() is no
        # help; the body must be inspected. This is the regression guard for
        # the KeyError the old client raised here.
        mock_get.return_value = _response({"Information": "rate limit reached"})

        data, failures = self.fetcher.fetch()

        self.assertEqual(data, {})
        self.assertEqual(len(failures), 3)
        self.assertTrue(all("quota exhausted" in f for f in failures))

    @patch("core.stock_fetcher.requests.get")
    def test_note_key_is_also_detected(self, mock_get):
        mock_get.return_value = _response({"Note": "call frequency exceeded"})

        _, failures = self.fetcher.fetch()

        self.assertTrue(all("quota exhausted" in f for f in failures))

    @patch("core.stock_fetcher.requests.get")
    def test_stops_calling_after_quota_hit(self, mock_get):
        mock_get.return_value = _response({"Information": "rate limit reached"})

        self.fetcher.fetch()

        # One call, then the loop abandons the rest: the budget is account-wide,
        # so continuing would only produce identical errors.
        self.assertEqual(mock_get.call_count, 1)

    @patch("core.stock_fetcher.requests.get")
    def test_keeps_symbols_fetched_before_the_quota_ran_out(self, mock_get):
        mock_get.side_effect = [
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
            _response({"Information": "rate limit reached"}),
        ]

        data, failures = self.fetcher.fetch()

        self.assertIn("AAPL", data)
        self.assertEqual(len(failures), 2)


class TestBadSymbol(StockFetcherTestCase):
    symbols = ["ZZZZNOPE", "AAPL"]

    @patch("core.stock_fetcher.requests.get")
    def test_empty_quote_fails_only_that_symbol(self, mock_get):
        mock_get.side_effect = [
            _response({"Global Quote": {}}),
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
        ]

        data, failures = self.fetcher.fetch()

        self.assertIn("AAPL", data)
        self.assertNotIn("ZZZZNOPE", data)
        self.assertEqual(len(failures), 1)

    @patch("core.stock_fetcher.requests.get")
    def test_error_message_key_is_surfaced(self, mock_get):
        mock_get.return_value = _response({"Error Message": "invalid api call"})

        data, failures = self.fetcher.fetch()

        self.assertEqual(data, {})
        self.assertEqual(len(failures), 2)


class TestNetworkFailure(StockFetcherTestCase):
    symbols = ["AAPL", "GOOG"]

    @patch("core.stock_fetcher.requests.get")
    def test_unreachable_api_does_not_stop_the_run(self, mock_get):
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("unreachable"),
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
        ]

        data, failures = self.fetcher.fetch()

        self.assertIn("GOOG", data)
        self.assertEqual(len(failures), 1)
        self.assertIn("request failed", failures[0])


class TestPartialOverview(StockFetcherTestCase):
    @patch("core.stock_fetcher.requests.get")
    def test_missing_company_name_fails_the_symbol(self, mock_get):
        # name and market_cap are NOT NULL, so a half-populated row must never
        # reach the database.
        mock_get.side_effect = [
            _response(QUOTE_PAYLOAD),
            _response({"Symbol": "AAPL", "MarketCapitalization": "3000"}),
        ]

        data, failures = self.fetcher.fetch()

        self.assertEqual(data, {})
        self.assertEqual(len(failures), 1)


class TestConfiguration(unittest.TestCase):
    def test_missing_api_key_fails_loudly(self):
        with patch("core.stock_fetcher.read_json", return_value={"symbols": ["AAPL"]}):
            with patch.dict("core.stock_fetcher.os.environ", {}, clear=True):
                with self.assertRaises(ValueError):
                    StockFetcher(MagicMock(spec=logging.Logger))

    def test_empty_symbol_list_fails_loudly(self):
        with patch("core.stock_fetcher.read_json", return_value={"symbols": []}):
            with patch.dict(
                "core.stock_fetcher.os.environ", {"ALPHA_API_KEY": "k"}, clear=True
            ):
                with self.assertRaises(ValueError):
                    StockFetcher(MagicMock(spec=logging.Logger))


if __name__ == "__main__":
    unittest.main()
