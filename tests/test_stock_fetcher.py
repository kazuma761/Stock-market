import logging
import unittest
from unittest.mock import MagicMock, patch

import requests

from core.stock_fetcher import StockFetcher

# Captured verbatim from the live API on 2026-09-10.
QUOTE_PAYLOAD = {
    "Global Quote": {
        "01. symbol": "AAPL",
        "02. open": "316.6700",
        "03. high": "326.7400",
        "04. low": "316.5100",
        "05. price": "326.5700",
        "06. volume": "70011913",
        "07. latest trading day": "2026-09-10",
        "08. previous close": "315.3400",
        "09. change": "11.2300",
        "10. change percent": "3.5612%",
    }
}

OVERVIEW_PAYLOAD = {
    "Symbol": "AAPL",
    "Name": "Apple Inc.",
    "MarketCapitalization": "4602128761000",
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

        # The fetcher paces itself to respect the 1 request/second free tier.
        # Real sleeping would make this suite take minutes.
        sleeper = patch("core.stock_fetcher.time.sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

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
                "name": "Apple Inc.",
                # The session the data describes, not the day we ran.
                "trading_day": "2026-09-10",
                "price": "326.5700",
                "open_price": "316.6700",
                "high_price": "326.7400",
                "low_price": "316.5100",
                "previous_close": "315.3400",
                "change_amount": "11.2300",
                # The trailing % must be stripped: the column is DECIMAL.
                "change_percent": "3.5612",
                "volume": "70011913",
                "market_cap": "4602128761000",
            },
        )

    @patch("core.stock_fetcher.requests.get")
    def test_optional_fields_become_none_not_failure(self, mock_get):
        # A quote missing its high/low is still a usable price record, so the
        # symbol must survive with NULLs rather than being rejected.
        sparse = {
            "Global Quote": {
                "05. price": "100.0",
                "06. volume": "123",
                "07. latest trading day": "2026-09-10",
            }
        }
        mock_get.side_effect = [_response(sparse), _response(OVERVIEW_PAYLOAD)]

        data, failures = self.fetcher.fetch()

        self.assertEqual(failures, [])
        self.assertIsNone(data["AAPL"]["high_price"])
        self.assertIsNone(data["AAPL"]["change_percent"])
        self.assertEqual(data["AAPL"]["price"], "100.0")

    @patch("core.stock_fetcher.requests.get")
    def test_missing_trading_day_fails_the_symbol(self, mock_get):
        # trading_day is half the unique key; without it the row cannot be
        # written idempotently, so the symbol must be rejected.
        broken = {"Global Quote": {"05. price": "100.0", "06. volume": "123"}}
        mock_get.side_effect = [_response(broken), _response(OVERVIEW_PAYLOAD)]

        data, failures = self.fetcher.fetch()

        self.assertEqual(data, {})
        self.assertEqual(len(failures), 1)

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
    def test_stops_calling_after_quota_confirmed(self, mock_get):
        mock_get.return_value = _response({"Information": "rate limit reached"})

        self.fetcher.fetch()

        # Four attempts (three backoffs plus a final try) before the quota is
        # declared spent, then the loop abandons the rest -- the budget is
        # account-wide.
        self.assertEqual(mock_get.call_count, 4)

    @patch("core.stock_fetcher.requests.get")
    def test_throttle_that_clears_on_retry_does_not_abort_the_run(self, mock_get):
        # Alpha Vantage returns the SAME "Information" key for the 1/second
        # burst limit as for the spent daily quota. Treating the first one as
        # terminal would abandon the run over a momentary throttle.
        mock_get.side_effect = [
            _response({"Information": "1 request per second"}),
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
        ]

        data, failures = self.fetcher.fetch()

        self.assertEqual(failures, [])
        self.assertEqual(len(data), 3)

    @patch("core.stock_fetcher.requests.get")
    def test_requests_are_paced(self, mock_get):
        mock_get.side_effect = [
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
        ] * 3

        self.fetcher.fetch()

        # Pacing must actually happen, or the free tier throttles us.
        self.assertTrue(self.sleep.called)

    @patch("core.stock_fetcher.requests.get")
    def test_keeps_symbols_fetched_before_the_quota_ran_out(self, mock_get):
        mock_get.side_effect = [
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
        ] + [_response({"Information": "rate limit reached"})] * 4

        data, failures = self.fetcher.fetch()

        self.assertIn("AAPL", data)
        self.assertEqual(len(failures), 2)


class TestBadSymbol(StockFetcherTestCase):
    symbols = ["ZZZZNOPE", "AAPL"]

    @patch("core.stock_fetcher.requests.get")
    def test_empty_quote_fails_only_that_symbol(self, mock_get):
        # Verified live: an unknown ticker returns HTTP 200 with an empty
        # "Global Quote" object, not an error status.
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
        # AAPL's first call fails on every network retry; GOOG then succeeds.
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("unreachable"),
            requests.exceptions.ConnectionError("unreachable"),
            requests.exceptions.ConnectionError("unreachable"),
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
        ]

        data, failures = self.fetcher.fetch()

        self.assertIn("GOOG", data)
        self.assertEqual(len(failures), 1)
        self.assertIn("request failed", failures[0])

    @patch("core.stock_fetcher.requests.get")
    def test_transient_network_error_is_retried(self, mock_get):
        # Airflow never retries the fetch for this (the task still succeeds),
        # so a blip that clears must be retried in-process.
        mock_get.side_effect = [
            requests.exceptions.Timeout("slow"),
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
            _response(QUOTE_PAYLOAD),
            _response(OVERVIEW_PAYLOAD),
        ]

        data, failures = self.fetcher.fetch()

        self.assertEqual(sorted(data), ["AAPL", "GOOG"])
        self.assertEqual(failures, [])


class TestApiKeyRedaction(StockFetcherTestCase):
    """The key must never reach logs, XCom, or the Airflow UI."""

    @patch("core.stock_fetcher.requests.get")
    def test_key_echoed_in_quota_notice_is_redacted(self, mock_get):
        # Alpha Vantage really does echo the key back in this message.
        mock_get.return_value = _response(
            {"Information": "We have detected your API key as test-key and ..."}
        )

        _, failures = self.fetcher.fetch()

        logged = " ".join(str(c) for c in self.logger.method_calls)
        self.assertNotIn("test-key", logged)
        self.assertNotIn("test-key", " ".join(failures))

    @patch("core.stock_fetcher.requests.get")
    def test_key_in_http_error_url_is_redacted(self, mock_get):
        response = _response({})
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error for url: https://x/query?apikey=test-key"
        )
        mock_get.return_value = response

        _, failures = self.fetcher.fetch()

        self.assertIn("apikey=***", failures[0])
        logged = " ".join(str(c) for c in self.logger.method_calls)
        self.assertNotIn("test-key", logged)


class TestPartialOverview(StockFetcherTestCase):
    @patch("core.stock_fetcher.requests.get")
    def test_missing_company_name_fails_the_symbol(self, mock_get):
        # name is NOT NULL, so a row without it must never reach the database.
        mock_get.side_effect = [
            _response(QUOTE_PAYLOAD),
            _response({"Symbol": "AAPL", "MarketCapitalization": "3000"}),
        ]

        data, failures = self.fetcher.fetch()

        self.assertEqual(data, {})
        self.assertEqual(len(failures), 1)

    @patch("core.stock_fetcher.requests.get")
    def test_missing_market_cap_is_tolerated(self, mock_get):
        # market_cap is nullable: an ETF or index has no meaningful one, and
        # losing the price record over it would be the wrong trade.
        mock_get.side_effect = [
            _response(QUOTE_PAYLOAD),
            _response({"Symbol": "AAPL", "Name": "Apple Inc."}),
        ]

        data, failures = self.fetcher.fetch()

        self.assertEqual(failures, [])
        self.assertIsNone(data["AAPL"]["market_cap"])


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
